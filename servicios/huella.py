"""
servicios/huella.py
────────────────────
Lado servidor de la verificación con el lector SecuGen.

Cómo funciona el reparto de tareas:

  1. El navegador (que corre en la laptop Windows donde está el lector)
     llama a https://localhost:8000/SGIFPCapture para capturar la huella.
  2. Para verificar, el navegador llama a /SGIMatchScore con la huella
     recién capturada y el template guardado del jugador, y recibe un
     puntaje de 0 a 199.
  3. El navegador manda ese puntaje a Flask, y esta clase decide si
     alcanza el umbral.

Es verificación 1:1: ya se sabe qué jugador se está presentando (viene
de la convocatoria), así que se compara solo contra SU template. La
búsqueda 1:N necesitaría una licencia aparte de SecuGen.

En modo "simulado" (para desarrollar en la Mac, sin lector) se acepta
la captura sin llamar a nada.
"""

PUNTAJE_MAXIMO = 199


class ErrorHuella(Exception):
    """Error de negocio de la huella: se muestra tal cual al usuario."""


class LectorHuella:
    """
    Decide si una huella capturada es válida o no.

    No habla con el lector: eso lo hace el navegador (static/js/huella.js),
    que es el único que puede llegar a https://localhost:8000. Esta clase
    recibe el puntaje que devolvió el lector y lo compara contra el umbral.

    En modo simulado acepta cualquier captura, para poder desarrollar sin
    el hardware conectado.
    """

    MODO_SECUGEN = "secugen"
    MODO_SIMULADO = "simulado"

    def __init__(self, modo=MODO_SIMULADO, umbral=45, url="https://localhost:8000"):
        modo = (modo or "").strip().lower()
        if modo not in (LectorHuella.MODO_SECUGEN, LectorHuella.MODO_SIMULADO):
            raise ValueError(
                f"HUELLA_MODO inválido: {modo}. Use secugen o simulado"
            )
        self.modo = modo
        self.umbral = umbral
        self.url = url

    @classmethod
    def desde_config(cls, config):
        return cls(
            modo=config.HUELLA_MODO,
            umbral=config.HUELLA_UMBRAL,
            url=config.SECUGEN_URL,
        )

    def es_simulado(self):
        return self.modo == LectorHuella.MODO_SIMULADO

    # ── Enrolamiento (una sola vez por jugador) ───────────────────

    def registrar_template(self, jugador, template):
        if self.es_simulado():
            template = template or f"SIMULADO-{jugador.cedula}"
        if not template:
            raise ErrorHuella(
                "No se recibió la huella. Vuelva a colocar el dedo en el lector."
            )
        jugador.codigo_huella = template
        return template

    def tiene_huella(self, jugador):
        return bool(jugador.codigo_huella)

    # ── Verificación (en cada check-in) ───────────────────────────

    def verificar(self, jugador, puntaje=None):
        """
        Devuelve el puntaje aceptado, o lanza ErrorHuella con un mensaje
        claro para mostrar en pantalla.
        """
        if self.es_simulado():
            return PUNTAJE_MAXIMO

        if not self.tiene_huella(jugador):
            raise ErrorHuella(
                f"{jugador.nombre_completo()} no tiene huella registrada. "
                f"Regístrela primero desde la ficha del jugador."
            )
        if puntaje is None:
            raise ErrorHuella(
                "El lector no devolvió un puntaje. Revise que el servicio "
                "SecuGen WebAPI esté corriendo en esta laptop."
            )

        try:
            puntaje = int(puntaje)
        except (TypeError, ValueError):
            raise ErrorHuella(f"Puntaje de huella inválido: {puntaje}")

        if puntaje < self.umbral:
            raise ErrorHuella(
                f"La huella no coincide (puntaje {puntaje} de {self.umbral} "
                f"requeridos). Intente de nuevo con el dedo bien centrado."
            )
        return puntaje

    def __repr__(self):
        return f"<LectorHuella modo={self.modo} umbral={self.umbral}>"
