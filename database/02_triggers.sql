-- ═══════════════════════════════════════════════════════════════════
--  GolStats — 02_triggers.sql
--  Reglas que un CHECK no puede expresar
-- ═══════════════════════════════════════════════════════════════════
--
--  Un CHECK solo puede mirar la fila que se esta insertando. Todo lo que
--  necesita consultar OTRAS filas —el estado del partido, si el jugador
--  hizo check-in, cuanto marca el cronometro— tiene que ser un trigger.
--
--  Estos triggers son la ultima linea de defensa, no la primera: la
--  aplicacion ya valida lo mismo y da mensajes mas utiles. Estan aqui
--  para que la regla se cumpla aunque alguien escriba por psql, por otra
--  aplicacion, o por un script de carga.
-- ═══════════════════════════════════════════════════════════════════

BEGIN;


-- ═══════════════════════════════════════════════════════════════════
--  Funcion auxiliar: el minuto que marca el cronometro
-- ═══════════════════════════════════════════════════════════════════
--
--  Mismo criterio que Partido.minuto_actual() en Python: corriendo se
--  muestra el minuto en curso, en pausa el ultimo cumplido, y nunca pasa
--  de 90. Se centraliza aqui para que la validacion de goles y las
--  vistas no puedan discrepar entre si.

CREATE OR REPLACE FUNCTION fn_minuto_actual(p_partido_id INTEGER)
RETURNS SMALLINT AS $$
DECLARE
    v_segundos NUMERIC;
    v_corriendo BOOLEAN;
    v_minuto INTEGER;
BEGIN
    SELECT
        segundos_jugados + COALESCE(EXTRACT(EPOCH FROM (NOW() - reloj_desde)), 0),
        reloj_desde IS NOT NULL
    INTO v_segundos, v_corriendo
    FROM partidos WHERE id = p_partido_id;

    IF v_segundos IS NULL THEN
        RETURN 0;
    END IF;

    -- Tope reglamentario: el reloj se queda clavado en 90.
    v_segundos := LEAST(v_segundos, 90 * 60);

    IF NOT v_corriendo THEN
        IF v_segundos = 0 THEN
            RETURN 0;
        END IF;
        v_minuto := GREATEST(1, CEIL(v_segundos / 60.0));
    ELSE
        v_minuto := FLOOR(v_segundos / 60.0) + 1;
    END IF;

    RETURN LEAST(v_minuto, 90);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION fn_minuto_actual IS
    'Minuto del cronometro; espejo de Partido.minuto_actual() en Python';


-- ═══════════════════════════════════════════════════════════════════
--  1. El convocado debe pertenecer a uno de los dos equipos
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION fn_validar_convocatoria()
RETURNS TRIGGER AS $$
DECLARE
    v_equipo_jugador INTEGER;
    v_local INTEGER;
    v_visitante INTEGER;
    v_estado VARCHAR(20);
BEGIN
    SELECT equipo_id INTO v_equipo_jugador
    FROM jugadores WHERE id = NEW.jugador_id;

    SELECT equipo_local_id, equipo_visitante_id, estado
    INTO v_local, v_visitante, v_estado
    FROM partidos WHERE id = NEW.partido_id;

    IF v_equipo_jugador NOT IN (v_local, v_visitante) THEN
        RAISE EXCEPTION
            'El jugador % no pertenece a ninguno de los dos equipos del partido %',
            NEW.jugador_id, NEW.partido_id;
    END IF;

    IF v_estado <> 'programado' THEN
        RAISE EXCEPTION
            'Solo se puede convocar mientras el partido esta programado (esta en %)',
            v_estado;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_convocatoria
    BEFORE INSERT ON convocatorias
    FOR EACH ROW EXECUTE FUNCTION fn_validar_convocatoria();


-- ═══════════════════════════════════════════════════════════════════
--  2. El check-in exige partido programado y jugador convocado
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION fn_validar_checkin()
RETURNS TRIGGER AS $$
DECLARE
    v_estado VARCHAR(20);
BEGIN
    SELECT estado INTO v_estado FROM partidos WHERE id = NEW.partido_id;

    IF v_estado <> 'programado' THEN
        RAISE EXCEPTION
            'El check-in solo se puede hacer antes de que inicie el partido (esta en %)',
            v_estado;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM convocatorias
        WHERE partido_id = NEW.partido_id AND jugador_id = NEW.jugador_id
    ) THEN
        RAISE EXCEPTION
            'El jugador % no esta convocado para el partido %',
            NEW.jugador_id, NEW.partido_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_checkin
    BEFORE INSERT ON checkins
    FOR EACH ROW EXECUTE FUNCTION fn_validar_checkin();


