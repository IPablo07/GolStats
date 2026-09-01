-- ═══════════════════════════════════════════════════════════════════
--  GolStats — 03_procedimientos.sql
--  Reglas de negocio que son una operacion completa, no una restriccion
-- ═══════════════════════════════════════════════════════════════════
--
--  Cuando una regla implica VARIOS pasos que tienen que ocurrir juntos o
--  no ocurrir —cobrar y sellar la fecha, iniciar el segundo tiempo o
--  declarar walkover— no basta con un CHECK ni con un trigger: hace falta
--  un procedimiento que lo haga todo dentro de una transaccion.
--
--  `sp_completar_pago_vocalia` ya estaba citado en modelos/pago.py mucho
--  antes de que existiera este archivo. Aqui por fin existe.
-- ═══════════════════════════════════════════════════════════════════

BEGIN;


-- ═══════════════════════════════════════════════════════════════════
--  sp_completar_pago_vocalia — cobrar la vocalia de un equipo
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION sp_completar_pago_vocalia(
    p_partido_id INTEGER,
    p_equipo_id  INTEGER,
    p_comprobante VARCHAR DEFAULT NULL
)
RETURNS pagos_vocalia AS $$
DECLARE
    v_pago pagos_vocalia;
BEGIN
    SELECT * INTO v_pago FROM pagos_vocalia
    WHERE partido_id = p_partido_id AND equipo_id = p_equipo_id
    FOR UPDATE;   -- bloquea la fila: dos cobros simultaneos no se pisan

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El equipo % no juega el partido %', p_equipo_id, p_partido_id;
    END IF;

    IF v_pago.estado = 'pagado' THEN
        RAISE EXCEPTION 'La vocalia de este equipo ya estaba pagada (%)',
            TO_CHAR(v_pago.fecha_pago, 'DD/MM/YYYY HH24:MI');
    END IF;

    UPDATE pagos_vocalia SET
        estado = 'pagado',
        fecha_pago = NOW(),
        comprobante_pdf = COALESCE(p_comprobante, comprobante_pdf)
    WHERE id = v_pago.id
    RETURNING * INTO v_pago;

    RETURN v_pago;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_completar_pago_vocalia IS
    'Cobra la vocalia de un equipo. Equivale a Partido.completar_pago()';


-- ═══════════════════════════════════════════════════════════════════
--  sp_iniciar_primer_tiempo — no arranca si falta algun check-in
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION sp_iniciar_primer_tiempo(p_partido_id INTEGER)
RETURNS VARCHAR AS $$
DECLARE
    v_estado VARCHAR(20);
    v_convocados INTEGER;
    v_faltantes INTEGER;
    v_nombres TEXT;
BEGIN
    SELECT estado INTO v_estado FROM partidos WHERE id = p_partido_id FOR UPDATE;

    IF v_estado IS NULL THEN
        RAISE EXCEPTION 'El partido % no existe', p_partido_id;
    END IF;
    IF v_estado <> 'programado' THEN
        RAISE EXCEPTION 'El partido no se puede iniciar porque esta en estado %', v_estado;
    END IF;

    SELECT COUNT(*) INTO v_convocados
    FROM convocatorias WHERE partido_id = p_partido_id;

    IF v_convocados = 0 THEN
        RAISE EXCEPTION 'No se puede iniciar un partido sin jugadores convocados';
    END IF;

    -- Quien esta convocado pero no se presento.
    SELECT COUNT(*), STRING_AGG(j.nombres || ' ' || j.apellidos, ', ')
    INTO v_faltantes, v_nombres
    FROM convocatorias c
    JOIN jugadores j ON j.id = c.jugador_id
    WHERE c.partido_id = p_partido_id
      AND NOT EXISTS (
          SELECT 1 FROM checkins ch
          WHERE ch.partido_id = c.partido_id AND ch.jugador_id = c.jugador_id
      );

    IF v_faltantes > 0 THEN
        RAISE EXCEPTION 'No se puede iniciar el partido: faltan % check-in(s) (%)',
            v_faltantes, v_nombres;
    END IF;

    -- El trigger de transicion se encarga de arrancar el cronometro.
    UPDATE partidos SET estado = 'primer_tiempo' WHERE id = p_partido_id;
    RETURN 'primer_tiempo';
