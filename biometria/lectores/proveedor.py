"""Proveedor sobre hardware real. **Reutilizable con cualquier lector.**

Esta clase es la razón de ser de la capa: contiene toda la política de
enrolamiento y verificación —reintentos, umbrales, normalización de scores,
consolidación de plantillas— y **ni una línea de código de fabricante**. Recibe
un `LectorHardware` y no sabe cuál es.

Soportar un lector nuevo no toca este archivo.

Dos decisiones que valen explicación
------------------------------------
**Consolidación por mejor-de-N con control de consistencia.** Los SDK de lector
crean una plantilla por imagen y no fusionan varias capturas. En lugar de quedarnos
con la última, se comparan todas contra todas y se elige la de mayor score
mediano. Eso además delata un enrolamiento inconsistente —típicamente alguien que
cambió de dedo a mitad del proceso—, que de otro modo produciría una identidad
que nunca vuelve a verificar.

**La búsqueda 1:N falla cerrada.** Si la captura falla durante la detección de
duplicados, se propaga la excepción en lugar de devolver `None`. Informar "no hay
duplicado" sin haber leído un dedo sería un fallo de seguridad: permitiría colar
un doble enrolamiento simplemente no apoyando el dedo.
"""

from __future__ import annotations

import statistics
import time
from datetime import datetime, timezone
from typing import Callable, Mapping, Sequence

from ..contratos import (
    CALIDAD_MINIMA,
    MUESTRAS_MINIMAS,
    CalidadInsuficiente,
    CapturaFallida,
    CodigoResultado,
    Coincidencia,
    Dedo,
    Diagnostico,
    Muestra,
    Plantilla,
    TiempoAgotado,
    TipoProveedor,
    Veredicto,
)
from ..proveedor import TIMEOUT_POR_OMISION_S, ProveedorBiometrico
from .base import ESCALA_SCORE, InfoLector, LectorHardware

#: Umbral de **verificación** en la escala normalizada 0-100. Es un parámetro de
#: control: hay que calibrarlo con el lector real y documentar el objetivo de
#: tasa de falsos aceptados antes de usar el sistema en producción.
UMBRAL_POR_OMISION = 40

#: Umbral de **consistencia del enrolamiento**, deliberadamente independiente del
#: anterior. Son dos decisiones distintas: una es cuán estrictos somos al
#: confirmar una identidad; la otra, cuán parecidas deben ser entre sí varias
#: capturas del mismo dedo. Acoplarlas haría que endurecer la verificación
#: impidiera enrolar, que es justo lo contrario de lo que se busca.
#: Un valor de 0 desactiva la comprobación.
UMBRAL_CONSISTENCIA_POR_OMISION = 40


def _reloj_utc() -> datetime:
    return datetime.now(timezone.utc)


