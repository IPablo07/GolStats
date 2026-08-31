"""Registro de modelos de lector.

Único punto donde el sistema aprende qué hardware sabe manejar. Agregar un
lector nuevo es registrar una entrada; nada más del sistema cambia.

Las claves siguen la forma ``fabricante:modelo`` en minúsculas, y existe también
``fabricante:auto`` para dejar que el SDK autodetecte el dispositivo conectado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .base import LectorHardware


@dataclass(frozen=True, slots=True)
class EntradaLector:
    """Un modelo de lector soportado."""

    clave: str
    fabricante: str
    modelo: str
    descripcion: str
    constructor: Callable[..., LectorHardware]

    def crear(self, **opciones: Any) -> LectorHardware:
        return self.constructor(**opciones)


_REGISTRO: dict[str, EntradaLector] = {}


def registrar_lector(entrada: EntradaLector, *, reemplazar: bool = False) -> None:
    """Añade un modelo al registro.

    Rechaza duplicados salvo `reemplazar=True`: un registro silenciosamente
    sobrescrito haría que la aplicación usara un controlador distinto al que se
    creyó configurar.
    """
    clave = entrada.clave.lower()
    if clave in _REGISTRO and not reemplazar:
        raise ValueError(f"la clave de lector ya está registrada: {clave!r}")
    _REGISTRO[clave] = entrada


def crear_lector(clave: str, **opciones: Any) -> LectorHardware:
    """Construye el lector de la clave indicada."""
    entrada = _REGISTRO.get(clave.lower())
    if entrada is None:
        disponibles = ", ".join(sorted(_REGISTRO)) or "ninguna"
        raise ValueError(
            f"modelo de lector desconocido: {clave!r}. Claves registradas: {disponibles}"
        )
    return entrada.crear(**opciones)


def lectores_registrados() -> tuple[EntradaLector, ...]:
    """Todos los modelos soportados, ordenados por clave."""
    return tuple(_REGISTRO[c] for c in sorted(_REGISTRO))


def obtener_entrada(clave: str) -> EntradaLector | None:
    return _REGISTRO.get(clave.lower())


def _limpiar_registro() -> None:
    """Vacía el registro. Solo para pruebas."""
    _REGISTRO.clear()
