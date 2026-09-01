-- ═══════════════════════════════════════════════════════════════════
--  GolStats — Esquema de PostgreSQL
--  01_schema.sql : tablas, claves e integridad declarativa
-- ═══════════════════════════════════════════════════════════════════
--
--  Cada restriccion de aqui replica una regla que hoy valida Python.
--  El mapeo completo (regla -> restriccion) esta en docs/modelo-datos.md.
--
--  Criterio: lo que se puede expresar con CHECK/UNIQUE/FK va aqui. Lo que
--  depende de otras filas (el minuto del cronometro, el estado del
--  partido) va en 02_triggers.sql. Lo que es una operacion completa con
--  varios pasos, en 03_procedimientos.sql.
--
--  Ejecutar en orden: 01 → 02 → 03 → 04 → 05
-- ═══════════════════════════════════════════════════════════════════

BEGIN;

-- ── Limpieza para reejecutar el script durante el desarrollo ────────
-- CASCADE arrastra las vistas de 04, que se vuelven a crear despues.
DROP TABLE IF EXISTS goles            CASCADE;
DROP TABLE IF EXISTS tarjetas         CASCADE;
DROP TABLE IF EXISTS checkins         CASCADE;
DROP TABLE IF EXISTS convocatorias    CASCADE;
DROP TABLE IF EXISTS pagos_vocalia    CASCADE;
DROP TABLE IF EXISTS partidos         CASCADE;
DROP TABLE IF EXISTS jugadores        CASCADE;
DROP TABLE IF EXISTS arbitros         CASCADE;
DROP TABLE IF EXISTS equipos          CASCADE;
DROP TABLE IF EXISTS usuarios         CASCADE;


-- ═══════════════════════════════════════════════════════════════════
--  1. usuarios — quien inicia sesion
-- ═══════════════════════════════════════════════════════════════════
--
--  Ojo con la diferencia entre usuario y jugador: desde que existe la
--  cuenta unica compartida, un jugador NO es un usuario. Hay dos filas
--  aqui en todo el sistema (el admin y la cuenta de jugadores), y por eso
--  esta tabla no tiene relacion con `jugadores`.

CREATE TABLE usuarios (
    id              SERIAL PRIMARY KEY,
    correo          VARCHAR(150) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    rol             VARCHAR(20)  NOT NULL,
    activo          BOOLEAN      NOT NULL DEFAULT TRUE,
    creado_en       TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_usuarios_correo   UNIQUE (correo),
    CONSTRAINT ck_usuarios_rol      CHECK (rol IN ('admin', 'jugador')),
    -- Un correo minimamente creible. No se valida a fondo a proposito:
    -- la comprobacion seria de verdad es enviar y ver si llega.
    CONSTRAINT ck_usuarios_correo   CHECK (correo LIKE '%_@_%.__%')
);

COMMENT ON TABLE  usuarios     IS 'Cuentas que inician sesion: el admin y la cuenta unica de jugadores';
COMMENT ON COLUMN usuarios.rol IS 'admin = escribe; jugador = solo lectura';


-- ═══════════════════════════════════════════════════════════════════
--  2. equipos
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE equipos (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    nombre_capitan  VARCHAR(150) NOT NULL,
    correo_capitan  VARCHAR(150),
    logo_url        VARCHAR(255),
    activo          BOOLEAN      NOT NULL DEFAULT TRUE,
    creado_en       TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_equipos_nombre     UNIQUE (nombre),
    CONSTRAINT ck_equipos_nombre     CHECK (LENGTH(TRIM(nombre)) > 0),
    CONSTRAINT ck_equipos_capitan    CHECK (LENGTH(TRIM(nombre_capitan)) > 0),
    CONSTRAINT ck_equipos_correo_cap CHECK (
        correo_capitan IS NULL OR correo_capitan LIKE '%_@_%.__%'
    )
);


-- ═══════════════════════════════════════════════════════════════════
--  3. jugadores
-- ═══════════════════════════════════════════════════════════════════
--
--  El correo es dato de contacto, no credencial: los jugadores dejaron de
--  tener cuenta propia. Por eso no es UNIQUE ni obligatorio.

