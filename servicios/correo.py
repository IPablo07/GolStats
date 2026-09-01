"""
servicios/correo.py
────────────────────
Puente entre las clases de modelos/notificacion.py y el envío real.

Si el .env no tiene servidor de correo configurado, las notificaciones
quedan en la bandeja simulada (BANDEJA_SIMULADA) y se ven en la consola;
así se puede probar todo el flujo sin cuenta de correo.
"""

from modelos.notificacion import (
    BANDEJA_SIMULADA,
    NotificacionPagoCompletado,
    NotificacionPartidoProximo,
    NotificacionWalkover,
    NotificacionReciboPDF,
)


class ServicioCorreo:
    """
    Manda las notificaciones del sistema.

    No sabe qué dice cada correo: eso lo resuelve cada subclase de
    Notificacion. Este servicio solo se ocupa de entregarlo, por Flask-Mail
    si hay servidor configurado, o a la bandeja simulada si no lo hay.
    """

    def __init__(self, activo=False, mail=None):
        self.activo = activo
        self.mail = mail          # instancia de Flask-Mail, cuando exista

    def enviar(self, notificacion):
        """Envía una Notificacion (cualquier subclase) — polimorfismo puro."""
        mensaje = notificacion.enviar()
        if self.activo and self.mail is not None:
            self._enviar_real(mensaje)
        else:
            print(f"[CORREO SIMULADO] Para: {mensaje['para']} | {mensaje['asunto']}")
        return mensaje

    def _enviar_real(self, mensaje):
        from flask_mail import Message
        correo = Message(
            subject=mensaje["asunto"],
            recipients=[mensaje["para"]],
            body=mensaje["cuerpo"],
        )
        self.mail.send(correo)

    def bandeja(self):
        """Correos simulados, del más nuevo al más viejo (para el panel admin)."""
        return list(reversed(BANDEJA_SIMULADA))

    # ── Atajos que usan las rutas ─────────────────────────────────

    def avisar_pago_completado(self, partido, equipo, monto):
        return self.enviar(
            NotificacionPagoCompletado(equipo.correo_capitan, equipo, partido, monto)
        )

    def avisar_partido_proximo(self, partido, equipo=None):
        """
        Avisa al capitán —o a los dos, si no se indica equipo— de que
        tienen partido. Devuelve la lista de correos enviados.
        """
        equipos = [equipo] if equipo is not None else list(partido.equipos())
        return [
            self.enviar(
                NotificacionPartidoProximo(
                    e.correo_capitan, e, partido,
                    monto=partido.obtener_pago(e).monto,
                )
            )
            for e in equipos
        ]

    def avisar_walkover(self, partido):
        enviados = []
        for equipo in partido.equipos():
            enviados.append(
                self.enviar(
                    NotificacionWalkover(
                        equipo.correo_capitan, equipo, partido,
                        partido.motivo_walkover,
                    )
                )
            )
        return enviados

    def enviar_recibos(self, partido, ruta_pdf="recibos/recibo.pdf"):
        enviados = []
        for equipo in partido.equipos():
            enviados.append(
                self.enviar(
                    NotificacionReciboPDF(
                        equipo.correo_capitan, equipo, partido, ruta_pdf
                    )
                )
            )
        return enviados
