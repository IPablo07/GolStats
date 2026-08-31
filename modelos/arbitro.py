"""
modelos/arbitro.py
───────────────────
El árbitro es solo un catálogo: no tiene cuenta ni entra al sistema.
Sus anotaciones en papel las carga el administrador.
"""


class Arbitro:
    """
    El árbitro que dirige un partido.

    No hereda de Usuario a propósito: no tiene cuenta ni entra al sistema.
    Anota los goles y las tarjetas en papel, y el administrador los carga
    después. Por eso es un catálogo y no un rol.
    """

    def __init__(self, id, nombres, correo=None, telefono=None):
        self.id = id
        self.nombres = nombres
        self.correo = correo
        self.telefono = telefono

    def __repr__(self):
        return f"<Arbitro {self.nombres}>"
