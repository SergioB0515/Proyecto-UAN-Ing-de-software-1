from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from flask_babel import gettext as _
from sqlalchemy import select
from app.extensions import db
from app.models.ticket import Ticket
from app.services.apelacion import ServicioApelaciones
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoCerradoError, ApelacionDuplicadaError,
    ApelacionNoEncontradaError, ApelacionNoPendienteError, MotivoRequeridoError,
    ErrorPersistencia,
)
from app.routes.decoradores import requiere_login, requiere_admin

apelaciones_bp = Blueprint("apelaciones", __name__)


@apelaciones_bp.route("/tickets/<int:ticket_id>/apelar", methods=["POST"])
@requiere_login
def solicitar(ticket_id):
    ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
    if ticket is None:
        flash(_("Ticket no encontrado"), "danger")
        return redirect(url_for("tickets.crear"))

    actor_id = session["usuario_id"]

    if actor_id != ticket.creador_id:
        flash(_("No tienes permiso para apelar este ticket"), "danger")
        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))

    motivo = request.form.get("motivo")
    try:
        ServicioApelaciones.solicitar_apelacion(
            ticket_id=ticket_id,
            solicitante_id=actor_id,
            motivo=motivo,
        )
        flash(_("Solicitud de apelacion enviada"), "success")
    except (TicketNoCerradoError, ApelacionDuplicadaError,
            MotivoRequeridoError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.detalle", ticket_id=ticket_id))


@apelaciones_bp.route("/apelaciones", methods=["GET"])
@requiere_admin
def pendientes():
    
    apelaciones = ServicioApelaciones.listar_pendientes()
    return render_template("apelaciones_pendientes.html", apelaciones=apelaciones)


def _destino_tras_decision(ticket_id):
    if request.form.get("origen") == "detalle" and ticket_id:
        return url_for("tickets.detalle", ticket_id=ticket_id)
    return url_for("apelaciones.pendientes")


@apelaciones_bp.route("/apelaciones/<int:apelacion_id>/aceptar", methods=["POST"])
@requiere_admin
def aceptar(apelacion_id):
    actor_id = session["usuario_id"]
    ticket_id = request.form.get("ticket_id")
    try:
        ServicioApelaciones.aceptar_apelacion(apelacion_id=apelacion_id, actor_id=actor_id)
        flash(_("Apelacion aceptada"), "success")
    except (ApelacionNoEncontradaError, ApelacionNoPendienteError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(_destino_tras_decision(ticket_id))


@apelaciones_bp.route("/apelaciones/<int:apelacion_id>/rechazar", methods=["POST"])
@requiere_admin
def rechazar(apelacion_id):
    actor_id = session["usuario_id"]
    ticket_id = request.form.get("ticket_id")
    try:
        ServicioApelaciones.rechazar_apelacion(apelacion_id=apelacion_id, actor_id=actor_id)
        flash(_("Apelacion rechazada"), "success")
    except (ApelacionNoEncontradaError, ApelacionNoPendienteError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(_destino_tras_decision(ticket_id))