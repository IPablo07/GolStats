"""
datos_prueba.py
────────────────
Datos de ejemplo en memoria para poder desarrollar el front-end sin
tener todavía la base de datos conectada.

Cuando entre PostgreSQL, este archivo se reemplaza por consultas
reales: el resto del código sigue pidiendo lo mismo (BD.equipos,
BD.buscar_usuario_por_correo(), etc.).

Los partidos se simulan con una semilla fija, así que los goles y las
tarjetas son siempre los mismos en todas las máquinas del equipo. Si
fueran aleatorios de verdad, cada uno vería una tabla de posiciones
distinta y no podríamos comparar resultados entre nosotros.

Cuentas de prueba:
    admin@golstats.com     / admin123      (administrador)
    jugadores@golstats.com / jugadores123  (cuenta unica, la misma para todos)

Ya no hay una cuenta por jugador: todos los jugadores entran con la
misma cuenta compartida (ver modelos.usuario.CuentaJugadores).
"""

import random
from datetime import datetime, timedelta

from modelos import (
    Administrador, CuentaJugadores, Jugador, Equipo, Arbitro, Partido,
    Tarjeta, CheckIn,
)

# Credenciales de la cuenta unica de jugadores: una sola, igual para todos.
CORREO_JUGADORES = "jugadores@golstats.com"
PASSWORD_JUGADORES = "jugadores123"
PASSWORD_ADMIN = "admin123"

# Cambiar este número genera otro torneo distinto, pero igual de estable.
SEMILLA = 2026

EQUIPOS = [
    {
        "id": 1,
        "nombre": "Leones FC",
        "capitan": "Andrés Salazar",
        "correo_capitan": "capitan.leones@golstats.com",
        "jugadores": [
            ("Andrés", "Salazar"), ("Bryan", "Vera"), ("Carlos", "Loor"),
            ("Diego", "Moran"), ("Erick", "Zambrano"), ("Fabián", "Ortiz"),
            ("Gustavo", "Reyes"), ("Henry", "Quinteros"),
        ],
    },
    {
        "id": 2,
        "nombre": "Águilas SC",
        "capitan": "Fernando Ruiz",
        "correo_capitan": "capitan.aguilas@golstats.com",
        "jugadores": [
            ("Fernando", "Ruiz"), ("Gabriel", "Ponce"), ("Hugo", "Cedeño"),
            ("Iván", "Bravo"), ("Jorge", "Alvarado"), ("Kléber", "Mina"),
            ("Luis", "Andrade"), ("Manuel", "Vinueza"),
        ],
    },
    {
        "id": 3,
        "nombre": "Tiburones FC",
        "capitan": "Kevin Ortega",
        "correo_capitan": "capitan.tiburones@golstats.com",
        "jugadores": [
            ("Kevin", "Ortega"), ("Luis", "Naranjo"), ("Marco", "Villacis"),
            ("Nestor", "Chavez"), ("Oscar", "Pinto"), ("Pablo", "Guaman"),
            ("Ramiro", "Toapanta"), ("Santiago", "Lema"),
        ],
    },
    {
        "id": 4,
        "nombre": "Halcones United",
        "capitan": "Pedro Sanchez",
        "correo_capitan": "capitan.halcones@golstats.com",
        "jugadores": [
            ("Pedro", "Sanchez"), ("Raul", "Guerrero"), ("Sergio", "Tapia"),
            ("Tomas", "Aguirre"), ("Victor", "Cruz"), ("Walter", "Yepez"),
            ("Wilson", "Cadena"), ("Xavier", "Montalvo"),
        ],
    },
]

# Cuántos goles hace un equipo en un tiempo: casi siempre 0 o 1, a veces más.
GOLES_POR_TIEMPO = [0, 0, 1, 1, 1, 2, 2, 3]
TARJETAS_POR_TIEMPO = [0, 1, 1, 2]
PROBABILIDAD_ASISTENCIA = 0.60
PROBABILIDAD_ROJA = 0.15


class BaseDatosMemoria:
    """
    Hace de repositorio mientras no exista la base de datos real.

    Expone los mismos métodos de búsqueda que va a tener la capa de
    PostgreSQL, para que las rutas de Flask no se enteren del cambio.
    """

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


# ══════════════════════════════════════════════════════════════════
#  Construcción de los datos
# ══════════════════════════════════════════════════════════════════

def _crear_equipos(bd):
    """Arma los cuatro equipos con sus plantillas."""
    for ficha in EQUIPOS:
        equipo = Equipo(
            ficha["id"], ficha["nombre"], ficha["capitan"], ficha["correo_capitan"]
        )
        bd.equipos.append(equipo)

        for numero, (nombres, apellidos) in enumerate(ficha["jugadores"], start=1):
            jugador_id = len(bd.jugadores) + 1
            jugador = Jugador(
                id=jugador_id,
                # Dato de contacto, no una credencial: el jugador no
                # inicia sesion con esto.
                correo=f"{nombres.split()[0].lower()}.{apellidos.lower()}@golstats.com",
                equipo=equipo,
                nombres=nombres,
                apellidos=apellidos,
                cedula=str(1700000000 + jugador_id),
                numero_camiseta=numero,
            )
            equipo.agregar_jugador(jugador)
            bd.jugadores.append(jugador)


def _calendario(equipos):
    """Todos contra todos, ida y vuelta: 12 partidos entre 4 equipos."""
    enfrentamientos = []
    for local in equipos:
        for visitante in equipos:
            if local.id != visitante.id:
                enfrentamientos.append((local, visitante))
    return enfrentamientos


