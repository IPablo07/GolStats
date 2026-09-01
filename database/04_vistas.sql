-- ═══════════════════════════════════════════════════════════════════
--  GolStats — 04_vistas.sql
--  Las cinco vistas que consume servicios/estadisticas.py
-- ═══════════════════════════════════════════════════════════════════
--
--  El docstring de servicios/estadisticas.py ya declara este mapeo:
--
--      tabla_posiciones()      → vw_tabla_posiciones
--      goleadores()            → vw_goleadores
--      asistencias()           → vw_asistencias
--      tarjetas()              → vw_tarjetas
--      estadisticas_jugador()  → vw_estadisticas_jugador
--
--  Las columnas y el orden replican lo que hoy devuelve cada funcion, de
--  modo que al conectar la base las plantillas no cambian.
--
--  REGLA COMUN: solo cuentan los partidos DISPUTADOS. Un cancelado esta
--  cerrado pero no se jugo; si entrara aqui le regalaria un empate a 0 a
--  los dos equipos. Es el mismo criterio que en Python separa
--  esta_cerrado() de cuenta_para_estadisticas().
-- ═══════════════════════════════════════════════════════════════════

BEGIN;

DROP VIEW IF EXISTS vw_estadisticas_jugador CASCADE;
DROP VIEW IF EXISTS vw_tarjetas             CASCADE;
DROP VIEW IF EXISTS vw_asistencias          CASCADE;
DROP VIEW IF EXISTS vw_goleadores           CASCADE;
DROP VIEW IF EXISTS vw_tabla_posiciones     CASCADE;
DROP VIEW IF EXISTS vw_partidos_disputados  CASCADE;


-- ── Base comun: que partidos cuentan ────────────────────────────────
CREATE VIEW vw_partidos_disputados AS
SELECT * FROM partidos
WHERE estado IN ('finalizado', 'walkover');

COMMENT ON VIEW vw_partidos_disputados IS
    'Partidos que reparten puntos; deja fuera los cancelados';


-- ═══════════════════════════════════════════════════════════════════
--  1. vw_tabla_posiciones
-- ═══════════════════════════════════════════════════════════════════
--
--  Un partido aporta dos filas —una por equipo— y luego se agrupa. Es
--  mas legible que resolverlo con CASE cruzados sobre local/visitante.

CREATE VIEW vw_tabla_posiciones AS
WITH participaciones AS (
    -- El equipo local
    SELECT
        p.equipo_local_id AS equipo_id,
        p.goles_local     AS gf,
        p.goles_visitante AS gc,
        p.estado,
        p.equipo_ganador_id
    FROM vw_partidos_disputados p
    UNION ALL
    -- El visitante
    SELECT
        p.equipo_visitante_id,
        p.goles_visitante,
        p.goles_local,
        p.estado,
        p.equipo_ganador_id
    FROM vw_partidos_disputados p
),
resumen AS (
    SELECT
        e.id AS equipo_id,
        e.nombre AS equipo,
        COUNT(pa.equipo_id)::INTEGER AS pj,
        COALESCE(SUM(pa.gf), 0)::INTEGER AS gf,
        COALESCE(SUM(pa.gc), 0)::INTEGER AS gc,
        -- Ganados
        COUNT(*) FILTER (
            WHERE pa.equipo_ganador_id = e.id
        )::INTEGER AS pg,
        -- Empatados: sin ganador y que NO sea walkover. Un walkover sin
        -- ganador (nadie pago) no es empate: pierden los dos.
        COUNT(*) FILTER (
            WHERE pa.equipo_ganador_id IS NULL AND pa.estado <> 'walkover'
        )::INTEGER AS pe,
        -- Perdidos: hubo otro ganador, o walkover sin ganador.
        COUNT(*) FILTER (
            WHERE (pa.equipo_ganador_id IS NOT NULL AND pa.equipo_ganador_id <> e.id)
               OR (pa.equipo_ganador_id IS NULL AND pa.estado = 'walkover')
        )::INTEGER AS pp
    FROM equipos e
    LEFT JOIN participaciones pa ON pa.equipo_id = e.id
    GROUP BY e.id, e.nombre
)
SELECT
    ROW_NUMBER() OVER (
        ORDER BY (pg * 3 + pe) DESC, (gf - gc) DESC, gf DESC, equipo ASC
    )::INTEGER AS posicion,
    equipo_id,
    equipo,
    pj, pg, pe, pp, gf, gc,
    (gf - gc)::INTEGER      AS dg,
    (pg * 3 + pe)::INTEGER  AS puntos
FROM resumen
ORDER BY puntos DESC, dg DESC, gf DESC, equipo ASC;

COMMENT ON VIEW vw_tabla_posiciones IS
    '3 puntos por victoria, 1 por empate. Desempate: DG, luego GF, luego nombre';


-- ═══════════════════════════════════════════════════════════════════
--  2. vw_goleadores
-- ═══════════════════════════════════════════════════════════════════

