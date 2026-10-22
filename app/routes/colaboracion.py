from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_babel import gettext as _

from app.extensions import db
from app.models.enum import Categoria
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.routes.decoradores import requiere_login, requiere_personal
from app.services.adjuntos import ServicioAdjuntos
from app.services.encuestas import ServicioEncuestas
from app.services.exceptions import (
    AdjuntoInvalidoError,
    AdjuntoNoEncontradoError,
    EncuestaNoDisponibleError,
    EncuestaYaRespondidaError,
    ErrorPersistencia,
    PermisoDenegadoError,
    RespuestaNoEncontradaError,
    TicketNoEncontradoError,
)
from app.services.permisos import ServicioPermisos
from app.services.respuestas_predefinidas import ServicioRespuestasPredefinidas
from app.services.seguimiento import ServicioSeguimiento

colaboracion_bp = Blueprint("colaboracion", __name__)


def _usuario_actual():
    return db.session.get(Usuario, session["usuario_id"])


def _ticket_visible_o_404(ticket_id):
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None or not ServicioPermisos.puede_ver_ticket(_usuario_actual(), ticket):
        abort(404)
    return ticket


@colaboracion_bp.route("/tickets/<int:ticket_id>/adjuntos", methods=["POST"])
@requiere_login
def subir_adjuntos(ticket_id):
    _ticket_visible_o_404(ticket_id)
    archivos = [a for a in request.files.getlist("archivos") if a and a.filename]
    if not archivos:
        flash(_("No se seleccionó ningún archivo"), "warning")
    subidos = 0
    for archivo in archivos:
        try:
            ServicioAdjuntos.guardar(ticket_id, session["usuario_id"], archivo)
            subidos += 1
        except (AdjuntoInvalidoError, TicketNoEncontradoError, ErrorPersistencia) as e:
            flash(f"{archivo.filename}: {e}", "danger")
    if subidos:
        flash(_("%(n)s archivo(s) adjuntado(s)", n=subidos), "success")
    return redirect(url_for("tickets.detalle", ticket_id=ticket_id) + "#adjuntos")


@colaboracion_bp.route("/adjuntos/<int:adjunto_id>")
@requiere_login
def descargar_adjunto(adjunto_id):
    try:
        adjunto = ServicioAdjuntos.obtener(adjunto_id)
    except AdjuntoNoEncontradoError:
        abort(404)
    _ticket_visible_o_404(adjunto.ticket_id)
    ruta = ServicioAdjuntos.ruta(adjunto)
    try:
        respuesta = send_file(
            ruta,
            mimetype=adjunto.tipo_mime,
            as_attachment=not (adjunto.es_imagen or adjunto.extension == "pdf") or request.args.get("descargar") == "1",
            download_name=adjunto.nombre_original,
            max_age=0,
        )
    except FileNotFoundError:
        abort(404)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["Cache-Control"] = "private, no-store"
    return respuesta


@colaboracion_bp.route("/adjuntos/<int:adjunto_id>/eliminar", methods=["POST"])
@requiere_login
def eliminar_adjunto(adjunto_id):
    try:
        adjunto = ServicioAdjuntos.obtener(adjunto_id)
    except AdjuntoNoEncontradoError:
        abort(404)
    ticket_id = adjunto.ticket_id
    _ticket_visible_o_404(ticket_id)
    try:
        ServicioAdjuntos.eliminar(adjunto_id, session["usuario_id"])
        flash(_("Archivo eliminado"), "success")
    except (PermisoDenegadoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("tickets.detalle", ticket_id=ticket_id) + "#adjuntos")


@colaboracion_bp.route("/tickets/<int:ticket_id>/seguir", methods=["POST"])
@requiere_personal
def seguir(ticket_id):
    _ticket_visible_o_404(ticket_id)
    try:
        if ServicioSeguimiento.sigue(ticket_id, session["usuario_id"]):
            ServicioSeguimiento.dejar_de_seguir(ticket_id, session["usuario_id"])
            flash(_("Ya no sigues este ticket"), "info")
        else:
            ServicioSeguimiento.seguir(ticket_id, _usuario_actual())
            flash(_("Ahora sigues este ticket: te avisaremos de su actividad"), "success")
    except (PermisoDenegadoError, TicketNoEncontradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("tickets.detalle", ticket_id=ticket_id))


@colaboracion_bp.route("/tickets/<int:ticket_id>/encuesta", methods=["POST"])
@requiere_login
def responder_encuesta(ticket_id):
    _ticket_visible_o_404(ticket_id)
    try:
        ServicioEncuestas.responder(
            ticket_id, session["usuario_id"],
            request.form.get("puntuacion"), request.form.get("comentario"),
        )
        flash(_("¡Gracias por tu opinión!"), "success")
    except (ValueError, EncuestaNoDisponibleError, EncuestaYaRespondidaError, PermisoDenegadoError,
            TicketNoEncontradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("tickets.detalle", ticket_id=ticket_id))


def _categoria_formulario():
    valor = request.form.get("categoria") or None
    if valor is None:
        return None
    try:
        return Categoria(valor)
    except ValueError:
        raise ValueError(_("Categoría no válida"))


@colaboracion_bp.route("/respuestas", methods=["GET", "POST"])
@requiere_personal
def respuestas():
    usuario = _usuario_actual()
    if request.method == "POST":
        try:
            ServicioRespuestasPredefinidas.crear(
                usuario.id, request.form.get("titulo"), request.form.get("contenido"),
                categoria=_categoria_formulario(), compartida=request.form.get("compartida") == "1",
            )
            flash(_("Respuesta predefinida creada"), "success")
        except (ValueError, PermisoDenegadoError, ErrorPersistencia) as e:
            flash(str(e), "danger")
        return redirect(url_for("colaboracion.respuestas"))
    return render_template(
        "respuestas_predefinidas.html",
        respuestas=ServicioRespuestasPredefinidas.listar_para(usuario.id),
        nombres_por_id={u.id: u.nombre for u in db.session.execute(db.select(Usuario)).scalars()},
        editar_id=request.args.get("editar", type=int),
    )


@colaboracion_bp.route("/respuestas/<int:respuesta_id>/editar", methods=["POST"])
@requiere_personal
def editar_respuesta(respuesta_id):
    try:
        ServicioRespuestasPredefinidas.actualizar(
            session["usuario_id"], respuesta_id, request.form.get("titulo"), request.form.get("contenido"),
            categoria=_categoria_formulario(), compartida=request.form.get("compartida") == "1",
        )
        flash(_("Respuesta predefinida actualizada"), "success")
    except (ValueError, PermisoDenegadoError, RespuestaNoEncontradaError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("colaboracion.respuestas"))


@colaboracion_bp.route("/respuestas/<int:respuesta_id>/eliminar", methods=["POST"])
@requiere_personal
def eliminar_respuesta(respuesta_id):
    try:
        ServicioRespuestasPredefinidas.eliminar(session["usuario_id"], respuesta_id)
        flash(_("Respuesta predefinida eliminada"), "success")
    except (PermisoDenegadoError, RespuestaNoEncontradaError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("colaboracion.respuestas"))


@colaboracion_bp.route("/respuestas/<int:respuesta_id>/uso", methods=["POST"])
@requiere_personal
def usar_respuesta(respuesta_id):
    try:
        respuesta = ServicioRespuestasPredefinidas.registrar_uso(respuesta_id, session["usuario_id"])
    except (RespuestaNoEncontradaError, ErrorPersistencia):
        return jsonify({"ok": False}), 404
    return jsonify({"ok": True, "usos": respuesta.usos})
