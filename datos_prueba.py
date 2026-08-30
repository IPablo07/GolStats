"""
datos_prueba.py
────────────────
Datos de ejemplo en memoria para poder desarrollar el front-end sin
tener todavía la base de datos conectada.

Cuando entre PostgreSQL, este archivo se reemplaza por consultas
reales: el resto del código sigue pidiendo lo mismo (BD.equipos,
BD.buscar_usuario_por_correo(), etc.).

Cuentas de prueba:
    admin@golstats.com / admin123
    cualquier jugador  / jugador123   (ver BD.jugadores)
"""

from datetime import datetime, timedelta

from modelos import (
    Administrador, Jugador, Equipo, Arbitro, Partido, Tarjeta, CheckIn,
)

PASSWORD_JUGADORES = "jugador123"
PASSWORD_ADMIN = "admin123"


class BaseDatosMemoria:
    """Contenedor simple que hace de repositorio mientras no hay BD."""

    def __init__(self):
        self.usuarios = []
        self.equipos = []
        self.jugadores = []
        self.arbitros = []
        self.partidos = []

    # ── Búsquedas ─────────────────────────────────────────────────

    def buscar_usuario_por_correo(self, correo):
        correo = (correo or "").strip().lower()
        for usuario in self.usuarios:
            if usuario.correo.lower() == correo:
                return usuario
        return None

    def buscar_usuario_por_id(self, usuario_id):
        return next((u for u in self.usuarios if u.id == usuario_id), None)

    def buscar_equipo(self, equipo_id):
        return next((e for e in self.equipos if e.id == equipo_id), None)

    def buscar_jugador(self, jugador_id):
        return next((j for j in self.jugadores if j.id == jugador_id), None)

    def buscar_partido(self, partido_id):
        return next((p for p in self.partidos if p.id == partido_id), None)

    # ── Listados para el front ────────────────────────────────────

    def partidos_por_estado(self, *estados):
        return [p for p in self.partidos if p.estado in estados]

    def proximos_partidos(self):
        return sorted(
            self.partidos_por_estado(Partido.PROGRAMADO),
            key=lambda p: p.fecha_hora,
        )

    def partidos_de_jugador(self, jugador):
        return [p for p in self.partidos if p.esta_convocado(jugador)]


def _crear_equipo(bd, id, nombre, capitan, correo_capitan, plantilla):
    equipo = Equipo(id, nombre, capitan, correo_capitan)
    bd.equipos.append(equipo)

    for numero, (nombres, apellidos, cedula) in enumerate(plantilla, start=1):
        jugador_id = len(bd.jugadores) + 1
        correo = f"{nombres.split()[0].lower()}.{apellidos.split()[0].lower()}@golstats.com"
        jugador = Jugador(
            id=jugador_id,
            correo=correo,
            password_plano=PASSWORD_JUGADORES,
            equipo=equipo,
            nombres=nombres,
            apellidos=apellidos,
            cedula=cedula,
            numero_camiseta=numero,
        )
        equipo.agregar_jugador(jugador)
        bd.jugadores.append(jugador)
        bd.usuarios.append(jugador)

    return equipo