CREATE VIEW vw_goleadores AS
SELECT
    j.id AS jugador_id,
    j.nombres || ' ' || j.apellidos AS jugador,
    e.id AS equipo_id,
    e.nombre AS equipo,
    COUNT(*)::INTEGER AS goles
FROM goles g
JOIN vw_partidos_disputados p ON p.id = g.partido_id
JOIN jugadores j ON j.id = g.jugador_id
JOIN equipos   e ON e.id = g.equipo_id
GROUP BY j.id, j.nombres, j.apellidos, e.id, e.nombre
ORDER BY goles DESC, jugador ASC;


-- ═══════════════════════════════════════════════════════════════════
--  3. vw_asistencias
-- ═══════════════════════════════════════════════════════════════════

CREATE VIEW vw_asistencias AS
SELECT
    j.id AS jugador_id,
    j.nombres || ' ' || j.apellidos AS jugador,
    e.id AS equipo_id,
    e.nombre AS equipo,
    COUNT(*)::INTEGER AS asistencias
FROM goles g
JOIN vw_partidos_disputados p ON p.id = g.partido_id
JOIN jugadores j ON j.id = g.jugador_asistencia_id
JOIN equipos   e ON e.id = j.equipo_id
WHERE g.jugador_asistencia_id IS NOT NULL
GROUP BY j.id, j.nombres, j.apellidos, e.id, e.nombre
ORDER BY asistencias DESC, jugador ASC;


-- ═══════════════════════════════════════════════════════════════════
--  4. vw_tarjetas
-- ═══════════════════════════════════════════════════════════════════

CREATE VIEW vw_tarjetas AS
SELECT
    j.id AS jugador_id,
    j.nombres || ' ' || j.apellidos AS jugador,
    e.id AS equipo_id,
    e.nombre AS equipo,
    COUNT(*) FILTER (WHERE t.tipo = 'amarilla')::INTEGER AS amarillas,
    COUNT(*) FILTER (WHERE t.tipo = 'roja')::INTEGER     AS rojas
FROM tarjetas t
JOIN vw_partidos_disputados p ON p.id = t.partido_id
JOIN jugadores j ON j.id = t.jugador_id
JOIN equipos   e ON e.id = t.equipo_id
GROUP BY j.id, j.nombres, j.apellidos, e.id, e.nombre
ORDER BY rojas DESC, amarillas DESC, jugador ASC;


-- ═══════════════════════════════════════════════════════════════════
--  5. vw_estadisticas_jugador — la ficha individual
-- ═══════════════════════════════════════════════════════════════════
--
--  Incluye a TODOS los jugadores, tambien a los que nunca jugaron: la
--  ficha de un jugador nuevo tiene que abrirse con ceros, no quedarse
--  vacia. De ahi los LEFT JOIN y los COALESCE.
--
--  "Partidos jugados" se cuenta por check-in, no por convocatoria: quien
--  no se presento no jugo.

CREATE VIEW vw_estadisticas_jugador AS
SELECT
    j.id AS jugador_id,
    j.nombres || ' ' || j.apellidos AS jugador,
    j.numero_camiseta,
    e.id AS equipo_id,
    e.nombre AS equipo,
    COALESCE(pj.total, 0)::INTEGER  AS partidos_jugados,
    COALESCE(gl.total, 0)::INTEGER  AS goles,
    COALESCE(asi.total, 0)::INTEGER AS asistencias,
    COALESCE(ta.amarillas, 0)::INTEGER AS amarillas,
    COALESCE(ta.rojas, 0)::INTEGER     AS rojas
FROM jugadores j
JOIN equipos e ON e.id = j.equipo_id
LEFT JOIN (
    SELECT c.jugador_id, COUNT(*) AS total
    FROM checkins c
    JOIN vw_partidos_disputados p ON p.id = c.partido_id
    GROUP BY c.jugador_id
) pj ON pj.jugador_id = j.id
LEFT JOIN (
    SELECT g.jugador_id, COUNT(*) AS total
    FROM goles g
    JOIN vw_partidos_disputados p ON p.id = g.partido_id
    GROUP BY g.jugador_id
) gl ON gl.jugador_id = j.id
LEFT JOIN (
    SELECT g.jugador_asistencia_id AS jugador_id, COUNT(*) AS total
    FROM goles g
    JOIN vw_partidos_disputados p ON p.id = g.partido_id
    WHERE g.jugador_asistencia_id IS NOT NULL
    GROUP BY g.jugador_asistencia_id
) asi ON asi.jugador_id = j.id
LEFT JOIN (
    SELECT t.jugador_id,
           COUNT(*) FILTER (WHERE t.tipo = 'amarilla') AS amarillas,
           COUNT(*) FILTER (WHERE t.tipo = 'roja')     AS rojas
    FROM tarjetas t
    JOIN vw_partidos_disputados p ON p.id = t.partido_id
    GROUP BY t.jugador_id
) ta ON ta.jugador_id = j.id
ORDER BY e.nombre, j.numero_camiseta;

COMMIT;
