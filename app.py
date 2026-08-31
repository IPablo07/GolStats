"""
app.py
───────
Aplicación Flask de GolStats.

Por ahora los datos vienen de datos_prueba.BD (memoria). Cuando se
conecte PostgreSQL, solo cambia de dónde se obtienen los objetos: las
rutas y las plantillas siguen igual.

Ejecutar:
    venv\\Scripts\\activate
    python app.py
    → http://localhost:5000
"""

import atexit
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
)

from config import Config
from datos_prueba import BD
from extensiones import db
from modelos import Partido, Tarjeta, CheckIn, RegistroBiometrico, TIPOS_PERSONA
from servicios import estadisticas
from servicios.correo import ServicioCorreo
from servicios.huella import LectorHuella, ErrorHuella

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
with app.app_context():
    print("DEBUG: probando conexión...")

    try:
        db.session.execute(db.text("SELECT 1"))
        print("DEBUG: conexión a PostgreSQL OK")

        print("DEBUG: creando tablas...")
        db.create_all()
        print("DEBUG: tablas creadas correctamente")

    except Exception as e:
        print("ERROR:")
        print(e)

lector = LectorHuella.desde_config(Config)
correo = ServicioCorreo(activo=Config.correo_activo())
atexit.register(lector.cerrar)  # libera el lector al apagar el servidor


# ══════════════════════════════════════════════════════════════════
#  Sesión y control de acceso
# ══════════════════════════════════════════════════════════════════

def usuario_actual():
    usuario_id = session.get("usuario_id")
    return BD.buscar_usuario_por_id(usuario_id) if usuario_id else None


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if usuario_actual() is None:
            flash("Inicie sesión para continuar.", "warning")
            return redirect(url_for("login"))
        return vista(*args, **kwargs)
    return envoltura


def admin_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        usuario = usuario_actual()
        if usuario is None:
            flash("Inicie sesión para continuar.", "warning")
            return redirect(url_for("login"))
        if usuario.rol != "admin":
            flash("Esta sección es solo para administradores.", "danger")
            return redirect(url_for("panel"))
        return vista(*args, **kwargs)
    return envoltura


@app.context_processor
def variables_globales():
    """Disponibles en todas las plantillas sin pasarlas una por una."""
    return {
        "usuario": usuario_actual(),
        "modo_huella": lector.modo,
        "umbral_huella": lector.umbral,
    }


# ══════════════════════════════════════════════════════════════════
#  Biometría: ubicar a la persona detrás de (tipo_persona, id)
# ══════════════════════════════════════════════════════════════════

def _persona_biometrica(tipo_persona, persona_id):
    """
    Los datos siguen en memoria (BD), pero la huella ya vive en Postgres:
    esta función es el puente entre ambos mundos mientras dure la
    migración. `tipo_persona` es uno de RegistroBiometrico.TIPOS_PERSONA.
    """
    if tipo_persona == "jugador":
        return BD.buscar_jugador(persona_id)
    if tipo_persona == "arbitro":
        return next((a for a in BD.arbitros if a.id == persona_id), None)
    if tipo_persona == "administrador":
        usuario = BD.buscar_usuario_por_id(persona_id)
        return usuario if usuario is not None and usuario.rol == "admin" else None
    return None


def _nombre_persona(persona):
    """
    Jugador tiene nombre_completo(), Árbitro tiene .nombres, y
    Administrador —tal como está modelado hoy— solo tiene .correo.
    """
    if hasattr(persona, "nombre_completo"):
        return persona.nombre_completo()
    return getattr(persona, "nombres", None) or persona.correo


# ══════════════════════════════════════════════════════════════════
#  Autenticación
# ══════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET", "POST"])
def login():
    if usuario_actual() is not None:
        return redirect(url_for("panel"))

    if request.method == "POST":
        correo_ingresado = request.form.get("correo", "").strip()
        password = request.form.get("password", "")

        if not correo_ingresado or not password:
            flash("Ingrese su correo y su contraseña.", "danger")
            return render_template("login.html", correo=correo_ingresado)

        usuario = BD.buscar_usuario_por_correo(correo_ingresado)
        if usuario is None or not usuario.verificar_password(password):
            flash("Correo o contraseña incorrectos.", "danger")
            return render_template("login.html", correo=correo_ingresado)

        session["usuario_id"] = usuario.id
        session["rol"] = usuario.rol
        return redirect(url_for("panel"))

    return render_template("login.html", correo="")