-- ═══════════════════════════════════════════════════════════════════
--  3. El gol: partido en juego, jugador con check-in, minuto coherente
-- ═══════════════════════════════════════════════════════════════════
--
--  Es la regla mas cargada del sistema y la que mas se apoya en otras
--  filas. Reune tres validaciones que en Python viven en
--  _validar_registro_en_juego() y registrar_gol().

CREATE OR REPLACE FUNCTION fn_validar_gol()
RETURNS TRIGGER AS $$
DECLARE
    v_estado VARCHAR(20);
    v_local INTEGER;
    v_visitante INTEGER;
    v_equipo_jugador INTEGER;
    v_equipo_asistente INTEGER;
    v_minuto SMALLINT;
BEGIN
    SELECT estado, equipo_local_id, equipo_visitante_id
    INTO v_estado, v_local, v_visitante
    FROM partidos WHERE id = NEW.partido_id;

    -- El medio tiempo esta explicitamente fuera: durante la pausa no se
    -- registran goles.
    IF v_estado NOT IN ('primer_tiempo', 'segundo_tiempo') THEN
        RAISE EXCEPTION
            'No se pueden registrar goles con el partido en estado %', v_estado;
    END IF;

    SELECT equipo_id INTO v_equipo_jugador
    FROM jugadores WHERE id = NEW.jugador_id;

    IF v_equipo_jugador NOT IN (v_local, v_visitante) THEN
        RAISE EXCEPTION 'El goleador no pertenece a ninguno de los dos equipos';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM checkins
        WHERE partido_id = NEW.partido_id AND jugador_id = NEW.jugador_id
    ) THEN
        RAISE EXCEPTION 'El jugador % no hizo check-in, no pudo jugar', NEW.jugador_id;
    END IF;

    -- La asistencia, si la hay, es de un companero del mismo equipo y
    -- tambien tuvo que presentarse.
    IF NEW.jugador_asistencia_id IS NOT NULL THEN
        SELECT equipo_id INTO v_equipo_asistente
        FROM jugadores WHERE id = NEW.jugador_asistencia_id;

        IF v_equipo_asistente <> v_equipo_jugador THEN
            RAISE EXCEPTION 'La asistencia debe ser de un companero del mismo equipo';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM checkins
            WHERE partido_id = NEW.partido_id
              AND jugador_id = NEW.jugador_asistencia_id
        ) THEN
            RAISE EXCEPTION 'El asistente no hizo check-in, no pudo jugar';
        END IF;
    END IF;

    -- El gol no puede ir en un minuto que el partido todavia no ha
    -- alcanzado. Solo se comprueba con el reloj en marcha: los partidos
    -- de carga historica se insertan con el cronometro en cero.
    v_minuto := fn_minuto_actual(NEW.partido_id);
    IF v_minuto > 0 AND NEW.minuto > v_minuto THEN
        RAISE EXCEPTION
            'El partido va por el minuto %: no se puede registrar un gol en el %',
            v_minuto, NEW.minuto;
    END IF;

    -- El equipo del gol se deduce del jugador, nunca se acepta a mano:
    -- asi la columna desnormalizada no puede quedar desalineada.
    NEW.equipo_id := v_equipo_jugador;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_gol
    BEFORE INSERT OR UPDATE ON goles
    FOR EACH ROW EXECUTE FUNCTION fn_validar_gol();


-- ═══════════════════════════════════════════════════════════════════
--  4. El marcador se recalcula solo
-- ═══════════════════════════════════════════════════════════════════
--
--  En Python, registrar_gol() incrementa el marcador y editar_gol() lo
--  descuenta y lo vuelve a sumar. Aqui se recalcula entero desde los
--  goles: es mas simple de razonar y no puede desincronizarse, pase lo
--  que pase con inserciones, ediciones o borrados.

CREATE OR REPLACE FUNCTION fn_recalcular_marcador()
RETURNS TRIGGER AS $$
DECLARE
    v_partido INTEGER;
BEGIN
    v_partido := COALESCE(NEW.partido_id, OLD.partido_id);

    UPDATE partidos p SET
        goles_local = (
            SELECT COUNT(*) FROM goles g
            WHERE g.partido_id = v_partido AND g.equipo_id = p.equipo_local_id
        ),
        goles_visitante = (
            SELECT COUNT(*) FROM goles g
            WHERE g.partido_id = v_partido AND g.equipo_id = p.equipo_visitante_id
        )
    WHERE p.id = v_partido;

    RETURN NULL;   -- AFTER trigger: el valor devuelto se ignora
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_recalcular_marcador
    AFTER INSERT OR UPDATE OR DELETE ON goles
    FOR EACH ROW EXECUTE FUNCTION fn_recalcular_marcador();