END;
$$ LANGUAGE plpgsql;


-- ═══════════════════════════════════════════════════════════════════
--  sp_iniciar_segundo_tiempo — o walkover, si alguien no pago
-- ═══════════════════════════════════════════════════════════════════
--
--  La regla mas cara del reglamento y la que mas justifica ser un
--  procedimiento: decidir el walkover, fijar el ganador y estampar el 3-0
--  tienen que pasar juntos o no pasar.

CREATE OR REPLACE FUNCTION sp_iniciar_segundo_tiempo(p_partido_id INTEGER)
RETURNS VARCHAR AS $$
DECLARE
    v_estado VARCHAR(20);
    v_local INTEGER;
    v_visitante INTEGER;
    v_deudores INTEGER;
    v_deudor INTEGER;
    v_ganador INTEGER;
    v_nombre_deudor VARCHAR(100);
BEGIN
    SELECT estado, equipo_local_id, equipo_visitante_id
    INTO v_estado, v_local, v_visitante
    FROM partidos WHERE id = p_partido_id FOR UPDATE;

    IF v_estado <> 'medio_tiempo' THEN
        RAISE EXCEPTION 'El segundo tiempo solo puede iniciar desde el medio tiempo';
    END IF;

    SELECT COUNT(*), MIN(equipo_id) INTO v_deudores, v_deudor
    FROM pagos_vocalia
    WHERE partido_id = p_partido_id AND estado = 'pendiente';

    -- Nadie pago: walkover sin ganador y sin marcador de oficio.
    IF v_deudores = 2 THEN
        UPDATE partidos SET
            estado = 'walkover',
            equipo_ganador_id = NULL,
            motivo_walkover = 'Ningun equipo completo el pago de la vocalia'
        WHERE id = p_partido_id;
        RETURN 'walkover';
    END IF;

    -- Uno solo debe: gana el contrario 3-0.
    IF v_deudores = 1 THEN
        v_ganador := CASE WHEN v_deudor = v_local THEN v_visitante ELSE v_local END;
        SELECT nombre INTO v_nombre_deudor FROM equipos WHERE id = v_deudor;

        UPDATE partidos SET
            estado = 'walkover',
            equipo_ganador_id = v_ganador,
            motivo_walkover = 'El equipo ' || v_nombre_deudor
                              || ' no completo el pago de la vocalia',
            goles_local     = CASE WHEN v_ganador = v_local THEN 3 ELSE 0 END,
            goles_visitante = CASE WHEN v_ganador = v_visitante THEN 3 ELSE 0 END
        WHERE id = p_partido_id;
        RETURN 'walkover';
    END IF;

    UPDATE partidos SET estado = 'segundo_tiempo' WHERE id = p_partido_id;
    RETURN 'segundo_tiempo';
END;
$$ LANGUAGE plpgsql;


-- ═══════════════════════════════════════════════════════════════════
--  sp_finalizar_partido — el ganador sale del marcador
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION sp_finalizar_partido(p_partido_id INTEGER)
RETURNS VARCHAR AS $$
DECLARE
    v_estado VARCHAR(20);
    v_local INTEGER;
    v_visitante INTEGER;
    v_gl SMALLINT;
    v_gv SMALLINT;
BEGIN
    SELECT estado, equipo_local_id, equipo_visitante_id, goles_local, goles_visitante
    INTO v_estado, v_local, v_visitante, v_gl, v_gv
    FROM partidos WHERE id = p_partido_id FOR UPDATE;

    IF v_estado <> 'segundo_tiempo' THEN
        RAISE EXCEPTION 'No se puede finalizar un partido en estado %', v_estado;
    END IF;

    UPDATE partidos SET
        estado = 'finalizado',
        equipo_ganador_id = CASE
            WHEN v_gl > v_gv THEN v_local
            WHEN v_gv > v_gl THEN v_visitante
            ELSE NULL                      -- empate
        END
    WHERE id = p_partido_id;

    RETURN 'finalizado';
END;
$$ LANGUAGE plpgsql;


