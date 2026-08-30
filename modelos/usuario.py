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
        return check_password_hash(self.password_hash, password_plano)

    def panel_info(self):
        """Cada subclase decide qué mostrar en su panel — polimorfismo."""
        raise NotImplementedError("Cada subclase debe definir su propio panel_info()")


class Administrador(Usuario):
    def __init__(self, id, correo, password_plano):
        super().__init__(id, correo, password_plano, rol="admin")

    def panel_info(self):
        return {
            "tipo": "admin",
            "mensaje": "Panel de administración: equipos, jugadores, partidos y vocalías.",
        }


class Jugador(Usuario):
    def __init__(self, id, correo, password_plano, equipo, nombres, apellidos, cedula, numero_camiseta):
        super().__init__(id, correo, password_plano, rol="jugador")
        self.equipo = equipo                    # objeto Equipo (lo creamos en el siguiente bloque)
        self.nombres = nombres
        self.apellidos = apellidos
        self.cedula = cedula
        self.numero_camiseta = numero_camiseta
        self.codigo_huella = None               # se llena más adelante, con el lector real

    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    def panel_info(self):
        return {
            "tipo": "jugador",
            "mensaje": f"Bienvenido, {self.nombre_completo()}. Aquí verás tus estadísticas.",
        }