"""Interfaz única del subsistema biométrico.

Todo el resto del sistema —enrolamiento, asistencia y firma del acta— habla
exclusivamente con este contrato. Cambiar de lector, o pasar del lector real al
simulado, no debe requerir tocar ninguna otra capa.

`es_probatorio` y `nivel` son concretos y derivan de `TipoProveedor`: una
implementación no puede declararse probatoria por su cuenta.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Sequence

from .contratos import (
    Coincidencia,
    Dedo,
    Diagnostico,
    NivelAseguramiento,
    Muestra,
    Plantilla,
    TipoProveedor,
    Veredicto,
)

#: Tiempo por omisión que se espera a que la persona apoye el dedo.
TIMEOUT_POR_OMISION_S = 15.0


class ProveedorBiometrico(ABC):
    """Contrato que toda implementación biométrica debe cumplir."""

    # -- Identidad del proveedor -------------------------------------------

    @property
    @abstractmethod
    def tipo(self) -> TipoProveedor:
        """Implementación concreta en uso."""

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre legible, para mostrar en la interfaz y en la bitácora."""

    @property
    def es_probatorio(self) -> bool:
        """Si los resultados de este proveedor tienen valor probatorio.

        Deliberadamente concreto: delega en `TipoProveedor`, que es la única
        fuente de verdad. Una subclase que lo sobrescriba está mintiendo.
        """
        return self.tipo.es_probatorio

    @property
    def nivel(self) -> NivelAseguramiento:
        return self.tipo.nivel

    # -- Diagnóstico -------------------------------------------------------

    @abstractmethod
    def diagnostico(self) -> Diagnostico:
        """Estado del lector y del SDK. No debe lanzar: informa, no falla.

        La pantalla de preflight depende de que este método sea seguro de
        llamar incluso cuando no hay hardware conectado.
        """

    # -- Enrolamiento ------------------------------------------------------

    @abstractmethod
    def capturar_muestra(
        self,
        dedo: Dedo,
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Muestra:
        """Espera que se apoye el dedo y devuelve una muestra.

        Lanza `TiempoAgotado`, `CalidadInsuficiente` o `CapturaFallida`.
        """

    @abstractmethod
    def crear_plantilla(self, muestras: Sequence[Muestra]) -> Plantilla:
        """Consolida varias muestras del mismo dedo en una plantilla.

        Lanza `ValueError` si las muestras no son del mismo dedo o si no
        alcanzan la cantidad mínima.
        """

    # -- Verificación ------------------------------------------------------

    @abstractmethod
    def verificar(
        self,
        plantilla: Plantilla,
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Veredicto:
        """Verificación 1:1 contra una identidad ya declarada.

        Devuelve un `Veredicto` para **todos** los desenlaces del intento
        —`OK`, `NO_MATCH`, `TIEMPO_AGOTADO`, `CALIDAD_INSUFICIENTE`,
        `CAPTURA_FALLIDA`—, porque todos deben quedar en la bitácora: una
        bitácora de solo éxitos no demuestra que el control discrimine.

        Lanza únicamente ante fallos de infraestructura (`LectorNoDisponible`,
        `ErrorBiometrico`), que no son resultados de la persona y no se
        registran como intentos suyos.
        """

    @abstractmethod
    def buscar(
        self,
        plantillas: Mapping[str, Plantilla],
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Coincidencia | None:
        """Búsqueda 1:N. Devuelve `None` si el dedo no está en el conjunto.

        Se usa en el enrolamiento para detectar que una persona ya fue
        registrada bajo otra identidad. Es la capacidad que justifica tener la
        plantilla en custodia propia.
        """

    # -- Ciclo de vida -----------------------------------------------------

    @abstractmethod
    def cerrar(self) -> None:
        """Libera el lector y los recursos del SDK. Debe ser idempotente."""

    def __enter__(self) -> "ProveedorBiometrico":
        return self

    def __exit__(self, *_excepcion: object) -> None:
        self.cerrar()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} tipo={self.tipo} probatorio={self.es_probatorio}>"
