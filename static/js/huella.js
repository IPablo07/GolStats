/*
 * static/js/huella.js
 * ────────────────────
 * Cliente del lector SecuGen.
 *
 * El servicio SecuGen WebAPI se instala en la laptop Windows junto con
 * el driver y queda escuchando en https://localhost:8000. Como es
 * localhost, esto SOLO funciona en el navegador de esa misma laptop.
 * La primera vez el navegador avisa que el certificado es autofirmado:
 * hay que aceptar la excepción entrando a https://localhost:8000.
 *
 *   SGIFPCapture   → captura la huella y devuelve el template (base64)
 *   SGIMatchScore  → compara dos templates y devuelve 0..199
 *
 * Verificación 1:1: ya sabemos qué jugador se presenta (está en la
 * convocatoria), así que solo comparamos contra SU template guardado.
 *
 * En modo "simulado" no se llama a nada: sirve para desarrollar en la
 * Mac, sin el lector conectado.
 */

class LectorHuella {

  constructor({ modo = "simulado", url = "https://localhost:8000", umbral = 45 } = {}) {
    this.modo = modo;
    this.url = url;
    this.umbral = umbral;
  }

  get simulado() {
    return this.modo !== "secugen";
  }

  /** Captura una huella y devuelve su template en base64. */
  async capturar() {
    if (this.simulado) {
      return "SIMULADO-" + Date.now();
    }
    const datos = await this._llamar("SGIFPCapture", { Timeout: 10000, Quality: 50 });
    if (!datos.TemplateBase64) {
      throw new Error("El lector no devolvió ninguna huella. Intente de nuevo.");
    }
    return datos.TemplateBase64;
  }

  /**
   * Captura la huella y la compara contra el template guardado del
   * jugador. Devuelve el puntaje (0..199) para que el servidor decida.
   */
  async verificar(templateGuardado) {
    if (this.simulado) {
      return 199;
    }
    if (!templateGuardado) {
      throw new Error(
        "Este jugador no tiene huella registrada. Regístrela primero " +
        "desde su ficha."
      );
    }

    const capturado = await this.capturar();
    const datos = await this._llamar("SGIMatchScore", {
      template1: templateGuardado,
      template2: capturado,
      licstr: ""
    });

    const puntaje = parseInt(datos.MatchingScore, 10);
    if (isNaN(puntaje)) {
      throw new Error("El lector no devolvió un puntaje válido.");
    }
    if (puntaje < this.umbral) {
      throw new Error(
        "La huella no coincide (puntaje " + puntaje + " de " + this.umbral +
        " requeridos). Coloque el dedo bien centrado e intente de nuevo."
      );
    }
    return puntaje;
  }

  /** Llamada al servicio local de SecuGen. */
  async _llamar(metodo, parametros) {
    let respuesta;
    try {
      respuesta = await fetch(this.url + "/" + metodo, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(parametros).toString()
      });
    } catch (error) {
      throw new Error(
        "No se pudo contactar al lector. Verifique que el servicio " +
        "SecuGen WebAPI esté corriendo y que haya aceptado el " +
        "certificado en " + this.url
      );
    }

    const datos = await respuesta.json();
    if (datos.ErrorCode && datos.ErrorCode !== 0) {
      throw new Error("Error del lector (código " + datos.ErrorCode + ").");
    }
    return datos;
  }
}
