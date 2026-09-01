# GolStats — Sistema de vocalías de fútbol

Flask + PostgreSQL (para las huellas) + (más adelante) PostgreSQL para todo lo
demás. Gestiona vocalías de partidos de fútbol amateur: convocatoria,
check-in con huella dactilar, registro de goles y tarjetas, pago de vocalía
por equipo, walkover automático y estadísticas del torneo.

## Cómo levantarlo

```bash
python -m venv venv
venv\Scripts\activate          # en Mac: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # en Mac: cp .env.example .env
```

Con `HUELLA_MODO=simulado` (el valor por omisión) no hace falta Postgres para
las pantallas que no tocan huellas, pero **la tabla de huellas sí requiere
PostgreSQL corriendo** (ver sección siguiente) porque `app.py` la crea al
arrancar. Con la base de datos creada y accesible desde `DATABASE_URL`:

```bash
python app.py
```

Abrir http://localhost:5000

### Crear la base de datos en PostgreSQL

`app.py` crea la tabla `registros_biometricos` sola al arrancar (con
`db.create_all()`), pero la base de datos en sí (`golstats`) hay que
crearla una vez, a mano. Con pgAdmin: clic derecho en **Databases** →
**Create** → **Database...** → nombre `golstats`. O por línea de comandos:

```bash
psql -U postgres -c "CREATE DATABASE golstats;"
```

Si `DATABASE_URL` en `.env` no coincide con el usuario/contraseña de tu
Postgres local, ajústalo ahí.

**Cuentas de prueba**

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@golstats.com` | `admin123` |
| Jugadores | `jugadores@golstats.com` | `jugadores123` |

La de jugadores es **una sola cuenta compartida**: todos entran con la
misma, no hay una por persona. Da acceso de lectura a los partidos, la
tabla de posiciones y las estadísticas de cualquier jugador de cualquier
equipo (ver `modelos/usuario.py`).

## Estado actual

Los datos del torneo (equipos, partidos, goles...) viven **en memoria**
(`datos_prueba.py`). El esquema de PostgreSQL ya está escrito y probado, en
[`database/`](database/): **10 tablas, 7 triggers, 7 procedimientos y 5
vistas**. Se conecta en la última etapa: las reglas de negocio que hoy valida
Python son las mismas que allá son restricciones y triggers, así que las rutas
y las plantillas no cambian.

El diseño, el diagrama entidad-relación y el mapeo de cada regla a su
restricción están en [`docs/modelo-datos.md`](docs/modelo-datos.md).

La excepción es la **huella dactilar**: `registros_biometricos` ya es una
tabla real de PostgreSQL (ver `modelos/huella.py`) que se va llenando sola,
una fila por persona, cada vez que un administrador enrola a un jugador, un
árbitro o un administrador desde `/biometria`. Se adelantó porque el lector
SecuGen y la base de datos van de la mano: no tiene sentido simular la
plantilla biométrica y guardarla en memoria si de todas formas hay que
conectar Postgres para probar el lector real.

## Estructura

```
GolStats/
├── app.py                  Rutas Flask (login, paneles, partidos, reportes)
├── config.py               Configuración desde .env
├── extensiones.py          Instancias compartidas: SQLAlchemy y Flask-Mail
├── datos_prueba.py         Datos de ejemplo en memoria + repositorio BD
├── prueba_modelos.py       Prueba de las clases del dominio (sin Flask)
├── prueba_rutas.py         Recorre todas las pantallas con el test client
├── database/               Esquema de PostgreSQL (ver database/README.md)
│   ├── 01_schema.sql       Tablas, PK, FK, CHECK, UNIQUE, DEFAULT
│   ├── 02_triggers.sql     Reglas que dependen de otras filas
│   ├── 03_procedimientos.sql  Operaciones de varios pasos
│   ├── 04_vistas.sql       Las 5 vistas de estadisticas
│   └── 05_datos_iniciales.sql
├── docs/
│   ├── diagrama-clases.md  Diagrama de clases y decisiones de diseño
│   └── modelo-datos.md     Diagrama entidad-relacion y diseño relacional
├── biometria/               Paquete del lector SecuGen (ctypes + sgfplib.dll)
│   ├── contratos.py         Tipos: Muestra, Plantilla, Veredicto, Dedo...
│   ├── proveedor.py         Contrato ProveedorBiometrico
│   ├── simulado.py          Proveedor simulado, sin hardware
│   ├── fabrica.py           crear_proveedor(tipo, lector=..., umbral=...)
│   └── lectores/            Implementación real (SecuGen) + registro de modelos
├── sgfplib.dll, sgfdusdax64.dll, ...   DLL del SDK de SecuGen (junto a app.py)
├── modelos/                Clases del dominio (POO)
│   ├── usuario.py          Usuario → Administrador, CuentaJugadores
│   ├── equipo.py           Equipo (encapsula su plantilla)
│   ├── arbitro.py          Árbitro (catálogo, sin cuenta)
│   ├── pago.py             PagoVocalia
│   ├── partido.py          Partido + EventoPartido → Gol, Tarjeta, CheckIn
│   ├── huella.py           RegistroBiometrico (tabla real en PostgreSQL)
│   └── notificacion.py     Notificacion → PagoCompletado, PartidoProximo,
│                           Walkover, ReciboPDF
├── servicios/
│   ├── estadisticas.py     Reportes (equivalen a las vistas SQL)
│   ├── huella.py           Enrolamiento y verificación con el lector SecuGen
│   └── correo.py           Envío de notificaciones (simulado o Flask-Mail)
├── templates/              Jinja2 + Bootstrap 5 (responsive)
│   ├── biometria.html      Enrolar jugadores, árbitros y administradores
│   └── gestion.html        Alta y baja de equipos, jugadores, árbitros y partidos
└── static/
    ├── css/estilos.css
    └── img/                Logo, favicon