class ProveedorHardware(ProveedorBiometrico):
    """Implementa `ProveedorBiometrico` sobre cualquier `LectorHardware`."""

    def __init__(
        self,
        lector: LectorHardware,
        *,
        umbral: int = UMBRAL_POR_OMISION,
        umbral_consistencia: int = UMBRAL_CONSISTENCIA_POR_OMISION,
        calidad_minima: int = CALIDAD_MINIMA,
        reloj: Callable[[], datetime] = _reloj_utc,
    ) -> None:
        if not 0 < umbral <= ESCALA_SCORE:
            raise ValueError(f"umbral fuera de la escala 1-{ESCALA_SCORE}: {umbral}")
        if not 0 <= umbral_consistencia <= ESCALA_SCORE:
            raise ValueError(
                f"umbral de consistencia fuera de la escala 0-{ESCALA_SCORE}: "
                f"{umbral_consistencia}"
            )
        self._lector = lector
        self._umbral = umbral
        self._umbral_consistencia = umbral_consistencia
        self._calidad_minima = calidad_minima
        self._reloj = reloj
        self._info: InfoLector | None = None

    # -- Identidad ---------------------------------------------------------

    @property
    def tipo(self) -> TipoProveedor:
        return TipoProveedor.EXTERNO

    @property
    def nombre(self) -> str:
        if self._info is not None:
            return self._info.descripcion
        return f"Lector externo ({self._lector.clave})"

    @property
    def umbral(self) -> int:
        return self._umbral

    @property
    def umbral_consistencia(self) -> int:
        return self._umbral_consistencia

    @property
    def lector(self) -> LectorHardware:
        return self._lector

    # -- Diagnóstico -------------------------------------------------------

    def diagnostico(self) -> Diagnostico:
        """Delega en el lector y **nunca lanza**, ni ante un SDK que falle mal.

        El preflight depende de esto: un SDK de terceros puede lanzar cualquier
        cosa, y una excepción aquí dejaría la aplicación sin pantalla inicial.
        """
        try:
            sondeo = self._lector.sondear()
        except Exception as error:  # noqa: BLE001 - frontera con SDK ajeno
            return Diagnostico(
                proveedor=self.tipo,
                disponible=False,
                lectores=0,
                mensajes=(
                    f"El sondeo del lector {self._lector.clave} falló: {error}",
                ),
            )

        if sondeo.info is not None:
            self._info = sondeo.info

        mensajes = list(sondeo.mensajes)
        if sondeo.info is not None:
            mensajes.append(
                f"{sondeo.info.descripcion} — {sondeo.info.ancho}×{sondeo.info.alto} "
                f"a {sondeo.info.dpi} ppp, plantillas {sondeo.info.formato_plantilla}"
            )
            if sondeo.info.serie:
                mensajes.append(f"Número de serie: {sondeo.info.serie}")
        mensajes.append(f"Umbral configurado: {self._umbral}/{ESCALA_SCORE}")

        return Diagnostico(
            proveedor=self.tipo,
            disponible=sondeo.disponible,
            lectores=sondeo.lectores,
            version_sdk=sondeo.version_sdk,
            mensajes=tuple(mensajes),
        )

    # -- Enrolamiento ------------------------------------------------------

    def capturar_muestra(
        self,
        dedo: Dedo,
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Muestra:
        self._asegurar_abierto()
        captura = self._lector.capturar(dedo, timeout_s)
        if captura.calidad < self._calidad_minima:
            raise CalidadInsuficiente(
                f"calidad {captura.calidad} por debajo del mínimo "
                f"{self._calidad_minima}"
            )
        return Muestra(
            datos=captura.plantilla,
            calidad=captura.calidad,
            dedo=captura.dedo,
            capturada_en=self._reloj(),
            proveedor=self.tipo,
        )

    def crear_plantilla(self, muestras: Sequence[Muestra]) -> Plantilla:
        self._asegurar_abierto()
        self._validar_muestras(muestras)

        elegida, mediana = self._elegir_mejor_muestra(muestras)
        if mediana < self._umbral_consistencia:
            raise ValueError(
                f"enrolamiento inconsistente: las capturas no concuerdan entre sí "
                f"(mejor score mediano {mediana}, umbral de consistencia "
                f"{self._umbral_consistencia}). Verifique que todas las capturas "
                "sean del mismo dedo y repita."
            )

        info = self._exigir_info()
        return Plantilla(
            datos=elegida.datos,
            formato=info.formato_plantilla,
            dedo=elegida.dedo,
            calidad=elegida.calidad,
            proveedor=self.tipo,
            muestras_usadas=len(muestras),
        )

    def _validar_muestras(self, muestras: Sequence[Muestra]) -> None:
        if len(muestras) < MUESTRAS_MINIMAS:
            raise ValueError(
                f"se requieren al menos {MUESTRAS_MINIMAS} muestras, "
                f"se recibieron {len(muestras)}"
            )
        dedos = {m.dedo for m in muestras}
        if len(dedos) != 1:
            raise ValueError(f"las muestras deben ser del mismo dedo, se vieron {dedos}")
        inutilizables = [m for m in muestras if m.calidad < self._calidad_minima]
        if inutilizables:
            raise ValueError(
                f"{len(inutilizables)} muestra(s) por debajo de la calidad mínima"
            )

    def _elegir_mejor_muestra(
        self, muestras: Sequence[Muestra]
    ) -> tuple[Muestra, int]:
        """Devuelve la muestra más representativa y su score mediano."""
        mejor: Muestra = muestras[0]
        mejor_mediana = -1
        for candidata in muestras:
            scores = [
                self._normalizar(
                    self._lector.comparar(candidata.datos, otra.datos)
                )
                for otra in muestras
                if otra is not candidata
            ]
            mediana = int(statistics.median(scores)) if scores else 0
            if mediana > mejor_mediana:
                mejor, mejor_mediana = candidata, mediana
        return mejor, mejor_mediana

    # -- Verificación ------------------------------------------------------

    def verificar(
        self,
        plantilla: Plantilla,
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Veredicto:
        self._asegurar_abierto()
        inicio = time.perf_counter()

        try:
            captura = self._lector.capturar(plantilla.dedo, timeout_s)
        except TiempoAgotado:
            return self._veredicto_fallido(
                CodigoResultado.TIEMPO_AGOTADO, inicio, calidad=0
            )
        except CalidadInsuficiente:
            return self._veredicto_fallido(
                CodigoResultado.CALIDAD_INSUFICIENTE, inicio, calidad=0
            )
        except CapturaFallida:
            return self._veredicto_fallido(
                CodigoResultado.CAPTURA_FALLIDA, inicio, calidad=0
            )

        if captura.calidad < self._calidad_minima:
            return self._veredicto_fallido(
                CodigoResultado.CALIDAD_INSUFICIENTE, inicio, calidad=captura.calidad
            )

        score = self._normalizar(
            self._lector.comparar(plantilla.datos, captura.plantilla)
        )
        coincide = score >= self._umbral
        return Veredicto(
            coincide=coincide,
            codigo=CodigoResultado.OK if coincide else CodigoResultado.NO_MATCH,
            score=score,
            umbral=self._umbral,
            calidad=captura.calidad,
            duracion_ms=self._transcurrido(inicio),
            proveedor=self.tipo,
            nivel=self.nivel,
        )

    def buscar(
        self,
        plantillas: Mapping[str, Plantilla],
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Coincidencia | None:
        self._asegurar_abierto()
        inicio = time.perf_counter()

        # Falla cerrada a propósito: si no se pudo leer un dedo, no se puede
        # afirmar que no haya duplicado. La excepción sube y el llamador repite.
        captura = self._lector.capturar(Dedo.DESCONOCIDO, timeout_s)

        mejor_referencia: str | None = None
        mejor_score = -1
        for referencia, candidata in plantillas.items():
            score = self._normalizar(
                self._lector.comparar(candidata.datos, captura.plantilla)
            )
            if score > mejor_score:
                mejor_referencia, mejor_score = referencia, score

        if mejor_referencia is None or mejor_score < self._umbral:
            return None
        return Coincidencia(
            referencia=mejor_referencia,
            score=mejor_score,
            umbral=self._umbral,
            duracion_ms=self._transcurrido(inicio),
            proveedor=self.tipo,
            nivel=self.nivel,
        )

    # -- Ciclo de vida -----------------------------------------------------

    def cerrar(self) -> None:
        self._lector.cerrar()

    # -- Auxiliares --------------------------------------------------------

    def _asegurar_abierto(self) -> None:
        if not self._lector.esta_abierto:
            self._lector.abrir()
        if self._info is None:
            self._info = self._lector.info()

    def _exigir_info(self) -> InfoLector:
        if self._info is None:
            self._info = self._lector.info()
        return self._info

    def _normalizar(self, score_bruto: int) -> int:
        """Traduce el score nativo del SDK a la escala 0-100.

        Es lo que permite que el umbral configurado signifique lo mismo con
        cualquier lector, y que cambiar de hardware no invalide la calibración.
        """
        rango = self._exigir_info().rango_score
        if rango <= 0:
            raise ValueError(f"el lector declara un rango de score inválido: {rango}")
        normalizado = round(score_bruto * ESCALA_SCORE / rango)
        return max(0, min(ESCALA_SCORE, normalizado))

    def _veredicto_fallido(
        self,
        codigo: CodigoResultado,
        inicio: float,
        *,
        calidad: int,
    ) -> Veredicto:
        return Veredicto(
            coincide=False,
            codigo=codigo,
            score=0,
            umbral=self._umbral,
            calidad=calidad,
            duracion_ms=self._transcurrido(inicio),
            proveedor=self.tipo,
            nivel=self.nivel,
        )

    @staticmethod
    def _transcurrido(inicio: float) -> int:
        return int((time.perf_counter() - inicio) * 1000)
