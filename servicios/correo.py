"""
servicios/correo.py
────────────────────
Puente entre las clases de modelos/notificacion.py y el envío real.

Si el .env no tiene servidor de correo configurado, las notificaciones
quedan en la bandeja simulada (BANDEJA_SIMULADA) y se ven en la consola;
así se puede probar todo el flujo sin cuenta de correo.

Un envío que falla NUNCA tumba la operación que lo disparó. Cobrar la
vocalía es lo importante; avisar al capitán es un accesorio. Si el correo
no sale —credenciales mal puestas, sin internet, el puerto 587 bloqueado
por la red— el pago se registra igual y quien está en pantalla se entera
de que el aviso no salió, en vez de recibir una pantalla de error sobre
una operación que en realidad sí funcionó.
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
        self.ultimo_error = None  # motivo del ultimo envio fallido

    def enviar(self, notificacion):
        """
        Envía una Notificacion (cualquier subclase) — polimorfismo puro.

        Nunca lanza por un fallo de entrega: devuelve el mensaje con
        `enviado` en False y el motivo en `error`. Quien llama decide qué
        contar al usuario; lo que no puede pasar es que un correo caído
        deshaga un cobro que ya se registró.
        """
        mensaje = notificacion.enviar()
        mensaje["enviado"] = True
        mensaje["error"] = None

        if not (self.activo and self.mail is not None):
            print(f"[CORREO SIMULADO] Para: {mensaje['para']} | {mensaje['asunto']}")
            return mensaje

        try:
            self._enviar_real(mensaje)
        except Exception as error:
            # Se traga a proposito, pero deja rastro en la consola: sin el
            # log, un correo que no sale es invisible.
            mensaje["enviado"] = False
            mensaje["error"] = f"{type(error).__name__}: {error}"
            self.ultimo_error = mensaje["error"]
            print(f"[CORREO FALLIDO] Para: {mensaje['para']} | "
                  f"{mensaje['asunto']} | {mensaje['error']}")
        return mensaje

    @staticmethod
    def todos_enviados(mensajes):
        """True si salieron todos. Acepta un mensaje suelto o una lista."""
        if isinstance(mensajes, dict):
            mensajes = [mensajes]
        return all(m.get("enviado", True) for m in mensajes)

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