def _generar_eventos(partido, azar, minuto_desde, minuto_hasta):
    """Reparte goles y tarjetas dentro de un tiempo del partido."""
    for equipo in partido.equipos():
        plantel = partido.obtener_convocados(equipo)
        for _ in range(azar.choice(GOLES_POR_TIEMPO)):
            goleador = azar.choice(plantel)
            asistente = None
            if azar.random() < PROBABILIDAD_ASISTENCIA:
                companeros = [j for j in plantel if j.id != goleador.id]
                asistente = azar.choice(companeros)
            partido.registrar_gol(
                goleador, azar.randint(minuto_desde, minuto_hasta), asistente,
                validar_minuto=False,
            )

    for _ in range(azar.choice(TARJETAS_POR_TIEMPO)):
        equipo = azar.choice(partido.equipos())
        jugador = azar.choice(partido.obtener_convocados(equipo))
        tipo = Tarjeta.ROJA if azar.random() < PROBABILIDAD_ROJA else Tarjeta.AMARILLA
        partido.registrar_tarjeta(jugador, tipo, azar.randint(minuto_desde, minuto_hasta))


def _convocar_y_confirmar(partido):
    """Convoca a las dos plantillas completas y les hace el check-in."""
    convocados = (partido.equipo_local.obtener_jugadores()
                  + partido.equipo_visitante.obtener_jugadores())
    partido.convocar_varios(convocados)
    for jugador in convocados:
        partido.registrar_checkin(jugador, CheckIn.HUELLA)
    return convocados


def _jugar_partido(partido, azar):
    """Recorre el ciclo completo: convocatoria, check-in, dos tiempos y cierre."""
    _convocar_y_confirmar(partido)
    partido.iniciar_primer_tiempo()
    _generar_eventos(partido, azar, 1, 45)
    partido.terminar_primer_tiempo()

    for equipo in partido.equipos():
        partido.completar_pago(equipo)

    partido.iniciar_segundo_tiempo()
    _generar_eventos(partido, azar, 46, 90)
    partido.finalizar()
    return partido


def _jugar_walkover(partido, azar, equipo_moroso):
    """
    Igual que _jugar_partido, pero uno de los dos equipos nunca paga.

    Al llamar a iniciar_segundo_tiempo(), el propio Partido detecta la deuda
    y se declara walkover solo. Sirve para tener ese caso en pantalla.
    """
    _convocar_y_confirmar(partido)
    partido.iniciar_primer_tiempo()
    _generar_eventos(partido, azar, 1, 45)
    partido.terminar_primer_tiempo()

    for equipo in partido.equipos():
        if equipo.id != equipo_moroso.id:
            partido.completar_pago(equipo)

    partido.iniciar_segundo_tiempo()
    return partido


def crear_datos_prueba():
    """Arma el torneo completo: equipos, árbitros y los 12 partidos."""
    azar = random.Random(SEMILLA)
    bd = BaseDatosMemoria()

    # Las unicas dos cuentas del sistema: el administrador y la cuenta
    # compartida con la que entran todos los jugadores.
    bd.usuarios.append(
        Administrador(id=1000, correo="admin@golstats.com",
                      password_plano=PASSWORD_ADMIN)
    )
    bd.usuarios.append(
        CuentaJugadores(id=1001, correo=CORREO_JUGADORES,
                        password_plano=PASSWORD_JUGADORES)
    )

    bd.arbitros = [
        Arbitro(1, "Carlos Mendoza", "cmendoza@golstats.com", "0991112233"),
        Arbitro(2, "Luis Paredes", "lparedes@golstats.com", "0994445566"),
        Arbitro(3, "Jorge Espinoza", "jespinoza@golstats.com", "0997778899"),
    ]

    _crear_equipos(bd)

    hoy = datetime.now().replace(minute=0, second=0, microsecond=0)
    enfrentamientos = _calendario(bd.equipos)

    for numero, (local, visitante) in enumerate(enfrentamientos, start=1):
        # Los 10 primeros ya se jugaron, los 2 últimos están por venir.
        ya_se_jugo = numero <= 10
        if ya_se_jugo:
            fecha = hoy - timedelta(days=(11 - numero) * 3)
        else:
            fecha = hoy + timedelta(days=(numero - 10) * 4)

        partido = Partido(
            id=numero,
            equipo_local=local,
            equipo_visitante=visitante,
            fecha_hora=fecha,
            arbitro=bd.arbitros[numero % len(bd.arbitros)],
        )

        if numero == 7:
            # Un walkover, para que se vea esa pantalla en el sistema.
            _jugar_walkover(partido, azar, equipo_moroso=visitante)
        elif ya_se_jugo:
            _jugar_partido(partido, azar)
        elif numero == 11:
            # Programado y con el check-in a medio hacer, para probar que el
            # partido no arranca hasta que estén todos.
            partido.convocar_varios(
                local.obtener_jugadores() + visitante.obtener_jugadores()
            )
            for jugador in local.obtener_jugadores()[:5]:
                partido.registrar_checkin(jugador, CheckIn.HUELLA)
            partido.completar_pago(local)
        else:
            # Programado, sin nada hecho todavía.
            partido.convocar_varios(
                local.obtener_jugadores() + visitante.obtener_jugadores()
            )

        bd.partidos.append(partido)

    return bd


# Instancia única que importan las rutas de Flask.
BD = crear_datos_prueba()