-- ═══════════════════════════════════════════════════════════════════
--  5. La tarjeta: mismas condiciones que el gol, sin tocar el marcador
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION fn_validar_tarjeta()
RETURNS TRIGGER AS $$
DECLARE
    v_estado VARCHAR(20);
    v_equipo_jugador INTEGER;
    v_local INTEGER;
    v_visitante INTEGER;
BEGIN
    SELECT estado, equipo_local_id, equipo_visitante_id
    INTO v_estado, v_local, v_visitante
    FROM partidos WHERE id = NEW.partido_id;

    -- Las tarjetas SI se admiten en el medio tiempo: el arbitro puede
    -- amonestar camino al vestuario, y la aplicacion tampoco lo impide.
    IF v_estado NOT IN ('primer_tiempo', 'medio_tiempo', 'segundo_tiempo') THEN
        RAISE EXCEPTION
            'No se pueden registrar tarjetas con el partido en estado %', v_estado;
    END IF;

    SELECT equipo_id INTO v_equipo_jugador
    FROM jugadores WHERE id = NEW.jugador_id;

    IF v_equipo_jugador NOT IN (v_local, v_visitante) THEN
        RAISE EXCEPTION 'El jugador amonestado no pertenece a ninguno de los dos equipos';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM checkins
        WHERE partido_id = NEW.partido_id AND jugador_id = NEW.jugador_id
    ) THEN
        RAISE EXCEPTION 'El jugador % no hizo check-in, no pudo ser amonestado',
            NEW.jugador_id;
    END IF;

    NEW.equipo_id := v_equipo_jugador;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_tarjeta
    BEFORE INSERT OR UPDATE ON tarjetas
    FOR EACH ROW EXECUTE FUNCTION fn_validar_tarjeta();


-- ═══════════════════════════════════════════════════════════════════
--  6. Las transiciones de estado del partido son las del reglamento
-- ═══════════════════════════════════════════════════════════════════
--
--  Impide saltarse pasos: de programado no se va directo a finalizado, y
--  un partido cerrado no vuelve a abrirse. Tambien mueve el cronometro,
--  para que arrancar el segundo tiempo no dependa de que la aplicacion
--  se acuerde de actualizar `reloj_desde`.

CREATE OR REPLACE FUNCTION fn_validar_transicion_partido()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.estado = OLD.estado THEN
        RETURN NEW;
    END IF;

    IF OLD.estado IN ('finalizado', 'walkover', 'cancelado') THEN
        RAISE EXCEPTION 'El partido esta cerrado (%): su estado ya no cambia', OLD.estado;
    END IF;

    IF NOT (
           (OLD.estado = 'programado'     AND NEW.estado IN ('primer_tiempo', 'cancelado'))
        OR (OLD.estado = 'primer_tiempo'  AND NEW.estado = 'medio_tiempo')
        OR (OLD.estado = 'medio_tiempo'   AND NEW.estado IN ('segundo_tiempo', 'walkover'))
        OR (OLD.estado = 'segundo_tiempo' AND NEW.estado = 'finalizado')
    ) THEN
        RAISE EXCEPTION 'Transicion invalida: % -> %', OLD.estado, NEW.estado;
    END IF;

    -- El reloj: arranca en los dos tiempos, se detiene en el resto.
    IF NEW.estado IN ('primer_tiempo', 'segundo_tiempo') THEN
        NEW.reloj_desde := NOW();
    ELSE
        IF OLD.reloj_desde IS NOT NULL THEN
            NEW.segundos_jugados := OLD.segundos_jugados
                + EXTRACT(EPOCH FROM (NOW() - OLD.reloj_desde));
        END IF;
        NEW.reloj_desde := NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_transicion_partido
    BEFORE UPDATE OF estado ON partidos
    FOR EACH ROW EXECUTE FUNCTION fn_validar_transicion_partido();


-- ═══════════════════════════════════════════════════════════════════
--  7. Los dos pagos de vocalia nacen con el partido
-- ═══════════════════════════════════════════════════════════════════
--
--  En Python los crea el constructor de Partido. Aqui lo hace un trigger
--  para que un partido insertado por cualquier via tenga siempre sus dos
--  pagos: sin ellos, el paso al segundo tiempo no sabria a quien cobrar.

CREATE OR REPLACE FUNCTION fn_crear_pagos_vocalia()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO pagos_vocalia (partido_id, equipo_id)
    VALUES (NEW.id, NEW.equipo_local_id),
           (NEW.id, NEW.equipo_visitante_id);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_crear_pagos_vocalia
    AFTER INSERT ON partidos
    FOR EACH ROW EXECUTE FUNCTION fn_crear_pagos_vocalia();

COMMIT;
