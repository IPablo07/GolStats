"""Lectores de huella: contrato de hardware, proveedor reutilizable y registro.

Estructura de la capa, de lo general a lo específico:

    base.py        LectorHardware — contrato que cumple cada familia de lector
    proveedor.py   ProveedorHardware — TODA la política, cero código de marca
    registro.py    qué modelos conoce el sistema
    secugen/       controlador de la familia SecuGen (Hamster Plus HSDU03P)

Para soportar un lector nuevo:

1. Cree `lectores/<fabricante>/` con una subclase de `LectorHardware`.
2. Exponga en su `__init__.py` una función `registrar()`.
3. Llámela abajo, en `_registrar_familias()`.

Nada más del sistema cambia: ni `ProveedorHardware`, ni la fábrica, ni las
pantallas, ni la base de datos.
"""

from .base import (
    ESCALA_SCORE,
    CapturaHardware,
    DiagnosticoHardware,
    InfoLector,
    LectorHardware,
)
from .proveedor import UMBRAL_POR_OMISION, ProveedorHardware
from .registro import (
    EntradaLector,
    crear_lector,
    lectores_registrados,
    obtener_entrada,
    registrar_lector,
)


def _registrar_familias() -> None:
    """Inscribe las familias incorporadas. Se ejecuta al importar el paquete."""
    from . import secugen

    secugen.registrar()


_registrar_familias()


__all__ = [
    "ESCALA_SCORE",
    "UMBRAL_POR_OMISION",
    "CapturaHardware",
    "DiagnosticoHardware",
    "EntradaLector",
    "InfoLector",
    "LectorHardware",
    "ProveedorHardware",
    "crear_lector",
    "lectores_registrados",
    "obtener_entrada",
    "registrar_lector",
]
