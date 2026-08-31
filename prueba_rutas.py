"""
prueba_rutas.py
────────────────
Recorre todas las pantallas con el cliente de pruebas de Flask, sin
levantar el servidor. Sirve para ver rápido si alguna plantilla se rompió.

Los casos se derivan de los datos (busca un partido finalizado, uno
programado, un jugador sin check-in), así que no hay que tocar este
archivo cada vez que cambie datos_prueba.py.

Ejecutar:  python prueba_rutas.py
"""

from app import app
from datos_prueba import BD, CORREO_JUGADORES, PASSWORD_JUGADORES
from modelos import Partido

# ── Casos sacados de los datos, no escritos a mano ────────────────
FINALIZADO = BD.partidos_por_estado(Partido.FINALIZADO)[0]
WALKOVER = BD.partidos_por_estado(Partido.WALKOVER)[0]
PROGRAMADO = BD.proximos_partidos()[0]
SIN_CHECKIN = PROGRAMADO.jugadores_sin_checkin()[0]
SIN_PAGAR = PROGRAMADO.equipos_sin_pagar()[0]

PANTALLAS = [
    ("/panel", 200),
    ("/equipos", 200),
    (f"/equipos/{BD.equipos[0].id}", 200),
    (f"/jugadores/{BD.jugadores[1].id}", 200),
    ("/partidos", 200),
    (f"/partidos/{FINALIZADO.id}", 200),
    (f"/partidos/{WALKOVER.id}", 200),
    (f"/partidos/{PROGRAMADO.id}", 200),
    ("/reportes", 200),
    ("/noexiste", 404),          # debe mostrar la pantalla de error, no reventar
]

fallos = 0


def revisar(cliente, etiqueta):
    global fallos
    print(f"\n--- {etiqueta} ---")
    for ruta, esperado in PANTALLAS:
        respuesta = cliente.get(ruta, follow_redirects=True)
        ok = respuesta.status_code == esperado
        if not ok:
            fallos += 1
        print(f"  [{'OK ' if ok else 'FALLA'}] {respuesta.status_code} "
              f"(esperado {esperado}) {ruta}")


def comprobar(descripcion, condicion):
    global fallos
    if not condicion:
        fallos += 1
    print(f"  [{'OK ' if condicion else 'FALLA'}] {descripcion}")


print(f"Datos: {len(BD.equipos)} equipos, {len(BD.jugadores)} jugadores, "
      f"{len(BD.partidos)} partidos")

with app.test_client() as cliente:
    print("\n=== SIN SESION ===")
    r = cliente.get("/panel", follow_redirects=True)
    comprobar("sin sesion manda al login", "Ingresar" in r.get_data(as_text=True))

    r = cliente.post("/", data={"correo": "admin@golstats.com", "password": "malo"},
                     follow_redirects=True)
    comprobar("password incorrecta rechazada",
              "incorrectos" in r.get_data(as_text=True))

    r = cliente.post("/", data={"correo": "admin@golstats.com",
                                "password": "admin123"}, follow_redirects=True)
    comprobar("login del administrador", r.status_code == 200)
    revisar(cliente, "PANTALLAS COMO ADMINISTRADOR")

    print("\n=== ACCIONES DEL ADMINISTRADOR ===")
    r = cliente.post(f"/partidos/{PROGRAMADO.id}/checkin",
                     json={"jugador_id": SIN_CHECKIN.id})
    datos = r.get_json()
    comprobar(f"check-in de {SIN_CHECKIN.nombre_completo()}", datos.get("ok") is True)
    comprobar("devuelve el carnet del jugador", "carnet" in datos)

    r = cliente.post(f"/partidos/{PROGRAMADO.id}/checkin",
                     json={"jugador_id": SIN_CHECKIN.id})
    comprobar("rechaza el check-in repetido", r.get_json().get("ok") is False)

    r = cliente.post(f"/partidos/{PROGRAMADO.id}/estado", data={"accion": "iniciar"},
                     follow_redirects=True)
    comprobar("no deja iniciar con check-ins pendientes",
              "faltan" in r.get_data(as_text=True))

    r = cliente.post(f"/partidos/{PROGRAMADO.id}/pago",
                     data={"equipo_id": SIN_PAGAR.id}, follow_redirects=True)
    comprobar("registra el pago de la vocalia",
              "Pago registrado" in r.get_data(as_text=True))

    cliente.get("/logout")

with app.test_client() as cliente:
    # Una sola cuenta compartida: ya no se entra con el correo de un jugador.
    r = cliente.post("/", data={"correo": BD.jugadores[1].correo,
                                "password": PASSWORD_JUGADORES},
                     follow_redirects=True)
    comprobar("el correo de un jugador ya no sirve para entrar",
              "incorrectos" in r.get_data(as_text=True))

    r = cliente.post("/", data={"correo": CORREO_JUGADORES,
                                "password": PASSWORD_JUGADORES},
                     follow_redirects=True)
    comprobar("login con la cuenta unica de jugadores", r.status_code == 200)
    revisar(cliente, "PANTALLAS COMO JUGADOR")

    print()
    print("=== LO QUE VE LA CUENTA DE JUGADORES ===")
    cuerpo = cliente.get("/panel", follow_redirects=True).get_data(as_text=True)
    comprobar("el inicio trae la tabla de partidos", "Partidos" in cuerpo)
    comprobar("el inicio trae la tabla de posiciones",
              "Tabla de posiciones" in cuerpo)

    # Desde Equipos se llega a la ficha de cualquier jugador, sea del
    # equipo que sea: antes solo se dejaba ver la propia.
    for jugador in (BD.equipos[0].obtener_jugadores()[0],
                    BD.equipos[-1].obtener_jugadores()[-1]):
        r = cliente.get(f"/jugadores/{jugador.id}", follow_redirects=True)
        comprobar(f"ve las estadisticas de {jugador.nombre_completo()} "
                  f"({jugador.equipo.nombre})",
                  r.status_code == 200
                  and jugador.nombre_completo() in r.get_data(as_text=True))

    print()
    print("=== LIMITES DE LA CUENTA DE JUGADORES ===")
    r = cliente.post(f"/partidos/{PROGRAMADO.id}/pago",
                     data={"equipo_id": SIN_PAGAR.id}, follow_redirects=True)
    comprobar("no puede registrar pagos",
              "administradores" in r.get_data(as_text=True))

    r = cliente.get(f"/partidos/{PROGRAMADO.id}/cronometro",
                    follow_redirects=True)
    comprobar("no puede leer el cronometro del admin",
              "administradores" in r.get_data(as_text=True))

print(f"\n{'=' * 50}")
print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