```

## Herencia y polimorfismo (criterio 3.3)

| Clase base | Subclases | Método polimórfico |
|---|---|---|
| `Usuario` | `Administrador`, `CuentaJugadores` | `panel_info()` — cada rol arma su panel |
| `EventoPartido` | `Gol`, `Tarjeta`, `CheckIn` | `descripcion()` — texto de la línea de tiempo |
| `Notificacion` | 4 tipos de correo | `asunto()` / `cuerpo()` |

El encapsulamiento aparece en `Equipo._jugadores`, `Partido._estado` y
`PagoVocalia._estado`: solo se cambian con métodos que validan primero.

## Reglas de negocio ya implementadas

1. El partido no inicia si falta el check-in de algún convocado.
2. Al iniciar el segundo tiempo, si un equipo no pagó → walkover automático 3-0
   a favor del otro (y se avisa por correo a los dos capitanes).
3. Al registrar un gol se actualiza el marcador solo.
4. Al finalizar, el ganador sale del marcador y se envían los recibos.
5. Un jugador sin check-in no puede aparecer en goles ni tarjetas.
6. El cronómetro lo maneja el admin: arranca, se pausa en el medio tiempo y se
   reanuda en el segundo, hasta los 90 minutos.
7. Un gol no puede registrarse en un minuto posterior al que marca el reloj, ni
   durante el medio tiempo.
8. Los goles y las tarjetas se editan solo mientras el partido sigue en curso.
9. El dorsal es único dentro del equipo y va del 1 al 99.
10. Un partido se cancela solo si está programado: no se borra, cambia de estado
    y deja de contar para la tabla de posiciones.

## Lector de huella SecuGen

Flask captura directo del lector desde el propio servidor, con el paquete
`biometria` (ctypes + `sgfplib.dll`, incluido en `GolStats/biometria/`). Ya
no hace falta instalar ni dejar corriendo el servicio SecuGen WebAPI aparte:
basta con que las DLL (`sgfplib.dll` y las demás) estén junto a `app.py`, que
el driver esté instalado, y que Flask corra en la misma laptop Windows donde
está conectado el lector.

- **Enrolamiento** (`/biometria`): un administrador pide 4 capturas del
  mismo dedo por persona (jugador, árbitro o administrador) y arma una
  plantilla; queda guardada en PostgreSQL, en `registros_biometricos`.
- **Verificación 1:1** (check-in de un partido): ya se sabe qué jugador se
  presenta —viene de la convocatoria—, así que se compara solo contra SU
  plantilla.
- **Verificación 1:N** (login del administrador, sin contraseña): no se
  sabe todavía quién es, así que se compara contra todas las plantillas de
  administradores. Esto lo resuelve el propio paquete `biometria` comparando
  en software (no hace falta una licencia aparte de SecuGen).

Para desarrollar sin el lector (por ejemplo en la Mac), en `.env`:

```
HUELLA_MODO=simulado
```

En modo simulado, `registrar()` y `verificar()` siempre tienen éxito (no hay
hardware que lo impida); `identificar()` — el login por huella — no
encuentra coincidencias salvo que se guione a propósito, así que para
probar ese flujo hace falta el lector real.

Con el lector conectado:

```
HUELLA_MODO=secugen
HUELLA_UMBRAL=45              # ajustar probando con el lector real
HUELLA_LECTOR=secugen:hsdu03p # modelo del lector (ver biometria/lectores)
```

## Correo

Mientras al `.env` le falte `MAIL_SERVER`, `MAIL_USERNAME` o `MAIL_PASSWORD`, los
correos quedan en una bandeja simulada (se ven en la consola y en el panel del
administrador). Así se puede probar todo el flujo sin cuenta de correo.

Para enviar de verdad con Gmail, `MAIL_PASSWORD` **no es la contraseña de la
cuenta**: es una [contraseña de aplicación](https://myaccount.google.com/apppasswords)
de 16 caracteres, y exige tener activada la verificación en dos pasos. Si
`MAIL_DEFAULT_SENDER` se deja vacío se usa `MAIL_USERNAME`, que es lo que
conviene: Gmail ignora cualquier otro remitente.

Esa contraseña va en el `.env` y en ningún otro sitio — el `.env.example` sí se
sube al repositorio.

Qué correos salen:

- **Recibo del partido** y **confirmación de pago de vocalía**, al capitán del
  equipo correspondiente.
- **Aviso de partido próximo** al capitán, con fecha, hora y monto de la
  vocalía. Reemplazó al viejo recordatorio de pago pendiente: el cobro se hace
  en cancha el día del partido, así que perseguirlo por correo llegaba tarde.

## Trabajo en equipo

Cada persona trabaja en su rama `feature/<algo>` y abre Pull Request hacia `main`.
Antes de programar: `git pull origin main`.
