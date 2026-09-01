"""
Paquete modelos
────────────────
Clases del dominio de GolStats. Se importan desde aquí para que el
resto del proyecto escriba: from modelos import Equipo, Partido, ...
"""

from modelos.usuario import Usuario, Administrador, CuentaJugadores, Jugador
from modelos.equipo import Equipo
from modelos.arbitro import Arbitro
from modelos.pago import PagoVocalia
from modelos.partido import Partido, EventoPartido, Gol, Tarjeta, CheckIn
from modelos.notificacion import (
    Notificacion,
    NotificacionPagoCompletado,
    NotificacionPartidoProximo,
    NotificacionWalkover,
    NotificacionReciboPDF,
)
from modelos.huella import RegistroBiometrico, TIPOS_PERSONA

__all__ = [
    "Usuario", "Administrador", "CuentaJugadores", "Jugador",
    "Equipo", "Arbitro", "PagoVocalia",
    "Partido", "EventoPartido", "Gol", "Tarjeta", "CheckIn",
    "Notificacion", "NotificacionPagoCompletado", "NotificacionPartidoProximo",
    "NotificacionWalkover", "NotificacionReciboPDF",
    "RegistroBiometrico", "TIPOS_PERSONA",
]
