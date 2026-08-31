"""
servicios/huella.py
────────────────────
Servicio de huella dactilar.

Antes, el navegador llamaba a un servicio SecuGen WebAPI aparte
(https://localhost:8000) y le mandaba el resultado a Flask. Ahora que
Flask corre en la misma laptop Windows donde está el lector, esa
intermediación ya no hace falta: este servicio habla directo con el
lector a través del paquete `biometria` (ctypes + sgfplib.dll), así que
no hay que instalar ni dejar corriendo nada aparte.

Tres operaciones:

  1. `registrar()`   — enrolamiento: pide varias capturas del mismo dedo
                        y arma una plantilla. Se hace una vez por persona
                        (jugador, árbitro o administrador) y la plantilla
                        queda guardada en PostgreSQL (RegistroBiometrico).
  2. `verificar()`    — 1:1: ya se sabe quién se presenta (el check-in
                        viene de la convocatoria), se compara solo contra
                        SU plantilla.
  3. `identificar()`  — 1:N: no se sabe todavía quién es (el login del
                        administrador), se compara contra todas las
                        plantillas de ese rol y se busca cuál coincide.
                        Esto lo resuelve el propio paquete `biometria`
                        comparando en software, sin licencia aparte.

En modo "simulado" (para desarrollar sin lector) no se toca hardware:
`registrar`/`verificar` siempre tienen éxito; `identificar` no encuentra
coincidencia salvo que se guione explícitamente (ver tests del paquete
`biometria`), así que el login con huella del administrador se prueba
mejor con HUELLA_MODO=secugen y el lector conectado.
"""

import os
import threading

from biometria import (
    MUESTRAS_POR_PLANTILLA,
    CalidadInsuficiente,
    CapturaFallida,
    CodigoResultado,
    Dedo,
    ErrorBiometrico,
    LectorNoDisponible,
    TiempoAgotado,
    crear_proveedor,
)

from sqlalchemy.exc import SQLAlchemyError

from extensiones import db
from modelos.huella import RegistroBiometrico

#: Carpeta de GolStats/, donde deben vivir las DLL de SecuGen (sgfplib.dll
#: y compañía), junto a app.py.
RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


#: Fallas al hablar con la tabla de huellas en PostgreSQL.
#:
#: `UnicodeDecodeError` no sobra: cuando Postgres rechaza la conexión, el
#: mensaje de error de Windows viene en español y codificado en cp1252, y
#: psycopg2 revienta al intentar leerlo como UTF-8 *antes* de poder
#: envolverlo en un SQLAlchemyError. Sin esta entrada, ese caso —el más
#: común: contraseña equivocada— se escaparía sin capturar.
ERRORES_BASE = (SQLAlchemyError, UnicodeDecodeError)


class ErrorHuella(Exception):
    """Error de negocio de la huella: se muestra tal cual al usuario."""


class BaseHuellasNoDisponible(ErrorHuella):
    """
    No se pudo consultar la tabla de huellas.

    Es distinto de "esta persona no tiene huella": acá no sabemos si la
    tiene o no. Se separa para que la interfaz no diga "sin registrar"
    cuando en realidad no pudo averiguarlo — un admin podría creer que a
    alguien le falta enrolar la huella cuando el problema es la base.

    Hereda de ErrorHuella para que las rutas que ya capturan ErrorHuella
    la muestren como un aviso normal en vez de reventar con un 500.
    """

    MENSAJE = (
        "No se pudo consultar la base de huellas. Revise DATABASE_URL en "
        "el archivo .env y que PostgreSQL esté levantado."
    )

    def __init__(self, mensaje=None):
        super().__init__(mensaje or BaseHuellasNoDisponible.MENSAJE)


