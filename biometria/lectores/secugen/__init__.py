"""Familia SecuGen: FDx SDK Pro sobre `sgfplib.dll`.

Modelo adquirido para el proyecto: **Hamster Plus HSDU03P**.

Para soportar otro modelo SecuGen basta añadir una entrada en `modelos.py`; el
controlador no cambia, porque toda la familia usa el mismo SDK.
"""

from ..registro import EntradaLector, registrar_lector
from .constantes import (
    FABRICANTE,
    FORMATO_PROYECTO,
    NOMBRES_FORMATO,
    RANGO_SCORE_PRESUNTO,
    describir_error,
    verificar_constantes,
)
from .enlace import (
    EnlaceCtypes,
    EnlaceSecuGen,
    ErrorSDKSecuGen,
    InfoDispositivoSDK,
)
from .lector import LectorSecuGen
from .modelos import MODELOS, POR_CLAVE, ModeloSecuGen


def registrar() -> None:
    """Inscribe todos los modelos SecuGen en el registro de lectores.

    Idempotente: se puede llamar varias veces sin error, para que importar el
    paquete dos veces no rompa nada.
    """
    for modelo in MODELOS:
        registrar_lector(
            EntradaLector(
                clave=modelo.clave,
                fabricante=FABRICANTE,
                modelo=modelo.modelo,
                descripcion=modelo.descripcion,
                constructor=lambda _m=modelo, **opciones: LectorSecuGen(
                    modelo=_m, **opciones
                ),
            ),
            reemplazar=True,
        )


__all__ = [
    "FABRICANTE",
    "FORMATO_PROYECTO",
    "MODELOS",
    "NOMBRES_FORMATO",
    "POR_CLAVE",
    "RANGO_SCORE_PRESUNTO",
    "EnlaceCtypes",
    "EnlaceSecuGen",
    "ErrorSDKSecuGen",
    "InfoDispositivoSDK",
    "LectorSecuGen",
    "ModeloSecuGen",
    "describir_error",
    "registrar",
    "verificar_constantes",
]
