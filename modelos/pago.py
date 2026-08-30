"""
modelos/pago.py
────────────────
Pago de la vocalía que debe hacer cada equipo antes del partido.

Regla del negocio: si un equipo no completó el pago cuando arranca el
segundo tiempo, pierde por walkover. Esa validación vive en Partido,
aquí solo se modela el pago en sí.

Equivalente en la base de datos: tabla `pagos_vocalia` + el stored
procedure sp_completar_pago_vocalia().
"""

from datetime import datetime


class PagoVocalia:

    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    ESTADOS = (PENDIENTE, COMPLETADO)

    def __init__(self, partido, equipo, monto):
        if monto <= 0:
            raise ValueError("El monto de la vocalía debe ser mayor a cero")
        self.partido = partido
        self.equipo = equipo
        self.monto = monto
        self._estado = PagoVocalia.PENDIENTE
        self.fecha_pago = None
        self.comprobante_pdf = None

    @property
    def estado(self):
        """Solo lectura desde afuera: para cambiarlo hay que usar completar()."""
        return self._estado

    def esta_pagado(self):
        return self._estado == PagoVocalia.COMPLETADO

    def completar(self, comprobante_pdf=None):
        if self.esta_pagado():
            raise ValueError(
                f"El pago del equipo {self.equipo.nombre} ya estaba completado"
            )
        self._estado = PagoVocalia.COMPLETADO
        self.fecha_pago = datetime.now()
        self.comprobante_pdf = comprobante_pdf
        return self

    def __repr__(self):
        return f"<PagoVocalia {self.equipo.nombre} ${self.monto:.2f} {self._estado}>"