class LectorHuella:
    """
    Fachada del subsistema biométrico para el resto de GolStats.

    El resto de la aplicación no sabe nada del paquete `biometria` ni de
    PostgreSQL: solo pide "registra la huella de este jugador" o
    "verifica la huella de este árbitro", y esta clase decide cómo.
    """

    MODO_SECUGEN = "secugen"
    MODO_SIMULADO = "simulado"

    def __init__(self, modo=MODO_SIMULADO, umbral=45, lector="secugen:hsdu03p"):
        modo = (modo or "").strip().lower()
        if modo not in (LectorHuella.MODO_SECUGEN, LectorHuella.MODO_SIMULADO):
            raise ValueError(
                f"HUELLA_MODO inválido: {modo}. Use secugen o simulado"
            )
        self.modo = modo
        self.umbral = umbral
        self.lector_modelo = lector
        self._proveedor = None
        # El lector físico es un solo dispositivo: dos capturas a la vez
        # (dos pestañas, dos peticiones) lo dejarían en un estado raro.
        self._candado = threading.Lock()

    @classmethod
    def desde_config(cls, config):
        return cls(
            modo=config.HUELLA_MODO,
            umbral=config.HUELLA_UMBRAL,
            lector=config.HUELLA_LECTOR,
        )

    def es_simulado(self):
        return self.modo == LectorHuella.MODO_SIMULADO

    def _obtener_proveedor(self):
        """Crea el proveedor biométrico la primera vez que se necesita."""
        if self._proveedor is not None:
            return self._proveedor

        if self.modo == LectorHuella.MODO_SECUGEN:
            # Que ctypes encuentre sgfplib.dll aunque Flask no se haya
            # arrancado con GolStats/ como directorio de trabajo.
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(RAIZ_PROYECTO)
            self._proveedor = crear_proveedor(
                "EXTERNO", lector=self.lector_modelo, umbral=self.umbral
            )
        else:
            self._proveedor = crear_proveedor("SIMULADO", umbral=self.umbral)
        return self._proveedor

    def diagnostico(self):
        """Estado del lector, para una pantalla de preflight si hiciera falta."""
        return self._obtener_proveedor().diagnostico()

    # ── Enrolamiento ───────────────────────────────────────────────

    def tiene_huella(self, tipo_persona, persona_id):
        """
        True / False / None, donde None es "no se pudo averiguar".

        Es una consulta de solo lectura que alimenta pantallas informativas
        (la ficha del jugador, el panel de huellas). Si la base no responde
        no tiene sentido tumbar la pantalla entera: se devuelve None y la
        vista muestra "No disponible". Las operaciones que sí escriben
        (registrar, verificar) siguen fallando con un mensaje explícito.
        """
        try:
            return (
                RegistroBiometrico.query.filter_by(
                    tipo_persona=tipo_persona, persona_id=persona_id
                ).first()
                is not None
            )
        except ERRORES_BASE:
            # La sesión queda inservible tras el fallo: sin rollback, la
            # siguiente consulta de la misma petición también falla.
            db.session.rollback()
            return None

    def huellas_registradas(self):
        """
        Todas las huellas, indexadas por (tipo_persona, persona_id).

        Devuelve None —y no un dict vacío— si la base no responde: un dict
        vacío significaría "no hay ninguna huella registrada", que es una
        afirmación distinta.
        """
        try:
            return {
                (r.tipo_persona, r.persona_id): r
                for r in RegistroBiometrico.query.all()
            }
        except ERRORES_BASE:
            db.session.rollback()
            return None

    def registrar(
        self,
        tipo_persona,
        persona_id,
        nombre_completo,
        correo=None,
        cedula=None,
        dedo=Dedo.INDICE_DERECHO,
        muestras_requeridas=MUESTRAS_POR_PLANTILLA,
    ):
        """
        Enrola a la persona: pide apoyar el dedo `muestras_requeridas`
        veces, arma la plantilla y la guarda (o la reemplaza si ya tenía
        una) en PostgreSQL. Bloquea la petición HTTP mientras el lector
        espera cada captura — es lo mismo que antes hacía el navegador,
        solo que ahora lo hace Flask.
        """
        proveedor = self._obtener_proveedor()
        with self._candado:
            muestras = []
            calidad_insuficiente_seguidas = 0
            while len(muestras) < muestras_requeridas:
                try:
                    muestras.append(proveedor.capturar_muestra(dedo, timeout_s=20))
                    calidad_insuficiente_seguidas = 0
                except TiempoAgotado:
                    raise ErrorHuella(
                        "No se detectó el dedo a tiempo. Vuelva a intentar."
                    )
                except CalidadInsuficiente:
                    calidad_insuficiente_seguidas += 1
                    if calidad_insuficiente_seguidas >= 3:
                        raise ErrorHuella(
                            "La calidad de las capturas es muy baja. Limpie el "
                            "sensor y el dedo, y vuelva a intentar."
                        )
                except CapturaFallida as error:
                    raise ErrorHuella(f"Falló la captura: {error}")
                except LectorNoDisponible:
                    raise ErrorHuella(
                        "No se pudo conectar con el lector SecuGen. Revise "
                        "que esté conectado y que el driver esté instalado."
                    )

            try:
                plantilla = proveedor.crear_plantilla(muestras)
            except ValueError as error:
                raise ErrorHuella(str(error))

        referencia = RegistroBiometrico.referencia_para(tipo_persona, persona_id)
        plantilla = plantilla.con_referencia(referencia)

        # La captura ya se hizo; lo que queda es guardarla. Si la base no
        # responde hay que decirlo con todas las letras: la huella que se
        # acaba de tomar se pierde y hay que repetir el enrolamiento.
        try:
            registro = RegistroBiometrico.query.filter_by(
                tipo_persona=tipo_persona, persona_id=persona_id
            ).first()
            if registro is None:
                registro = RegistroBiometrico(
                    tipo_persona=tipo_persona, persona_id=persona_id
                )
                db.session.add(registro)

            registro.nombre_completo = nombre_completo
            registro.correo = correo
            registro.cedula = cedula
            registro.dedo = int(plantilla.dedo)
            registro.formato = plantilla.formato
            registro.plantilla = plantilla.datos
            registro.calidad = plantilla.calidad
            registro.muestras_usadas = plantilla.muestras_usadas
            registro.proveedor = plantilla.proveedor.value
            db.session.commit()
        except ERRORES_BASE:
            db.session.rollback()
            raise BaseHuellasNoDisponible(
                "Se capturó la huella pero no se pudo guardar: "
                + BaseHuellasNoDisponible.MENSAJE
            )
        return registro

    # ── Verificación 1:1 (check-in: ya se sabe quién es) ────────────

    def verificar(self, tipo_persona, persona_id, nombre_visible=""):
        """Devuelve el `Veredicto`, o lanza `ErrorHuella` con un mensaje claro.

        `proveedor.verificar()` nunca lanza por un intento fallido de la
        persona (dedo mal puesto, tiempo agotado...): eso viaja *dentro*
        del `Veredicto`, en `codigo`. Solo lanza ante fallas de
        infraestructura (lector desconectado, error del SDK), que sí
        capturamos aquí como `ErrorHuella`.
        """
        try:
            registro = RegistroBiometrico.query.filter_by(
                tipo_persona=tipo_persona, persona_id=persona_id
            ).first()
        except ERRORES_BASE:
            db.session.rollback()
            raise BaseHuellasNoDisponible()
        if registro is None:
            raise ErrorHuella(
                f"{nombre_visible or 'Esta persona'} no tiene huella registrada. "
                f"Regístrela primero."
            )

        proveedor = self._obtener_proveedor()
        with self._candado:
            try:
                veredicto = proveedor.verificar(registro.a_plantilla(), timeout_s=20)
            except LectorNoDisponible:
                raise ErrorHuella("No se pudo conectar con el lector SecuGen.")
            except ErrorBiometrico as error:
                raise ErrorHuella(f"Error del lector: {error}")

        if veredicto.coincide:
            return veredicto

        mensajes = {
            CodigoResultado.TIEMPO_AGOTADO:
                "No se detectó el dedo a tiempo. Intente de nuevo.",
            CodigoResultado.CALIDAD_INSUFICIENTE:
                "La captura salió borrosa. Limpie el sensor y el dedo, y "
                "vuelva a intentar.",
            CodigoResultado.CAPTURA_FALLIDA:
                "Falló la captura. Vuelva a intentar.",
            CodigoResultado.NO_MATCH:
                f"La huella no coincide (puntaje {veredicto.score} de "
                f"{veredicto.umbral} requeridos). Intente de nuevo con el "
                f"dedo bien centrado.",
        }
        raise ErrorHuella(
            mensajes.get(veredicto.codigo, f"Verificación fallida ({veredicto.codigo}).")
        )

    # ── Verificación 1:N (login: todavía no se sabe quién es) ───────

    def identificar(self, tipo_persona):
        """
        Busca, entre todas las huellas registradas de `tipo_persona`, cuál
        coincide con el dedo recién apoyado. Devuelve `(persona_id,
        Coincidencia)`, o lanza `ErrorHuella` si no hay match.
        """
        try:
            registros = RegistroBiometrico.query.filter_by(
                tipo_persona=tipo_persona
            ).all()
        except ERRORES_BASE:
            db.session.rollback()
            raise BaseHuellasNoDisponible()
        if not registros:
            raise ErrorHuella(
                f"Todavía no hay huellas registradas para «{tipo_persona}»."
            )

        plantillas = {r.referencia_propia(): r.a_plantilla() for r in registros}

        proveedor = self._obtener_proveedor()
        with self._candado:
            try:
                coincidencia = proveedor.buscar(plantillas, timeout_s=20)
            except TiempoAgotado:
                raise ErrorHuella("No se detectó el dedo a tiempo. Vuelva a intentar.")
            except CalidadInsuficiente:
                raise ErrorHuella(
                    "La captura salió borrosa. Limpie el sensor y el dedo, "
                    "y vuelva a intentar."
                )
            except CapturaFallida as error:
                raise ErrorHuella(f"Falló la captura: {error}")
            except LectorNoDisponible:
                raise ErrorHuella("No se pudo conectar con el lector SecuGen.")
            except ErrorBiometrico as error:
                raise ErrorHuella(f"Error del lector: {error}")

        if coincidencia is None:
            raise ErrorHuella("La huella no coincide con ninguna registrada.")

        _, persona_id = RegistroBiometrico.descomponer_referencia(
            coincidencia.referencia
        )
        return persona_id, coincidencia

    # ── Ciclo de vida ────────────────────────────────────────────

    def cerrar(self):
        if self._proveedor is not None:
            self._proveedor.cerrar()
            self._proveedor = None

    def __repr__(self):
        return f"<LectorHuella modo={self.modo} umbral={self.umbral}>"
