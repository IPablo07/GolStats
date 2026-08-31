"""
servicios/huella.py
────────────────────
Servicio de huella dactilar para GolStats.

Maneja:
  1. registrar()    -> enrolamiento de una huella.
  2. verificar()    -> comparación 1:1.
  3. identificar()  -> comparación 1:N.
  4. cerrar()       -> cierre del lector.

El lector físico SecuGen se comunica mediante el paquete `biometria`.
Las plantillas biométricas se almacenan en PostgreSQL mediante
RegistroBiometrico.
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

from extensiones import db
from modelos.huella import RegistroBiometrico


# Carpeta raíz del proyecto GolStats.
# Aquí deben encontrarse las DLL de SecuGen.
RAIZ_PROYECTO = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)


class ErrorHuella(Exception):
    """
    Error controlado del sistema biométrico.

    Los mensajes de esta excepción están pensados para mostrarse
    directamente al usuario.
    """
    pass


class LectorHuella:
    """
    Fachada del sistema biométrico de GolStats.

    El resto de la aplicación no necesita conocer los detalles
    del SDK SecuGen.
    """

    MODO_SECUGEN = "secugen"
    MODO_SIMULADO = "simulado"

    def __init__(
        self,
        modo=MODO_SIMULADO,
        umbral=45,
        lector="secugen:hsdu03p"
    ):
        modo = (modo or "").strip().lower()

        if modo not in (
            LectorHuella.MODO_SECUGEN,
            LectorHuella.MODO_SIMULADO,
        ):
            raise ValueError(
                f"HUELLA_MODO inválido: {modo}. "
                f"Use secugen o simulado"
            )

        self.modo = modo
        self.umbral = umbral
        self.lector_modelo = lector

        # Proveedor biométrico.
        self._proveedor = None

        # El lector físico es un dispositivo único.
        # Evita dos capturas simultáneas.
        self._candado = threading.Lock()

    # ─────────────────────────────────────────────────────────────
    # CONFIGURACIÓN
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def desde_config(cls, config):
        """
        Crea el lector usando la configuración de Flask.
        """
        return cls(
            modo=config.HUELLA_MODO,
            umbral=config.HUELLA_UMBRAL,
            lector=config.HUELLA_LECTOR,
        )

    def es_simulado(self):
        """
        Devuelve True si se está utilizando el lector simulado.
        """
        return self.modo == LectorHuella.MODO_SIMULADO

    # ─────────────────────────────────────────────────────────────
    # PROVEEDOR
    # ─────────────────────────────────────────────────────────────

    def _obtener_proveedor(self):
        """
        Crea el proveedor biométrico la primera vez que se necesita.
        """

        if self._proveedor is not None:
            return self._proveedor

        if self.modo == LectorHuella.MODO_SECUGEN:

            # Permite encontrar sgfplib.dll y demás DLL de SecuGen
            # aunque Flask no se haya iniciado desde la carpeta raíz.
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(RAIZ_PROYECTO)

            try:
                self._proveedor = crear_proveedor(
                    "EXTERNO",
                    lector=self.lector_modelo,
                    umbral=self.umbral
                )

            except Exception as error:
                raise ErrorHuella(
                    "No se pudo iniciar el lector SecuGen. "
                    "Revise que esté conectado y que las DLL "
                    "del dispositivo estén instaladas."
                ) from error

        else:
            self._proveedor = crear_proveedor(
                "SIMULADO",
                umbral=self.umbral
            )

        return self._proveedor

    # ─────────────────────────────────────────────────────────────
    # MENSAJES DE ERROR
    # ─────────────────────────────────────────────────────────────

    def _mensaje_captura_fallida(self, error):
        """
        Convierte errores técnicos del SDK SecuGen en mensajes
        comprensibles para el usuario.
        """

        mensaje = str(error).lower()

        # Error típico cuando SGFPM_GetImageEx falla porque
        # el lector fue desconectado o dejó de responder.
        if (
            "sgfpm_getimageex" in mensaje
            or "código 2" in mensaje
            or "codigo 2" in mensaje
            or "code 2" in mensaje
        ):
            return (
                "El detector de huella fue desconectado "
                "o dejó de responder. "
                "Conecte nuevamente el lector e inténtelo otra vez."
            )

        return f"Falló la captura de la huella: {error}"

    def _mensaje_error_lector(self, error):
        """
        Convierte errores generales del SDK en mensajes claros.
        """

        mensaje = str(error).lower()

        if (
            "sgfpm_getimageex" in mensaje
            or "código 2" in mensaje
            or "codigo 2" in mensaje
            or "code 2" in mensaje
        ):
            return (
                "El detector de huella fue desconectado "
                "o dejó de responder. "
                "Conecte nuevamente el lector e inténtelo otra vez."
            )

        return f"Error del lector de huella: {error}"

    # ─────────────────────────────────────────────────────────────
    # DIAGNÓSTICO
    # ─────────────────────────────────────────────────────────────

    def diagnostico(self):
        """
        Devuelve el estado actual del lector.
        """

        try:
            return self._obtener_proveedor().diagnostico()

        except LectorNoDisponible as error:
            raise ErrorHuella(
                "El detector de huella no está disponible. "
                "Conecte el lector SecuGen."
            ) from error

        except ErrorBiometrico as error:
            raise ErrorHuella(
                self._mensaje_error_lector(error)
            ) from error

        except Exception as error:
            raise ErrorHuella(
                self._mensaje_error_lector(error)
            ) from error

    # ─────────────────────────────────────────────────────────────
    # REGISTRAR HUELLA
    # ─────────────────────────────────────────────────────────────

    def tiene_huella(self, tipo_persona, persona_id):
        """
        Comprueba si una persona ya tiene una huella registrada.
        """

        return (
            RegistroBiometrico.query.filter_by(
                tipo_persona=tipo_persona,
                persona_id=persona_id
            ).first()
            is not None
        )

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
        Registra la huella de una persona.

        Se realizan varias capturas del mismo dedo y posteriormente
        se genera una plantilla biométrica que se almacena en PostgreSQL.
        """

        proveedor = self._obtener_proveedor()

        with self._candado:

            muestras = []
            calidad_insuficiente_seguidas = 0

            while len(muestras) < muestras_requeridas:

                try:

                    muestra = proveedor.capturar_muestra(
                        dedo,
                        timeout_s=20
                    )

                    muestras.append(muestra)
                    calidad_insuficiente_seguidas = 0

                except TiempoAgotado:

                    raise ErrorHuella(
                        "No se detectó el dedo a tiempo. "
                        "Coloque el dedo sobre el sensor e inténtelo nuevamente."
                    )

                except CalidadInsuficiente:

                    calidad_insuficiente_seguidas += 1

                    if calidad_insuficiente_seguidas >= 3:

                        raise ErrorHuella(
                            "La calidad de las capturas es muy baja. "
                            "Limpie el sensor y el dedo y vuelva a intentar."
                        )

                except CapturaFallida as error:

                    raise ErrorHuella(
                        self._mensaje_captura_fallida(error)
                    ) from error

                except LectorNoDisponible as error:

                    raise ErrorHuella(
                        "No se pudo conectar con el lector SecuGen. "
                        "Revise que esté conectado y que el driver "
                        "esté instalado correctamente."
                    ) from error

                except ErrorBiometrico as error:

                    raise ErrorHuella(
                        self._mensaje_error_lector(error)
                    ) from error

            # Crear plantilla con las muestras obtenidas.
            try:

                plantilla = proveedor.crear_plantilla(muestras)

            except ValueError as error:

                raise ErrorHuella(str(error)) from error

            except ErrorBiometrico as error:

                raise ErrorHuella(
                    self._mensaje_error_lector(error)
                ) from error

        # Referencia de la persona.
        referencia = RegistroBiometrico.referencia_para(
            tipo_persona,
            persona_id
        )

        plantilla = plantilla.con_referencia(referencia)

        # Buscar si ya existe una huella.
        registro = RegistroBiometrico.query.filter_by(
            tipo_persona=tipo_persona,
            persona_id=persona_id
        ).first()

        if registro is None:

            registro = RegistroBiometrico(
                tipo_persona=tipo_persona,
                persona_id=persona_id
            )

            db.session.add(registro)

        # Guardar información.
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

        return registro

    # ─────────────────────────────────────────────────────────────
    # VERIFICAR 
    # ─────────────────────────────────────────────────────────────

    def verificar(
        self,
        tipo_persona,
        persona_id,
        nombre_visible=""
    ):
        """
        Verifica una huella contra la plantilla de una persona específica.
        """

        registro = RegistroBiometrico.query.filter_by(
            tipo_persona=tipo_persona,
            persona_id=persona_id
        ).first()

        if registro is None:

            raise ErrorHuella(
                f"{nombre_visible or 'Esta persona'} "
                f"no tiene huella registrada. "
                f"Regístrela primero."
            )

        proveedor = self._obtener_proveedor()

        with self._candado:

            try:

                veredicto = proveedor.verificar(
                    registro.a_plantilla(),
                    timeout_s=20
                )

            except TiempoAgotado:

                raise ErrorHuella(
                    "No se detectó el dedo a tiempo. "
                    "Coloque el dedo sobre el sensor e inténtelo nuevamente."
                )

            except CalidadInsuficiente:

                raise ErrorHuella(
                    "La captura salió borrosa. "
                    "Limpie el sensor y el dedo y vuelva a intentar."
                )

            except CapturaFallida as error:

                raise ErrorHuella(
                    self._mensaje_captura_fallida(error)
                ) from error

            except LectorNoDisponible as error:

                raise ErrorHuella(
                    "No se pudo conectar con el lector SecuGen. "
                    "Revise que esté conectado."
                ) from error

            except ErrorBiometrico as error:

                raise ErrorHuella(
                    self._mensaje_error_lector(error)
                ) from error

        # La huella coincide.
        if veredicto.coincide:
            return veredicto

        # Mensajes para diferentes resultados.
        mensajes = {

            CodigoResultado.TIEMPO_AGOTADO:
                "No se detectó el dedo a tiempo. "
                "Intente nuevamente.",

            CodigoResultado.CALIDAD_INSUFICIENTE:
                "La captura salió borrosa. "
                "Limpie el sensor y el dedo y vuelva a intentar.",

            CodigoResultado.CAPTURA_FALLIDA:
                "Falló la captura. "
                "Verifique que el lector esté conectado.",

            CodigoResultado.NO_MATCH:
                f"La huella no coincide "
                f"(puntaje {veredicto.score} de "
                f"{veredicto.umbral} requeridos). "
                f"Coloque correctamente el dedo e intente nuevamente.",
        }

        raise ErrorHuella(
            mensajes.get(
                veredicto.codigo,
                f"Verificación fallida ({veredicto.codigo})."
            )
        )

    # ─────────────────────────────────────────────────────────────
    # IDENTIFICAR 
    # ─────────────────────────────────────────────────────────────

    def identificar(self, tipo_persona):
        """
        Busca una coincidencia entre todas las huellas registradas
        de un determinado tipo de persona.
        """

        registros = RegistroBiometrico.query.filter_by(
            tipo_persona=tipo_persona
        ).all()

        if not registros:

            raise ErrorHuella(
                f"Todavía no hay huellas registradas "
                f"para «{tipo_persona}»."
            )

        # Convertir registros de PostgreSQL a plantillas biométricas.
        plantillas = {
            r.referencia_propia(): r.a_plantilla()
            for r in registros
        }

        proveedor = self._obtener_proveedor()

        with self._candado:

            try:

                coincidencia = proveedor.buscar(
                    plantillas,
                    timeout_s=20
                )

            except TiempoAgotado:

                raise ErrorHuella(
                    "No se detectó el dedo a tiempo. "
                    "Coloque el dedo sobre el sensor e inténtelo nuevamente."
                )

            except CalidadInsuficiente:

                raise ErrorHuella(
                    "La captura salió borrosa. "
                    "Limpie el sensor y el dedo y vuelva a intentar."
                )

            except CapturaFallida as error:

                raise ErrorHuella(
                    self._mensaje_captura_fallida(error)
                ) from error

            except LectorNoDisponible as error:

                raise ErrorHuella(
                    "No se pudo conectar con el lector SecuGen. "
                    "Revise que esté conectado."
                ) from error

            except ErrorBiometrico as error:

                raise ErrorHuella(
                    self._mensaje_error_lector(error)
                ) from error

        # No hubo coincidencia.
        if coincidencia is None:

            raise ErrorHuella(
                "La huella no coincide con ninguna registrada."
            )

        # Recuperar ID de persona.
        _, persona_id = RegistroBiometrico.descomponer_referencia(
            coincidencia.referencia
        )

        return persona_id, coincidencia

    # ─────────────────────────────────────────────────────────────
    # CERRAR LECTOR
    # ─────────────────────────────────────────────────────────────

    def cerrar(self):
        """
        Cierra correctamente el proveedor biométrico.
        """

        if self._proveedor is not None:

            try:
                self._proveedor.cerrar()

            except Exception:
                # Evitamos que un error al cerrar el dispositivo
                # provoque el cierre inesperado de Flask.
                pass

            finally:
                self._proveedor = None

    # ─────────────────────────────────────────────────────────────
    # REPRESENTACIÓN
    # ─────────────────────────────────────────────────────────────

    def __repr__(self):

        return (
            f"<LectorHuella "
            f"modo={self.modo} "
            f"umbral={self.umbral}>"
        )
