"""Contrato de bajo nivel del hardware. Neutral al fabricante.

Separa dos responsabilidades que suelen mezclarse:

- `LectorHardware` — habla con **un** modelo de lector. Es lo único que hay que
  escribir para soportar un lector nuevo.
- `ProveedorHardware` (en `proveedor.py`) — implementa toda la política de
  enrolamiento y verificación sobre *cualquier* `LectorHardware`, sin conocer al
  fabricante.

Garantía estructural: **la imagen del dedo nunca cruza esta frontera.**
`capturar` devuelve la plantilla derivada y su calidad; la imagen se crea, se
usa y se descarta dentro de la implementación. Así el resto del sistema no puede
persistir una imagen ni siquiera por error, que es la exigencia del diseño de
protección de datos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..contratos import Dedo

#: Escala normalizada a la que se traducen todos los scores, sea cual sea el
#: rango nativo del SDK. Permite que el umbral de la aplicación sea el mismo
#: número con cualquier lector.
ESCALA_SCORE = 100


@dataclass(frozen=True, slots=True)
class InfoLector:
    """Identificación y características del lector conectado.

    `rango_score` es el máximo que devuelve `comparar` en la escala nativa del
    SDK. `ProveedorHardware` lo usa para normalizar a `ESCALA_SCORE`, de modo que
    el umbral configurado signifique lo mismo con cualquier hardware.
    """

    fabricante: str
    modelo: str
    serie: str | None
    ancho: int
    alto: int
    dpi: int
    rango_score: int
    formato_plantilla: str
    version_sdk: str | None = None

    @property
    def descripcion(self) -> str:
        return f"{self.fabricante} {self.modelo}"


@dataclass(frozen=True, slots=True)
class CapturaHardware:
    """Resultado de una captura: plantilla y calidad. Nunca la imagen."""

    plantilla: bytes
    calidad: int
    dedo: Dedo


@dataclass(frozen=True, slots=True)
class DiagnosticoHardware:
    """Sondeo no destructivo del lector. Nunca lanza."""

    disponible: bool
    lectores: int
    info: InfoLector | None = None
    version_sdk: str | None = None
    mensajes: tuple[str, ...] = field(default_factory=tuple)


class LectorHardware(ABC):
    """Contrato que debe implementar cada familia de lector.

    Para soportar un modelo nuevo basta con una subclase de esta clase y una
    entrada en el registro. Ni `ProveedorHardware` ni las pantallas cambian.
    """

    # -- Identidad ---------------------------------------------------------

    @property
    @abstractmethod
    def clave(self) -> str:
        """Identificador del registro, p. ej. ``secugen:hsdu03p``."""

    # -- Ciclo de vida -----------------------------------------------------

    @abstractmethod
    def abrir(self) -> None:
        """Inicializa el SDK y toma el dispositivo. Idempotente.

        Lanza `LectorNoDisponible` si no hay SDK, driver o dispositivo.
        """

    @abstractmethod
    def cerrar(self) -> None:
        """Libera dispositivo y SDK. Idempotente y seguro tras un fallo."""

    @property
    @abstractmethod
    def esta_abierto(self) -> bool: ...

    # -- Información -------------------------------------------------------

    @abstractmethod
    def info(self) -> InfoLector:
        """Características del dispositivo. Requiere estar abierto."""

    @abstractmethod
    def sondear(self) -> DiagnosticoHardware:
        """Comprueba disponibilidad **sin lanzar**, para el preflight.

        Debe funcionar con el lector desconectado y con el SDK ausente: en esos
        casos informa `disponible=False` y explica por qué en `mensajes`.
        """

    # -- Operaciones biométricas -------------------------------------------

    @abstractmethod
    def capturar(self, dedo: Dedo, timeout_s: float) -> CapturaHardware:
        """Espera el dedo y devuelve su plantilla y calidad.

        La imagen se descarta antes de retornar. Lanza `TiempoAgotado`,
        `CalidadInsuficiente` o `CapturaFallida`.
        """

    @abstractmethod
    def comparar(self, plantilla_a: bytes, plantilla_b: bytes) -> int:
        """Compara dos plantillas y devuelve el score en la escala nativa.

        No decide si coinciden: el umbral es política de la aplicación, no del
        controlador. Devolver el score crudo es lo que permite auditar y
        recalibrar sin tocar esta capa.
        """

    # -- Azúcar ------------------------------------------------------------

    def __enter__(self) -> "LectorHardware":
        self.abrir()
        return self

    def __exit__(self, *_excepcion: object) -> None:
        self.cerrar()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} clave={self.clave} abierto={self.esta_abierto}>"
