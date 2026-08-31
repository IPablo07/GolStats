# Diagrama de clases — GolStats

Modelo orientado a objetos del sistema de vocalías. Los diagramas están en
Mermaid, así que GitHub los renderiza solo al abrir este archivo.

Convención de visibilidad: `+` público, `-` privado (en Python, atributos que
empiezan con guion bajo y solo se tocan desde métodos de la propia clase).

---

## 1. Dominio principal

```mermaid
classDiagram
    class Usuario {
        +int id
        +str correo
        +str password_hash
        +str rol
        +verificar_password(password) bool
        +panel_info() dict
    }

    class Administrador {
        +panel_info() dict
    }

    class Jugador {
        +Equipo equipo
        +str nombres
        +str apellidos
        +str cedula
        +int numero_camiseta
        +str codigo_huella
        +nombre_completo() str
        +panel_info() dict
    }

    class Equipo {
        +int id
        +str nombre
        +str nombre_capitan
        +str correo_capitan
        +str logo_url
        +bool activo
        -list _jugadores
        +agregar_jugador(jugador)
        +obtener_jugadores() list
        +cantidad_jugadores() int
        +buscar_jugador_por_cedula(cedula) Jugador
        +buscar_jugador_por_id(id) Jugador
    }

    class Arbitro {
        +int id
        +str nombres
        +str correo
        +str telefono
    }

    class Partido {
        +int id
        +Equipo equipo_local
        +Equipo equipo_visitante
        +datetime fecha_hora
        +Arbitro arbitro
        +int goles_local
        +int goles_visitante
        +Equipo equipo_ganador
        +str motivo_walkover
        -str _estado
        -list _convocados
        -list _checkins
        -list _goles
        -list _tarjetas
        -dict _pagos
        +estado() str
        +convocar(jugador)
        +registrar_checkin(jugador, metodo) CheckIn
        +todos_confirmaron() bool
        +iniciar_primer_tiempo() str
        +terminar_primer_tiempo() str
        +iniciar_segundo_tiempo() str
        +finalizar() str
        +registrar_gol(jugador, minuto, asistente) Gol
        +registrar_tarjeta(jugador, tipo, minuto) Tarjeta
        +completar_pago(equipo) PagoVocalia
        +obtener_eventos() list
        +marcador() str
    }

    class PagoVocalia {
        +Partido partido
        +Equipo equipo
        +float monto
        +datetime fecha_pago
        +str comprobante_pdf
        -str _estado
        +estado() str
        +esta_pagado() bool
        +completar(comprobante) PagoVocalia
    }

    class EventoPartido {
        +Partido partido
        +Jugador jugador
        +int minuto
        +datetime registrado_en
        +descripcion() str
    }

    class Gol {
        +Jugador jugador_asistencia
        +Equipo equipo
        +descripcion() str
    }

    class Tarjeta {
        +str tipo
        +Equipo equipo
        +descripcion() str
    }

    class CheckIn {
        +str metodo
        +datetime hora_registro
        +descripcion() str
    }

    Usuario <|-- Administrador
    Usuario <|-- Jugador
    EventoPartido <|-- Gol
    EventoPartido <|-- Tarjeta
    EventoPartido <|-- CheckIn

    Equipo "1" o-- "0..*" Jugador : plantilla
    Partido "0..*" --> "2" Equipo : local / visitante
    Partido "0..*" --> "0..1" Arbitro : dirige
    Partido "1" *-- "2" PagoVocalia : vocalia
    Partido "1" *-- "0..*" Gol
    Partido "1" *-- "0..*" Tarjeta
    Partido "1" *-- "0..*" CheckIn
    EventoPartido "0..*" --> "1" Jugador : protagonista
```

**Cómo leer los rombos.** El rombo relleno (`*--`) es composición: los goles,
tarjetas, check-ins y pagos no existen fuera de su partido, y si el partido
desaparece se van con él. El rombo vacío (`o--`) es agregación: los jugadores
pertenecen a un equipo, pero siguen existiendo como personas aunque el equipo
se desarme.

---

## 2. Jerarquía de notificaciones

Los cuatro correos que manda el sistema comparten destinatario y forma de envío,
y solo se diferencian en qué dicen. Por eso la clase base resuelve `enviar()` una
sola vez y cada subclase define únicamente `asunto()` y `cuerpo()`.

```mermaid
classDiagram
    class Notificacion {
        +str destinatario
        +Equipo equipo
        +Partido partido
        +datetime enviada_en
        +list adjuntos
        +asunto() str
        +cuerpo() str
        +enviar() dict
        -_entregar(mensaje)
        -_encabezado_partido() str
    }

    class NotificacionPagoCompletado {
        +float monto
        +asunto() str
        +cuerpo() str
    }

    class NotificacionPagoPendiente {
        +float monto
        +asunto() str
        +cuerpo() str
    }

    class NotificacionWalkover {
        +str motivo
        +asunto() str
        +cuerpo() str
    }

    class NotificacionReciboPDF {
        +str ruta_pdf
        +asunto() str
        +cuerpo() str
    }

    Notificacion <|-- NotificacionPagoCompletado
    Notificacion <|-- NotificacionPagoPendiente
    Notificacion <|-- NotificacionWalkover
    Notificacion <|-- NotificacionReciboPDF
```

