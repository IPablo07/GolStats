"""Subsistema biométrico: contrato único y sus implementaciones.

Superficie pública del paquete. El resto del sistema importa desde aquí y nunca
desde los módulos internos, para que cambiar de proveedor o de lector no
propague cambios.

Capas, de lo abstracto a lo concreto:

    contratos.py   tipos que cruzan la frontera; niveles de aseguramiento
    proveedor.py   ProveedorBiometrico — el contrato que consume la aplicación
    simulado.py    mock determinista y guionable
    lectores/      hardware real: contrato, proveedor reutilizable y registro
    fabrica.py     único lugar que decide qué implementación se usa
"""

from .contratos import (
    CALIDAD_MINIMA,
    FORMATO_ISO_19794_2,
    MUESTRAS_MINIMAS,
    MUESTRAS_POR_PLANTILLA,
    CalidadInsuficiente,
    CapturaFallida,
    CodigoResultado,
    Coincidencia,
    Dedo,
    Diagnostico,
    ErrorBiometrico,
    LectorNoDisponible,
    Muestra,
    NivelAseguramiento,
    Plantilla,
    TiempoAgotado,
    TipoProveedor,
    Veredicto,
    nivel_resultante,
)
from .fabrica import crear_proveedor
from .lectores import (
    ESCALA_SCORE,
    UMBRAL_POR_OMISION as UMBRAL_HARDWARE_POR_OMISION,
    CapturaHardware,
    DiagnosticoHardware,
    EntradaLector,
    InfoLector,
    LectorHardware,
    ProveedorHardware,
    crear_lector,
    lectores_registrados,
    obtener_entrada,
    registrar_lector,
)
from .proveedor import TIMEOUT_POR_OMISION_S, ProveedorBiometrico
from .simulado import (
    CALIDAD_POR_OMISION,
    MARCA_SIMULADO,
    UMBRAL_POR_OMISION,
    OperacionRegistrada,
    ReglaSimulada,
    SimuladoProvider,
)

__all__ = [
    "CALIDAD_MINIMA",
    "CALIDAD_POR_OMISION",
    "ESCALA_SCORE",
    "FORMATO_ISO_19794_2",
    "MARCA_SIMULADO",
    "MUESTRAS_MINIMAS",
    "MUESTRAS_POR_PLANTILLA",
    "TIMEOUT_POR_OMISION_S",
    "UMBRAL_HARDWARE_POR_OMISION",
    "UMBRAL_POR_OMISION",
    "CalidadInsuficiente",
    "CapturaFallida",
    "CapturaHardware",
    "CodigoResultado",
    "Coincidencia",
    "Dedo",
    "Diagnostico",
    "DiagnosticoHardware",
    "EntradaLector",
    "ErrorBiometrico",
    "InfoLector",
    "LectorHardware",
    "LectorNoDisponible",
    "Muestra",
    "NivelAseguramiento",
    "OperacionRegistrada",
    "Plantilla",
    "ProveedorBiometrico",
    "ProveedorHardware",
    "ReglaSimulada",
    "SimuladoProvider",
    "TiempoAgotado",
    "TipoProveedor",
    "Veredicto",
    "crear_lector",
    "crear_proveedor",
    "lectores_registrados",
    "nivel_resultante",
    "obtener_entrada",
    "registrar_lector",
]
