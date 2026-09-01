-- ═══════════════════════════════════════════════════════════════════
--  GolStats — 05_datos_iniciales.sql
--  Datos minimos para arrancar
-- ═══════════════════════════════════════════════════════════════════
--
--  Solo lo imprescindible: las dos cuentas del sistema, los cuatro
--  equipos con sus plantillas y los arbitros. NO se cargan partidos
--  jugados: esos los genera datos_prueba.py en memoria, y duplicarlos
--  aqui daria dos torneos distintos conviviendo.
--
--  Las contrasenas son hashes de werkzeug (mismo formato que genera
--  Usuario.__init__). Corresponden a admin123 y jugadores123, que son
--  las credenciales de desarrollo: cambiarlas antes de cualquier uso
--  real es obligatorio.
--
--  Reejecutable: ON CONFLICT DO NOTHING en todo.
-- ═══════════════════════════════════════════════════════════════════

BEGIN;

-- ── Las dos unicas cuentas del sistema ──────────────────────────────
INSERT INTO usuarios (correo, password_hash, rol) VALUES
    ('admin@golstats.com',
     'scrypt:32768:8:1$PLACEHOLDER$CAMBIAR_POR_HASH_REAL',
     'admin'),
    ('jugadores@golstats.com',
     'scrypt:32768:8:1$PLACEHOLDER$CAMBIAR_POR_HASH_REAL',
     'jugador')
ON CONFLICT (correo) DO NOTHING;

-- Los hashes de arriba son marcadores: werkzeug genera una sal distinta
-- cada vez, asi que no se pueden dejar fijos en un script versionado.
-- Para rellenarlos de verdad, desde la raiz del proyecto:
--
--   python -c "from werkzeug.security import generate_password_hash as h; print(h('admin123'))"
--
-- y luego:
--
--   UPDATE usuarios SET password_hash = '<lo que imprimio>'
--   WHERE correo = 'admin@golstats.com';


-- ── Equipos ─────────────────────────────────────────────────────────
INSERT INTO equipos (nombre, nombre_capitan, correo_capitan) VALUES
    ('Leones FC',       'Andres Salazar', 'capitan.leones@golstats.com'),
    ('Aguilas SC',      'Fernando Ruiz',  'capitan.aguilas@golstats.com'),
    ('Tiburones FC',    'Kevin Ortega',   'capitan.tiburones@golstats.com'),
    ('Halcones United', 'Pedro Sanchez',  'capitan.halcones@golstats.com')
ON CONFLICT (nombre) DO NOTHING;


-- ── Arbitros ────────────────────────────────────────────────────────
INSERT INTO arbitros (nombres, correo, telefono) VALUES
    ('Carlos Mendoza',  'cmendoza@golstats.com',  '0991112233'),
    ('Luis Paredes',    'lparedes@golstats.com',  '0994445566'),
    ('Jorge Espinoza',  'jespinoza@golstats.com', '0997778899')
ON CONFLICT DO NOTHING;


-- ── Plantillas ──────────────────────────────────────────────────────
--
--  Se insertan resolviendo el equipo por nombre en vez de por id fijo:
--  los SERIAL pueden no empezar en 1 si el script se reejecuta.
--  La cedula sigue el mismo patron que datos_prueba.py (1700000000 + n).

