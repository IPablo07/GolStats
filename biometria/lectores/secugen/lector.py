"""Controlador de los lectores SecuGen. Implementa `LectorHardware`.

Es el único archivo específico del fabricante con lógica. Todo lo demás
—política de enrolamiento, umbrales, normalización de scores— vive en
`ProveedorHardware`, que no sabe que SecuGen existe.

Responsabilidades:

1. Orquestar el ciclo de vida del SDK: crear, inicializar, abrir, fijar el
   formato de plantilla, consultar el dispositivo.
2. Traducir los códigos de error del SDK a las excepciones del dominio.
3. **Descartar la imagen del dedo** antes de devolver la captura.
4. Validar que los datos del dispositivo sean plausibles, para que una
   disposición de struct equivocada se detecte de inmediato y no produzca
   comportamiento errático.
"""

from __future__ import annotations

from ...contratos import (
    CapturaFallida,
    Dedo,
    LectorNoDisponible,
    TiempoAgotado,
)
from ..base import CapturaHardware, DiagnosticoHardware, InfoLector, LectorHardware
from . import modelos
from .constantes import (
    CODIGOS_TIEMPO_AGOTADO,
    FABRICANTE,
    FORMATO_PROYECTO,
    NOMBRES_FORMATO,
    RANGO_SCORE_PRESUNTO,
    SG_DEVICE_AUTO_DETECT,
)
from .enlace import EnlaceCtypes, EnlaceSecuGen, ErrorSDKSecuGen, InfoDispositivoSDK

#: Rangos con los que se valida la respuesta de `SGFPM_GetDeviceInfo`. Un struct
#: mal alineado devuelve valores fuera de estos límites, y así el fallo aparece
#: en el diagnóstico en lugar de manifestarse como capturas corruptas.
LIMITES_PLAUSIBLES = {
    "ancho": (16, 4096),
    "alto": (16, 4096),
    "dpi": (100, 4000),
    "tamano_plantilla": (16, 262_144),
}


