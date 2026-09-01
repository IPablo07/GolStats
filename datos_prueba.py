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

# Escenario del calendario. Con 4 equipos salen 12 partidos y estos numeros
# dan lo que interesa ensenar: 10 jugados, uno resuelto por walkover y uno
# con el check-in a medias. Si el torneo tiene menos equipos se recortan
# solos, para no quedarse sin ningun partido programado que abrir en la
# vocalia (ver _escenario_calendario).
PARTIDOS_JUGADOS = 10
PARTIDO_WALKOVER = 7
PARTIDO_CHECKIN_PARCIAL = 11

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


# ── Gestión de Entidades (Alta y Baja) ────────────────────────
    
    def agregar_jugador(self, equipo, nombres, apellidos, cedula, numero_camiseta, correo):
        if not nombres or not apellidos or not cedula:
            raise ValueError("Nombres, apellidos y cédula son obligatorios.")
            
        nuevo_id = max([j.id for j in self.jugadores], default=0) + 1
        jugador = Jugador(
            id=nuevo_id,
            correo=correo,
            equipo=equipo,
            nombres=nombres,
            apellidos=apellidos,
            cedula=cedula,
            numero_camiseta=int(numero_camiseta)
        )
        equipo.agregar_jugador(jugador)  # Lanza error si el número se repite
        self.jugadores.append(jugador)
        return jugador

    def eliminar_jugador(self, jugador_id):
        jugador = self.buscar_jugador(jugador_id)
        if not jugador:
            raise ValueError("Jugador no encontrado.")

        # Regla: No se puede borrar si tiene goles o tarjetas en partidos cerrados
        for partido in self.partidos:
            if partido.esta_cerrado():
                for evento in partido.obtener_eventos():
                    if evento.jugador.id == jugador.id:
                        raise ValueError(f"No se puede eliminar: tiene eventos registrados en el partido #{partido.id} que ya finalizó.")
                    if hasattr(evento, 'jugador_asistencia') and evento.jugador_asistencia and evento.jugador_asistencia.id == jugador.id:
                        raise ValueError(f"No se puede eliminar: tiene asistencias en el partido #{partido.id} que ya finalizó.")

        if jugador.equipo:
            jugador.equipo.quitar_jugador(jugador)
        self.jugadores.remove(jugador)

    def agregar_equipo(self, nombre, nombre_capitan, correo_capitan):
        if not nombre or not nombre_capitan:
            raise ValueError("El nombre del equipo y del capitán son obligatorios.")
            
        nuevo_id = max([e.id for e in self.equipos], default=0) + 1
        equipo = Equipo(nuevo_id, nombre, nombre_capitan, correo_capitan)
        self.equipos.append(equipo)
        return equipo

    def eliminar_equipo(self, equipo_id):
        equipo = self.buscar_equipo(equipo_id)
        if not equipo:
            raise ValueError("Equipo no encontrado.")

        # Regla: No borrar si tiene partidos asociados
        for partido in self.partidos:
            if equipo.id in (partido.equipo_local.id, partido.equipo_visitante.id):
                raise ValueError(f"No se puede eliminar: el equipo tiene partidos (ej. Partido #{partido.id}).")

        # Regla: Impedir borrado si aún tiene jugadores inscritos (más seguro)
        if equipo.cantidad_jugadores() > 0:
            raise ValueError("No se puede eliminar el equipo porque aún tiene jugadores en su plantilla. Elimínelos primero.")

        self.equipos.remove(equipo)

    def agregar_arbitro(self, nombres, correo="", telefono=""):
        if not nombres:
            raise ValueError("El nombre del árbitro es obligatorio.")
            
        nuevo_id = max([a.id for a in self.arbitros], default=0) + 1
        arbitro = Arbitro(nuevo_id, nombres, correo, telefono)
        self.arbitros.append(arbitro)
        return arbitro

    def eliminar_arbitro(self, arbitro_id):
        arbitro = next((a for a in self.arbitros if a.id == arbitro_id), None)
        if not arbitro:
            raise ValueError("Árbitro no encontrado.")

        # Regla: No borrar si está asignado a partidos
        for partido in self.partidos:
            if partido.arbitro and partido.arbitro.id == arbitro.id:
                raise ValueError("No se puede eliminar: el árbitro está asignado a uno o más partidos.")

        self.arbitros.remove(arbitro)

    def crear_partido(self, equipo_local, equipo_visitante, fecha_hora, arbitro=None):
        """
        Programa un partido nuevo.

        El propio Partido ya rechaza que un equipo juegue contra sí mismo,
        así que esa regla no se repite aquí. Lo que sí se valida es lo que
        el modelo no puede saber: que los equipos existan, que la fecha
        venga completa y que no sea pasada.
        """
        if equipo_local is None or equipo_visitante is None:
            raise ValueError("Seleccione los dos equipos del partido.")
        if fecha_hora is None:
            raise ValueError("Indique la fecha y la hora del partido.")
        if fecha_hora < datetime.now():
            raise ValueError("No se puede programar un partido en una fecha pasada.")

        # max()+1 y no len()+1: con partidos cancelados o borrados, len()
        # se repite y dos partidos acabarian con el mismo id.
        nuevo_id = max([p.id for p in self.partidos], default=0) + 1
        partido = Partido(
            id=nuevo_id,
            equipo_local=equipo_local,
            equipo_visitante=equipo_visitante,
            fecha_hora=fecha_hora,
            arbitro=arbitro,
        )
        # Se convoca a las dos plantillas completas, igual que hace el
        # calendario de prueba: sin convocados el partido no puede iniciar.
        partido.convocar_varios(
            equipo_local.obtener_jugadores() + equipo_visitante.obtener_jugadores()
        )
        self.partidos.append(partido)
        return partido

    def cancelar_partido(self, partido_id, motivo=None):
        """Marca el partido como cancelado. No lo borra: ver Partido.cancelar()."""
        partido = self.buscar_partido(partido_id)
        if partido is None:
            raise ValueError("Partido no encontrado.")
        partido.cancelar(motivo)
        return partido