def crear_datos_prueba():
    bd = BaseDatosMemoria()

    # ── Administrador ─────────────────────────────────────────────
    admin = Administrador(id=1000, correo="admin@golstats.com",
                          password_plano=PASSWORD_ADMIN)
    bd.usuarios.append(admin)

    # ── Árbitros (catálogo, sin cuenta) ───────────────────────────
    bd.arbitros = [
        Arbitro(1, "Carlos Mendoza", "cmendoza@golstats.com", "0991112233"),
        Arbitro(2, "Luis Paredes", "lparedes@golstats.com", "0994445566"),
    ]

    # ── Equipos y jugadores ───────────────────────────────────────
    leones = _crear_equipo(
        bd, 1, "Leones FC", "Andrés Salazar", "capitan.leones@golstats.com",
        [
            ("Andrés", "Salazar", "0102030405"),
            ("Bryan", "Vera", "0102030406"),
            ("Carlos", "Loor", "0102030407"),
            ("Diego", "Moran", "0102030408"),
            ("Erick", "Zambrano", "0102030409"),
        ],
    )
    aguilas = _crear_equipo(
        bd, 2, "Águilas SC", "Fernando Ruiz", "capitan.aguilas@golstats.com",
        [
            ("Fernando", "Ruiz", "0202030405"),
            ("Gabriel", "Ponce", "0202030406"),
            ("Hugo", "Cedeño", "0202030407"),
            ("Iván", "Bravo", "0202030408"),
            ("Jorge", "Alvarado", "0202030409"),
        ],
    )
    tiburones = _crear_equipo(
        bd, 3, "Tiburones FC", "Kevin Ortega", "capitan.tiburones@golstats.com",
        [
            ("Kevin", "Ortega", "0302030405"),
            ("Luis", "Naranjo", "0302030406"),
            ("Marco", "Villacis", "0302030407"),
            ("Nestor", "Chavez", "0302030408"),
            ("Oscar", "Pinto", "0302030409"),
        ],
    )
    halcones = _crear_equipo(
        bd, 4, "Halcones United", "Pedro Sanchez", "capitan.halcones@golstats.com",
        [
            ("Pedro", "Sanchez", "0402030405"),
            ("Raul", "Guerrero", "0402030406"),
            ("Sergio", "Tapia", "0402030407"),
            ("Tomas", "Aguirre", "0402030408"),
            ("Victor", "Cruz", "0402030409"),
        ],
    )

    hoy = datetime.now().replace(minute=0, second=0, microsecond=0)

    # ── Partido 1: jugado de principio a fin ──────────────────────
    p1 = Partido(1, leones, aguilas, hoy - timedelta(days=7), bd.arbitros[0])
    _jugar_partido_completo(
        p1,
        goles_primer_tiempo=[
            (leones.obtener_jugadores()[1], 12, leones.obtener_jugadores()[0]),
            (aguilas.obtener_jugadores()[2], 27, None),
        ],
        goles_segundo_tiempo=[
            (leones.obtener_jugadores()[1], 58, leones.obtener_jugadores()[3]),
            (leones.obtener_jugadores()[4], 71, None),
        ],
        tarjetas=[
            (aguilas.obtener_jugadores()[3], Tarjeta.AMARILLA, 35),
            (aguilas.obtener_jugadores()[3], Tarjeta.ROJA, 64),
        ],
    )
    bd.partidos.append(p1)

    # ── Partido 2: walkover porque Halcones no pagó la vocalía ────
    p2 = Partido(2, tiburones, halcones, hoy - timedelta(days=5), bd.arbitros[1])
    p2.convocar_varios(tiburones.obtener_jugadores() + halcones.obtener_jugadores())
    for jugador in p2.obtener_convocados():
        p2.registrar_checkin(jugador, CheckIn.HUELLA)
    p2.iniciar_primer_tiempo()
    p2.registrar_gol(tiburones.obtener_jugadores()[0], 20)
    p2.terminar_primer_tiempo()
    p2.completar_pago(tiburones)          # Halcones nunca pagó
    p2.iniciar_segundo_tiempo()           # dispara el walkover automático
    bd.partidos.append(p2)

    # ── Partido 3: jugado, con empate ─────────────────────────────
    p3 = Partido(3, aguilas, tiburones, hoy - timedelta(days=2), bd.arbitros[0])
    _jugar_partido_completo(
        p3,
        goles_primer_tiempo=[
            (aguilas.obtener_jugadores()[0], 15, aguilas.obtener_jugadores()[1]),
        ],
        goles_segundo_tiempo=[
            (tiburones.obtener_jugadores()[1], 62, tiburones.obtener_jugadores()[0]),
        ],
        tarjetas=[
            (tiburones.obtener_jugadores()[4], Tarjeta.AMARILLA, 78),
        ],
    )
    bd.partidos.append(p3)

    # ── Partido 4: programado, con check-in a medias ──────────────
    p4 = Partido(4, leones, halcones, hoy + timedelta(days=2), bd.arbitros[1])
    p4.convocar_varios(leones.obtener_jugadores() + halcones.obtener_jugadores())
    for jugador in leones.obtener_jugadores()[:3]:
        p4.registrar_checkin(jugador, CheckIn.HUELLA)
    p4.completar_pago(leones)
    bd.partidos.append(p4)

    # ── Partido 5: programado, sin nada todavía ───────────────────
    p5 = Partido(5, halcones, aguilas, hoy + timedelta(days=5), bd.arbitros[0])
    p5.convocar_varios(halcones.obtener_jugadores() + aguilas.obtener_jugadores())
    bd.partidos.append(p5)

    return bd


def _jugar_partido_completo(partido, goles_primer_tiempo, goles_segundo_tiempo,
                            tarjetas):
    """Recorre el ciclo de vida completo: convocatoria → check-in → final."""
    convocados = (partido.equipo_local.obtener_jugadores()
                  + partido.equipo_visitante.obtener_jugadores())
    partido.convocar_varios(convocados)
    for jugador in convocados:
        partido.registrar_checkin(jugador, CheckIn.HUELLA)

    partido.iniciar_primer_tiempo()
    for jugador, minuto, asistente in goles_primer_tiempo:
        partido.registrar_gol(jugador, minuto, asistente)
    for jugador, tipo, minuto in tarjetas:
        if minuto <= 45:
            partido.registrar_tarjeta(jugador, tipo, minuto)

    partido.terminar_primer_tiempo()
    for equipo in partido.equipos():
        partido.completar_pago(equipo)
    partido.iniciar_segundo_tiempo()

    for jugador, minuto, asistente in goles_segundo_tiempo:
        partido.registrar_gol(jugador, minuto, asistente)
    for jugador, tipo, minuto in tarjetas:
        if minuto > 45:
            partido.registrar_tarjeta(jugador, tipo, minuto)

    partido.finalizar()
    return partido


# Instancia única que importan las rutas de Flask.
BD = crear_datos_prueba()
