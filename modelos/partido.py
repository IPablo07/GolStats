"""
modelos/partido.py
───────────────────
El corazón del sistema: el partido y todo lo que pasa dentro de él
(convocatoria, check-in con huella, goles, tarjetas, pago de vocalía,
walkover y cierre).

Las mismas reglas que aquí se validan en Python están replicadas como
triggers en PostgreSQL (ver sql/schema.sql). Por ahora todo vive en
memoria; cuando se conecte la base de datos, la interfaz pública de
esta clase no cambia.

Jerarquía de eventos: EventoPartido (base) → Gol, Tarjeta, CheckIn.
Cada uno define su propio descripcion() — polimorfismo.
"""

from datetime import datetime

from modelos.pago import PagoVocalia


# ══════════════════════════════════════════════════════════════════
#  Eventos que ocurren dentro de un partido
# ══════════════════════════════════════════════════════════════════

class EventoPartido:
    """Clase base de todo lo que se registra durante un partido."""

    def __init__(self, partido, jugador, minuto=None):
        self.partido = partido
        self.jugador = jugador
        self.minuto = minuto
        self.registrado_en = datetime.now()

    def descripcion(self):
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

    PROGRAMADO = "programado"
    PRIMER_TIEMPO = "primer_tiempo"
    MEDIO_TIEMPO = "medio_tiempo"
    SEGUNDO_TIEMPO = "segundo_tiempo"
    FINALIZADO = "finalizado"
    WALKOVER = "walkover"

    ESTADOS = (
        PROGRAMADO, PRIMER_TIEMPO, MEDIO_TIEMPO,
        SEGUNDO_TIEMPO, FINALIZADO, WALKOVER,
    )

    MONTO_VOCALIA = 20.00

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

        # Colecciones internas — se leen con los métodos obtener_*()
        self._convocados = []
        self._checkins = []
        self._goles = []
        self._tarjetas = []

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

    # ── Convocatoria ──────────────────────────────────────────────

    def convocar(self, jugador):
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
        return self._estado

    def terminar_primer_tiempo(self):
        if self._estado != Partido.PRIMER_TIEMPO:
            raise ValueError("Solo se puede ir al medio tiempo desde el primer tiempo")
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
        return self._estado

    def _declarar_walkover(self, ganador, motivo):
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
        self._estado = Partido.FINALIZADO
        if self.goles_local > self.goles_visitante:
            self.equipo_ganador = self.equipo_local
        elif self.goles_visitante > self.goles_local:
            self.equipo_ganador = self.equipo_visitante
        else:
            self.equipo_ganador = None       # empate
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

    def registrar_gol(self, jugador, minuto, jugador_asistencia=None):
        """Regla 3: al registrar un gol se actualiza solo el marcador."""
        self._validar_registro_en_juego(jugador)
        if jugador_asistencia is not None:
            self._validar_registro_en_juego(jugador_asistencia)
            if jugador_asistencia.equipo.id != jugador.equipo.id:
                raise ValueError(
                    "La asistencia debe ser de un compañero del mismo equipo"
                )

        gol = Gol(self, jugador, minuto, jugador_asistencia)
        self._goles.append(gol)
        if self.es_local(jugador.equipo):
            self.goles_local += 1
        else:
            self.goles_visitante += 1
        return gol

    def registrar_tarjeta(self, jugador, tipo, minuto):
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