CREATE TABLE jugadores (
    id                SERIAL PRIMARY KEY,
    equipo_id         INTEGER      NOT NULL,
    nombres           VARCHAR(100) NOT NULL,
    apellidos         VARCHAR(100) NOT NULL,
    cedula            VARCHAR(20)  NOT NULL,
    numero_camiseta   SMALLINT     NOT NULL,
    correo            VARCHAR(150),
    activo            BOOLEAN      NOT NULL DEFAULT TRUE,
    creado_en         TIMESTAMP    NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_jugadores_equipo FOREIGN KEY (equipo_id)
        REFERENCES equipos (id)
        -- RESTRICT y no CASCADE: borrar un equipo no puede llevarse por
        -- delante a sus jugadores, que tienen goles y tarjetas colgando.
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT uq_jugadores_cedula  UNIQUE (cedula),
    -- El dorsal es unico dentro del equipo, no en todo el torneo: el 10
    -- de un equipo y el 10 de otro conviven sin problema.
    CONSTRAINT uq_jugadores_dorsal  UNIQUE (equipo_id, numero_camiseta),

    CONSTRAINT ck_jugadores_dorsal  CHECK (numero_camiseta BETWEEN 1 AND 99),
    CONSTRAINT ck_jugadores_nombres CHECK (LENGTH(TRIM(nombres)) > 0),
    CONSTRAINT ck_jugadores_apell   CHECK (LENGTH(TRIM(apellidos)) > 0),
    CONSTRAINT ck_jugadores_cedula  CHECK (LENGTH(TRIM(cedula)) > 0),
    CONSTRAINT ck_jugadores_correo  CHECK (
        correo IS NULL OR correo LIKE '%_@_%.__%'
    )
);

CREATE INDEX ix_jugadores_equipo ON jugadores (equipo_id);


-- ═══════════════════════════════════════════════════════════════════
--  4. arbitros — catalogo suelto, sin cuenta
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE arbitros (
    id          SERIAL PRIMARY KEY,
    nombres     VARCHAR(150) NOT NULL,
    correo      VARCHAR(150),
    telefono    VARCHAR(20),
    activo      BOOLEAN      NOT NULL DEFAULT TRUE,

    CONSTRAINT ck_arbitros_nombres CHECK (LENGTH(TRIM(nombres)) > 0),
    CONSTRAINT ck_arbitros_correo  CHECK (
        correo IS NULL OR correo LIKE '%_@_%.__%'
    )
);


-- ═══════════════════════════════════════════════════════════════════
--  5. partidos
-- ═══════════════════════════════════════════════════════════════════
--
--  El cronometro se guarda igual que en Python: los segundos ya
--  acumulados mas el instante en que arranco el tramo actual. El minuto
--  se calcula al consultarlo (ver fn_minuto_actual en 02_triggers.sql).
--  Guardar "el minuto" como numero obligaria a que alguien lo
--  incrementara, y bastaria un reinicio para perderlo.