---

## 3. Capa de servicios

Las clases del paquete `servicios/` no son entidades del negocio: son
herramientas que operan sobre las entidades. Se separaron del paquete `modelos/`
justamente para que el dominio no dependa de detalles técnicos como el lector de
huella o el servidor de correo.

```mermaid
classDiagram
    class LectorHuella {
        +str modo
        +int umbral
        +str url
        +desde_config(config) LectorHuella
        +es_simulado() bool
        +registrar_template(jugador, template) str
        +tiene_huella(jugador) bool
        +verificar(jugador, puntaje) int
    }

    class ErrorHuella {
        <<Exception>>
    }

    class ServicioCorreo {
        +bool activo
        +Mail mail
        +enviar(notificacion) dict
        +bandeja() list
        +avisar_pago_completado(partido, equipo, monto)
        +avisar_pago_pendiente(partido, equipo, monto)
        +avisar_walkover(partido)
        +enviar_recibos(partido, ruta_pdf)
        -_enviar_real(mensaje)
    }

    class estadisticas {
        <<module>>
        +tabla_posiciones(equipos, partidos) list
        +goleadores(partidos, limite) list
        +asistencias(partidos, limite) list
        +tarjetas(partidos, limite) list
        +estadisticas_jugador(jugador, partidos) dict
        +estadisticas_equipo(equipo, partidos) dict
    }

    LectorHuella ..> ErrorHuella : lanza
    ServicioCorreo ..> Notificacion : envia
```

---

## 4. Estados del partido

El ciclo de vida de un partido no es libre: cada transición tiene una condición
que se valida antes de dejar pasar. Estas mismas reglas están replicadas como
triggers en PostgreSQL.

```mermaid
stateDiagram-v2
    [*] --> programado

    programado --> primer_tiempo : todos los convocados<br/>hicieron check-in
    programado --> programado : falta algun check-in<br/>(se rechaza)

    primer_tiempo --> medio_tiempo

    medio_tiempo --> segundo_tiempo : los dos equipos pagaron
    medio_tiempo --> walkover : algun equipo<br/>no pago la vocalia

    segundo_tiempo --> finalizado : gana quien tenga<br/>mas goles

    finalizado --> [*]
    walkover --> [*]
```

Un partido en `walkover` se cierra con marcador 3-0 a favor del equipo que sí
pagó. Si ninguno de los dos pagó, se cierra sin ganador.

---

## 5. Decisiones de diseño

### Por qué `Jugador` hereda de `Usuario`

En este sistema un jugador **es** un usuario: entra con correo y contraseña a ver
sus estadísticas. Modelarlo como una clase aparte con un campo `usuario_id`
habría obligado a mantener dos objetos sincronizados para representar a una sola
persona. La herencia refleja mejor la realidad y evita ese problema.

`Administrador` y `Jugador` redefinen `panel_info()`: la ruta `/panel` llama al
mismo método sin preguntar el rol, y cada clase responde con lo suyo. Eso es
polimorfismo resolviendo un `if` que si no habría que repetir en cada vista.

### Por qué existe `EventoPartido`

Goles, tarjetas y check-ins comparten estructura: los tres ocurren en un partido,
los protagoniza un jugador, tienen un momento y se pueden describir en texto.
La clase base recoge eso y cada subclase define su `descripcion()`. Gracias a
eso, `obtener_eventos()` puede juntar goles y tarjetas en una sola lista
ordenada y la plantilla los recorre sin preguntar de qué tipo es cada uno.

### Qué se encapsuló y por qué

| Atributo | Por qué es privado |
|---|---|
| `Equipo._jugadores` | `agregar_jugador()` valida que el número de camiseta no esté repetido. Si la lista fuera pública, cualquiera podría meter un duplicado con `.append()`. |
| `Partido._estado` | Solo cambia por los métodos de transición, que verifican check-ins y pagos antes de dejar avanzar. Asignarlo a mano saltearía todas las reglas del negocio. |
| `PagoVocalia._estado` | Marcar un pago exige registrar también la fecha. `completar()` hace las dos cosas juntas; un atributo público permitiría dejar el pago en un estado incoherente. |
| `Partido._goles` y `_tarjetas` | `registrar_gol()` actualiza el marcador en el mismo paso. Agregar un gol por fuera dejaría el marcador desactualizado. |

Los métodos `obtener_*()` devuelven **copias** de las listas internas
(`list(self._jugadores)`), no la lista real. Así, si alguien modifica lo que
recibe, no está tocando el estado interno del objeto sin querer.
