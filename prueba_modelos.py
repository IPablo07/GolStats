"""
prueba_modelos.py
──────────────────
Prueba rápida de las clases del dominio, sin base de datos ni Flask.
Ejecutar:  python prueba_modelos.py
"""

from datos_prueba import BD, CORREO_JUGADORES, PASSWORD_JUGADORES
from modelos import Partido
from servicios import estadisticas


def separador(titulo):
    print()
    print("=" * 62)
    print(titulo)
    print("=" * 62)


separador("PARTIDOS")
for p in BD.partidos:
    print(f"  {p}")
    if p.motivo_walkover:
        print(f"     walkover: {p.motivo_walkover} -> gana {p.equipo_ganador.nombre}")

separador("TABLA DE POSICIONES")
print(f"  {'#':<3}{'EQUIPO':<20}{'PJ':>3}{'PG':>3}{'PE':>3}{'PP':>3}{'GF':>4}{'GC':>4}{'DG':>4}{'PTS':>5}")
for f in estadisticas.tabla_posiciones(BD.equipos, BD.partidos):
    print(f"  {f['posicion']:<3}{f['equipo'].nombre:<20}{f['pj']:>3}{f['pg']:>3}"
          f"{f['pe']:>3}{f['pp']:>3}{f['gf']:>4}{f['gc']:>4}{f['dg']:>4}{f['puntos']:>5}")

separador("GOLEADORES")
for f in estadisticas.goleadores(BD.partidos, limite=5):
    print(f"  {f['jugador'].nombre_completo():<25}{f['equipo'].nombre:<20}{f['goles']} gol(es)")

separador("ASISTENCIAS")
for f in estadisticas.asistencias(BD.partidos, limite=5):
    print(f"  {f['jugador'].nombre_completo():<25}{f['equipo'].nombre:<20}{f['asistencias']}")

separador("TARJETAS")
for f in estadisticas.tarjetas(BD.partidos):
    print(f"  {f['jugador'].nombre_completo():<25}{f['equipo'].nombre:<20}"
          f"A:{f['amarillas']}  R:{f['rojas']}")

separador("VALIDACIONES (deben fallar a proposito)")
p4 = BD.buscar_partido(4)
try:
    p4.iniciar_primer_tiempo()
except ValueError as e:
    print(f"  OK bloqueado -> {e}")

jugador = BD.jugadores[0]
try:
    p4.registrar_gol(jugador, 10)
except ValueError as e:
    print(f"  OK bloqueado -> {e}")

separador("LOGIN")
u = BD.buscar_usuario_por_correo("admin@golstats.com")
print(f"  admin password correcta: {u.verificar_password('admin123')}")
print(f"  admin password incorrecta: {u.verificar_password('otra')}")
print(f"  panel: {u.panel_info()['mensaje']}")

# Ya no hay una cuenta por jugador: todos comparten esta.
c = BD.buscar_usuario_por_correo(CORREO_JUGADORES)
print(f"  cuenta de jugadores: {c.correo} (rol {c.rol})")
print(f"  password correcta: {c.verificar_password(PASSWORD_JUGADORES)}")
print(f"  panel: {c.panel_info()['mensaje']}")

# El jugador ya no es un usuario, es solo sujeto de estadisticas.
j = BD.jugadores[1]
print(f"  ya no inicia sesion: {BD.buscar_usuario_por_correo(j.correo) is None}")
print(f"  jugador: {j.nombre_completo()} - {j.equipo.nombre} #{j.numero_camiseta}")
print(f"  stats: {estadisticas.estadisticas_jugador(j, BD.partidos)}")

separador("CRONOMETRO")
pc = BD.buscar_partido(12)
print(f"  antes de iniciar: {pc.minuto_actual()}' - {pc.fase_reloj()}")
for jugador in pc.obtener_convocados():
    pc.registrar_checkin(jugador)
pc.iniciar_primer_tiempo()
print(f"  tras iniciar:     {pc.minuto_actual()}' - {pc.fase_reloj()} "
      f"(corriendo: {pc.reloj_corriendo()})")
pc.terminar_primer_tiempo()
print(f"  en el descanso:   {pc.minuto_actual()}' - {pc.fase_reloj()} "
      f"(corriendo: {pc.reloj_corriendo()})")
for equipo in pc.equipos():
    pc.completar_pago(equipo)
pc.iniciar_segundo_tiempo()
print(f"  segundo tiempo:   {pc.minuto_actual()}' - {pc.fase_reloj()} "
      f"(corriendo: {pc.reloj_corriendo()})")
