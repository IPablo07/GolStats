"""
modelos/usuario.py
───────────────────
Jerarquía de usuarios: clase base + dos subclases (admin/jugador).
Todavía sin conexión a base de datos — por ahora los datos viven en
memoria (ver datos_prueba.py), y más adelante esta misma clase se
conecta a PostgreSQL sin que el resto del código cambie.
"""

from werkzeug.security import generate_password_hash, check_password_hash


class Usuario:
    """Clase base: todo lo que comparten un administrador y un jugador."""

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


class Jugador(Usuario):
    """
    Un jugador del torneo, que además es usuario del sistema: entra con su
    correo a ver sus propias estadísticas, y nada más que las suyas.

    Hereda de Usuario porque en este sistema el jugador *es* un usuario. Si
    fueran dos clases separadas habría que mantener sincronizados dos objetos
    para representar a una sola persona.
    """

    def __init__(self, id, correo, password_plano, equipo, nombres, apellidos, cedula, numero_camiseta):
        super().__init__(id, correo, password_plano, rol="jugador")
        self.equipo = equipo                    # objeto Equipo
        self.nombres = nombres
        self.apellidos = apellidos
        self.cedula = cedula
        self.numero_camiseta = numero_camiseta
        # La huella ya no se guarda aquí: vive en PostgreSQL
        # (modelos.huella.RegistroBiometrico), enlazada por (tipo_persona,
        # persona_id) = ("jugador", self.id). Ver servicios/huella.py.

    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    def panel_info(self):
        return {
            "tipo": "jugador",
            "mensaje": f"Bienvenido, {self.nombre_completo()}. Aquí verás tus estadísticas.",
        }