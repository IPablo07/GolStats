"""Constantes del FDx SDK Pro de SecuGen.

╔══════════════════════════════════════════════════════════════════════════════╗
║  VERIFICAR ANTES DE USAR CON HARDWARE REAL                                   ║
║                                                                              ║
║  Estos valores se escribieron SIN el SDK instalado en la máquina de           ║
║  desarrollo. Los marcados como CONFIRMAR deben cotejarse contra el            ║
║  `sgfplib.h` que trae el FDx SDK Pro instalado.                              ║
║                                                                              ║
║  Ejecute:  py herramientas/verificar_constantes.py <ruta_a_sgfplib.h>        ║
║                                                                              ║
║  El diseño limita el daño de un valor incorrecto: la corrección del código   ║
║  solo depende de que el éxito sea 0 (`SGFDX_ERROR_NONE`), que es seguro. El  ║
║  resto de los códigos se usa únicamente para redactar mensajes, y un código  ║
║  desconocido se reporta como tal en lugar de interpretarse mal.              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import re
from pathlib import Path

FABRICANTE = "SecuGen"

#: Nombre de la biblioteca principal del SDK. Se carga por nombre para que
#: Windows la resuelva por el PATH o por el directorio de la aplicación.
DLL_PRINCIPAL = "sgfplib"

#: Bibliotecas auxiliares que el SDK carga por su cuenta. Se listan solo para
#: poder diagnosticar una instalación incompleta.
DLL_AUXILIARES = ("sgfpamx", "sgwsqlib", "sgfdusda")


# ---------------------------------------------------------------------------
# Códigos de retorno
# ---------------------------------------------------------------------------

#: Éxito. Es el único valor del que depende la corrección del código.
SGFDX_ERROR_NONE = 0

#: Mensajes por código. CONFIRMAR los valores numéricos contra `sgfplib.h`.
#: Un código ausente de este mapa se reporta como desconocido, nunca se
#: reinterpreta.
MENSAJES_ERROR: dict[int, str] = {
    0: "sin error",
    1: "no se pudo crear el objeto del SDK",
    2: "la función del SDK falló",
    3: "parámetro inválido",
    4: "función no utilizada",
    5: "no se pudo cargar sgfplib.dll",
    6: "no se pudo cargar la biblioteca del driver",
    7: "no se pudo cargar la biblioteca del algoritmo",
    51: "no se pudo cargar el controlador del sistema",
    52: "falló la inicialización del dispositivo",
    53: "se perdió la comunicación con el dispositivo",
    54: "tiempo de espera agotado",
    55: "dispositivo no encontrado",
    56: "no se pudo cargar la biblioteca del dispositivo",
    57: "imagen inválida",
    58: "ancho de banda USB insuficiente",
    59: "el dispositivo ya está abierto",
    60: "no se pudo leer el número de serie",
    61: "dispositivo no soportado",
}

#: Códigos que corresponden a "no hay dispositivo" y no a un fallo del programa.
#: CONFIRMAR. Se usan solo para elegir el mensaje del preflight.
CODIGOS_SIN_DISPOSITIVO = frozenset({51, 52, 55, 56, 61})

#: Códigos que corresponden a un tiempo de espera. CONFIRMAR.
CODIGOS_TIEMPO_AGOTADO = frozenset({54})


def describir_error(codigo: int) -> str:
    """Mensaje legible de un código de retorno del SDK."""
    conocido = MENSAJES_ERROR.get(codigo)
    if conocido is not None:
        return f"{conocido} (código {codigo})"
    return f"código {codigo} no catalogado; consulte sgfplib.h del SDK instalado"


# ---------------------------------------------------------------------------
# Dispositivos
# ---------------------------------------------------------------------------

#: Autodetección del dispositivo conectado. Es el valor por omisión del
#: proyecto: evita depender de las constantes por modelo, que son las que tienen
#: más riesgo de estar mal.
SG_DEV_AUTO = 0xFF

#: Puerto/identificador de dispositivo para autodetección en `SGFPM_OpenDevice`.
SG_DEVICE_AUTO_DETECT = 0xFF


# ---------------------------------------------------------------------------
# Formatos de plantilla
# ---------------------------------------------------------------------------
# CONFIRMAR los tres valores. El proyecto exige ISO/IEC 19794-2 para no quedar
# atado al fabricante, así que un error aquí se detecta de inmediato: las
# plantillas saldrían con un tamaño distinto al esperado.

TEMPLATE_FORMAT_ANSI378 = 0x0100
TEMPLATE_FORMAT_SG400 = 0x0200
TEMPLATE_FORMAT_ISO19794 = 0x0300

NOMBRES_FORMATO = {
    TEMPLATE_FORMAT_ANSI378: "ANSI/INCITS 378",
    TEMPLATE_FORMAT_SG400: "SecuGen SG400 (propietario)",
    TEMPLATE_FORMAT_ISO19794: "ISO/IEC 19794-2",
}

#: Formato que usa el proyecto. No cambiar sin revisar el diseño: la
#: portabilidad entre fabricantes depende de esta elección.
FORMATO_PROYECTO = TEMPLATE_FORMAT_ISO19794


# ---------------------------------------------------------------------------
# Niveles de seguridad del comparador
# ---------------------------------------------------------------------------
# El proyecto NO los usa para decidir coincidencias: obtiene el score crudo con
# `SGFPM_GetMatchingScore` y aplica su propio umbral, porque el umbral es un
# parámetro de control auditable de la aplicación y no del controlador.

SL_NONE = 0
SL_LOWEST = 1
SL_LOWER = 2
SL_LOW = 3
SL_BELOW_NORMAL = 4
SL_NORMAL = 5
SL_ABOVE_NORMAL = 6
SL_HIGH = 7
SL_HIGHER = 8
SL_HIGHEST = 9


# ---------------------------------------------------------------------------
# Escala de score
# ---------------------------------------------------------------------------

#: Máximo que devuelve `SGFPM_GetMatchingScore`. CONFIRMAR empíricamente: es un
#: parámetro de calibración, no un dato del encabezado. Se expone como argumento
#: del constructor de `LectorSecuGen` para poder corregirlo sin tocar código.
#:
#: Procedimiento de calibración: enrolar varios dedos, medir la distribución de
#: scores de comparaciones genuinas y de impostores, y fijar el umbral de la
#: aplicación en el punto que cumpla el objetivo de falsos aceptados.
RANGO_SCORE_PRESUNTO = 199


# ---------------------------------------------------------------------------
# Calidad de imagen
# ---------------------------------------------------------------------------

#: Escala de `SGFPM_GetImageQuality`: 0 a 100. Coincide con la escala interna
#: del proyecto, así que no requiere normalización.
RANGO_CALIDAD = 100


# ---------------------------------------------------------------------------
# Verificación contra el encabezado real
# ---------------------------------------------------------------------------

_PATRON_DEFINE = re.compile(
    r"^\s*#define\s+(?P<nombre>[A-Za-z_][A-Za-z0-9_]*)\s+"
    r"\(?\s*(?P<valor>0[xX][0-9A-Fa-f]+|\d+)\s*\)?",
    re.MULTILINE,
)

#: Constantes de este módulo que deben coincidir con el encabezado.
A_VERIFICAR = {
    "SGFDX_ERROR_NONE": SGFDX_ERROR_NONE,
    "SG_DEV_AUTO": SG_DEV_AUTO,
    "TEMPLATE_FORMAT_ANSI378": TEMPLATE_FORMAT_ANSI378,
    "TEMPLATE_FORMAT_SG400": TEMPLATE_FORMAT_SG400,
    "TEMPLATE_FORMAT_ISO19794": TEMPLATE_FORMAT_ISO19794,
    "SL_NORMAL": SL_NORMAL,
    "SL_HIGHEST": SL_HIGHEST,
}


def leer_defines(ruta_encabezado: str | Path) -> dict[str, int]:
    """Extrae los `#define` numéricos de un encabezado C.

    Se lee con `utf-8-sig` a propósito: un encabezado guardado con BOM dejaría
    un `\\ufeff` antes del primer `#define`, y como no es un carácter de espacio
    la primera constante del archivo no coincidiría con el patrón. Sería un
    fallo silencioso —reportaría ausente algo que sí está—, así que conviene
    quitarlo al leer.
    """
    texto = Path(ruta_encabezado).read_text(encoding="utf-8-sig", errors="replace")
    return {
        m.group("nombre"): int(m.group("valor"), 0)
        for m in _PATRON_DEFINE.finditer(texto)
    }


def verificar_constantes(ruta_encabezado: str | Path) -> dict[str, tuple[int, int | None]]:
    """Compara las constantes del proyecto con el encabezado del SDK.

    Devuelve solo las discrepancias, como ``{nombre: (nuestro, del_encabezado)}``.
    Un valor `None` significa que el nombre no aparece en el encabezado.
    """
    defines = leer_defines(ruta_encabezado)
    discrepancias: dict[str, tuple[int, int | None]] = {}
    for nombre, nuestro in A_VERIFICAR.items():
        real = defines.get(nombre)
        if real != nuestro:
            discrepancias[nombre] = (nuestro, real)
    return discrepancias
