"""
Paquete modelos
────────────────
Clases del dominio de GolStats. Se importan desde aquí para que el
resto del proyecto escriba: from modelos import Equipo, Partido, ...
"""

from modelos.usuario import Usuario, Administrador, Jugador
from modelos.equipo import Equipo
from modelos.arbitro import Arbitro
from modelos.pago import PagoVocalia
from modelos.partido import Partido, EventoPartido, Gol, Tarjeta, CheckIn
from modelos.notificacion import (
    Notificacion,
    NotificacionPagoCompletado,
    NotificacionPagoPendiente,
    NotificacionWalkover,
    NotificacionReciboPDF,
)
from modelos.huella import RegistroBiometrico, TIPOS_PERSONA

__all__ = [
    "Usuario", "Administrador", "Jugador",
    "Equipo", "Arbitro", "PagoVocalia",
    "Partido", "EventoPartido", "Gol", "Tarjeta", "CheckIn",
    "Notificacion", "NotificacionPagoCompletado", "NotificacionPagoPendiente",
    "NotificacionWalkover", "NotificacionReciboPDF",
    "RegistroBiometrico", "TIPOS_PERSONA",
]