@app.route("/login/huella", methods=["POST"])
def login_huella():
    """
    Ingreso sin contraseña: solo para administradores, y solo con huella
    ya registrada (ver /biometria). Es 1:N — no hace falta decir antes
    quién es, el lector lo determina comparando contra todas las huellas
    de administradores.
    """
    if usuario_actual() is not None:
        return redirect(url_for("panel"))

    try:
        persona_id, coincidencia = lector.identificar("administrador")
    except ErrorHuella as e:
        flash(str(e), "danger")
        return redirect(url_for("login"))

    usuario = BD.buscar_usuario_por_id(persona_id)
    if usuario is None or usuario.rol != "admin":
        flash("La huella no corresponde a ningún administrador activo.", "danger")
        return redirect(url_for("login"))

    session["usuario_id"] = usuario.id
    session["rol"] = usuario.rol
    flash(
        f"Bienvenido, {usuario.correo} (ingreso con huella, "
        f"puntaje {coincidencia.score}).",
        "success",
    )
    return redirect(url_for("panel"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════════
#  Paneles (uno por rol — polimorfismo de panel_info())
# ══════════════════════════════════════════════════════════════════

@app.route("/panel")
@login_requerido
def panel():
    usuario = usuario_actual()
    info = usuario.panel_info()

    if info["tipo"] == "admin":
        return render_template(
            "panel_admin.html",
            info=info,
            equipos=BD.equipos,
            partidos=sorted(BD.partidos, key=lambda p: p.fecha_hora, reverse=True),
            proximos=BD.proximos_partidos(),
            posiciones=estadisticas.tabla_posiciones(BD.equipos, BD.partidos)[:4],
            goleadores=estadisticas.goleadores(BD.partidos, limite=5),
            bandeja=correo.bandeja()[:5],
        )

    # La cuenta de jugadores es una sola y compartida: no representa a
    # nadie en particular, así que su inicio muestra lo que le sirve a
    # cualquiera del torneo — la tabla de partidos y la de posiciones.
    return render_template(
        "panel_jugador.html",
        info=info,
        partidos=sorted(BD.partidos, key=lambda p: p.fecha_hora, reverse=True),
        posiciones=estadisticas.tabla_posiciones(BD.equipos, BD.partidos),
    )


# ══════════════════════════════════════════════════════════════════
#  Equipos y jugadores
# ══════════════════════════════════════════════════════════════════

@app.route("/equipos")
@login_requerido
def equipos():
    return render_template(
        "equipos.html",
        equipos=BD.equipos,
        posiciones=estadisticas.tabla_posiciones(BD.equipos, BD.partidos),
    )


@app.route("/equipos/<int:equipo_id>")
@login_requerido
def equipo_detalle(equipo_id):
    equipo = BD.buscar_equipo(equipo_id)
    if equipo is None:
        abort(404)
    return render_template(
        "equipo_detalle.html",
        equipo=equipo,
        datos=estadisticas.estadisticas_equipo(equipo, BD.partidos),
        partidos=[p for p in BD.partidos if equipo in p.equipos()],
    )


@app.route("/jugadores/<int:jugador_id>")
@login_requerido
def jugador_detalle(jugador_id):
    jugador = BD.buscar_jugador(jugador_id)
    if jugador is None:
        abort(404)

    # Sin restricción por dueño: con la cuenta compartida no hay "mis"
    # estadísticas, y desde Equipos se llega a la ficha de cualquier
    # jugador de cualquier equipo. Escribir sigue siendo solo del admin
    # (el botón de enrolar huella lo controla la plantilla).
    return render_template(
        "jugador_detalle.html",
        jugador=jugador,
        resumen=estadisticas.estadisticas_jugador(jugador, BD.partidos),
        tiene_huella=lector.tiene_huella("jugador", jugador.id),
    )


# ══════════════════════════════════════════════════════════════════
#  Biometría: enrolamiento de jugadores, árbitros y administradores
# ══════════════════════════════════════════════════════════════════

@app.route("/biometria")
@admin_requerido
def biometria_panel():
    """
    Un solo lugar para enrolar a las tres clases de persona. Cada fila que
    se registra aquí es la que va construyendo la tabla
    `registros_biometricos` en Postgres.
    """
    administradores = [u for u in BD.usuarios if u.rol == "admin"]
    huellas = {
        (r.tipo_persona, r.persona_id): r for r in RegistroBiometrico.query.all()
    }
    return render_template(
        "biometria.html",
        jugadores=BD.jugadores,
        arbitros=BD.arbitros,
        administradores=administradores,
        huellas=huellas,
    )


@app.route("/biometria/<tipo_persona>/<int:persona_id>/registrar", methods=["POST"])
@admin_requerido
def registrar_huella(tipo_persona, persona_id):
    """Enrolamiento: pide varias capturas y guarda la plantilla en Postgres."""
    if tipo_persona not in TIPOS_PERSONA:
        abort(404)
    persona = _persona_biometrica(tipo_persona, persona_id)
    if persona is None:
        abort(404)

    nombre = _nombre_persona(persona)
    try:
        lector.registrar(
            tipo_persona,
            persona_id,
            nombre,
            correo=getattr(persona, "correo", None),
            cedula=getattr(persona, "cedula", None),
        )
        flash(f"Huella registrada para {nombre}.", "success")
    except ErrorHuella as e:
        flash(str(e), "danger")

    if tipo_persona == "jugador":
        return redirect(url_for("jugador_detalle", jugador_id=persona_id))
    return redirect(url_for("biometria_panel"))


# ══════════════════════════════════════════════════════════════════
#  Partidos
# ══════════════════════════════════════════════════════════════════

@app.route("/partidos")
@login_requerido
def partidos():
    return render_template(
        "partidos.html",
        partidos=sorted(BD.partidos, key=lambda p: p.fecha_hora, reverse=True),
    )


@app.route("/partidos/<int:partido_id>")
@login_requerido
def partido_detalle(partido_id):
    partido = BD.buscar_partido(partido_id)
    if partido is None:
        abort(404)
    return render_template(
        "partido_detalle.html",
        partido=partido,
        eventos=partido.obtener_eventos(),
        pagos=partido.obtener_pagos(),
    )


@app.route("/partidos/<int:partido_id>/checkin", methods=["POST"])
@admin_requerido
def checkin(partido_id):
    """
    Check-in con huella. El admin hace clic en "Huella" junto al jugador y
    Flask captura directo del lector (bloquea la petición mientras tanto);
    ya no hace falta que el navegador hable con nada aparte.
    Responde JSON con el carnet del jugador para mostrarlo en pantalla.
    """
    partido = BD.buscar_partido(partido_id)
    if partido is None:
        abort(404)

    datos = request.get_json(silent=True) or request.form
    jugador = BD.buscar_jugador(int(datos.get("jugador_id", 0)))
    if jugador is None:
        return jsonify({"ok": False, "error": "Jugador no encontrado."}), 404

    try:
        if lector.es_simulado():
            puntaje = None
            metodo = CheckIn.MANUAL
        else:
            veredicto = lector.verificar(
                "jugador", jugador.id, jugador.nombre_completo()
            )
            puntaje = veredicto.score
            metodo = CheckIn.HUELLA
        registro = partido.registrar_checkin(jugador, metodo)
    except (ErrorHuella, ValueError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    return jsonify({
        "ok": True,
        "puntaje": puntaje,
        "mensaje": registro.descripcion(),
        "faltantes": len(partido.jugadores_sin_checkin()),
        "listo_para_iniciar": partido.todos_confirmaron(),
        "carnet": {
            "nombre": jugador.nombre_completo(),
            "equipo": jugador.equipo.nombre,
            "numero": jugador.numero_camiseta,
            "cedula": jugador.cedula,
            "hora": registro.hora_registro.strftime("%H:%M:%S"),
        },
    })


@app.route("/partidos/<int:partido_id>/estado", methods=["POST"])
@admin_requerido
def cambiar_estado(partido_id):
    partido = BD.buscar_partido(partido_id)
    if partido is None:
        abort(404)

    acciones = {
        "iniciar": partido.iniciar_primer_tiempo,
        "medio_tiempo": partido.terminar_primer_tiempo,
        "segundo_tiempo": partido.iniciar_segundo_tiempo,
        "finalizar": partido.finalizar,
    }
    accion = request.form.get("accion")
    if accion not in acciones:
        flash(f"Acción desconocida: {accion}", "danger")
        return redirect(url_for("partido_detalle", partido_id=partido.id))

    try:
        nuevo_estado = acciones[accion]()
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("partido_detalle", partido_id=partido.id))

    if nuevo_estado == Partido.WALKOVER:
        correo.avisar_walkover(partido)
        flash(f"Walkover: {partido.motivo_walkover}", "warning")
    elif nuevo_estado == Partido.FINALIZADO:
        correo.enviar_recibos(partido)
        flash("Partido finalizado. Se enviaron los recibos por correo.", "success")
    else:
        flash(f"El partido pasó a {nuevo_estado.replace('_', ' ')}.", "success")

    return redirect(url_for("partido_detalle", partido_id=partido.id))


@app.route("/partidos/<int:partido_id>/cronometro")
@admin_requerido
def cronometro(partido_id):
    """
    Minuto y fase del partido, para el reloj de la vocalía.

    El reloj real vive en el objeto Partido (servidor): esta ruta solo lo
    lee. La pantalla la consulta cada pocos segundos para resincronizarse,
    así el minuto no se desvía aunque el admin recargue o abra la vocalía
    en otra máquina.
    """
    partido = BD.buscar_partido(partido_id)
    if partido is None:
        abort(404)
    return jsonify(partido.cronometro())


@app.route("/partidos/<int:partido_id>/gol", methods=["POST"])
@admin_requerido
def registrar_gol(partido_id):
    partido = BD.buscar_partido(partido_id)
    if partido is None:
        abort(404)

    try:
        jugador = BD.buscar_jugador(int(request.form.get("jugador_id", 0)))
        if jugador is None:
            raise ValueError("Seleccione el jugador que anotó el gol.")
        asistencia_id = request.form.get("asistencia_id")
        asistente = BD.buscar_jugador(int(asistencia_id)) if asistencia_id else None
        minuto = int(request.form.get("minuto", 0))
        if not 1 <= minuto <= 120:
            raise ValueError("El minuto debe estar entre 1 y 120.")
        gol = partido.registrar_gol(jugador, minuto, asistente)
        flash(gol.descripcion(), "success")
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("partido_detalle", partido_id=partido.id))


@app.route("/partidos/<int:partido_id>/tarjeta", methods=["POST"])
@admin_requerido
def registrar_tarjeta(partido_id):
    partido = BD.buscar_partido(partido_id)
    if partido is None:
        abort(404)

    try:
        jugador = BD.buscar_jugador(int(request.form.get("jugador_id", 0)))
        if jugador is None:
            raise ValueError("Seleccione el jugador amonestado.")
        minuto = int(request.form.get("minuto", 0))
        if not 1 <= minuto <= 120:
            raise ValueError("El minuto debe estar entre 1 y 120.")
        tarjeta = partido.registrar_tarjeta(
            jugador, request.form.get("tipo", Tarjeta.AMARILLA), minuto
        )
        flash(tarjeta.descripcion(), "success")
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("partido_detalle", partido_id=partido.id))


