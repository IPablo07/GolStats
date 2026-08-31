"""
modelos/usuario.py
───────────────────
Jerarquía de usuarios del sistema: clase base + dos subclases
(administrador / cuenta compartida de jugadores).

Ojo con la diferencia entre *usuario* y *jugador*:

    Usuario  → alguien que entra al sistema (tiene correo y contraseña)
    Jugador  → una persona de la plantilla de un equipo

Antes cada jugador era además un usuario, con su propia cuenta. Ya no:
ahora existe UNA SOLA cuenta compartida para todos los jugadores
(CuentaJugadores), y `Jugador` pasó a ser una entidad del dominio sin
credenciales. Ver la nota en CuentaJugadores.

Todavía sin conexión a base de datos — por ahora los datos viven en
memoria (ver datos_prueba.py), y más adelante estas mismas clases se
conectan a PostgreSQL sin que el resto del código cambie.
"""

from werkzeug.security import generate_password_hash, check_password_hash


class Usuario:
    """Clase base: todo lo que comparten las cuentas que inician sesión."""

    def __init__(self, id, correo, password_plano, rol):
        self.id = id
        self.correo = correo
        self.password_hash = generate_password_hash(password_plano)
        self.rol = rol

    def verificar_password(self, password_plano):
        """
        Compara la contraseña escrita contra el hash guardado.

        La contraseña en texto plano nunca se almacena: solo se guarda su
        hash, y esta comparación es la única forma de validarla.
        """
        return check_password_hash(self.password_hash, password_plano)

    def panel_info(self):
        """Cada subclase decide qué mostrar en su panel — polimorfismo."""
        raise NotImplementedError("Cada subclase debe definir su propio panel_info()")


class Administrador(Usuario):
    """
    Quien carga la vocalía: registra los goles y tarjetas que anotó el
    árbitro en papel, cobra la vocalía y controla el check-in.

    Es el único rol que puede modificar datos del sistema.
    """

    def __init__(self, id, correo, password_plano):
        super().__init__(id, correo, password_plano, rol="admin")

    def panel_info(self):
        return {
            "tipo": "admin",
            "mensaje": "Panel de administración: equipos, jugadores, partidos y vocalías.",
        }


class CuentaJugadores(Usuario):
    """
    La cuenta única y compartida con la que entran TODOS los jugadores.

    Por qué una sola cuenta y no una por jugador: lo que los jugadores
    consultan (partidos, posiciones y estadísticas de cualquier jugador)
    es información pública del torneo, igual para todos. Mantener una
    cuenta por persona obligaba a crear, repartir y resetear decenas de
    contraseñas para no proteger ningún dato privado.

    Consecuencia de diseño: esta cuenta es anónima — no representa a un
    jugador concreto, así que no tiene equipo ni número de camiseta, y su
    panel muestra el torneo entero en vez de "mis estadísticas".

    Es de solo lectura: comparte el rol "jugador", que es exactamente el
    que admin_requerido() deja fuera de las acciones de escritura.
    """

    def __init__(self, id, correo, password_plano):
        super().__init__(id, correo, password_plano, rol="jugador")

    def panel_info(self):
        return {
            "tipo": "jugador",
            "mensaje": "Partidos y tabla de posiciones del torneo.",
        }


class Jugador:
    """
    Un jugador del torneo: alguien de la plantilla de un equipo.

    Ya no hereda de Usuario ni tiene contraseña. Con la cuenta compartida
    (CuentaJugadores) el jugador dejó de ser una cuenta del sistema y pasó
    a ser solo un sujeto de estadísticas: se lo consulta desde Equipos, no
    inicia sesión.

    El `correo` que sigue guardando es un dato de contacto (recibos,
    avisos del capitán), no una credencial.
    """

    def __init__(self, id, correo, equipo, nombres, apellidos, cedula, numero_camiseta):
        self.id = id
        self.correo = correo
        self.equipo = equipo                    # objeto Equipo
        self.nombres = nombres
        self.apellidos = apellidos
        self.cedula = cedula
        self.numero_camiseta = numero_camiseta
        # La huella no se guarda aquí: vive en PostgreSQL
        # (modelos.huella.RegistroBiometrico), enlazada por (tipo_persona,
        # persona_id) = ("jugador", self.id). Ver servicios/huella.py.

    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    def __repr__(self):
        return f"<Jugador {self.nombre_completo()} #{self.numero_camiseta}>"