# ══════════════════════════════════════════════════════════════════
#  Carga desde PostgreSQL
# ══════════════════════════════════════════════════════════════════
#
#  Si las tablas del esquema (database/) existen y tienen filas, el torneo
#  se arma con ESOS datos en vez de con la lista EQUIPOS de arriba. Asi se
#  puede insertar por SQL o por pgAdmin y verlo en la web al reiniciar.
#
#  Es una carga de solo lectura, y al arrancar: lo que se cree despues
#  desde la pantalla de Gestion sigue viviendo solo en memoria. Conectar
#  tambien la escritura es el paso siguiente.


def _conexion_postgres():
    """
    Conexion directa con psycopg2, sin pasar por SQLAlchemy.

    Este modulo se importa en app.py ANTES de que exista la aplicacion
    Flask —`db.init_app(app)` viene despues—, asi que aqui no hay contexto
    de aplicacion y `db.session` no se puede usar. psycopg2 ya es
    dependencia del proyecto y no necesita contexto.
    """
    import psycopg2
    from config import Config
    return psycopg2.connect(Config.DATABASE_URL, connect_timeout=5)


def _cargar_torneo_desde_postgres(bd):
    """
    Llena `bd` con los equipos, jugadores y arbitros de PostgreSQL.

    Devuelve True si cargo algo util, y False si no habia base, no estaban
    las tablas o estaban vacias — en cuyo caso el llamador se queda con los
    datos de ejemplo. Nunca lanza: que la base no responda no puede impedir
    que la aplicacion arranque.

    Las cuentas de usuario NO se leen de la base a proposito:
    05_datos_iniciales.sql guarda un hash de marcador, no uno real, y
    cargarlo dejaria a todo el mundo sin poder entrar. Las dos cuentas se
    siguen creando en codigo.
    """
    try:
        conn = _conexion_postgres()
    except Exception:
        return False

    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT id, nombre, nombre_capitan, correo_capitan"
            " FROM equipos WHERE activo ORDER BY id"
        )
        filas_equipos = cur.fetchall()
        if not filas_equipos:
            return False

        por_id = {}
        for id_, nombre, capitan, correo_capitan in filas_equipos:
            equipo = Equipo(id_, nombre, capitan, correo_capitan)
            por_id[id_] = equipo
            bd.equipos.append(equipo)

        cur.execute(
            "SELECT id, equipo_id, nombres, apellidos, cedula,"
            " numero_camiseta, correo"
            " FROM jugadores WHERE activo ORDER BY equipo_id, numero_camiseta"
        )
        for id_, equipo_id, nombres, apellidos, cedula, dorsal, correo in cur.fetchall():
            equipo = por_id.get(equipo_id)
            if equipo is None:
                continue
            jugador = Jugador(
                id=id_, correo=correo, equipo=equipo, nombres=nombres,
                apellidos=apellidos, cedula=cedula, numero_camiseta=dorsal,
            )
            equipo.agregar_jugador(jugador)
            bd.jugadores.append(jugador)

        cur.execute(
            "SELECT id, nombres, correo, telefono"
            " FROM arbitros WHERE activo ORDER BY id"
        )
        bd.arbitros = [Arbitro(*fila) for fila in cur.fetchall()]

        # Un torneo sin jugadores no sirve para nada: mejor caer a los
        # datos de ejemplo que arrancar con equipos vacios.
        return len(bd.jugadores) > 0
    except Exception:
        return False
    finally:
        conn.close()