class LectorSecuGen(LectorHardware):
    """Lector SecuGen sobre el FDx SDK Pro.

    Sirve para toda la familia: el modelo solo determina la constante de
    inicialización, y por omisión se usa la autodetección.
    """

    def __init__(
        self,
        *,
        modelo: modelos.ModeloSecuGen = modelos.AUTO,
        enlace: EnlaceSecuGen | None = None,
        rango_score: int = RANGO_SCORE_PRESUNTO,
        ruta_dll: str | None = None,
    ) -> None:
        self._modelo = modelo
        self._enlace = enlace if enlace is not None else EnlaceCtypes(ruta_dll)
        self._rango_score = rango_score
        self._manejador: int | None = None
        self._info_sdk: InfoDispositivoSDK | None = None
        self._tamano_plantilla = 0

    # -- Identidad ---------------------------------------------------------

    @property
    def clave(self) -> str:
        return self._modelo.clave

    @property
    def modelo(self) -> modelos.ModeloSecuGen:
        return self._modelo

    @property
    def esta_abierto(self) -> bool:
        return self._manejador is not None

    # -- Ciclo de vida -----------------------------------------------------

    def abrir(self) -> None:
        if self._manejador is not None:
            return

        manejador: int | None = None
        try:
            manejador = self._enlace.crear()
            self._enlace.init(manejador, self._modelo.constante_dispositivo)
            self._enlace.abrir(manejador, SG_DEVICE_AUTO_DETECT)
            self._enlace.fijar_formato_plantilla(manejador, FORMATO_PROYECTO)
            tamano = self._enlace.tamano_maximo_plantilla(manejador)
            info = self._enlace.info_dispositivo(manejador)
        except ErrorSDKSecuGen as error:
            if manejador is not None:
                self._liberar_silenciosamente(manejador)
            raise LectorNoDisponible(
                f"no se pudo abrir el lector {self._modelo.descripcion}: {error}"
            ) from error

        self._validar_plausibilidad(info, tamano)
        self._manejador = manejador
        self._info_sdk = info
        self._tamano_plantilla = tamano

    def cerrar(self) -> None:
        if self._manejador is None:
            return
        self._liberar_silenciosamente(self._manejador)
        self._manejador = None
        self._info_sdk = None
        self._tamano_plantilla = 0

    def _liberar_silenciosamente(self, manejador: int) -> None:
        """Libera dispositivo y SDK sin propagar fallos.

        `cerrar` tiene que ser seguro también después de un error de apertura,
        cuando puede que el dispositivo nunca se haya abierto.
        """
        for operacion in (
            self._enlace.cerrar_dispositivo,
            self._enlace.terminar,
        ):
            try:
                operacion(manejador)
            except ErrorSDKSecuGen:
                pass

    def _validar_plausibilidad(self, info: InfoDispositivoSDK, tamano: int) -> None:
        medidos = {
            "ancho": info.ancho,
            "alto": info.alto,
            "dpi": info.dpi,
            "tamano_plantilla": tamano,
        }
        for campo, valor in medidos.items():
            minimo, maximo = LIMITES_PLAUSIBLES[campo]
            if not minimo <= valor <= maximo:
                raise LectorNoDisponible(
                    f"el SDK reportó {campo}={valor}, fuera del rango plausible "
                    f"[{minimo}, {maximo}]. Es el síntoma de una disposición "
                    "incorrecta de SGDeviceInfoParam: coteje enlace.py contra el "
                    "sgfplib.h del SDK instalado."
                )

    # -- Información -------------------------------------------------------

    def info(self) -> InfoLector:
        sdk = self._exigir_info()
        return InfoLector(
            fabricante=FABRICANTE,
            modelo=(
                self._modelo.modelo
                if self._modelo.modelo != "AUTO"
                else f"autodetectado (id {sdk.device_id})"
            ),
            serie=sdk.serie,
            ancho=sdk.ancho,
            alto=sdk.alto,
            dpi=sdk.dpi,
            rango_score=self._rango_score,
            formato_plantilla=NOMBRES_FORMATO.get(FORMATO_PROYECTO, "desconocido"),
            version_sdk=self._enlace.identificacion(),
        )

    def sondear(self) -> DiagnosticoHardware:
        """Comprueba el SDK y el dispositivo sin lanzar nunca."""
        disponible_sdk, motivo = self._enlace.disponible()
        if not disponible_sdk:
            return DiagnosticoHardware(
                disponible=False,
                lectores=0,
                mensajes=(motivo,),
            )

        ya_estaba_abierto = self.esta_abierto
        try:
            self.abrir()
            info = self.info()
        except LectorNoDisponible as error:
            return DiagnosticoHardware(
                disponible=False,
                lectores=0,
                mensajes=(motivo, str(error)),
            )
        except Exception as error:  # noqa: BLE001 - frontera con SDK ajeno
            return DiagnosticoHardware(
                disponible=False,
                lectores=0,
                mensajes=(motivo, f"fallo inesperado del SDK: {error}"),
            )
        finally:
            if not ya_estaba_abierto and self.esta_abierto:
                # El sondeo no debe dejar el dispositivo tomado.
                self.cerrar()

        return DiagnosticoHardware(
            disponible=True,
            lectores=1,
            info=info,
            version_sdk=info.version_sdk,
            mensajes=(motivo,),
        )

    # -- Operaciones biométricas -------------------------------------------

    def capturar(self, dedo: Dedo, timeout_s: float) -> CapturaHardware:
        manejador = self._exigir_abierto()
        sdk = self._exigir_info()
        timeout_ms = max(0, int(timeout_s * 1000))

        try:
            # Umbral de calidad en 0: la decisión de rechazar por calidad es de
            # la aplicación, no del SDK, para que el intento quede registrado
            # con su calidad real en lugar de perderse como un error.
            imagen = self._enlace.capturar_imagen(
                manejador, timeout_ms, 0, sdk.ancho, sdk.alto
            )
            calidad = self._enlace.calidad_imagen(
                manejador, sdk.ancho, sdk.alto, imagen
            )
            plantilla = self._enlace.crear_plantilla(
                manejador, imagen, int(dedo), calidad, self._tamano_plantilla
            )
        except ErrorSDKSecuGen as error:
            if error.codigo in CODIGOS_TIEMPO_AGOTADO:
                raise TiempoAgotado(
                    f"no se apoyó el dedo en {timeout_s:.0f} s"
                ) from error
            raise CapturaFallida(f"falló la captura: {error}") from error
        finally:
            # La imagen no sale de este método ni se persiste jamás. Se suelta la
            # referencia de inmediato. No es borrado criptográfico —`bytes` es
            # inmutable—, pero garantiza que ninguna capa superior la reciba.
            imagen = None  # noqa: F841

        return CapturaHardware(plantilla=plantilla, calidad=calidad, dedo=dedo)

    def comparar(self, plantilla_a: bytes, plantilla_b: bytes) -> int:
        manejador = self._exigir_abierto()
        try:
            return self._enlace.score(manejador, plantilla_a, plantilla_b)
        except ErrorSDKSecuGen as error:
            raise CapturaFallida(f"falló la comparación: {error}") from error

    # -- Auxiliares --------------------------------------------------------

    def _exigir_abierto(self) -> int:
        if self._manejador is None:
            raise LectorNoDisponible("el lector no está abierto")
        return self._manejador

    def _exigir_info(self) -> InfoDispositivoSDK:
        if self._info_sdk is None:
            raise LectorNoDisponible("el lector no está abierto")
        return self._info_sdk
