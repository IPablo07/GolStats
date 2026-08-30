"""
modelos/notificacion.py
────────────────────────
Correos que el sistema le manda al capitán de cada equipo.

Todas heredan de Notificacion, que ya sabe a quién se envía y cómo se
manda. Cada subclase solo define su asunto y su cuerpo — herencia +
polimorfismo (criterio 3.3 de la rúbrica).

Por ahora el envío es simulado: se guarda en BANDEJA_SIMULADA y se
imprime en consola. Cuando se conecte Flask-Mail, lo único que cambia
es el método _entregar() de la clase base.
"""

from datetime import datetime


# Bandeja de salida falsa, para poder probar sin servidor de correo.
BANDEJA_SIMULADA = []


class Notificacion:
    """Clase base de todos los correos del sistema."""

    def __init__(self, destinatario, equipo=None, partido=None):
        if not destinatario or "@" not in destinatario:
            raise ValueError(f"Correo de destinatario inválido: {destinatario}")
        self.destinatario = destinatario
        self.equipo = equipo
        self.partido = partido
        self.enviada_en = None
        self.adjuntos = []

    # ── Lo que cada subclase debe definir ─────────────────────────

    def asunto(self):
        raise NotImplementedError("Cada notificación debe definir su asunto()")

    def cuerpo(self):
        raise NotImplementedError("Cada notificación debe definir su cuerpo()")

    # ── Lo que todas comparten ────────────────────────────────────

    def enviar(self):
        mensaje = {
            "para": self.destinatario,
            "asunto": self.asunto(),
            "cuerpo": self.cuerpo(),
            "adjuntos": list(self.adjuntos),
            "tipo": self.__class__.__name__,
        }
        self._entregar(mensaje)
        self.enviada_en = datetime.now()
        return mensaje

    def _entregar(self, mensaje):
        """Único punto que hay que cambiar para usar Flask-Mail de verdad."""
        BANDEJA_SIMULADA.append(mensaje)

    def _encabezado_partido(self):
        if self.partido is None:
            return ""
        p = self.partido
        return (
            f"Partido: {p.equipo_local.nombre} vs {p.equipo_visitante.nombre}\n"
            f"Fecha: {p.fecha_hora.strftime('%d/%m/%Y %H:%M')}\n"
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} para {self.destinatario}>"


class NotificacionPagoCompletado(Notificacion):
    """Se manda al capitán cuando el equipo ya pagó la vocalía."""

    def __init__(self, destinatario, equipo, partido, monto):
        super().__init__(destinatario, equipo, partido)
        self.monto = monto

    def asunto(self):
        return f"GolStats - Pago de vocalía completado ({self.equipo.nombre})"

    def cuerpo(self):
        return (
            f"Hola {self.equipo.nombre_capitan},\n\n"
            f"Confirmamos el pago de la vocalía por ${self.monto:.2f} "
            f"del equipo {self.equipo.nombre}.\n\n"
            f"{self._encabezado_partido()}\n"
            f"Su equipo está habilitado para jugar el partido completo.\n\n"
            f"GolStats"
        )


class NotificacionPagoPendiente(Notificacion):
    """Recordatorio: si no paga antes del segundo tiempo, pierde por walkover."""

    def __init__(self, destinatario, equipo, partido, monto):
        super().__init__(destinatario, equipo, partido)
        self.monto = monto

    def asunto(self):
        return f"GolStats - Pago de vocalía PENDIENTE ({self.equipo.nombre})"

    def cuerpo(self):
        return (
            f"Hola {self.equipo.nombre_capitan},\n\n"
            f"El equipo {self.equipo.nombre} todavía no ha cancelado la vocalía "
            f"de ${self.monto:.2f}.\n\n"
            f"{self._encabezado_partido()}\n"
            f"IMPORTANTE: si el pago no se completa antes de que inicie el "
            f"segundo tiempo, el partido se declara walkover a favor del equipo "
            f"contrario.\n\n"
            f"GolStats"
        )


class NotificacionWalkover(Notificacion):
    """Aviso de que el partido se perdió (o se ganó) por walkover."""

    def __init__(self, destinatario, equipo, partido, motivo):
        super().__init__(destinatario, equipo, partido)
        self.motivo = motivo

    def asunto(self):
        return f"GolStats - Partido declarado walkover ({self.equipo.nombre})"

    def cuerpo(self):
        ganador = self.partido.equipo_ganador
        resultado = (
            f"Equipo ganador: {ganador.nombre}" if ganador
            else "Sin equipo ganador: ninguno cumplio con el pago."
        )
        return (
            f"Hola {self.equipo.nombre_capitan},\n\n"
            f"{self._encabezado_partido()}\n"
            f"El partido fue declarado WALKOVER.\n"
            f"Motivo: {self.motivo}\n"
            f"{resultado}\n"
            f"Marcador registrado: {self.partido.marcador()}\n\n"
            f"GolStats"
        )


class NotificacionReciboPDF(Notificacion):
    """Recibo del partido finalizado, con el PDF adjunto."""

    def __init__(self, destinatario, equipo, partido, ruta_pdf):
        super().__init__(destinatario, equipo, partido)
        self.ruta_pdf = ruta_pdf
        self.adjuntos.append(ruta_pdf)

    def asunto(self):
        return f"GolStats - Recibo del partido ({self.equipo.nombre})"

    def cuerpo(self):
        p = self.partido
        return (
            f"Hola {self.equipo.nombre_capitan},\n\n"
            f"{self._encabezado_partido()}"
            f"Resultado final: {p.equipo_local.nombre} {p.marcador()} "
            f"{p.equipo_visitante.nombre}\n\n"
            f"Adjuntamos el recibo de la vocalía en PDF.\n"
            f"Las estadísticas de sus jugadores ya fueron actualizadas en el sistema.\n\n"
            f"GolStats"
        )
