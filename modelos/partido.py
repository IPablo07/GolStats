"""
modelos/partido.py
───────────────────
El corazón del sistema: el partido y todo lo que pasa dentro de él
(convocatoria, check-in con huella, goles, tarjetas, pago de vocalía,
walkover y cierre).

Las mismas reglas que aquí se validan en Python están replicadas como
triggers en PostgreSQL (ver database/02_triggers.sql). Por ahora todo
vive en memoria; cuando se conecte la base de datos, la interfaz pública
de esta clase no cambia.

Jerarquía de eventos: EventoPartido (base) → Gol, Tarjeta, CheckIn.
Cada uno define su propio descripcion() — polimorfismo.
"""

from datetime import datetime
from math import ceil

from modelos.pago import PagoVocalia


# ══════════════════════════════════════════════════════════════════
#  Eventos que ocurren dentro de un partido
# ══════════════════════════════════════════════════════════════════

class EventoPartido:
    """Clase base de todo lo que se registra durante un partido."""
    
    _contador_ids = 0  # Identificador para la edición

    def __init__(self, partido, jugador, minuto=None):
        EventoPartido._contador_ids += 1
        self.id = EventoPartido._contador_ids
        self.partido = partido
        self.jugador = jugador
        self.minuto = minuto
        self.registrado_en = datetime.now()

    def descripcion(self):
        """
        Texto del evento para la línea de tiempo del partido.

        Cada subclase lo redefine. Gracias a eso, obtener_eventos() puede
        mezclar goles y tarjetas en una sola lista y la plantilla los
        recorre sin preguntar de qué tipo es cada uno.
        """
        raise NotImplementedError("Cada evento debe definir su propia descripcion()")

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.descripcion()}>"


class Gol(EventoPartido):
    """Un gol. Puede tener (o no) un jugador que dio la asistencia."""

    def __init__(self, partido, jugador, minuto, jugador_asistencia=None):
        super().__init__(partido, jugador, minuto)
        if jugador_asistencia is not None and jugador_asistencia.id == jugador.id:
            raise ValueError("Un jugador no puede asistirse a sí mismo")
        self.jugador_asistencia = jugador_asistencia
        self.equipo = jugador.equipo

    def descripcion(self):
        texto = f"Gol de {self.jugador.nombre_completo()} al minuto {self.minuto}"
        if self.jugador_asistencia:
            texto += f" (asistencia de {self.jugador_asistencia.nombre_completo()})"
        return texto


class Tarjeta(EventoPartido):
    """Tarjeta amarilla o roja mostrada por el árbitro."""

    AMARILLA = "amarilla"
    ROJA = "roja"
    TIPOS = (AMARILLA, ROJA)

    def __init__(self, partido, jugador, tipo, minuto):
        super().__init__(partido, jugador, minuto)
        if tipo not in Tarjeta.TIPOS:
            raise ValueError(
                f"Tipo de tarjeta inválido: {tipo}. Debe ser amarilla o roja"
            )
        self.tipo = tipo
        self.equipo = jugador.equipo

    def descripcion(self):
        return (
            f"Tarjeta {self.tipo} para {self.jugador.nombre_completo()} "
            f"al minuto {self.minuto}"
        )


class CheckIn(EventoPartido):
    """Confirmación de que el jugador se presentó, antes de iniciar el partido."""

    HUELLA = "huella"
    MANUAL = "manual"
    METODOS = (HUELLA, MANUAL)

    def __init__(self, partido, jugador, metodo=HUELLA):
        super().__init__(partido, jugador, minuto=None)
        if metodo not in CheckIn.METODOS:
            raise ValueError(
                f"Método de check-in inválido: {metodo}. Debe ser huella o manual"
            )
        self.metodo = metodo
        self.hora_registro = self.registrado_en

    def descripcion(self):
        hora = self.hora_registro.strftime("%H:%M:%S")
        return f"Check-in ({self.metodo}) de {self.jugador.nombre_completo()} a las {hora}"


# ══════════════════════════════════════════════════════════════════
#  El partido
# ══════════════════════════════════════════════════════════════════

