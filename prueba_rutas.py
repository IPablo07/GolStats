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
from datos_prueba import BD
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
    jugador = BD.jugadores[1]
    cliente.post("/", data={"correo": jugador.correo, "password": "jugador123"},
                 follow_redirects=True)
    revisar(cliente, "PANTALLAS COMO JUGADOR")

    print("\n=== LIMITES DEL JUGADOR ===")
    otro = next(j for j in BD.jugadores if j.id != jugador.id)
    r = cliente.get(f"/jugadores/{otro.id}", follow_redirects=True)
    comprobar("no puede ver la ficha de otro jugador",
              "propias" in r.get_data(as_text=True))

    r = cliente.post(f"/partidos/{PROGRAMADO.id}/pago",
                     data={"equipo_id": SIN_PAGAR.id}, follow_redirects=True)
    comprobar("no puede registrar pagos",
              "administradores" in r.get_data(as_text=True))

print(f"\n{'=' * 50}")
print("TODO OK" if fallos == 0 else f"{fallos} FALLO(S)")
