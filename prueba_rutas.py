"""
prueba_rutas.py
────────────────
Recorre todas las pantallas con el cliente de pruebas de Flask, sin
levantar el servidor. Sirve para ver rápido si alguna plantilla se rompe.

Ejecutar:  python prueba_rutas.py
"""

from app import app

RUTAS = [
    "/panel", "/equipos", "/equipos/1", "/jugadores/2",
    "/partidos", "/partidos/1", "/partidos/2", "/partidos/4",
    "/reportes", "/noexiste",
]


def revisar(cliente, etiqueta):
    print(f"\n--- {etiqueta} ---")
    for ruta in RUTAS:
        respuesta = cliente.get(ruta, follow_redirects=True)
        estado = "OK " if respuesta.status_code == 200 else "FALLA"
        print(f"  [{estado}] {respuesta.status_code} {ruta}")


with app.test_client() as cliente:
    print("=== Sin sesion (debe mandar al login) ===")
    r = cliente.get("/panel", follow_redirects=True)
    print(f"  login mostrado: {'Ingresar' in r.get_data(as_text=True)}")

    r = cliente.post("/", data={"correo": "admin@golstats.com", "password": "malo"},
                     follow_redirects=True)
    print(f"  password incorrecta rechazada: "
          f"{'incorrectos' in r.get_data(as_text=True)}")

    r = cliente.post("/", data={"correo": "admin@golstats.com", "password": "admin123"},
                     follow_redirects=True)
    print(f"  login admin: {r.status_code == 200}")
    revisar(cliente, "ADMIN")

    # Check-in por JSON sobre el partido 4 (programado)
    r = cliente.post("/partidos/4/checkin", json={"jugador_id": 4})
    print(f"\n  check-in JSON: {r.status_code} {r.get_json()}")

    r = cliente.post("/partidos/4/pago", data={"equipo_id": 4}, follow_redirects=True)
    print(f"  registrar pago: {r.status_code}")

    cliente.get("/logout")

with app.test_client() as cliente:
    cliente.post("/", data={"correo": "bryan.vera@golstats.com",
                            "password": "jugador123"}, follow_redirects=True)
    revisar(cliente, "JUGADOR")
    r = cliente.get("/jugadores/1", follow_redirects=True)
    print(f"  no puede ver otro jugador: "
          f"{'propias estadisticas' in r.get_data(as_text=True) or 'propias' in r.get_data(as_text=True)}")
    r = cliente.post("/partidos/4/pago", data={"equipo_id": 1}, follow_redirects=True)
    print(f"  no puede tocar pagos: {'administradores' in r.get_data(as_text=True)}")
