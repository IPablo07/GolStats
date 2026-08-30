"""
servicios/estadisticas.py
──────────────────────────
Reportes del torneo calculados sobre los objetos en memoria.

Cada función de aquí es el equivalente de una vista de PostgreSQL, y
devuelve exactamente las mismas columnas, para que al conectar la base
de datos las plantillas HTML no cambien:

    tabla_posiciones()      → vw_tabla_posiciones
    goleadores()            → vw_goleadores
    asistencias()           → vw_asistencias
    tarjetas()              → vw_tarjetas
    estadisticas_jugador()  → vw_estadisticas_jugador
"""

from modelos.partido import Partido, Tarjeta

PUNTOS_VICTORIA = 3
PUNTOS_EMPATE = 1


def partidos_cerrados(partidos):
    """Solo cuentan los partidos ya terminados (finalizados o walkover)."""
    return [p for p in partidos if p.esta_cerrado()]


# ══════════════════════════════════════════════════════════════════
#  Reporte 1: tabla de posiciones
# ══════════════════════════════════════════════════════════════════

def tabla_posiciones(equipos, partidos):
    tabla = {
        e.id: {
            "equipo": e,
            "pj": 0, "pg": 0, "pe": 0, "pp": 0,
            "gf": 0, "gc": 0, "dg": 0, "puntos": 0,
        }
        for e in equipos
    }

    for partido in partidos_cerrados(partidos):
        local = tabla.get(partido.equipo_local.id)
        visita = tabla.get(partido.equipo_visitante.id)
        if local is None or visita is None:
            continue

        local["pj"] += 1
        visita["pj"] += 1
        local["gf"] += partido.goles_local
        local["gc"] += partido.goles_visitante
        visita["gf"] += partido.goles_visitante
        visita["gc"] += partido.goles_local

        ganador = partido.equipo_ganador
        if ganador is None:
            # Empate, o walkover sin ganador (ninguno pagó)
            if partido.estado == Partido.WALKOVER:
                local["pp"] += 1
                visita["pp"] += 1
            else:
                local["pe"] += 1
                visita["pe"] += 1
                local["puntos"] += PUNTOS_EMPATE
                visita["puntos"] += PUNTOS_EMPATE
        else:
            gana = local if ganador.id == partido.equipo_local.id else visita
            pierde = visita if gana is local else local
            gana["pg"] += 1
            gana["puntos"] += PUNTOS_VICTORIA
            pierde["pp"] += 1

    filas = list(tabla.values())
    for fila in filas:
        fila["dg"] = fila["gf"] - fila["gc"]

    filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"], f["equipo"].nombre))
    for posicion, fila in enumerate(filas, start=1):
        fila["posicion"] = posicion
    return filas


# ══════════════════════════════════════════════════════════════════
#  Reporte 2: goleadores, asistencias y tarjetas
# ══════════════════════════════════════════════════════════════════

def goleadores(partidos, limite=None):
    conteo = {}
    for partido in partidos_cerrados(partidos):
        for gol in partido.obtener_goles():
            fila = conteo.setdefault(
                gol.jugador.id,
                {"jugador": gol.jugador, "equipo": gol.equipo, "goles": 0},
            )
            fila["goles"] += 1

    filas = sorted(
        conteo.values(),
        key=lambda f: (-f["goles"], f["jugador"].nombre_completo()),
    )
    return filas[:limite] if limite else filas


def asistencias(partidos, limite=None):
    conteo = {}
    for partido in partidos_cerrados(partidos):
        for gol in partido.obtener_goles():
            asistente = gol.jugador_asistencia
            if asistente is None:
                continue
            fila = conteo.setdefault(
                asistente.id,
                {"jugador": asistente, "equipo": asistente.equipo, "asistencias": 0},
            )
            fila["asistencias"] += 1

    filas = sorted(
        conteo.values(),
        key=lambda f: (-f["asistencias"], f["jugador"].nombre_completo()),
    )
    return filas[:limite] if limite else filas


def tarjetas(partidos, limite=None):
    conteo = {}
    for partido in partidos_cerrados(partidos):
        for tarjeta in partido.obtener_tarjetas():
            fila = conteo.setdefault(
                tarjeta.jugador.id,
                {
                    "jugador": tarjeta.jugador,
                    "equipo": tarjeta.equipo,
                    "amarillas": 0,
                    "rojas": 0,
                },
            )
            if tarjeta.tipo == Tarjeta.AMARILLA:
                fila["amarillas"] += 1
            else:
                fila["rojas"] += 1

    filas = sorted(
        conteo.values(),
        key=lambda f: (-f["rojas"], -f["amarillas"], f["jugador"].nombre_completo()),
    )
    return filas[:limite] if limite else filas


# ══════════════════════════════════════════════════════════════════
#  Estadísticas individuales (lo que ve cada jugador en su panel)
# ══════════════════════════════════════════════════════════════════

def estadisticas_jugador(jugador, partidos):
    resumen = {
        "jugador": jugador,
        "equipo": jugador.equipo,
        "partidos_jugados": 0,
        "goles": 0,
        "asistencias": 0,
        "amarillas": 0,
        "rojas": 0,
    }

    for partido in partidos_cerrados(partidos):
        if partido.tiene_checkin(jugador):
            resumen["partidos_jugados"] += 1
        for gol in partido.obtener_goles():
            if gol.jugador.id == jugador.id:
                resumen["goles"] += 1
            if gol.jugador_asistencia and gol.jugador_asistencia.id == jugador.id:
                resumen["asistencias"] += 1
        for tarjeta in partido.obtener_tarjetas():
            if tarjeta.jugador.id != jugador.id:
                continue
            if tarjeta.tipo == Tarjeta.AMARILLA:
                resumen["amarillas"] += 1
            else:
                resumen["rojas"] += 1

    return resumen


def estadisticas_equipo(equipo, partidos):
    """Resumen de un equipo, para la ficha de equipo del front."""
    fila = next(
        (f for f in tabla_posiciones([equipo], partidos) if f["equipo"].id == equipo.id),
        None,
    )
    jugadores = [estadisticas_jugador(j, partidos) for j in equipo.obtener_jugadores()]
    jugadores.sort(key=lambda r: (-r["goles"], r["jugador"].nombre_completo()))
    return {"resumen": fila, "jugadores": jugadores}
