"""Catálogo de modelos SecuGen.

Agregar un modelo de la misma familia es añadir una entrada aquí: el
controlador `LectorSecuGen` no cambia, porque todos hablan el mismo SDK.

Las dimensiones son **nominales**, solo para diagnóstico previo a la conexión.
En tiempo de ejecución se usan siempre las que reporta `SGFPM_GetDeviceInfo`,
que es la fuente autoritativa.
"""

from __future__ import annotations

from dataclasses import dataclass

from .constantes import SG_DEV_AUTO


@dataclass(frozen=True, slots=True)
class ModeloSecuGen:
    """Un modelo concreto de lector SecuGen."""

    clave: str
    modelo: str
    nombre_comercial: str
    #: Constante `SG_DEV_*` para `SGFPM_Init`. `SG_DEV_AUTO` deja que el SDK
    #: autodetecte, que es lo preferible: no depende de constantes por modelo.
    constante_dispositivo: int = SG_DEV_AUTO
    ancho_nominal: int = 0
    alto_nominal: int = 0
    dpi_nominal: int = 500

    @property
    def descripcion(self) -> str:
        return f"SecuGen {self.nombre_comercial} ({self.modelo})"


#: El lector adquirido para el proyecto.
HSDU03P = ModeloSecuGen(
    clave="secugen:hsdu03p",
    modelo="HSDU03P",
    nombre_comercial="Hamster Plus",
    ancho_nominal=260,
    alto_nominal=300,
    dpi_nominal=500,
)

#: Autodetección: sirve para cualquier lector SecuGen conectado.
AUTO = ModeloSecuGen(
    clave="secugen:auto",
    modelo="AUTO",
    nombre_comercial="autodetectado",
)

#: Otros modelos de la misma familia, soportados sin código adicional.
HU20AP = ModeloSecuGen(
    clave="secugen:hu20ap",
    modelo="HU20AP",
    nombre_comercial="Hamster Pro 20",
    ancho_nominal=300,
    alto_nominal=400,
)

HFDU06 = ModeloSecuGen(
    clave="secugen:hfdu06",
    modelo="HFDU06",
    nombre_comercial="Hamster IV",
    ancho_nominal=258,
    alto_nominal=336,
)

MODELOS: tuple[ModeloSecuGen, ...] = (AUTO, HSDU03P, HU20AP, HFDU06)

POR_CLAVE: dict[str, ModeloSecuGen] = {m.clave: m for m in MODELOS}
