"""
modelos/huella.py
───────────────────
Registro biométrico persistido en PostgreSQL.

Es la única parte del sistema que ya vive en base de datos real: el resto
(equipos, partidos, goles...) sigue en memoria (ver datos_prueba.py) hasta
la etapa de conexión completa que describe el README. Esta tabla se va
construyendo sola, una fila a la vez, cada vez que un administrador
enrola la huella de un jugador, un árbitro o un administrador — por eso
vive aparte y no depende de que el resto de la base de datos ya exista.

`tipo_persona` + `persona_id` identifican a la persona dentro de los
datos en memoria (BD.jugadores, BD.arbitros, BD.usuarios); cuando esos
datos se muden a PostgreSQL, `persona_id` pasa a ser una FK real sin que
esta tabla cambie de forma.
"""

from datetime import datetime, timezone

from extensiones import db

#: Roles que pueden tener una huella registrada.
TIPOS_PERSONA = ("jugador", "arbitro", "administrador")


def _ahora():
    return datetime.now(timezone.utc)


class RegistroBiometrico(db.Model):
    """Una fila = la huella enrolada de una persona (jugador/árbitro/admin)."""

    __tablename__ = "registros_biometricos"

    id = db.Column(db.Integer, primary_key=True)

    # ── A quién pertenece ────────────────────────────────────────
    tipo_persona = db.Column(db.String(20), nullable=False)   # jugador|arbitro|administrador
    persona_id = db.Column(db.Integer, nullable=False)
    nombre_completo = db.Column(db.String(150), nullable=False)
    correo = db.Column(db.String(150))
    cedula = db.Column(db.String(20))

    # ── La plantilla biométrica en sí (ver biometria.Plantilla) ───
    dedo = db.Column(db.Integer, nullable=False)
    formato = db.Column(db.String(50), nullable=False)
    plantilla = db.Column(db.LargeBinary, nullable=False)
    calidad = db.Column(db.Integer, nullable=False)
    muestras_usadas = db.Column(db.Integer, nullable=False)
    proveedor = db.Column(db.String(20), nullable=False)      # EXTERNO|SIMULADO

    registrado_en = db.Column(db.DateTime, default=_ahora)
    actualizado_en = db.Column(db.DateTime, default=_ahora, onupdate=_ahora)

    __table_args__ = (
        db.UniqueConstraint("tipo_persona", "persona_id", name="uq_persona_huella"),
    )

    # ── Referencia: la clave que usa el paquete `biometria` para 1:N ──

    @staticmethod
    def referencia_para(tipo_persona, persona_id):
        return f"{tipo_persona}:{persona_id}"

    def referencia_propia(self):
        return RegistroBiometrico.referencia_para(self.tipo_persona, self.persona_id)

    @staticmethod
    def descomponer_referencia(referencia):
        """Inversa de `referencia_para`: 'jugador:12' → ('jugador', 12)."""
        tipo_persona, persona_id = referencia.split(":", 1)
        return tipo_persona, int(persona_id)

    # ── Conversión hacia el paquete `biometria` ───────────────────

    def a_plantilla(self):
        """Reconstruye el `Plantilla` que entiende el paquete `biometria`."""
        from biometria import Dedo, Plantilla, TipoProveedor

        return Plantilla(
            datos=bytes(self.plantilla),
            formato=self.formato,
            dedo=Dedo(self.dedo),
            calidad=self.calidad,
            proveedor=TipoProveedor(self.proveedor),
            muestras_usadas=self.muestras_usadas,
            referencia=self.referencia_propia(),
        )

    def __repr__(self):
        return f"<RegistroBiometrico {self.tipo_persona}:{self.persona_id}>"
