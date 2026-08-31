"""Contratos de datos del subsistema biométrico.

Este módulo no depende de ningún proveedor concreto ni de Flask ni de la base de
datos. Define únicamente los tipos que cruzan la frontera de
`ProveedorBiometrico`, de modo que el resto del sistema pueda construirse y
probarse sin lector físico.

Regla estructural: el nivel de aseguramiento viaja **dentro** de cada veredicto.
No se puede obtener un resultado biométrico sin saber de qué proveedor vino.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Iterable


# ---------------------------------------------------------------------------
# Nivel de aseguramiento
# ---------------------------------------------------------------------------


class NivelAseguramiento(StrEnum):
    """Valor probatorio de un evento de autenticación.

    `DEMOSTRATIVO` es contagioso: un acta compuesta por eventos de niveles
    distintos hereda siempre el más débil (ver `nivel_resultante`).
    """

    PROBATORIO = "PROBATORIO"
    DEMOSTRATIVO = "DEMOSTRATIVO"


def nivel_resultante(niveles: Iterable[NivelAseguramiento]) -> NivelAseguramiento:
    """Devuelve el nivel más débil del conjunto.

    Es la implementación del invariante del sistema: *un acta hereda el nivel de
    aseguramiento más débil de todos los eventos que la componen*. Un conjunto
    vacío no puede ser probatorio, porque no hay evidencia que lo sustente.
    """
    materializados = list(niveles)
    if not materializados:
        return NivelAseguramiento.DEMOSTRATIVO
    if any(n is NivelAseguramiento.DEMOSTRATIVO for n in materializados):
        return NivelAseguramiento.DEMOSTRATIVO
    return NivelAseguramiento.PROBATORIO


# ---------------------------------------------------------------------------
# Proveedores
# ---------------------------------------------------------------------------


class TipoProveedor(StrEnum):
    """Implementaciones disponibles del subsistema biométrico.

    `es_probatorio` vive aquí y en ningún otro lugar: es la única fuente de
    verdad sobre el valor probatorio de un proveedor, para que ninguna
    implementación pueda declararse probatoria por su cuenta.
    """

    EXTERNO = "EXTERNO"
    SIMULADO = "SIMULADO"

    @property
    def es_probatorio(self) -> bool:
        return self is TipoProveedor.EXTERNO

    @property
    def nivel(self) -> NivelAseguramiento:
        return (
            NivelAseguramiento.PROBATORIO
            if self.es_probatorio
            else NivelAseguramiento.DEMOSTRATIVO
        )


# ---------------------------------------------------------------------------
# Dominio biométrico
# ---------------------------------------------------------------------------


class Dedo(IntEnum):
    """Posición del dedo según los códigos de ISO/IEC 19794-2.

    Se usan los valores del estándar y no un enum propio para que las plantillas
    sean interpretables por cualquier otro sistema conforme.
    """

    DESCONOCIDO = 0
    PULGAR_DERECHO = 1
    INDICE_DERECHO = 2
    MEDIO_DERECHO = 3
    ANULAR_DERECHO = 4
    MENIQUE_DERECHO = 5
    PULGAR_IZQUIERDO = 6
    INDICE_IZQUIERDO = 7
    MEDIO_IZQUIERDO = 8
    ANULAR_IZQUIERDO = 9
    MENIQUE_IZQUIERDO = 10


class CodigoResultado(StrEnum):
    """Desenlace de una operación biométrica.

    Se registran todos, no solo `OK`: una bitácora que únicamente contiene
    éxitos no permite demostrar que el control discrimina.
    """

    OK = "OK"
    NO_MATCH = "NO_MATCH"
    CALIDAD_INSUFICIENTE = "CALIDAD_INSUFICIENTE"
    CAPTURA_FALLIDA = "CAPTURA_FALLIDA"
    TIEMPO_AGOTADO = "TIEMPO_AGOTADO"
    CANCELADO = "CANCELADO"
    LECTOR_NO_DISPONIBLE = "LECTOR_NO_DISPONIBLE"
    ERROR_SDK = "ERROR_SDK"

    @property
    def es_exito(self) -> bool:
        return self is CodigoResultado.OK


FORMATO_ISO_19794_2 = "ISO/IEC 19794-2"

#: Calidad mínima aceptable de una muestra, en la escala 0-100 del SDK.
CALIDAD_MINIMA = 60

#: Cantidad de muestras del mismo dedo que pide la pantalla de enrolamiento.
MUESTRAS_POR_PLANTILLA = 4

#: Mínimo con el que se acepta consolidar una plantilla, si alguna captura falló.
MUESTRAS_MINIMAS = 3


@dataclass(frozen=True, slots=True)
class Muestra:
    """Captura individual del sensor. Insumo para construir una plantilla.

    Nunca se persiste: la muestra es la representación más cercana a la imagen
    del dedo y solo vive en memoria durante el enrolamiento.
    """

    datos: bytes
    calidad: int
    dedo: Dedo
    capturada_en: datetime
    proveedor: TipoProveedor

    @property
    def es_utilizable(self) -> bool:
        return self.calidad >= CALIDAD_MINIMA


@dataclass(frozen=True, slots=True)
class Plantilla:
    """Plantilla biométrica consolidada. Es lo único que se persiste.

    `referencia` identifica a la identidad dueña de la plantilla cuando ya fue
    persistida. El proveedor externo la ignora; el simulado la usa como clave de
    guion, y `buscar` la emplea para reportar coincidencias.
    """

    datos: bytes
    formato: str
    dedo: Dedo
    calidad: int
    proveedor: TipoProveedor
    muestras_usadas: int
    referencia: str | None = None

    def con_referencia(self, referencia: str) -> "Plantilla":
        """Copia la plantilla asociándola a una identidad persistida."""
        return Plantilla(
            datos=self.datos,
            formato=self.formato,
            dedo=self.dedo,
            calidad=self.calidad,
            proveedor=self.proveedor,
            muestras_usadas=self.muestras_usadas,
            referencia=referencia,
        )


@dataclass(frozen=True, slots=True)
class Veredicto:
    """Resultado de una verificación 1:1.

    No es un booleano: el score, el umbral y la calidad son necesarios para
    auditar la decisión, y `nivel` impide que un resultado se separe de su
    procedencia.
    """

    coincide: bool
    codigo: CodigoResultado
    score: int
    umbral: int
    calidad: int
    duracion_ms: int
    proveedor: TipoProveedor
    nivel: NivelAseguramiento

    def __post_init__(self) -> None:
        if self.coincide and not self.codigo.es_exito:
            raise ValueError(
                f"veredicto incoherente: coincide=True con código {self.codigo}"
            )
        if not self.coincide and self.codigo.es_exito:
            raise ValueError("veredicto incoherente: código OK sin coincidencia")


@dataclass(frozen=True, slots=True)
class Coincidencia:
    """Resultado de una búsqueda 1:N. Se usa para detectar doble enrolamiento."""

    referencia: str
    score: int
    umbral: int
    duracion_ms: int
    proveedor: TipoProveedor
    nivel: NivelAseguramiento


@dataclass(frozen=True, slots=True)
class Diagnostico:
    """Estado del proveedor, consumido por la pantalla de preflight."""

    proveedor: TipoProveedor
    disponible: bool
    lectores: int
    version_sdk: str | None = None
    mensajes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def nivel(self) -> NivelAseguramiento:
        return self.proveedor.nivel


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


class ErrorBiometrico(Exception):
    """Raíz de los errores del subsistema biométrico."""

    codigo: CodigoResultado = CodigoResultado.ERROR_SDK


class LectorNoDisponible(ErrorBiometrico):
    codigo = CodigoResultado.LECTOR_NO_DISPONIBLE


class CapturaFallida(ErrorBiometrico):
    codigo = CodigoResultado.CAPTURA_FALLIDA


class CalidadInsuficiente(CapturaFallida):
    codigo = CodigoResultado.CALIDAD_INSUFICIENTE


class TiempoAgotado(ErrorBiometrico):
    codigo = CodigoResultado.TIEMPO_AGOTADO
