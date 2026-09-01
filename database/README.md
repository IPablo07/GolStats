# database/ — Esquema de PostgreSQL

Scripts SQL de GolStats. El diseño, el diagrama entidad-relación y el mapeo
completo de reglas están en [`docs/modelo-datos.md`](../docs/modelo-datos.md).

## Qué hay aquí

| Archivo | Contenido |
|---|---|
| `01_schema.sql` | 10 tablas del torneo: PK, FK, CHECK, UNIQUE, DEFAULT e índices. Añade además los CHECK que le faltaban a `registros_biometricos`. |
| `02_triggers.sql` | 7 triggers + `fn_minuto_actual()`. Las reglas que necesitan consultar otras filas. |
| `03_procedimientos.sql` | 7 procedimientos. Las operaciones de varios pasos que deben ocurrir juntas. |
| `04_vistas.sql` | Las 5 vistas que consume `servicios/estadisticas.py`, más su vista base. |
| `05_datos_iniciales.sql` | Las 2 cuentas, 4 equipos, 32 jugadores y 3 árbitros. Sin partidos jugados. |

## Cómo montarlo

```bash
psql -U postgres -c "CREATE DATABASE golstats;"
```

```bash
psql -U postgres -d golstats -f database/01_schema.sql
```

```bash
psql -U postgres -d golstats -f database/02_triggers.sql
```

```bash
psql -U postgres -d golstats -f database/03_procedimientos.sql
```

```bash
psql -U postgres -d golstats -f database/04_vistas.sql
```

```bash
psql -U postgres -d golstats -f database/05_datos_iniciales.sql
```

**El orden importa**: los triggers necesitan las tablas, las vistas necesitan
las tablas que consultan, y los datos iniciales necesitan las restricciones
puestas para validarse al entrar.

## Dos avisos

**`01_schema.sql` borra y recrea las diez tablas del torneo.** Es reejecutable
a propósito, para poder rehacer el esquema durante el desarrollo. Si algún día
hay datos reales que conservar, hará falta una migración en vez de este script.

**No toca `registros_biometricos`.** Esa tabla la crea SQLAlchemy desde
`modelos/huella.py` y ya está en producción con huellas enroladas. El script
solo le añade los `CHECK` que le faltaban, sin recrearla ni vaciarla.

## Las contraseñas de `05_datos_iniciales.sql`

Van con un marcador, no con un hash real: werkzeug genera una sal distinta en
cada ejecución, así que un hash fijo en un archivo versionado no sirve. Para
rellenarlas, desde la raíz del proyecto:

```bash
python -c "from werkzeug.security import generate_password_hash as h; print(h('admin123'))"
```

Y luego un `UPDATE usuarios SET password_hash = '<lo que imprimió>'`.

## Estado

Los cinco scripts se probaron ejecutándolos completos contra PostgreSQL 18 en
una base desechable, comprobando que las restricciones **rechazan** lo que
deben: dorsales repetidos, equipos contra sí mismos, goles fuera del tiempo
del cronómetro, cobros duplicados y transiciones de estado inválidas.

La aplicación **todavía no los usa**: el torneo sigue viviendo en memoria
(`datos_prueba.py`) y PostgreSQL solo guarda las huellas. Conectar la capa de
datos es el paso siguiente, y estos scripts son su punto de partida.
