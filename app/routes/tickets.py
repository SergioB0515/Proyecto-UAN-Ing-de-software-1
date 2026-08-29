from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy import select
from app.extensions import db
from app.services.tickets import ServicioTickets, TRANSICIONES_VALIDAS
from app.services.exceptions import TransicionInvalidaError, AgenteYaAsignadoError, TicketNoEncontradoError
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import Categoria, EstadoTicket, RolUsuario
from app.routes.decoradores import requiere_login

tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("/tickets/crear", methods=["GET", "POST"])
@requiere_login
def crear():
    if request.method == "POST":
        texto = request.form["texto"]

        creador = db.session.execute(
            select(Usuario).where(Usuario.id == session["usuario_id"])
        ).scalar()

        exito, ticket = ServicioTickets.crear_ticket(creador=creador, texto=texto)

        if exito:
            flash(f"Ticket #{ticket.id} creado. Categoría: {ticket.categoria.value}, prioridad: {ticket.prioridad.value}", "success")
        else:
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

    tickets = ServicioTickets.listar_tickets_por_area(categoria)

    # Transiciones válidas por ticket, para armar el <select> de cada fila
    transiciones_por_ticket = {
        t.id: [e.value for e in TRANSICIONES_VALIDAS[t.estado]] for t in tickets
    }

    # Agentes del área, para el campo de asignación al pasar a EN_PROGRESO
    agentes_del_area = db.session.execute(
        select(Usuario).where(Usuario.area_soporte == categoria)
    ).scalars().all()

    return render_template(
        "tickets_por_area.html",
        tickets=tickets,
        area=area,
        transiciones_por_ticket=transiciones_por_ticket,
        agentes_del_area=agentes_del_area,
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
        exito, estado = ServicioTickets.cambiar_estado(
            ticket_id=ticket_id, nuevo_estado=nuevo_estado,
            actor_id=actor_id, agente_id=agente_id
        )
        flash(f"Ticket #{ticket_id} actualizado a {estado.value}", "success")
    except (TransicionInvalidaError, AgenteYaAsignadoError, TicketNoEncontradoError) as e:
        flash(str(e), "danger")

    return redirect(url_for("tickets.listar_por_area", area=ticket.categoria.value))