INSERT INTO jugadores (equipo_id, nombres, apellidos, cedula, numero_camiseta, correo)
SELECT e.id, d.nombres, d.apellidos, d.cedula, d.dorsal, d.correo
FROM (VALUES
    -- Leones FC
    ('Leones FC', 'Andres',  'Salazar',   '1700000001', 1, 'andres.salazar@golstats.com'),
    ('Leones FC', 'Bryan',   'Vera',      '1700000002', 2, 'bryan.vera@golstats.com'),
    ('Leones FC', 'Carlos',  'Loor',      '1700000003', 3, 'carlos.loor@golstats.com'),
    ('Leones FC', 'Diego',   'Moran',     '1700000004', 4, 'diego.moran@golstats.com'),
    ('Leones FC', 'Erick',   'Zambrano',  '1700000005', 5, 'erick.zambrano@golstats.com'),
    ('Leones FC', 'Fabian',  'Ortiz',     '1700000006', 6, 'fabian.ortiz@golstats.com'),
    ('Leones FC', 'Gustavo', 'Reyes',     '1700000007', 7, 'gustavo.reyes@golstats.com'),
    ('Leones FC', 'Henry',   'Quinteros', '1700000008', 8, 'henry.quinteros@golstats.com'),
    -- Aguilas SC
    ('Aguilas SC', 'Fernando', 'Ruiz',    '1700000009',  1, 'fernando.ruiz@golstats.com'),
    ('Aguilas SC', 'Gabriel',  'Ponce',   '1700000010',  2, 'gabriel.ponce@golstats.com'),
    ('Aguilas SC', 'Hugo',     'Cedeno',  '1700000011',  3, 'hugo.cedeno@golstats.com'),
    ('Aguilas SC', 'Ivan',     'Bravo',   '1700000012',  4, 'ivan.bravo@golstats.com'),
    ('Aguilas SC', 'Jorge',    'Alvarado','1700000013',  5, 'jorge.alvarado@golstats.com'),
    ('Aguilas SC', 'Kleber',   'Mina',    '1700000014',  6, 'kleber.mina@golstats.com'),
    ('Aguilas SC', 'Luis',     'Andrade', '1700000015',  7, 'luis.andrade@golstats.com'),
    ('Aguilas SC', 'Manuel',   'Vinueza', '1700000016',  8, 'manuel.vinueza@golstats.com'),
    -- Tiburones FC
    ('Tiburones FC', 'Kevin',    'Ortega',   '1700000017', 1, 'kevin.ortega@golstats.com'),
    ('Tiburones FC', 'Luis',     'Naranjo',  '1700000018', 2, 'luis.naranjo@golstats.com'),
    ('Tiburones FC', 'Marco',    'Villacis', '1700000019', 3, 'marco.villacis@golstats.com'),
    ('Tiburones FC', 'Nestor',   'Chavez',   '1700000020', 4, 'nestor.chavez@golstats.com'),
    ('Tiburones FC', 'Oscar',    'Pinto',    '1700000021', 5, 'oscar.pinto@golstats.com'),
    ('Tiburones FC', 'Pablo',    'Guaman',   '1700000022', 6, 'pablo.guaman@golstats.com'),
    ('Tiburones FC', 'Ramiro',   'Toapanta', '1700000023', 7, 'ramiro.toapanta@golstats.com'),
    ('Tiburones FC', 'Santiago', 'Lema',     '1700000024', 8, 'santiago.lema@golstats.com'),
    -- Halcones United
    ('Halcones United', 'Pedro',  'Sanchez',   '1700000025', 1, 'pedro.sanchez@golstats.com'),
    ('Halcones United', 'Raul',   'Guerrero',  '1700000026', 2, 'raul.guerrero@golstats.com'),
    ('Halcones United', 'Sergio', 'Tapia',     '1700000027', 3, 'sergio.tapia@golstats.com'),
    ('Halcones United', 'Tomas',  'Aguirre',   '1700000028', 4, 'tomas.aguirre@golstats.com'),
    ('Halcones United', 'Victor', 'Cruz',      '1700000029', 5, 'victor.cruz@golstats.com'),
    ('Halcones United', 'Walter', 'Yepez',     '1700000030', 6, 'walter.yepez@golstats.com'),
    ('Halcones United', 'Wilson', 'Cadena',    '1700000031', 7, 'wilson.cadena@golstats.com'),
    ('Halcones United', 'Xavier', 'Montalvo',  '1700000032', 8, 'xavier.montalvo@golstats.com')
) AS d(equipo, nombres, apellidos, cedula, dorsal, correo)
JOIN equipos e ON e.nombre = d.equipo
ON CONFLICT (cedula) DO NOTHING;

COMMIT;


-- ═══════════════════════════════════════════════════════════════════
--  Comprobacion rapida tras la carga
-- ═══════════════════════════════════════════════════════════════════
--
--  SELECT 'usuarios' AS tabla, COUNT(*) FROM usuarios
--  UNION ALL SELECT 'equipos',   COUNT(*) FROM equipos
--  UNION ALL SELECT 'jugadores', COUNT(*) FROM jugadores
--  UNION ALL SELECT 'arbitros',  COUNT(*) FROM arbitros;
--
--  Esperado: 2 usuarios, 4 equipos, 32 jugadores, 3 arbitros.
