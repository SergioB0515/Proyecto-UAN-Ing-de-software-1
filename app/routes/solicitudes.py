from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_babel import gettext as _
from sqlalchemy import select
from app.extensions import db
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.transferencia import SolicitudTransferencia
from app.models.enum import RolUsuario, Categoria, Prioridad
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoEnProgresoError, SolicitudDuplicadaError,
    SolicitudNoEncontradaError, SolicitudNoPendienteError, AgenteDestinoInvalidoError,
    ErrorPersistencia, MotivoRequeridoError, AreaDestinoInvalidaError,PrioridadDestinoInvalidaError
)
from app.routes.decoradores import requiere_login, requiere_admin

solicitudes_bp = Blueprint("solicitudes", __name__)


@solicitudes_bp.route("/tickets/<int:ticket_id>/solicitar-transferencia", methods=["POST"])
@requiere_login
def solicitar(ticket_id):
    ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
    if ticket is None:
        flash(_("Ticket no encontrado"), "danger")
        return redirect(url_for("tickets.crear"))

    rol = session.get("rol")
    actor_id = session["usuario_id"]
    
    if rol != RolUsuario.ADMIN and actor_id != ticket.agente_id:
        flash(_("No tienes permiso para transferir este ticket"), "danger")
        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))
    agente_destino_id = request.form.get("agente_destino_id", type=int)
    motivo = request.form.get("motivo") or None

    try:
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket_id, agente_destino_id=agente_destino_id,
            solicitante_id=actor_id, motivo=motivo,
        )
        flash(_("Solicitud de transferencia enviada"), "success")
    except (TicketNoEncontradoError, TicketNoEnProgresoError, SolicitudDuplicadaError,
            AgenteDestinoInvalidoError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.detalle", ticket_id=ticket_id))


@solicitudes_bp.route("/solicitudes", methods=["GET"])
@requiere_login
def pendientes():
    actor_id = session["usuario_id"]
    rol = session.get("rol")
    es_admin = rol == RolUsuario.ADMIN

    if es_admin:
        solicitudes = ServicioSolicitudesTransferencia.listar_transferencias_pendientes()
    else:
        solicitudes = ServicioSolicitudesTransferencia.listar_pendientes_para_agente(actor_id)

    destino_ids = {s.agente_destino_id for s in solicitudes}
    destinos = db.session.execute(select(Usuario).where(Usuario.id.in_(destino_ids))).scalars().all()
    nombres_por_id = {u.id: u.nombre for u in destinos}

    return render_template(
        "solicitudes_pendientes.html",
        solicitudes=solicitudes,
        nombres_por_id=nombres_por_id,
        es_admin=es_admin,
    )
@solicitudes_bp.route("/solicitudes/<int:solicitud_id>/aceptar", methods=["POST"])
@requiere_login
def aceptar(solicitud_id):
    solicitud = db.session.execute(
        select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
    ).scalar()
    if solicitud is None:
        flash(_("Solicitud no encontrada"), "danger")
        return redirect(url_for("solicitudes.pendientes"))

    actor_id = session["usuario_id"]

    if actor_id != solicitud.agente_destino_id:
        flash(_("Usted no puede aceptar este ticket"), "warning")
        return redirect(url_for("solicitudes.pendientes"))
    try:
        ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud_id, actor_id)
        flash(_("Transferencia aceptada"), "success")
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
        flash(_("Solicitud no encontrada"), "danger")
        return redirect(url_for("solicitudes.pendientes"))

    actor_id = session["usuario_id"]

    if actor_id != solicitud.agente_destino_id:
        flash(_("Usted no puede rechazar este ticket"), "warning")
        return redirect(url_for("solicitudes.pendientes"))
    try:
        ServicioSolicitudesTransferencia.rechazar_solicitud(solicitud_id, actor_id)
        flash(_("Transferencia rechazada"), "success")
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
        flash(_("Solicitud no encontrada"), "danger")
        return redirect(url_for("solicitudes.pendientes"))

    actor_id = session["usuario_id"]
    rol = session.get("rol")
    
    if rol != RolUsuario.ADMIN and actor_id != solicitud.solicitante_id:
        flash(_("No tienes permiso para cancelar este ticket"), "danger")
        return redirect(url_for("tickets.detalle", ticket_id=solicitud.ticket_id))
    try:
        ServicioSolicitudesTransferencia.cancelar_solicitud(solicitud_id, actor_id)
        flash(_("Solicitud cancelada"), "success")
    except (SolicitudNoEncontradaError, SolicitudNoPendienteError,
            ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.detalle", ticket_id=solicitud.ticket_id))

@solicitudes_bp.route("/tickets/<int:ticket_id>/escalar-area", methods=["POST"])
@requiere_login
def escalar_area(ticket_id):

    ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
    if ticket is None:
        flash(_("Ticket no encontrado"), "danger")
        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))

    rol = session.get("rol")
    actor_id = session["usuario_id"]
    
    if rol != RolUsuario.ADMIN and actor_id != ticket.agente_id:
        flash(_("No tienes permiso para transferir este ticket"), "danger")
        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))
    
    area_destino_raw = request.form.get("area_destino")
    try:
        area_destino= Categoria(area_destino_raw)
    except ValueError:
        flash(_("Área destino no válida"), "danger")
        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))
        
    motivo = request.form.get("motivo", "")
    
    try:
        ServicioSolicitudesTransferencia.escalar_a_area(
            ticket_id=ticket_id, area_destino=area_destino,
            solicitante_id=actor_id, motivo=motivo,
        )
        flash(_("Solicitud de escalamiento enviada"), "success")
    except (TicketNoEncontradoError, TicketNoEnProgresoError, SolicitudDuplicadaError,
            AreaDestinoInvalidaError,MotivoRequeridoError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.detalle", ticket_id=ticket_id))


@solicitudes_bp.route("/escalamientos", methods=["GET"])
@requiere_admin
def escalamientos_pendientes():
    escalamientos= ServicioSolicitudesTransferencia.listar_escalamientos_pendientes()
    return render_template("escalamientos_pendientes.html", escalamientos=escalamientos)



@solicitudes_bp.route("/escalamientos/<int:solicitud_id>/aprobar", methods=["POST"])
@requiere_admin
def aprobar_escalamiento(solicitud_id):
    actor_id = session["usuario_id"]
    try:
        ServicioSolicitudesTransferencia.aprobar_escalamiento(solicitud_id,actor_id)
        flash(_("Escalamiento aprobado"), "success")
    except (SolicitudNoEncontradaError, SolicitudNoPendienteError,
                TicketNoEnProgresoError, ErrorPersistencia) as e:
            flash(str(e), "danger")
    return redirect(url_for("solicitudes.escalamientos_pendientes"))
        


@solicitudes_bp.route("/escalamientos/<int:solicitud_id>/rechazar", methods=["POST"])
@requiere_admin
def rechazar_escalamiento(solicitud_id):
    actor_id = session["usuario_id"]
    try:
        ServicioSolicitudesTransferencia.rechazar_escalamiento(solicitud_id,actor_id)
        flash(_("Escalamiento rechazado"), "success")
    except (SolicitudNoEncontradaError, SolicitudNoPendienteError,
                TicketNoEnProgresoError, ErrorPersistencia) as e:
            flash(str(e), "danger")
    return redirect(url_for("solicitudes.escalamientos_pendientes"))

@solicitudes_bp.route("/tickets/<int:ticket_id>/cambiar-prioridad", methods=["POST"])
@requiere_login
def cambiar_prioridad(ticket_id):

    ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
    if ticket is None:
        flash(_("Ticket no encontrado"), "danger")
        return redirect(url_for("tickets.crear"))
    
    rol = session.get("rol")
    actor_id = session["usuario_id"]
    
    if rol != RolUsuario.ADMIN and actor_id != ticket.agente_id:
        flash(_("No tienes permiso para cambiar este ticket"), "danger")
        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))
    
    prioridad_destino_raw = request.form.get("prioridad_destino")
    try:
        prioridad_destino= Prioridad(prioridad_destino_raw)
    except ValueError:
        flash(_("La prioridad no es válida"), "danger")
        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))
        
    motivo = request.form.get("motivo", "")
    
    try:
        ServicioSolicitudesTransferencia.cambiar_prioridad(
            ticket_id=ticket_id, prioridad_destino=prioridad_destino,
            solicitante_id=actor_id, motivo=motivo,
        )
        flash(_("Solicitud de cambio de prioridad enviada"), "success")
    except (TicketNoEncontradoError, TicketNoEnProgresoError, SolicitudDuplicadaError,
            PrioridadDestinoInvalidaError, MotivoRequeridoError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.detalle", ticket_id=ticket_id))


@solicitudes_bp.route("/cambios-prioridad", methods=["GET"])
@requiere_admin
def cambios_prioridad_pendientes():
    
    cambios= ServicioSolicitudesTransferencia.listar_cambios_prioridad_pendientes()
    return render_template("cambios_prioridad_pendientes.html", cambios=cambios)



@solicitudes_bp.route("/cambios-prioridad/<int:solicitud_id>/aprobar", methods=["POST"])
@requiere_admin
def aprobar_cambio_prioridad(solicitud_id):

    actor_id = session["usuario_id"]
    
    try:
        ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(solicitud_id,actor_id)
        flash(_("Cambio de prioridad aprobado"), "success")
    except (SolicitudNoEncontradaError, SolicitudNoPendienteError,
                TicketNoEnProgresoError, ErrorPersistencia) as e:
            flash(str(e), "danger")
    return redirect(url_for("solicitudes.cambios_prioridad_pendientes"))
    


@solicitudes_bp.route("/cambios-prioridad/<int:solicitud_id>/rechazar", methods=["POST"])
@requiere_admin
def rechazar_cambio_prioridad(solicitud_id):
    actor_id = session["usuario_id"]
    
    try:
        ServicioSolicitudesTransferencia.rechazar_cambio_prioridad(solicitud_id,actor_id)
        flash(_("Cambio de prioridad rechazado"), "success")
    except (SolicitudNoEncontradaError, SolicitudNoPendienteError,
                TicketNoEnProgresoError, ErrorPersistencia) as e:
            flash(str(e), "danger")
    return redirect(url_for("solicitudes.cambios_prioridad_pendientes"))