def _escenario_calendario(total_partidos):
    """
    Cuantos partidos se dan por jugados y cuales son los casos especiales.

    Con los 4 equipos de ejemplo salen 12 partidos y devuelve exactamente
    lo de siempre (10 jugados, el 7 walkover, el 11 a medias). Si el torneo
    que viene de la base tiene menos equipos, se recorta: siempre quedan al
    menos dos partidos por jugar, porque sin ellos no habria nada que abrir
    en la vocalia ni forma de ensenar el cronometro.
    """
    jugados = min(PARTIDOS_JUGADOS, max(0, total_partidos - 2))
    walkover = PARTIDO_WALKOVER if PARTIDO_WALKOVER <= jugados else None
    parcial = (PARTIDO_CHECKIN_PARCIAL
               if PARTIDO_CHECKIN_PARCIAL <= total_partidos
               else (jugados + 1 if total_partidos > jugados else None))
    return jugados, walkover, parcial


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
    """
    Arma el torneo completo: equipos, arbitros y su calendario.

    Los equipos, jugadores y arbitros salen de PostgreSQL si las tablas
    del esquema estan creadas y con datos; si no, de la lista EQUIPOS de
    este archivo. Los partidos se simulan igual en los dos casos: la base
    guarda el plantel, no los resultados.
    """
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

    desde_base = _cargar_torneo_desde_postgres(bd)
    if desde_base:
        print(f"DEBUG: torneo cargado desde PostgreSQL "
              f"({len(bd.equipos)} equipos, {len(bd.jugadores)} jugadores)")
    else:
        print("DEBUG: torneo desde los datos de ejemplo (datos_prueba.EQUIPOS)")
        _crear_equipos(bd)

    if not bd.arbitros:
        bd.arbitros = [
            Arbitro(1, "Carlos Mendoza", "cmendoza@golstats.com", "0991112233"),
            Arbitro(2, "Luis Paredes", "lparedes@golstats.com", "0994445566"),
            Arbitro(3, "Jorge Espinoza", "jespinoza@golstats.com", "0997778899"),
        ]

    hoy = datetime.now().replace(minute=0, second=0, microsecond=0)
    enfrentamientos = _calendario(bd.equipos)
    jugados, n_walkover, n_parcial = _escenario_calendario(len(enfrentamientos))

    for numero, (local, visitante) in enumerate(enfrentamientos, start=1):
        # Los primeros ya se jugaron, los ultimos estan por venir.
        ya_se_jugo = numero <= jugados
        if ya_se_jugo:
            fecha = hoy - timedelta(days=(jugados + 1 - numero) * 3)
        else:
            fecha = hoy + timedelta(days=(numero - jugados) * 4)

        partido = Partido(
            id=numero,
            equipo_local=local,
            equipo_visitante=visitante,
            fecha_hora=fecha,
            arbitro=bd.arbitros[numero % len(bd.arbitros)] if bd.arbitros else None,
        )

        if numero == n_walkover:
            # Un walkover, para que se vea esa pantalla en el sistema.
            _jugar_walkover(partido, azar, equipo_moroso=visitante)
        elif ya_se_jugo:
            _jugar_partido(partido, azar)
        elif numero == n_parcial:
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
