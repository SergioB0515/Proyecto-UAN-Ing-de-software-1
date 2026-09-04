from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy import select
from app.extensions import db
from app.services.tickets import ServicioTickets, TRANSICIONES_VALIDAS
from app.services.exceptions import TransicionInvalidaError, AgenteYaAsignadoError, ComentarioVacioError, TicketNoEncontradoError, TicketNoEnProgresoError, ErrorPersistencia
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.comentario import Comentario 
from app.models.enum import Categoria, EstadoTicket, RolUsuario, AccionAuditoria, Prioridad
from app.routes.decoradores import requiere_login
from app.services.gestor_sla import GestorSLA
from datetime import datetime, timedelta
tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("/tickets/crear", methods=["GET", "POST"])
@requiere_login
def crear():
    if request.method == "POST":
        texto = request.form["texto"]

        creador = db.session.execute(
            select(Usuario).where(Usuario.id == session["usuario_id"])
        ).scalar()

        try:
            ticket = ServicioTickets.crear_ticket(creador=creador, texto=texto)
            flash(f"Ticket #{ticket.id} creado. Categoría: {ticket.categoria.value}, prioridad: {ticket.prioridad.value}", "success")
        except ErrorPersistencia:
            flash("No se pudo crear el ticket, intenta de nuevo", "danger")

        return redirect(url_for("tickets.crear"))

    return render_template("crear_ticket.html")