@app.route("/partidos/<int:partido_id>/pago", methods=["POST"])
@admin_requerido
def registrar_pago(partido_id):
    partido = BD.buscar_partido(partido_id)
    if partido is None:
        abort(404)

    equipo = BD.buscar_equipo(int(request.form.get("equipo_id", 0)))
    if equipo is None:
        flash("Equipo no encontrado.", "danger")
        return redirect(url_for("partido_detalle", partido_id=partido.id))

    try:
        pago = partido.completar_pago(equipo)
        correo.avisar_pago_completado(partido, equipo, pago.monto)
        flash(
            f"Pago registrado. Se avisó al capitán de {equipo.nombre} por correo.",
            "success",
        )
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("partido_detalle", partido_id=partido.id))


@app.route("/partidos/<int:partido_id>/recordar-pago", methods=["POST"])
@admin_requerido
def recordar_pago(partido_id):
    partido = BD.buscar_partido(partido_id)
    if partido is None:
        abort(404)

    equipo = BD.buscar_equipo(int(request.form.get("equipo_id", 0)))
    pago = partido.obtener_pago(equipo)
    correo.avisar_pago_pendiente(partido, equipo, pago.monto)
    flash(f"Recordatorio enviado al capitán de {equipo.nombre}.", "info")
    return redirect(url_for("partido_detalle", partido_id=partido.id))


# ══════════════════════════════════════════════════════════════════
#  Reportes
# ══════════════════════════════════════════════════════════════════

@app.route("/reportes")
@login_requerido
def reportes():
    return render_template(
        "reportes.html",
        posiciones=estadisticas.tabla_posiciones(BD.equipos, BD.partidos),
        goleadores=estadisticas.goleadores(BD.partidos),
        asistencias=estadisticas.asistencias(BD.partidos),
        tarjetas=estadisticas.tarjetas(BD.partidos),
    )


# ══════════════════════════════════════════════════════════════════
#  Errores
# ══════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def no_encontrado(e):
    return render_template("error.html", codigo=404,
                           mensaje="La página que busca no existe."), 404


@app.errorhandler(500)
def error_interno(e):
    return render_template("error.html", codigo=500,
                           mensaje="Ocurrió un error inesperado."), 500


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, port=5000)
