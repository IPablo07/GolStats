"""Proveedor simulado: mock determinista y guionable del subsistema biométrico.

Existe por dos razones, y ninguna es "no tener hardware todavía":

1. Permite ejercitar el 100 % de la lógica de negocio —nóminas, asistencia,
   acta, tarjetas, cadena de hash, firmas y recibos— **sin datos biométricos de
   ninguna persona real**.
2. Permite provocar a voluntad los desenlaces que un lector real no deja
   reproducir de forma confiable: no-match, tiempo agotado, calidad
   insuficiente, doble enrolamiento.

No usa `random`: todos los valores derivan por hash de sus entradas, de modo que
una misma corrida produce siempre los mismos scores. Las pruebas pueden afirmar
sobre valores concretos.

Sus resultados **nunca** son probatorios: `TipoProveedor.SIMULADO.es_probatorio`
es `False` y no hay forma de sobrescribirlo desde aquí.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping, Sequence

from .contratos import (
    CALIDAD_MINIMA,
    FORMATO_ISO_19794_2,
    MUESTRAS_MINIMAS,
    CalidadInsuficiente,
    CapturaFallida,
    CodigoResultado,
    Coincidencia,
    Dedo,
    Diagnostico,
    LectorNoDisponible,
    Muestra,
    Plantilla,
    TiempoAgotado,
    TipoProveedor,
    Veredicto,
)
from .proveedor import TIMEOUT_POR_OMISION_S, ProveedorBiometrico

#: Marca que llevan los datos sintéticos. Hace imposible confundir una plantilla
#: simulada con una real al inspeccionar la base de datos.
MARCA_SIMULADO = b"SIMULADO:"

#: Umbral de coincidencia por omisión, en la escala 0-100.
UMBRAL_POR_OMISION = 40

#: Calidad que reporta el sensor simulado cuando el guion no dice otra cosa.
CALIDAD_POR_OMISION = 82


@dataclass(frozen=True, slots=True)
class ReglaSimulada:
    """Desenlace que el guion impone para una referencia dada.

    Los campos en `None` se resuelven con el comportamiento por omisión del
    proveedor. `veces` limita cuántas operaciones consume la regla: sirve para
    guionar "falla dos veces y luego funciona", que es el caso realista de una
    persona que apoya mal el dedo.
    """

    codigo: CodigoResultado = CodigoResultado.OK
    score: int | None = None
    calidad: int | None = None
    latencia_ms: int | None = None
    veces: int | None = None


@dataclass(frozen=True, slots=True)
class OperacionRegistrada:
    """Entrada del historial, para que las pruebas afirmen sobre lo ocurrido."""

    operacion: str
    referencia: str | None
    codigo: CodigoResultado
    score: int


def _reloj_utc() -> datetime:
    return datetime.now(timezone.utc)


def _pseudo(semilla: bytes, minimo: int, maximo: int) -> int:
    """Entero determinista en `[minimo, maximo]` derivado de `semilla`.

    Reemplaza a `random` para que el mock sea reproducible entre corridas.
    """
    if minimo > maximo:
        raise ValueError(f"rango inválido: [{minimo}, {maximo}]")
    digest = hashlib.blake2b(semilla, digest_size=8).digest()
    return minimo + int.from_bytes(digest, "big") % (maximo - minimo + 1)


class SimuladoProvider(ProveedorBiometrico):
    """Implementación de `ProveedorBiometrico` sin hardware.

    El guion se indexa por `Plantilla.referencia`, es decir por la identidad
    contra la que se verifica. Una referencia ausente del guion se comporta como
    un caso feliz.
    """

    def __init__(
        self,
        *,
        guion: Mapping[str, ReglaSimulada] | None = None,
        coincidencia_en_busqueda: str | None = None,
        umbral: int = UMBRAL_POR_OMISION,
        calidad_por_omision: int = CALIDAD_POR_OMISION,
        latencia_ms: int = 0,
        lectores: int = 1,
        disponible: bool = True,
        reloj: Callable[[], datetime] = _reloj_utc,
    ) -> None:
        self._guion: dict[str, ReglaSimulada] = dict(guion or {})
        self._consumos: dict[str, int] = {}
        self._coincidencia_en_busqueda = coincidencia_en_busqueda
        self._umbral = umbral
        self._calidad_por_omision = calidad_por_omision
        self._latencia_ms = latencia_ms
        self._lectores = lectores
        self._disponible = disponible
        self._reloj = reloj
        self._cerrado = False
        self._historial: list[OperacionRegistrada] = []

    # -- Identidad ---------------------------------------------------------

    @property
    def tipo(self) -> TipoProveedor:
        return TipoProveedor.SIMULADO

    @property
    def nombre(self) -> str:
        return "Lector simulado (sin hardware)"

    @property
    def umbral(self) -> int:
        return self._umbral

    @property
    def historial(self) -> tuple[OperacionRegistrada, ...]:
        """Operaciones ejecutadas, en orden. Solo para pruebas y diagnóstico."""
        return tuple(self._historial)

    # -- Guion -------------------------------------------------------------

    def guionar(self, referencia: str, regla: ReglaSimulada) -> None:
        """Instala o reemplaza la regla de una referencia y reinicia su consumo."""
        self._guion[referencia] = regla
        self._consumos.pop(referencia, None)

    def _regla_para(self, referencia: str | None) -> ReglaSimulada | None:
        if referencia is None:
            return None
        regla = self._guion.get(referencia)
        if regla is None:
            return None
        if regla.veces is None:
            return regla
        usadas = self._consumos.get(referencia, 0)
        if usadas >= regla.veces:
            return None
        self._consumos[referencia] = usadas + 1
        return regla

    # -- Diagnóstico -------------------------------------------------------

    def diagnostico(self) -> Diagnostico:
        mensajes = [
            "Proveedor simulado activo: los resultados NO tienen valor probatorio.",
        ]
        if self._guion:
            mensajes.append(f"Guion cargado con {len(self._guion)} regla(s).")
        if self._cerrado:
            mensajes.append("El proveedor ya fue cerrado.")
        return Diagnostico(
            proveedor=self.tipo,
            disponible=self._disponible and not self._cerrado,
            lectores=self._lectores if self._disponible else 0,
            version_sdk="simulado-1.0",
            mensajes=tuple(mensajes),
        )

    # -- Enrolamiento ------------------------------------------------------

    def capturar_muestra(
        self,
        dedo: Dedo,
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Muestra:
        self._exigir_operativo()
        referencia = f"captura:{int(dedo)}"
        regla = self._regla_para(referencia)
        self._dormir(regla)

        codigo = regla.codigo if regla else CodigoResultado.OK
        calidad = self._resolver_calidad(regla, semilla=referencia.encode())

        if codigo is CodigoResultado.TIEMPO_AGOTADO:
            self._anotar("capturar_muestra", referencia, codigo, 0)
            raise TiempoAgotado(f"no se apoyó el dedo en {timeout_s:.0f} s")
        if codigo is CodigoResultado.CALIDAD_INSUFICIENTE or calidad < CALIDAD_MINIMA:
            self._anotar(
                "capturar_muestra", referencia, CodigoResultado.CALIDAD_INSUFICIENTE, 0
            )
            raise CalidadInsuficiente(
                f"calidad {calidad} por debajo del mínimo {CALIDAD_MINIMA}"
            )
        if not codigo.es_exito:
            self._anotar("capturar_muestra", referencia, codigo, 0)
            raise CapturaFallida(f"captura fallida con código {codigo}")

        self._anotar("capturar_muestra", referencia, codigo, 0)
        secuencia = len(self._historial)
        return Muestra(
            datos=MARCA_SIMULADO
            + hashlib.blake2b(
                f"muestra:{int(dedo)}:{secuencia}".encode(), digest_size=32
            ).digest(),
            calidad=calidad,
            dedo=dedo,
            capturada_en=self._reloj(),
            proveedor=self.tipo,
        )

    def crear_plantilla(self, muestras: Sequence[Muestra]) -> Plantilla:
        self._exigir_operativo()
        if len(muestras) < MUESTRAS_MINIMAS:
            raise ValueError(
                f"se requieren al menos {MUESTRAS_MINIMAS} muestras, "
                f"se recibieron {len(muestras)}"
            )
        dedos = {m.dedo for m in muestras}
        if len(dedos) != 1:
            raise ValueError(f"las muestras deben ser del mismo dedo, se vieron {dedos}")
        inutilizables = [m for m in muestras if not m.es_utilizable]
        if inutilizables:
            raise ValueError(
                f"{len(inutilizables)} muestra(s) por debajo de la calidad mínima"
            )

        consolidado = hashlib.blake2b(digest_size=32)
        for muestra in muestras:
            consolidado.update(muestra.datos)
        return Plantilla(
            datos=MARCA_SIMULADO + consolidado.digest(),
            formato=FORMATO_ISO_19794_2,
            dedo=next(iter(dedos)),
            calidad=min(m.calidad for m in muestras),
            proveedor=self.tipo,
            muestras_usadas=len(muestras),
        )

    # -- Verificación ------------------------------------------------------

    def verificar(
        self,
        plantilla: Plantilla,
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Veredicto:
        self._exigir_operativo()
        regla = self._regla_para(plantilla.referencia)
        self._dormir(regla)
        inicio = time.perf_counter()

        codigo = regla.codigo if regla else CodigoResultado.OK
        calidad = self._resolver_calidad(regla, semilla=plantilla.datos)
        score = self._resolver_score(regla, codigo, semilla=plantilla.datos)
        duracion_ms = self._duracion_ms(inicio, regla)

        self._anotar("verificar", plantilla.referencia, codigo, score)
        return Veredicto(
            coincide=codigo.es_exito,
            codigo=codigo,
            score=score,
            umbral=self._umbral,
            calidad=calidad,
            duracion_ms=duracion_ms,
            proveedor=self.tipo,
            nivel=self.nivel,
        )

    def buscar(
        self,
        plantillas: Mapping[str, Plantilla],
        timeout_s: float = TIMEOUT_POR_OMISION_S,
    ) -> Coincidencia | None:
        self._exigir_operativo()
        self._dormir(None)
        inicio = time.perf_counter()

        objetivo = self._coincidencia_en_busqueda
        if objetivo is None or objetivo not in plantillas:
            self._anotar("buscar", objetivo, CodigoResultado.NO_MATCH, 0)
            return None

        score = _pseudo(f"buscar:{objetivo}".encode(), self._umbral, 100)
        self._anotar("buscar", objetivo, CodigoResultado.OK, score)
        return Coincidencia(
            referencia=objetivo,
            score=score,
            umbral=self._umbral,
            duracion_ms=self._duracion_ms(inicio, None),
            proveedor=self.tipo,
            nivel=self.nivel,
        )

    # -- Ciclo de vida -----------------------------------------------------

    def cerrar(self) -> None:
        self._cerrado = True

    # -- Auxiliares --------------------------------------------------------

    def _exigir_operativo(self) -> None:
        if self._cerrado:
            raise LectorNoDisponible("el proveedor simulado ya fue cerrado")
        if not self._disponible:
            raise LectorNoDisponible("el lector simulado está marcado como ausente")

    def _dormir(self, regla: ReglaSimulada | None) -> None:
        ms = self._latencia_ms if regla is None or regla.latencia_ms is None else regla.latencia_ms
        if ms > 0:
            time.sleep(ms / 1000)

    def _resolver_calidad(self, regla: ReglaSimulada | None, *, semilla: bytes) -> int:
        if regla is not None and regla.calidad is not None:
            return regla.calidad
        if regla is not None and regla.codigo is CodigoResultado.CALIDAD_INSUFICIENTE:
            return _pseudo(b"calidad-baja:" + semilla, 10, CALIDAD_MINIMA - 1)
        return self._calidad_por_omision

    def _resolver_score(
        self,
        regla: ReglaSimulada | None,
        codigo: CodigoResultado,
        *,
        semilla: bytes,
    ) -> int:
        if regla is not None and regla.score is not None:
            return regla.score
        if codigo.es_exito:
            return _pseudo(b"score-ok:" + semilla, self._umbral, 100)
        if codigo is CodigoResultado.NO_MATCH:
            return _pseudo(b"score-no:" + semilla, 0, max(0, self._umbral - 1))
        return 0

    def _duracion_ms(self, inicio: float, regla: ReglaSimulada | None) -> int:
        medido = int((time.perf_counter() - inicio) * 1000)
        latencia = (
            self._latencia_ms if regla is None or regla.latencia_ms is None else regla.latencia_ms
        )
        return max(medido, latencia)

    def _anotar(
        self,
        operacion: str,
        referencia: str | None,
        codigo: CodigoResultado,
        score: int,
    ) -> None:
        self._historial.append(
            OperacionRegistrada(
                operacion=operacion,
                referencia=referencia,
                codigo=codigo,
                score=score,
            )
        )