@tickets_bp.route("/tickets/area/<area>")
@requiere_login
def listar_por_area(area):
    rol = session.get("rol")

    try:
        categoria = Categoria(area)
    except ValueError:
        flash("Área no válida", "danger")
        return redirect(url_for("tickets.crear"))

    if rol != RolUsuario.ADMIN:
        agente = db.session.execute(
            select(Usuario).where(Usuario.id == session["usuario_id"])
        ).scalar()

        if agente.area_soporte is None or agente.area_soporte != categoria:
            flash("No tienes permiso para ver tickets de esa área", "warning")
            return redirect(url_for("tickets.crear"))


    estado_raw = request.args.get("estado")
    estado = None
    if estado_raw:
        try:
            estado = EstadoTicket(estado_raw)
        except ValueError:
            estado = None

    prioridad_raw = request.args.get("prioridad")
    prioridad = None
    if prioridad_raw:
        try:
            prioridad = Prioridad(prioridad_raw)
        except ValueError:
            prioridad = None

    fecha_desde_raw = request.args.get("fecha_desde")
    fecha_desde = None
    if fecha_desde_raw:  
        try:
            fecha_desde = datetime.strptime(fecha_desde_raw, "%Y-%m-%d")
        except ValueError:
            fecha_desde = None

    fecha_hasta_raw = request.args.get("fecha_hasta")
    fecha_hasta = None
    if fecha_hasta_raw:
        try:
            fecha_hasta = datetime.strptime(fecha_hasta_raw, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            fecha_hasta = None

    tickets = ServicioTickets.listar_tickets_por_area(
        categoria,
        estado=estado,
        prioridad=prioridad,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    transiciones_por_ticket = {
        t.id: [e.value for e in TRANSICIONES_VALIDAS[t.estado]] for t in tickets
    }

    agentes_del_area = db.session.execute(
        select(Usuario).where(Usuario.area_soporte == categoria)
    ).scalars().all()

    vencidos, proximos = GestorSLA.verificar_vencimientos()
    ids_vencidos = {t.id for t in vencidos}
    ids_proximos = {t.id for t in proximos}


    filtros_actuales = {
    "prioridad": prioridad_raw,
    "estado": estado_raw,
    "fecha_desde": fecha_desde_raw,
    "fecha_hasta": fecha_hasta_raw,
}

    return render_template(
        "tickets_por_area.html",
        tickets=tickets,
        area=area,
        transiciones_por_ticket=transiciones_por_ticket,
        agentes_del_area=agentes_del_area,
        ids_vencidos=ids_vencidos,
        ids_proximos=ids_proximos,
        filtros_actuales=filtros_actuales,
    )


@tickets_bp.route("/tickets/<int:ticket_id>/cambiar-estado", methods=["POST"])
@requiere_login
def cambiar_estado(ticket_id):
    rol = session.get("rol")
    actor_id = session["usuario_id"]

    ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
    if ticket is None:
        flash("Ticket no encontrado", "danger")
        return redirect(url_for("tickets.crear"))

    if rol != RolUsuario.ADMIN:
        agente = db.session.execute(select(Usuario).where(Usuario.id == actor_id)).scalar()
        if agente.area_soporte is None or agente.area_soporte != ticket.categoria:
            flash("No tienes permiso sobre tickets de esa área", "warning")
            return redirect(url_for("tickets.crear"))

    nuevo_estado = EstadoTicket(request.form["nuevo_estado"])
    agente_id = request.form.get("agente_id", type=int)

    try:
        estado = ServicioTickets.cambiar_estado(
            ticket_id=ticket_id, nuevo_estado=nuevo_estado,
            actor_id=actor_id, agente_id=agente_id
        )
        flash(f"Ticket #{ticket_id} actualizado a {estado.value}", "success")
    except (TransicionInvalidaError, AgenteYaAsignadoError, TicketNoEncontradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.listar_por_area", area=ticket.categoria.value))
@tickets_bp.route("/tickets/<int:ticket_id>/reasignar", methods=["POST"])
@requiere_login
def reasignar(ticket_id):
    rol = session.get("rol")
    actor_id = session["usuario_id"]

    ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
    if ticket is None:
        flash("Ticket no encontrado", "danger")
        return redirect(url_for("tickets.crear"))

    if rol != RolUsuario.ADMIN:
        agente = db.session.execute(select(Usuario).where(Usuario.id == actor_id)).scalar()
        if agente.area_soporte is None or agente.area_soporte != ticket.categoria:
            flash("No tienes permiso sobre tickets de esa área", "warning")
            return redirect(url_for("tickets.crear"))

    nuevo_agente_id = request.form.get("nuevo_agente_id", type=int)

    try:
        ServicioTickets.reasignar_agente(
            ticket_id=ticket_id, nuevo_agente_id=nuevo_agente_id, actor_id=actor_id
        )
        flash(f"Ticket #{ticket_id} reasignado correctamente", "success")
    except (TicketNoEncontradoError, TicketNoEnProgresoError, AgenteYaAsignadoError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.listar_por_area", area=ticket.categoria.value))

@tickets_bp.route("/tickets/<int:ticket_id>", methods=["GET", "POST"])
@requiere_login
def detalle(ticket_id):
    ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
    if ticket is None:
        flash("Ticket no encontrado", "danger")
        return redirect(url_for("tickets.crear"))

    if request.method == "POST":
        texto = request.form["texto"]
        autor_id = session["usuario_id"]

        try:
            ServicioTickets.agregar_comentario(ticket_id=ticket_id, autor_id=autor_id, texto=texto)
            flash("Comentario agregado", "success")
        except (ComentarioVacioError, TicketNoEncontradoError, ErrorPersistencia) as e:
            flash(str(e), "danger")

        return redirect(url_for("tickets.detalle", ticket_id=ticket_id))

    comentarios = db.session.execute(
        select(Comentario).where(Comentario.ticket_id == ticket_id).order_by(Comentario.fecha)
    ).scalars().all()

    autores_ids = {c.autor_id for c in comentarios}
    autores = db.session.execute(select(Usuario).where(Usuario.id.in_(autores_ids))).scalars().all()
    nombres_por_id = {u.id: u.nombre for u in autores}

    return render_template(
        "ticket_detalle.html",
        ticket=ticket,
        comentarios=comentarios,
        nombres_por_id=nombres_por_id,
    )