class Partido:
    """
    Un partido entre dos equipos, con toda su vocalía.

    Es la clase que concentra las reglas del negocio. El estado avanza solo
    por los métodos de transición, y cada uno valida antes de dejar pasar:

        programado --> primer_tiempo    exige que todos hayan hecho check-in
        medio_tiempo --> segundo_tiempo exige que los dos equipos hayan pagado
                                        (si no, se declara walkover)

    Las colecciones internas (_convocados, _checkins, _goles, _tarjetas,
    _pagos) son privadas porque registrar un gol también actualiza el
    marcador: agregarlo por fuera dejaría el partido incoherente.
    """

    PROGRAMADO = "programado"
    PRIMER_TIEMPO = "primer_tiempo"
    MEDIO_TIEMPO = "medio_tiempo"
    SEGUNDO_TIEMPO = "segundo_tiempo"
    FINALIZADO = "finalizado"
    WALKOVER = "walkover"
    CANCELADO = "cancelado"

    ESTADOS = (
        PROGRAMADO, PRIMER_TIEMPO, MEDIO_TIEMPO,
        SEGUNDO_TIEMPO, FINALIZADO, WALKOVER, CANCELADO,
    )

    MONTO_VOCALIA = 20.00

    # Duracion reglamentaria. El cronometro no pasa de aqui: al llegar a
    # 90' se queda clavado y espera a que el admin finalice el partido.
    MINUTOS_REGLAMENTARIOS = 90

    def __init__(self, id, equipo_local, equipo_visitante, fecha_hora, arbitro=None,
                 monto_vocalia=MONTO_VOCALIA):
        if equipo_local.id == equipo_visitante.id:
            raise ValueError("Un equipo no puede jugar contra sí mismo")

        self.id = id
        self.equipo_local = equipo_local
        self.equipo_visitante = equipo_visitante
        self.fecha_hora = fecha_hora
        self.arbitro = arbitro

        self._estado = Partido.PROGRAMADO
        self.goles_local = 0
        self.goles_visitante = 0
        self.equipo_ganador = None
        self.motivo_walkover = None
        self.motivo_cancelacion = None

        # Colecciones internas — se leen con los métodos obtener_*()
        self._convocados = []
        self._checkins = []
        self._goles = []
        self._tarjetas = []

        # Cronómetro del partido (ver la sección "Cronómetro" más abajo).
        # Solo corre durante los dos tiempos: el medio tiempo lo pausa.
        self._segundos_jugados = 0.0
        self._reloj_desde = None

        # Un pago de vocalía por equipo
        self._pagos = {
            equipo_local.id: PagoVocalia(self, equipo_local, monto_vocalia),
            equipo_visitante.id: PagoVocalia(self, equipo_visitante, monto_vocalia),
        }

    # ── Estado ────────────────────────────────────────────────────

    @property
    def estado(self):
        """Solo lectura: el estado únicamente cambia por los métodos del partido."""
        return self._estado

    def esta_en_juego(self):
        return self._estado in (Partido.PRIMER_TIEMPO, Partido.MEDIO_TIEMPO,
                                Partido.SEGUNDO_TIEMPO)

    def esta_cerrado(self):
        """
        El partido ya no admite cambios.

        Incluye los cancelados a propósito: es lo que hace que la vocalía
        oculte sola los controles del admin, el cobro y la edición de
        eventos, sin tener que repetir la comprobación en cada sitio.

        Ojo: "cerrado" no es lo mismo que "jugado". Para las estadísticas
        hace falta además que el partido se haya disputado — ver
        `cuenta_para_estadisticas()`.
        """
        return self._estado in (Partido.FINALIZADO, Partido.WALKOVER,
                                Partido.CANCELADO)

    def esta_cancelado(self):
        return self._estado == Partido.CANCELADO

    def cuenta_para_estadisticas(self):
        """
        Si este partido suma en la tabla de posiciones y los goleadores.

        Un cancelado está cerrado pero nunca se jugó: no reparte puntos ni
        goles. Sin esta distinción, cancelar un partido le regalaría un
        empate a 0 a los dos equipos.
        """
        return self._estado in (Partido.FINALIZADO, Partido.WALKOVER)

    def marcador(self):
        return f"{self.goles_local} - {self.goles_visitante}"

    def equipos(self):
        return (self.equipo_local, self.equipo_visitante)

    def es_local(self, equipo):
        return equipo.id == self.equipo_local.id

    def _validar_equipo(self, jugador):
        """Un jugador solo participa si pertenece a uno de los dos equipos."""
        if jugador.equipo is None or jugador.equipo.id not in (
            self.equipo_local.id, self.equipo_visitante.id
        ):
            raise ValueError(
                f"{jugador.nombre_completo()} no pertenece a ninguno de los dos "
                f"equipos de este partido"
            )

    # ── Cronómetro ────────────────────────────────────────────────
    #
    # Funciona como el reloj de un partido real, pero el que manda es el
    # administrador, no un temporizador automático: el reloj arranca,
    # se pausa y se reanuda enganchado a las transiciones de estado que
    # él dispara desde la vocalía.
    #
    #     iniciar_primer_tiempo()   → arranca
    #     terminar_primer_tiempo()  → pausa   (medio tiempo, sin límite)
    #     iniciar_segundo_tiempo()  → reanuda desde donde quedó
    #     finalizar() / walkover    → detiene
    #
    # No se guarda "el minuto" como un número que alguien incrementa:
    # se guardan los segundos ya acumulados más el instante en que
    # arrancó el tramo actual, y el minuto se calcula al consultarlo.
    # Así el reloj sigue avanzando aunque nadie tenga la página abierta,
    # y dos pantallas distintas nunca muestran minutos distintos.

    def _arrancar_reloj(self):
        if self._reloj_desde is None:
            self._reloj_desde = datetime.now()

    def _pausar_reloj(self):
        """Acumula lo corrido en este tramo y deja el reloj detenido."""
        if self._reloj_desde is not None:
            self._segundos_jugados += (
                datetime.now() - self._reloj_desde
            ).total_seconds()
            self._reloj_desde = None

    def reloj_corriendo(self):
        return self._reloj_desde is not None

    def segundos_jugados(self):
        """Segundos de juego efectivo, sin contar el medio tiempo."""
        segundos = self._segundos_jugados
        if self._reloj_desde is not None:
            segundos += (datetime.now() - self._reloj_desde).total_seconds()
        return min(segundos, Partido.MINUTOS_REGLAMENTARIOS * 60)

    def minuto_actual(self):
        """
        El minuto que se muestra en pantalla, como en la transmisión de un
        partido. Devuelve 0 si el partido todavía no arrancó, y nunca pasa
        de los 90.

        Con el reloj corriendo se muestra el minuto que se está jugando
        (apenas se pita el inicio ya va el 1). Con el reloj en pausa se
        muestra el último minuto cumplido: al irse al descanso después de
        45 minutos el tablero dice 45', no 46'.
        """
        segundos = self.segundos_jugados()
        if not self.reloj_corriendo():
            if segundos == 0:
                return 0
            minuto = max(1, ceil(segundos / 60))
        else:
            minuto = int(segundos // 60) + 1
        return min(minuto, Partido.MINUTOS_REGLAMENTARIOS)

    def tiempo_cumplido(self):
        """True cuando ya se llegó a los 90 minutos reglamentarios."""
        return self.segundos_jugados() >= Partido.MINUTOS_REGLAMENTARIOS * 60

    def fase_reloj(self):
        """Nombre legible de la fase en la que está el partido ahora."""
        return {
            Partido.PROGRAMADO: "Sin iniciar",
            Partido.PRIMER_TIEMPO: "Primer tiempo",
            Partido.MEDIO_TIEMPO: "Medio tiempo",
            Partido.SEGUNDO_TIEMPO: "Segundo tiempo",
            Partido.FINALIZADO: "Finalizado",
            Partido.WALKOVER: "Walkover",
        }[self._estado]

    def cronometro(self):
        """Todo lo que necesita la pantalla del admin, en un solo dict."""
        return {
            "estado": self._estado,
            "fase": self.fase_reloj(),
            "minuto": self.minuto_actual(),
            "segundos": int(self.segundos_jugados()),
            "corriendo": self.reloj_corriendo(),
            "cumplido": self.tiempo_cumplido(),
            "minutos_reglamentarios": Partido.MINUTOS_REGLAMENTARIOS,
        }

    # ── Convocatoria ──────────────────────────────────────────────

    def convocar(self, jugador):
        """
        Anota a un jugador en la lista de convocados.

        Solo se puede convocar con el partido todavía programado, y el
        jugador tiene que pertenecer a alguno de los dos equipos. Lanza
        ValueError si ya estaba convocado.
        """
        if self._estado != Partido.PROGRAMADO:
            raise ValueError(
                "Solo se puede convocar jugadores mientras el partido está programado"
            )
        self._validar_equipo(jugador)
        if self.esta_convocado(jugador):
            raise ValueError(f"{jugador.nombre_completo()} ya estaba convocado")
        self._convocados.append(jugador)
        return jugador

    def convocar_varios(self, jugadores):
        for jugador in jugadores:
            self.convocar(jugador)

    def esta_convocado(self, jugador):
        return any(j.id == jugador.id for j in self._convocados)

    def obtener_convocados(self, equipo=None):
        if equipo is None:
            return list(self._convocados)
        return [j for j in self._convocados if j.equipo.id == equipo.id]

    # ── Check-in ──────────────────────────────────────────────────

    def registrar_checkin(self, jugador, metodo=CheckIn.HUELLA):
        """
        Confirma que el jugador se presentó, antes de que arranque el partido.

        La huella ya se validó afuera (ver servicios/huella.py): acá solo se
        deja el registro. Exige que el jugador esté convocado y que no haya
        hecho check-in antes.
        """
        if self._estado != Partido.PROGRAMADO:
            raise ValueError(
                "El check-in solo se puede hacer antes de que inicie el partido"
            )
        if not self.esta_convocado(jugador):
            raise ValueError(
                f"{jugador.nombre_completo()} no está convocado para este partido"
            )
        if self.tiene_checkin(jugador):
            raise ValueError(f"{jugador.nombre_completo()} ya hizo su check-in")

        checkin = CheckIn(self, jugador, metodo)
        self._checkins.append(checkin)
        return checkin

    def tiene_checkin(self, jugador):
        return any(c.jugador.id == jugador.id for c in self._checkins)

    def obtener_checkins(self, equipo=None):
        if equipo is None:
            return list(self._checkins)
        return [c for c in self._checkins if c.jugador.equipo.id == equipo.id]

    def jugadores_sin_checkin(self):
        return [j for j in self._convocados if not self.tiene_checkin(j)]

    def todos_confirmaron(self):
        """
        True si todos los convocados hicieron check-in.

        Un partido sin convocados devuelve False, no True: no tendría sentido
        dejar arrancar un partido con la lista vacía.
        """
        return len(self._convocados) > 0 and len(self.jugadores_sin_checkin()) == 0

    # ── Pagos de vocalía ──────────────────────────────────────────

    def obtener_pago(self, equipo):
        pago = self._pagos.get(equipo.id)
        if pago is None:
            raise ValueError(f"El equipo {equipo.nombre} no juega este partido")
        return pago

    def obtener_pagos(self):
        return list(self._pagos.values())

    def completar_pago(self, equipo, comprobante_pdf=None):
        """Equivalente al stored procedure sp_completar_pago_vocalia()."""
        return self.obtener_pago(equipo).completar(comprobante_pdf)

    def equipos_sin_pagar(self):
        return [p.equipo for p in self._pagos.values() if not p.esta_pagado()]

    def vocalia_al_dia(self):
        return len(self.equipos_sin_pagar()) == 0

    # ── Transiciones de estado ────────────────────────────────────

    def iniciar_primer_tiempo(self):
        """Regla 1: no arranca si falta algún check-in."""
        if self._estado != Partido.PROGRAMADO:
            raise ValueError(
                f"El partido no se puede iniciar porque está en estado {self._estado}"
            )
        if not self._convocados:
            raise ValueError("No se puede iniciar un partido sin jugadores convocados")

        faltantes = self.jugadores_sin_checkin()
        if faltantes:
            nombres = ", ".join(j.nombre_completo() for j in faltantes)
            raise ValueError(
                f"No se puede iniciar el partido: faltan {len(faltantes)} "
                f"check-in(s) ({nombres})"
            )

        self._estado = Partido.PRIMER_TIEMPO
        self._arrancar_reloj()
        return self._estado

    def terminar_primer_tiempo(self):
        """
        Manda el partido al medio tiempo.

        Es el momento en que hay que cobrarle la vocalía a los equipos que
        todavía deben: al reanudar, el que no pagó pierde por walkover.
        """
        if self._estado != Partido.PRIMER_TIEMPO:
            raise ValueError("Solo se puede ir al medio tiempo desde el primer tiempo")
        self._pausar_reloj()
        self._estado = Partido.MEDIO_TIEMPO
        return self._estado

    def iniciar_segundo_tiempo(self):
        """
        Regla 2: si algún equipo no completó el pago de la vocalía, el partido
        termina en walkover a favor del equipo que sí pagó.
        """
        if self._estado != Partido.MEDIO_TIEMPO:
            raise ValueError(
                "El segundo tiempo solo puede iniciar desde el medio tiempo"
            )

        deudores = self.equipos_sin_pagar()
        if len(deudores) == 2:
            return self._declarar_walkover(
                ganador=None,
                motivo="Ningún equipo completó el pago de la vocalía",
            )
        if len(deudores) == 1:
            deudor = deudores[0]
            ganador = (self.equipo_visitante if self.es_local(deudor)
                       else self.equipo_local)
            return self._declarar_walkover(
                ganador=ganador,
                motivo=f"El equipo {deudor.nombre} no completó el pago de la vocalía",
            )

        self._estado = Partido.SEGUNDO_TIEMPO
        self._arrancar_reloj()
        return self._estado

    def _declarar_walkover(self, ganador, motivo):
        self._pausar_reloj()
        self._estado = Partido.WALKOVER
        self.equipo_ganador = ganador
        self.motivo_walkover = motivo
        if ganador is not None:
            if self.es_local(ganador):
                self.goles_local, self.goles_visitante = 3, 0
            else:
                self.goles_local, self.goles_visitante = 0, 3
        return self._estado

    def finalizar(self):
        """Regla 4: al cerrar, el ganador sale del marcador (si no hubo walkover)."""
        if self._estado != Partido.SEGUNDO_TIEMPO:
            raise ValueError(
                f"No se puede finalizar un partido en estado {self._estado}"
            )
        self._pausar_reloj()
        self._estado = Partido.FINALIZADO
        if self.goles_local > self.goles_visitante:
            self.equipo_ganador = self.equipo_local
        elif self.goles_visitante > self.goles_local:
            self.equipo_ganador = self.equipo_visitante
        else:
            self.equipo_ganador = None       # empate
        return self._estado

    def cancelar(self, motivo=None):
        """
        Suspende un partido que todavía no se ha jugado.

        Solo desde `programado`, y por eso no es una transición más del
        ciclo normal: un partido ya iniciado no se cancela, se resuelve
        —por walkover si alguien no pagó, o finalizándolo—. Cancelar uno
        en juego borraría de un plumazo goles y tarjetas ya registrados.

        No se elimina el partido: se marca. El historial queda a la vista
        y ni la tabla de posiciones ni los goleadores lo cuentan, porque
        `cuenta_para_estadisticas()` lo deja fuera.
        """
        if self._estado == Partido.CANCELADO:
            raise ValueError("El partido ya estaba cancelado")
        if self._estado != Partido.PROGRAMADO:
            raise ValueError(
                f"Solo se puede cancelar un partido programado. Este está en "
                f"estado {self._estado.replace('_', ' ')}"
            )

        self._estado = Partido.CANCELADO
        self.motivo_cancelacion = motivo or "Cancelado por el administrador"
        return self._estado

    # ── Goles y tarjetas ──────────────────────────────────────────

    def _validar_registro_en_juego(self, jugador):
        if not self.esta_en_juego():
            raise ValueError(
                f"No se pueden registrar eventos: el partido está en estado "
                f"{self._estado}"
            )
        self._validar_equipo(jugador)
        if not self.tiene_checkin(jugador):
            raise ValueError(
                f"{jugador.nombre_completo()} no hizo check-in, no pudo jugar"
            )

    def registrar_gol(self, jugador, minuto, jugador_asistencia=None, validar_minuto=True):
        """Regla 3: al registrar un gol se actualiza solo el marcador."""
        # Los goles quedan bloqueados en el medio tiempo. No se toca
        # esta_en_juego() porque también la usan las tarjetas y el
        # encargo solo pide bloquear goles.
        if self._estado == Partido.MEDIO_TIEMPO:
            raise ValueError("No se pueden registrar goles durante el medio tiempo")

        self._validar_registro_en_juego(jugador)
        if jugador_asistencia is not None:
            self._validar_registro_en_juego(jugador_asistencia)
            if jugador_asistencia.equipo.id != jugador.equipo.id:
                raise ValueError(
                    "La asistencia debe ser de un compañero del mismo equipo"
                )

        # El minuto no puede ir por delante del cronómetro. datos_prueba.py
        # genera los 12 partidos del torneo llamando a iniciar_primer_tiempo()
        # y registrando goles de forma instantánea: el reloj arranca, pero
        # el partido entero se juega en microsegundos, así que
        # minuto_actual() marcaría siempre 1 y rechazaría casi todos los
        # goles simulados. Por eso el parámetro validar_minuto: la ruta real
        # de la vocalía (app.py) lo deja en True; datos_prueba.py lo pasa en
        # False porque ahí el minuto es simulado, no cronometrado de verdad.
        if validar_minuto and self.reloj_corriendo() and minuto > self.minuto_actual():
            raise ValueError(
                f"El partido va por el minuto {self.minuto_actual()}: no se "
                f"puede registrar un gol en el {minuto}"
            )

        gol = Gol(self, jugador, minuto, jugador_asistencia)
        self._goles.append(gol)
        if self.es_local(jugador.equipo):
            self.goles_local += 1
        else:
            self.goles_visitante += 1
        return gol

   
    def editar_gol(self, gol_id, jugador, minuto, jugador_asistencia=None):
        """Edita un gol existente y recalcula el marcador."""
        if self.esta_cerrado():
            raise ValueError("No se pueden editar eventos de un partido finalizado")

        gol = next((g for g in self._goles if g.id == gol_id), None)
        if not gol:
            raise ValueError("El gol no existe")

        self._validar_registro_en_juego(jugador)
        
        if jugador_asistencia is not None:
            self._validar_registro_en_juego(jugador_asistencia)
            if jugador_asistencia.equipo.id != jugador.equipo.id:
                raise ValueError("La asistencia debe ser de un compañero del mismo equipo")
            if jugador_asistencia.id == jugador.id:
                raise ValueError("Un jugador no puede asistirse a sí mismo")

        if self.reloj_corriendo() and minuto > self.minuto_actual():
            raise ValueError(f"El partido va por el minuto {self.minuto_actual()}: no se puede poner el {minuto}")

        # Recalcular el marcador (restar el anterior, sumar el nuevo)
        if self.es_local(gol.equipo):
            self.goles_local -= 1
        else:
            self.goles_visitante -= 1

        gol.jugador = jugador
        gol.minuto = minuto
        gol.jugador_asistencia = jugador_asistencia
        gol.equipo = jugador.equipo

        if self.es_local(gol.equipo):
            self.goles_local += 1
        else:
            self.goles_visitante += 1

        return gol

    def editar_tarjeta(self, tarjeta_id, jugador, tipo, minuto):
        """Edita una tarjeta existente."""
        if self.esta_cerrado():
            raise ValueError("No se pueden editar eventos de un partido finalizado")

        tarjeta = next((t for t in self._tarjetas if t.id == tarjeta_id), None)
        if not tarjeta:
            raise ValueError("La tarjeta no existe")

        if tipo not in Tarjeta.TIPOS:
            raise ValueError(f"Tipo de tarjeta inválido: {tipo}")

        self._validar_registro_en_juego(jugador)

        tarjeta.jugador = jugador
        tarjeta.tipo = tipo
        tarjeta.minuto = minuto
        tarjeta.equipo = jugador.equipo

        return tarjeta
    
    def registrar_tarjeta(self, jugador, tipo, minuto):
        """
        Carga una tarjeta que el árbitro anotó en papel.

        Como con los goles, el partido tiene que estar en juego y el jugador
        tiene que haber hecho check-in: si no jugó, no lo pudieron amonestar.
        """
        self._validar_registro_en_juego(jugador)
        tarjeta = Tarjeta(self, jugador, tipo, minuto)
        self._tarjetas.append(tarjeta)
        return tarjeta

    def obtener_goles(self, equipo=None):
        if equipo is None:
            return list(self._goles)
        return [g for g in self._goles if g.equipo.id == equipo.id]

    def obtener_tarjetas(self, equipo=None):
        if equipo is None:
            return list(self._tarjetas)
        return [t for t in self._tarjetas if t.equipo.id == equipo.id]

    def obtener_eventos(self):
        """Goles y tarjetas juntos, ordenados por minuto — para la línea de tiempo."""
        eventos = self._goles + self._tarjetas
        return sorted(eventos, key=lambda e: (e.minuto is None, e.minuto))

    def __repr__(self):
        return (
            f"<Partido {self.equipo_local.nombre} {self.marcador()} "
            f"{self.equipo_visitante.nombre} [{self._estado}]>"
        )
