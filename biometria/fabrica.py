"""Fábrica del proveedor biométrico.

Único lugar del sistema donde se decide qué implementación se usa. El resto del
código recibe un `ProveedorBiometrico` y no sabe —ni debe saber— cuál es, ni de
qué fabricante es el lector que hay detrás.
"""

from __future__ import annotations

from typing import Any, Mapping

from .contratos import TipoProveedor
from .lectores import ProveedorHardware, crear_lector, lectores_registrados
from .proveedor import ProveedorBiometrico
from .simulado import SimuladoProvider


def crear_proveedor(
    tipo: TipoProveedor | str,
    *,
    lector: str | None = None,
    opciones_lector: Mapping[str, Any] | None = None,
    **opciones: Any,
) -> ProveedorBiometrico:
    """Construye el proveedor indicado.

    Para `EXTERNO` hay que nombrar el modelo de lector: no se elige uno por
    omisión a propósito, porque operar con un controlador distinto al que se
    creyó configurar es peor que no arrancar.

        crear_proveedor("EXTERNO", lector="secugen:hsdu03p", umbral=45)
        crear_proveedor("SIMULADO", guion={...})
    """
    resuelto = tipo if isinstance(tipo, TipoProveedor) else TipoProveedor(tipo)

    if resuelto is TipoProveedor.SIMULADO:
        if lector is not None:
            raise ValueError("el proveedor SIMULADO no usa un modelo de lector")
        return SimuladoProvider(**opciones)

    if resuelto is TipoProveedor.EXTERNO:
        if not lector:
            claves = ", ".join(e.clave for e in lectores_registrados())
            raise ValueError(
                "el proveedor EXTERNO requiere el argumento «lector» con el "
                f"modelo a usar. Modelos registrados: {claves}"
            )
        return ProveedorHardware(
            crear_lector(lector, **dict(opciones_lector or {})), **opciones
        )

    raise ValueError(f"tipo de proveedor desconocido: {tipo!r}")
