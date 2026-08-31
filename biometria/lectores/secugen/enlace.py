"""Enlace con `sgfplib.dll`: la frontera con el código nativo.

Existe como clase abstracta a propósito. Todo el `ctypes` vive aquí y en ningún
otro lugar, así que `LectorSecuGen` es probable en su totalidad inyectando un
enlace falso. Sin esta costura, la única forma de probar el controlador sería
tener el lector conectado.

╔══════════════════════════════════════════════════════════════════════════════╗
║  Confirmado contra `sgfplib.h` del SDK v4.3.1:                               ║
║  · `SGDeviceInfoParam.DeviceSN` es un arreglo de 16 bytes, no un DWORD;       ║
║  · `SGFPM_GetImageEx(hFpm, buffer, time, dispWnd, quality)` — 5 parámetros.   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import ctypes
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .constantes import (
    DLL_PRINCIPAL,
    SGFDX_ERROR_NONE,
    describir_error,
)


class ErrorSDKSecuGen(Exception):
    """Una función del SDK devolvió un código distinto de cero."""

    def __init__(self, codigo: int, funcion: str) -> None:
        self.codigo = codigo
        self.funcion = funcion
        super().__init__(f"{funcion}: {describir_error(codigo)}")


@dataclass(frozen=True, slots=True)
class InfoDispositivoSDK:
    """Lo que devuelve `SGFPM_GetDeviceInfo`, ya en tipos de Python."""

    device_id: int
    serie: str | None
    ancho: int
    alto: int
    dpi: int
    brillo: int
    contraste: int
    ganancia: int
    version_fw: int


# ---------------------------------------------------------------------------
# Contrato del enlace
# ---------------------------------------------------------------------------


class EnlaceSecuGen(ABC):
    """Operaciones del SDK que necesita el controlador.

    Cada método lanza `ErrorSDKSecuGen` si el SDK devuelve un código distinto de
    `SGFDX_ERROR_NONE`. La traducción a las excepciones del dominio la hace
    `LectorSecuGen`, no este enlace: aquí solo se cruza la frontera nativa.
    """

    @abstractmethod
    def disponible(self) -> tuple[bool, str]:
        """`(disponible, motivo)`. Nunca lanza: lo consume el preflight."""

    @abstractmethod
    def identificacion(self) -> str | None:
        """Identificación de la biblioteca cargada, para la bitácora."""

    @abstractmethod
    def crear(self) -> int: ...

    @abstractmethod
    def init(self, manejador: int, dispositivo: int) -> None: ...

    @abstractmethod
    def abrir(self, manejador: int, id_dispositivo: int) -> None: ...

    @abstractmethod
    def cerrar_dispositivo(self, manejador: int) -> None: ...

    @abstractmethod
    def terminar(self, manejador: int) -> None: ...

    @abstractmethod
    def info_dispositivo(self, manejador: int) -> InfoDispositivoSDK: ...

    @abstractmethod
    def fijar_formato_plantilla(self, manejador: int, formato: int) -> None: ...

    @abstractmethod
    def tamano_maximo_plantilla(self, manejador: int) -> int: ...

    @abstractmethod
    def capturar_imagen(
        self,
        manejador: int,
        timeout_ms: int,
        calidad_umbral: int,
        ancho: int,
        alto: int,
    ) -> bytes:
        """Espera el dedo y devuelve la imagen cruda en escala de grises."""

    @abstractmethod
    def calidad_imagen(
        self, manejador: int, ancho: int, alto: int, imagen: bytes
    ) -> int: ...

    @abstractmethod
    def crear_plantilla(
        self,
        manejador: int,
        imagen: bytes,
        numero_dedo: int,
        calidad: int,
        tamano_maximo: int,
    ) -> bytes: ...

    @abstractmethod
    def score(self, manejador: int, plantilla_a: bytes, plantilla_b: bytes) -> int:
        """Score crudo de la comparación, en la escala nativa del SDK."""


# ---------------------------------------------------------------------------
# Estructuras nativas
# ---------------------------------------------------------------------------


class SGDeviceInfoParam(ctypes.Structure):
    """`SGDeviceInfoParam` de sgfplib.h. Confirmado contra el SDK v4.3.1."""

    _fields_ = [
        ("DeviceID", ctypes.c_uint32),
        ("DeviceSN", ctypes.c_ubyte * 16),
        ("ComPort", ctypes.c_uint32),
        ("ComSpeed", ctypes.c_uint32),
        ("ImageWidth", ctypes.c_uint32),
        ("ImageHeight", ctypes.c_uint32),
        ("Contrast", ctypes.c_uint32),
        ("Brightness", ctypes.c_uint32),
        ("Gain", ctypes.c_uint32),
        ("ImageDPI", ctypes.c_uint32),
        ("FWVersion", ctypes.c_uint32),
    ]


class SGFingerInfo(ctypes.Structure):
    """`SGFingerInfo` de sgfplib.h."""

    _fields_ = [
        ("FingerNumber", ctypes.c_uint16),
        ("ViewNumber", ctypes.c_uint16),
        ("ImageQuality", ctypes.c_uint16),
        ("ImpressionType", ctypes.c_uint16),
        ("ViewCount", ctypes.c_uint16),
    ]


#: Tipo de huella: 0 = "live scan, plain", el que corresponde a un lector óptico
#: de contacto como el Hamster Plus.
IMPRESSION_LIVE_SCAN_PLAIN = 0


# ---------------------------------------------------------------------------
# Implementación sobre ctypes
# ---------------------------------------------------------------------------


class EnlaceCtypes(EnlaceSecuGen):
    """Enlace real con `sgfplib.dll`.

    La biblioteca se carga de forma diferida: construir el objeto nunca falla,
    de modo que el preflight pueda preguntar por su disponibilidad sin riesgo.
    """

    def __init__(self, ruta_dll: str | None = None) -> None:
        self._ruta_dll = ruta_dll or DLL_PRINCIPAL
        self._lib: ctypes.WinDLL | None = None
        self._motivo_fallo: str | None = None

    # -- Carga -------------------------------------------------------------

    def _cargar(self) -> ctypes.WinDLL:
        if self._lib is not None:
            return self._lib
        if not hasattr(ctypes, "WinDLL"):
            self._motivo_fallo = "el SDK de SecuGen solo existe para Windows"
            raise ErrorSDKSecuGen(-1, "carga de biblioteca")
        try:
            lib = ctypes.WinDLL(self._ruta_dll)
        except OSError as error:
            self._motivo_fallo = (
                f"no se pudo cargar {self._ruta_dll}: {error}. "
                "Instale el FDx SDK Pro de SecuGen y su driver, o copie "
                "sgfplib.dll junto a la aplicación."
            )
            raise ErrorSDKSecuGen(-1, "carga de biblioteca") from error
        self._declarar_firmas(lib)
        self._lib = lib
        return lib

    @staticmethod
    def _declarar_firmas(lib: ctypes.WinDLL) -> None:
        """Fija los tipos de argumento y retorno de cada función usada.

        Declararlos evita que un puntero de 64 bits se truncte a 32, que es la
        causa más común de fallos erráticos al usar ctypes en Windows x64.
        """
        c_ulong = ctypes.c_ulong
        c_void_p = ctypes.c_void_p

        lib.SGFPM_Create.argtypes = [ctypes.POINTER(c_void_p)]
        lib.SGFPM_Create.restype = c_ulong

        lib.SGFPM_Init.argtypes = [c_void_p, c_ulong]
        lib.SGFPM_Init.restype = c_ulong

        lib.SGFPM_OpenDevice.argtypes = [c_void_p, c_ulong]
        lib.SGFPM_OpenDevice.restype = c_ulong

        lib.SGFPM_CloseDevice.argtypes = [c_void_p]
        lib.SGFPM_CloseDevice.restype = c_ulong

        lib.SGFPM_Terminate.argtypes = [c_void_p]
        lib.SGFPM_Terminate.restype = c_ulong

        lib.SGFPM_GetDeviceInfo.argtypes = [c_void_p, ctypes.POINTER(SGDeviceInfoParam)]
        lib.SGFPM_GetDeviceInfo.restype = c_ulong

        lib.SGFPM_SetTemplateFormat.argtypes = [c_void_p, ctypes.c_uint16]
        lib.SGFPM_SetTemplateFormat.restype = c_ulong

        lib.SGFPM_GetMaxTemplateSize.argtypes = [c_void_p, ctypes.POINTER(c_ulong)]
        lib.SGFPM_GetMaxTemplateSize.restype = c_ulong

        lib.SGFPM_GetImageEx.argtypes = [
            c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            c_ulong,
            c_void_p,
            c_ulong,
        ]
        lib.SGFPM_GetImageEx.restype = c_ulong

        lib.SGFPM_GetImageQuality.argtypes = [
            c_void_p,
            c_ulong,
            c_ulong,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(c_ulong),
        ]
        lib.SGFPM_GetImageQuality.restype = c_ulong

        lib.SGFPM_CreateTemplate.argtypes = [
            c_void_p,
            ctypes.POINTER(SGFingerInfo),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
        ]
        lib.SGFPM_CreateTemplate.restype = c_ulong

        lib.SGFPM_GetMatchingScore.argtypes = [
            c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(c_ulong),
        ]
        lib.SGFPM_GetMatchingScore.restype = c_ulong

    @staticmethod
    def _exigir(codigo: int, funcion: str) -> None:
        if codigo != SGFDX_ERROR_NONE:
            raise ErrorSDKSecuGen(codigo, funcion)

    # -- Contrato ----------------------------------------------------------

    def disponible(self) -> tuple[bool, str]:
        try:
            self._cargar()
        except ErrorSDKSecuGen:
            return False, self._motivo_fallo or "no se pudo cargar el SDK"
        return True, f"{self._ruta_dll} cargada"

    def identificacion(self) -> str | None:
        return self._ruta_dll if self._lib is not None else None

    def crear(self) -> int:
        lib = self._cargar()
        manejador = ctypes.c_void_p()
        self._exigir(lib.SGFPM_Create(ctypes.byref(manejador)), "SGFPM_Create")
        if not manejador.value:
            raise ErrorSDKSecuGen(-1, "SGFPM_Create devolvió un manejador nulo")
        return int(manejador.value)

    def init(self, manejador: int, dispositivo: int) -> None:
        lib = self._cargar()
        self._exigir(
            lib.SGFPM_Init(ctypes.c_void_p(manejador), dispositivo), "SGFPM_Init"
        )

    def abrir(self, manejador: int, id_dispositivo: int) -> None:
        lib = self._cargar()
        self._exigir(
            lib.SGFPM_OpenDevice(ctypes.c_void_p(manejador), id_dispositivo),
            "SGFPM_OpenDevice",
        )

    def cerrar_dispositivo(self, manejador: int) -> None:
        lib = self._cargar()
        self._exigir(
            lib.SGFPM_CloseDevice(ctypes.c_void_p(manejador)), "SGFPM_CloseDevice"
        )

    def terminar(self, manejador: int) -> None:
        lib = self._cargar()
        self._exigir(
            lib.SGFPM_Terminate(ctypes.c_void_p(manejador)), "SGFPM_Terminate"
        )

    def info_dispositivo(self, manejador: int) -> InfoDispositivoSDK:
        lib = self._cargar()
        crudo = SGDeviceInfoParam()
        self._exigir(
            lib.SGFPM_GetDeviceInfo(ctypes.c_void_p(manejador), ctypes.byref(crudo)),
            "SGFPM_GetDeviceInfo",
        )
        numero_serie = bytes(crudo.DeviceSN).rstrip(b"\x00").decode("ascii", errors="replace")
        return InfoDispositivoSDK(
            device_id=int(crudo.DeviceID),
            serie=numero_serie or None,
            ancho=int(crudo.ImageWidth),
            alto=int(crudo.ImageHeight),
            dpi=int(crudo.ImageDPI),
            brillo=int(crudo.Brightness),
            contraste=int(crudo.Contrast),
            ganancia=int(crudo.Gain),
            version_fw=int(crudo.FWVersion),
        )

    def fijar_formato_plantilla(self, manejador: int, formato: int) -> None:
        lib = self._cargar()
        self._exigir(
            lib.SGFPM_SetTemplateFormat(ctypes.c_void_p(manejador), formato),
            "SGFPM_SetTemplateFormat",
        )

    def tamano_maximo_plantilla(self, manejador: int) -> int:
        lib = self._cargar()
        tamano = ctypes.c_ulong(0)
        self._exigir(
            lib.SGFPM_GetMaxTemplateSize(
                ctypes.c_void_p(manejador), ctypes.byref(tamano)
            ),
            "SGFPM_GetMaxTemplateSize",
        )
        return int(tamano.value)

    def capturar_imagen(
        self,
        manejador: int,
        timeout_ms: int,
        calidad_umbral: int,
        ancho: int,
        alto: int,
    ) -> bytes:
        lib = self._cargar()
        bufer = (ctypes.c_ubyte * (ancho * alto))()
        self._exigir(
            lib.SGFPM_GetImageEx(
                ctypes.c_void_p(manejador),
                bufer,
                timeout_ms,
                None,  # hWnd: sin ventana, no queremos mensajes de Windows
                calidad_umbral,
            ),
            "SGFPM_GetImageEx",
        )
        return bytes(bufer)

    def calidad_imagen(
        self, manejador: int, ancho: int, alto: int, imagen: bytes
    ) -> int:
        lib = self._cargar()
        bufer = (ctypes.c_ubyte * len(imagen)).from_buffer_copy(imagen)
        calidad = ctypes.c_ulong(0)
        self._exigir(
            lib.SGFPM_GetImageQuality(
                ctypes.c_void_p(manejador),
                ancho,
                alto,
                bufer,
                ctypes.byref(calidad),
            ),
            "SGFPM_GetImageQuality",
        )
        return int(calidad.value)

    def crear_plantilla(
        self,
        manejador: int,
        imagen: bytes,
        numero_dedo: int,
        calidad: int,
        tamano_maximo: int,
    ) -> bytes:
        lib = self._cargar()
        info = SGFingerInfo(
            FingerNumber=numero_dedo,
            ViewNumber=0,
            ImageQuality=calidad,
            ImpressionType=IMPRESSION_LIVE_SCAN_PLAIN,
            ViewCount=1,
        )
        bufer_imagen = (ctypes.c_ubyte * len(imagen)).from_buffer_copy(imagen)
        bufer_plantilla = (ctypes.c_ubyte * tamano_maximo)()
        self._exigir(
            lib.SGFPM_CreateTemplate(
                ctypes.c_void_p(manejador),
                ctypes.byref(info),
                bufer_imagen,
                bufer_plantilla,
            ),
            "SGFPM_CreateTemplate",
        )
        return bytes(bufer_plantilla)

    def score(self, manejador: int, plantilla_a: bytes, plantilla_b: bytes) -> int:
        lib = self._cargar()
        bufer_a = (ctypes.c_ubyte * len(plantilla_a)).from_buffer_copy(plantilla_a)
        bufer_b = (ctypes.c_ubyte * len(plantilla_b)).from_buffer_copy(plantilla_b)
        valor = ctypes.c_ulong(0)
        self._exigir(
            lib.SGFPM_GetMatchingScore(
                ctypes.c_void_p(manejador),
                bufer_a,
                bufer_b,
                ctypes.byref(valor),
            ),
            "SGFPM_GetMatchingScore",
        )
        return int(valor.value)