# GolStats — Sistema de vocalías de fútbol

Flask + (más adelante) PostgreSQL. Gestiona vocalías de partidos de fútbol amateur:
convocatoria, check-in con huella dactilar, registro de goles y tarjetas, pago de
vocalía por equipo, walkover automático y estadísticas del torneo.

## Cómo levantarlo

```bash
python -m venv venv
venv\Scripts\activate          # en Mac: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # en Mac: cp .env.example .env
python app.py
```

Abrir http://localhost:5000

**Cuentas de prueba**

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@golstats.com` | `admin123` |
| Jugador | `bryan.vera@golstats.com` | `jugador123` |

Los demás jugadores usan `nombre.apellido@golstats.com` / `jugador123`
(ver `datos_prueba.py`).

## Estado actual

Los datos viven **en memoria** (`datos_prueba.py`). El esquema de PostgreSQL
(10 tablas, 4 triggers, 1 stored procedure y 5 vistas) ya está diseñado y probado,
y se conecta en la última etapa: las reglas de negocio que hoy valida Python son
las mismas que allá son triggers, así que las rutas y plantillas no cambian.

## Estructura

```
GolStats/
├── app.py                  Rutas Flask (login, paneles, partidos, reportes)
├── config.py               Configuración desde .env
├── datos_prueba.py         Datos de ejemplo en memoria + repositorio BD
├── prueba_modelos.py       Prueba de las clases del dominio (sin Flask)
├── prueba_rutas.py         Recorre todas las pantallas con el test client
├── modelos/                Clases del dominio (POO)
│   ├── usuario.py          Usuario → Administrador, Jugador
│   ├── equipo.py           Equipo (encapsula su plantilla)
│   ├── arbitro.py          Árbitro (catálogo, sin cuenta)
│   ├── pago.py             PagoVocalia
│   ├── partido.py          Partido + EventoPartido → Gol, Tarjeta, CheckIn
│   └── notificacion.py     Notificacion → PagoCompletado, PagoPendiente,
│                           Walkover, ReciboPDF
├── servicios/
│   ├── estadisticas.py     Reportes (equivalen a las vistas SQL)
│   ├── huella.py           Verificación 1:1 con el lector SecuGen
│   └── correo.py           Envío de notificaciones (simulado o Flask-Mail)
├── templates/              Jinja2 + Bootstrap 5 (responsive)
└── static/
    ├── css/estilos.css
    └── js/huella.js        Cliente del SecuGen WebAPI
```

## Herencia y polimorfismo (criterio 3.3)

| Clase base | Subclases | Método polimórfico |
|---|---|---|
| `Usuario` | `Administrador`, `Jugador` | `panel_info()` — cada rol arma su panel |
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

## Lector de huella SecuGen

El servicio **SecuGen WebAPI** se instala en la laptop Windows junto con el driver
y escucha en `https://localhost:8000`. Solo funciona en el navegador de esa misma
laptop, y la primera vez hay que aceptar el certificado autofirmado entrando a
`https://localhost:8000`.

- `SGIFPCapture` → captura y devuelve el template en base64.
- `SGIMatchScore` → compara dos templates y devuelve 0..199.

Es verificación **1:1**: ya se sabe qué jugador se presenta (viene de la
convocatoria), así que se compara solo contra su propio template guardado.
La búsqueda 1:N necesitaría una licencia aparte.

Para desarrollar sin el lector (por ejemplo en la Mac), en `.env`:

```
HUELLA_MODO=simulado
```

Con el lector conectado:

```
HUELLA_MODO=secugen
HUELLA_UMBRAL=45          # ajustar probando con el lector real
```

## Correo

Mientras el `.env` no tenga `MAIL_SERVER` y `MAIL_USERNAME`, los correos quedan en
una bandeja simulada (se ven en la consola y en el panel del administrador). Así
se puede probar todo el flujo sin cuenta de correo.

## Trabajo en equipo

Cada persona trabaja en su rama `feature/<algo>` y abre Pull Request hacia `main`.
Antes de programar: `git pull origin main`.
