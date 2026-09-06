from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy import select
from app.extensions import db
from app.models.ticket import Ticket
from app.models.transferencia import SolicitudTransferencia
from app.models.enum import RolUsuario
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoEnProgresoError, SolicitudDuplicadaError,
    SolicitudNoEncontradaError, SolicitudNoPendienteError, AgenteDestinoInvalidoError,
    ErrorPersistencia,
)
from app.routes.decoradores import requiere_login

solicitudes_bp = Blueprint("solicitudes", __name__)


@solicitudes_bp.route("/tickets/<int:ticket_id>/solicitar-transferencia", methods=["POST"])
@requiere_login
def solicitar(ticket_id):
    ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
    if ticket is None:
        flash("Ticket no encontrado", "danger")
        return redirect(url_for("tickets.crear"))

    rol = session.get("rol")
    actor_id = session["usuario_id"]
    
    if rol != RolUsuario.ADMIN and actor_id != ticket.agente_id:
        flash("No tienes permiso para transferir este ticket", "danger")
        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))
    agente_destino_id = request.form.get("agente_destino_id", type=int)
    motivo = request.form.get("motivo") or None

    try:
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket_id, agente_destino_id=agente_destino_id,
            solicitante_id=actor_id, motivo=motivo,
        )
        flash("Solicitud de transferencia enviada", "success")
    except (TicketNoEncontradoError, TicketNoEnProgresoError, SolicitudDuplicadaError,
            AgenteDestinoInvalidoError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.detalle", ticket_id=ticket_id))


@solicitudes_bp.route("/solicitudes", methods=["GET"])
@requiere_login
def pendientes():
    actor_id = session["usuario_id"]
    solicitudes = ServicioSolicitudesTransferencia.listar_pendientes_para_agente(actor_id)
    return render_template("solicitudes_pendientes.html", solicitudes=solicitudes)


@solicitudes_bp.route("/solicitudes/<int:solicitud_id>/aceptar", methods=["POST"])
@requiere_login
def aceptar(solicitud_id):
    solicitud = db.session.execute(
        select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
    ).scalar()
    if solicitud is None:
        flash("Solicitud no encontrada", "danger")
        return redirect(url_for("solicitudes.pendientes"))

    actor_id = session["usuario_id"]

    if actor_id != solicitud.agente_destino_id:
        flash("Usted no puede aceptar este ticket", "warning")
        return redirect(url_for("solicitudes.pendientes"))
    try:
        ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud_id, actor_id)
        flash("Transferencia aceptada", "success")
    except (SolicitudNoEncontradaError, SolicitudNoPendienteError,
            TicketNoEnProgresoError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("solicitudes.pendientes"))


@solicitudes_bp.route("/solicitudes/<int:solicitud_id>/rechazar", methods=["POST"])
@requiere_login
def rechazar(solicitud_id):
    
    solicitud = db.session.execute(
        select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
    ).scalar()
    if solicitud is None:
        flash("Solicitud no encontrada", "danger")
        return redirect(url_for("solicitudes.pendientes"))

    actor_id = session["usuario_id"]

    if actor_id != solicitud.agente_destino_id:
        flash("Usted no puede rechazar este ticket", "warning")
        return redirect(url_for("solicitudes.pendientes"))
    try:
        ServicioSolicitudesTransferencia.rechazar_solicitud(solicitud_id, actor_id)
        flash("Transferencia rechazada", "success")
    except (SolicitudNoEncontradaError, SolicitudNoPendienteError,
            ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("solicitudes.pendientes"))


@solicitudes_bp.route("/solicitudes/<int:solicitud_id>/cancelar", methods=["POST"])
@requiere_login
def cancelar(solicitud_id):
    
    solicitud = db.session.execute(
        select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
    ).scalar()
    if solicitud is None:
        flash("Solicitud no encontrada", "danger")
        return redirect(url_for("solicitudes.pendientes"))

    actor_id = session["usuario_id"]
    rol = session.get("rol")
    
    if rol != RolUsuario.ADMIN and actor_id != solicitud.solicitante_id:
        flash("No tienes permiso para cancelar este ticket", "danger")
        return redirect(url_for("tickets.detalle", ticket_id=solicitud.ticket_id))
    try:
        ServicioSolicitudesTransferencia.cancelar_solicitud(solicitud_id, actor_id)
        flash("Solicitud cancelada", "success")
    except (SolicitudNoEncontradaError, SolicitudNoPendienteError,
            ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("solicitudes.pendientes"))