CREATE TABLE partidos (
    id                    SERIAL PRIMARY KEY,
    equipo_local_id       INTEGER   NOT NULL,
    equipo_visitante_id   INTEGER   NOT NULL,
    arbitro_id            INTEGER,
    fecha_hora            TIMESTAMP NOT NULL,

    estado                VARCHAR(20) NOT NULL DEFAULT 'programado',
    goles_local           SMALLINT    NOT NULL DEFAULT 0,
    goles_visitante       SMALLINT    NOT NULL DEFAULT 0,
    equipo_ganador_id     INTEGER,
    motivo_walkover       VARCHAR(255),
    motivo_cancelacion    VARCHAR(255),

    -- Cronometro
    segundos_jugados      NUMERIC(8,2) NOT NULL DEFAULT 0,
    reloj_desde           TIMESTAMP,

    creado_en             TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_partidos_local     FOREIGN KEY (equipo_local_id)
        REFERENCES equipos (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_partidos_visitante FOREIGN KEY (equipo_visitante_id)
        REFERENCES equipos (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_partidos_arbitro   FOREIGN KEY (arbitro_id)
        -- SET NULL: si se borra el arbitro, el partido sigue existiendo
        -- sin arbitro asignado. El campo admite NULL a proposito.
        REFERENCES arbitros (id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_partidos_ganador   FOREIGN KEY (equipo_ganador_id)
        REFERENCES equipos (id) ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT ck_partidos_estado CHECK (estado IN (
        'programado', 'primer_tiempo', 'medio_tiempo',
        'segundo_tiempo', 'finalizado', 'walkover', 'cancelado'
    )),
    -- Un equipo no juega contra si mismo.
    CONSTRAINT ck_partidos_rivales CHECK (equipo_local_id <> equipo_visitante_id),
    CONSTRAINT ck_partidos_marcador CHECK (
        goles_local >= 0 AND goles_visitante >= 0
    ),
    -- El ganador, si lo hay, tiene que ser uno de los dos que jugaron.
    CONSTRAINT ck_partidos_ganador CHECK (
        equipo_ganador_id IS NULL
        OR equipo_ganador_id IN (equipo_local_id, equipo_visitante_id)
    ),
    CONSTRAINT ck_partidos_reloj CHECK (segundos_jugados >= 0),
    -- El motivo de cancelacion solo tiene sentido si esta cancelado, y al
    -- reves: un cancelado siempre dice por que.
    CONSTRAINT ck_partidos_cancelacion CHECK (
        (estado = 'cancelado' AND motivo_cancelacion IS NOT NULL)
        OR (estado <> 'cancelado' AND motivo_cancelacion IS NULL)
    ),
    CONSTRAINT ck_partidos_walkover CHECK (
        estado = 'walkover' OR motivo_walkover IS NULL
    )
);

CREATE INDEX ix_partidos_fecha  ON partidos (fecha_hora DESC);
CREATE INDEX ix_partidos_estado ON partidos (estado);

COMMENT ON COLUMN partidos.segundos_jugados IS
    'Segundos de juego efectivo acumulados; el medio tiempo no suma';
COMMENT ON COLUMN partidos.reloj_desde IS
    'Instante en que arranco el tramo actual; NULL = reloj detenido';


-- ═══════════════════════════════════════════════════════════════════
--  6. convocatorias — quien esta citado a cada partido
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE convocatorias (
    partido_id  INTEGER NOT NULL,
    jugador_id  INTEGER NOT NULL,
    creado_en   TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Clave primaria compuesta: la relacion es N:M y un jugador no puede
    -- estar convocado dos veces al mismo partido.
    CONSTRAINT pk_convocatorias PRIMARY KEY (partido_id, jugador_id),

    CONSTRAINT fk_convocatorias_partido FOREIGN KEY (partido_id)
        -- CASCADE aqui si: la convocatoria no existe sin su partido.
        REFERENCES partidos (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_convocatorias_jugador FOREIGN KEY (jugador_id)
        REFERENCES jugadores (id) ON DELETE RESTRICT ON UPDATE CASCADE
);


-- ═══════════════════════════════════════════════════════════════════
--  7. checkins — confirmacion de presencia antes de iniciar
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE checkins (
    id            SERIAL PRIMARY KEY,
    partido_id    INTEGER     NOT NULL,
    jugador_id    INTEGER     NOT NULL,
    metodo        VARCHAR(10) NOT NULL DEFAULT 'huella',
    hora_registro TIMESTAMP   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_checkins_partido FOREIGN KEY (partido_id)
        REFERENCES partidos (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_checkins_jugador FOREIGN KEY (jugador_id)
        REFERENCES jugadores (id) ON DELETE RESTRICT ON UPDATE CASCADE,

    -- Un solo check-in por jugador y partido.
    CONSTRAINT uq_checkins UNIQUE (partido_id, jugador_id),
    CONSTRAINT ck_checkins_metodo CHECK (metodo IN ('huella', 'manual'))
);


-- ═══════════════════════════════════════════════════════════════════
--  8. goles
-- ═══════════════════════════════════════════════════════════════════
--
--  `equipo_id` esta desnormalizado a proposito: se puede deducir del
--  jugador, pero guardarlo evita un JOIN en cada consulta del marcador y
--  de la tabla de posiciones, que son las mas frecuentes. Un trigger lo
--  mantiene coherente para que no pueda quedar desalineado a mano.

CREATE TABLE goles (
    id                     SERIAL PRIMARY KEY,
    partido_id             INTEGER  NOT NULL,
    jugador_id             INTEGER  NOT NULL,
    jugador_asistencia_id  INTEGER,
    equipo_id              INTEGER  NOT NULL,
    minuto                 SMALLINT NOT NULL,
    registrado_en          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_goles_partido    FOREIGN KEY (partido_id)
        REFERENCES partidos (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_goles_jugador    FOREIGN KEY (jugador_id)
        REFERENCES jugadores (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_goles_asistencia FOREIGN KEY (jugador_asistencia_id)
        REFERENCES jugadores (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_goles_equipo     FOREIGN KEY (equipo_id)
        REFERENCES equipos (id) ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT ck_goles_minuto CHECK (minuto BETWEEN 1 AND 120),
    -- Nadie se asiste a si mismo. IS DISTINCT FROM y no <> porque con
    -- NULL (gol sin asistencia) la comparacion normal daria NULL y el
    -- CHECK pasaria por accidente.
    CONSTRAINT ck_goles_autoasistencia CHECK (
        jugador_asistencia_id IS DISTINCT FROM jugador_id
    )
);

CREATE INDEX ix_goles_partido ON goles (partido_id);
CREATE INDEX ix_goles_jugador ON goles (jugador_id);


-- ═══════════════════════════════════════════════════════════════════
--  9. tarjetas
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE tarjetas (
    id            SERIAL PRIMARY KEY,
    partido_id    INTEGER     NOT NULL,
    jugador_id    INTEGER     NOT NULL,
    equipo_id     INTEGER     NOT NULL,
    tipo          VARCHAR(10) NOT NULL,
    minuto        SMALLINT    NOT NULL,
    registrado_en TIMESTAMP   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_tarjetas_partido FOREIGN KEY (partido_id)
        REFERENCES partidos (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_tarjetas_jugador FOREIGN KEY (jugador_id)
        REFERENCES jugadores (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_tarjetas_equipo  FOREIGN KEY (equipo_id)
        REFERENCES equipos (id) ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT ck_tarjetas_tipo   CHECK (tipo IN ('amarilla', 'roja')),
    CONSTRAINT ck_tarjetas_minuto CHECK (minuto BETWEEN 1 AND 120)
);

CREATE INDEX ix_tarjetas_partido ON tarjetas (partido_id);
CREATE INDEX ix_tarjetas_jugador ON tarjetas (jugador_id);


-- ═══════════════════════════════════════════════════════════════════
--  10. pagos_vocalia — un pago por equipo y partido
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE pagos_vocalia (
    id               SERIAL PRIMARY KEY,
    partido_id       INTEGER       NOT NULL,
    equipo_id        INTEGER       NOT NULL,
    monto            NUMERIC(10,2) NOT NULL DEFAULT 20.00,
    estado           VARCHAR(20)   NOT NULL DEFAULT 'pendiente',
    fecha_pago       TIMESTAMP,
    comprobante_pdf  VARCHAR(255),

    CONSTRAINT fk_pagos_partido FOREIGN KEY (partido_id)
        REFERENCES partidos (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_pagos_equipo  FOREIGN KEY (equipo_id)
        REFERENCES equipos (id) ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT uq_pagos UNIQUE (partido_id, equipo_id),
    CONSTRAINT ck_pagos_monto  CHECK (monto > 0),
    CONSTRAINT ck_pagos_estado CHECK (estado IN ('pendiente', 'pagado')),
    -- La fecha de pago y el estado van de la mano: no hay pagados sin
    -- fecha ni pendientes con ella.
    CONSTRAINT ck_pagos_coherencia CHECK (
        (estado = 'pagado'    AND fecha_pago IS NOT NULL)
        OR (estado = 'pendiente' AND fecha_pago IS NULL)
    )
);


-- ═══════════════════════════════════════════════════════════════════
--  11. registros_biometricos — YA EXISTE, creada por SQLAlchemy
-- ═══════════════════════════════════════════════════════════════════
--
--  Esta tabla no se crea aqui: la genera `db.create_all()` desde
--  modelos/huella.py, y es la unica que ya esta en produccion. Lo que
--  falta son sus CHECK, que SQLAlchemy no declaraba. Se añaden sin
--  recrear la tabla para no perder las huellas ya enroladas.
--
--  IF NOT EXISTS en el DO: el script tiene que poder reejecutarse.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'registros_biometricos') THEN

        ALTER TABLE registros_biometricos
            DROP CONSTRAINT IF EXISTS ck_biometria_tipo_persona,
            DROP CONSTRAINT IF EXISTS ck_biometria_proveedor,
            DROP CONSTRAINT IF EXISTS ck_biometria_dedo,
            DROP CONSTRAINT IF EXISTS ck_biometria_calidad,
            DROP CONSTRAINT IF EXISTS ck_biometria_muestras;

        ALTER TABLE registros_biometricos
            ADD CONSTRAINT ck_biometria_tipo_persona
                CHECK (tipo_persona IN ('jugador', 'arbitro', 'administrador')),
            ADD CONSTRAINT ck_biometria_proveedor
                CHECK (proveedor IN ('EXTERNO', 'SIMULADO')),
            -- Los diez dedos, segun el enum Dedo del paquete biometria.
            ADD CONSTRAINT ck_biometria_dedo
                CHECK (dedo BETWEEN 1 AND 10),
            ADD CONSTRAINT ck_biometria_calidad
                CHECK (calidad BETWEEN 0 AND 100),
            ADD CONSTRAINT ck_biometria_muestras
                CHECK (muestras_usadas > 0);
    END IF;
END $$;

COMMIT;
