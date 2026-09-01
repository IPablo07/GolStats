"""
config.py
──────────
Configuración de la aplicación, leída desde variables de entorno
(archivo .env). Ver .env.example para la plantilla.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _bool(valor, por_defecto=False):
    if valor is None:
        return por_defecto
    return str(valor).strip().lower() in ("1", "true", "si", "sí", "yes", "on")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "clave-de-desarrollo-cambiar-en-produccion")
    DEBUG = _bool(os.getenv("FLASK_DEBUG"), True)

    # ── Lector de huella SecuGen ──────────────────────────────────
    # "secugen"  → Flask captura directo del lector con el paquete
    #              `biometria` (ctypes + sgfplib.dll). Debe correr en la
    #              misma laptop Windows donde está conectado el lector.
    # "simulado" → no toca hardware, para desarrollar sin lector.
    HUELLA_MODO = os.getenv("HUELLA_MODO", "simulado")
    HUELLA_UMBRAL = int(os.getenv("HUELLA_UMBRAL", "45"))
    HUELLA_LECTOR = os.getenv("HUELLA_LECTOR", "secugen:hsdu03p")

    # ── Correo ────────────────────────────────────────────────────
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = _bool(os.getenv("MAIL_USE_TLS"), True)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    # Remitente por defecto. Gmail ignora cualquier remitente que no sea la
    # propia cuenta autenticada, así que si MAIL_USERNAME está configurado
    # se usa ese: poner otro haría que los correos salgan "en nombre de"
    # una dirección que no existe, y acaban en spam.
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or (
        f"GolStats <{MAIL_USERNAME}>" if MAIL_USERNAME
        else "GolStats <no-reply@golstats.com>"
    )

    # Días de antelación con que se avisa al capitán del partido próximo.
    DIAS_AVISO_PARTIDO = int(os.getenv("DIAS_AVISO_PARTIDO", "3"))

    # Si no hay servidor de correo configurado, los correos se simulan.
    @classmethod
    def correo_activo(cls):
        return bool(cls.MAIL_SERVER and cls.MAIL_USERNAME and cls.MAIL_PASSWORD)

    # ── Base de datos ────────────────────────────────────────────
    # Por ahora PostgreSQL solo guarda la tabla de huellas (registros_
    # biometricos); equipos/partidos siguen en memoria (datos_prueba.py)
    # hasta la etapa de conexión completa que describe el README.
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/golstats"
    )
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