-- ═══════════════════════════════════════════════════════════════════
--  sp_cancelar_partido — marca, no borra
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION sp_cancelar_partido(
    p_partido_id INTEGER,
    p_motivo     VARCHAR DEFAULT NULL
)
RETURNS VARCHAR AS $$
DECLARE
    v_estado VARCHAR(20);
BEGIN
    SELECT estado INTO v_estado FROM partidos WHERE id = p_partido_id FOR UPDATE;

    IF v_estado = 'cancelado' THEN
        RAISE EXCEPTION 'El partido ya estaba cancelado';
    END IF;
    IF v_estado <> 'programado' THEN
        RAISE EXCEPTION
            'Solo se puede cancelar un partido programado. Este esta en estado %', v_estado;
    END IF;

    -- No se borra: el historial queda, y las vistas ya lo dejan fuera de
    -- la tabla de posiciones por su estado.
    UPDATE partidos SET
        estado = 'cancelado',
        motivo_cancelacion = COALESCE(NULLIF(TRIM(p_motivo), ''),
                                      'Cancelado por el administrador')
    WHERE id = p_partido_id;

    RETURN 'cancelado';
END;
$$ LANGUAGE plpgsql;


-- ═══════════════════════════════════════════════════════════════════
--  sp_registrar_gol — el gol con todas sus validaciones
-- ═══════════════════════════════════════════════════════════════════
--
--  El trigger fn_validar_gol ya protege la tabla, pero este procedimiento
--  es el camino que deberia usar la aplicacion: devuelve el gol creado y
--  el marcador resultante en una sola llamada, sin tener que releer.

CREATE OR REPLACE FUNCTION sp_registrar_gol(
    p_partido_id    INTEGER,
    p_jugador_id    INTEGER,
    p_minuto        SMALLINT,
    p_asistencia_id INTEGER DEFAULT NULL
)
RETURNS TABLE (gol_id INTEGER, goles_local SMALLINT, goles_visitante SMALLINT) AS $$
DECLARE
    v_gol_id INTEGER;
BEGIN
    -- equipo_id lo rellena el trigger a partir del jugador; se manda 0
    -- solo para satisfacer el NOT NULL.
    INSERT INTO goles (partido_id, jugador_id, jugador_asistencia_id, equipo_id, minuto)
    VALUES (p_partido_id, p_jugador_id, p_asistencia_id, 0, p_minuto)
    RETURNING id INTO v_gol_id;

    RETURN QUERY
    SELECT v_gol_id, p.goles_local, p.goles_visitante
    FROM partidos p WHERE p.id = p_partido_id;
END;
$$ LANGUAGE plpgsql;


-- ═══════════════════════════════════════════════════════════════════
--  sp_cambiar_numero_camiseta — dorsal libre dentro del equipo
-- ═══════════════════════════════════════════════════════════════════
--
--  La restriccion uq_jugadores_dorsal ya lo impide, pero el error de
--  clave duplicada no le dice nada util a quien esta en la pantalla.
--  Este procedimiento da el mensaje que el admin necesita leer.

CREATE OR REPLACE FUNCTION sp_cambiar_numero_camiseta(
    p_jugador_id INTEGER,
    p_numero     SMALLINT
)
RETURNS VOID AS $$
DECLARE
    v_equipo INTEGER;
    v_ocupante VARCHAR(200);
BEGIN
    IF p_numero < 1 OR p_numero > 99 THEN
        RAISE EXCEPTION 'El numero de camiseta debe estar entre 1 y 99';
    END IF;

    SELECT equipo_id INTO v_equipo FROM jugadores WHERE id = p_jugador_id;
    IF v_equipo IS NULL THEN
        RAISE EXCEPTION 'El jugador % no existe', p_jugador_id;
    END IF;

    SELECT nombres || ' ' || apellidos INTO v_ocupante
    FROM jugadores
    WHERE equipo_id = v_equipo AND numero_camiseta = p_numero AND id <> p_jugador_id;

    IF v_ocupante IS NOT NULL THEN
        RAISE EXCEPTION 'El numero % ya esta ocupado por % en este equipo',
            p_numero, v_ocupante;
    END IF;

    UPDATE jugadores SET numero_camiseta = p_numero WHERE id = p_jugador_id;
END;
$$ LANGUAGE plpgsql;

COMMIT;
