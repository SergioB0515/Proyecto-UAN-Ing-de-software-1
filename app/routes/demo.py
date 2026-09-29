from functools import wraps
from flask import Blueprint, render_template, request, session, jsonify, current_app, abort, url_for
from flask_babel import gettext as _
from sqlalchemy import select
from app.extensions import db
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import EstadoTicket
from app.routes.decoradores import requiere_admin
from app.services.demo import ServicioDemo, plantillas_notificacion, plantillas_correo
from app.services.exceptions import TicketNoEncontradoError, ErrorPersistencia
from app.notificaciones_i18n import render as render_notif
from app.traducciones import etiqueta

demo_bp = Blueprint("demo", __name__)


def requiere_modo_demo(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_app.config.get("MODO_DEMO"):
            abort(404)
        return func(*args, **kwargs)
    return wrapper


def _ticket_id_form():
    valor = request.form.get("ticket_id") or request.args.get("ticket_id")
    return int(valor) if valor and valor.isdigit() else None


def _ok(mensaje, **extra):
    return jsonify({"ok": True, "mensaje": mensaje, **extra})


def _error(mensaje, codigo=400):
    return jsonify({"ok": False, "mensaje": mensaje}), codigo


@demo_bp.route("/admin/demo")
@requiere_admin
@requiere_modo_demo
def panel():
    usuarios = db.session.execute(select(Usuario).order_by(Usuario.rol, Usuario.nombre)).scalars().all()
    tickets = db.session.execute(select(Ticket).order_by(Ticket.id.desc()).limit(50)).scalars().all()
    tickets_activos = [t for t in tickets if t.estado != EstadoTicket.CERRADO]
    admin = db.session.get(Usuario, session["usuario_id"])
    return render_template(
        "demo.html",
        usuarios=usuarios,
        tickets=tickets,
        tickets_activos=tickets_activos,
        plantillas={k: render_notif(v, "N") for k, v in plantillas_notificacion().items()},
        plantillas_correo={k: render_notif(v, "N") for k, v in plantillas_correo().items()},
        email_admin=admin.email,
        correo_configurado=bool(current_app.config.get("MAIL_USERNAME") and current_app.config.get("MAIL_PASSWORD")),
        correo_suprimido=bool(current_app.config.get("MAIL_SUPPRESS_SEND")),
    )


@demo_bp.route("/admin/demo/notificacion", methods=["POST"])
@requiere_admin
@requiere_modo_demo
def notificacion():
    usuario_id = request.form.get("usuario_id", type=int) or session["usuario_id"]
    try:
        r = ServicioDemo.enviar_notificacion(usuario_id, request.form.get("plantilla"), _ticket_id_form())
    except (ValueError, TicketNoEncontradoError) as e:
        return _error(str(e))
    usuario = db.session.get(Usuario, usuario_id)
    mensaje = _("Notificación enviada a %(nombre)s", nombre=usuario.nombre if usuario else usuario_id)
    if r["con_correo"]:
        mensaje += " " + _("(esta plantilla también dispara un correo a %(email)s)", email=usuario.email)
    return _ok(mensaje, **r)


@demo_bp.route("/admin/demo/rafaga", methods=["POST"])
@requiere_admin
@requiere_modo_demo
def rafaga():
    usuario_id = session["usuario_id"]
    nombres = ["TRANSFERENCIA_NUEVA", "ESCALAMIENTO_PENDIENTE", "CLASIFICACION_PENDIENTE"]
    for nombre in nombres:
        ServicioDemo.enviar_notificacion(usuario_id, nombre, _ticket_id_form())
    return _ok(_("%(n)s notificaciones enviadas a tu usuario", n=len(nombres)))


@demo_bp.route("/admin/demo/correo", methods=["POST"])
@requiere_admin
@requiere_modo_demo
def correo():
    destinatario = (request.form.get("destinatario") or "").strip()
    if "@" not in destinatario:
        return _error(_("Correo destinatario inválido"))
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        return _error(_("El envío de correos está suprimido (TESTING=true)"))
    if not current_app.config.get("MAIL_USERNAME"):
        return _error(_("Falta configurar MAIL_USERNAME y MAIL_PASSWORD en el .env"))
    try:
        ServicioDemo.enviar_correo(destinatario, request.form.get("plantilla"), _ticket_id_form())
    except (ValueError, TicketNoEncontradoError) as e:
        return _error(str(e))
    except Exception as e:
        return _error(_("Error SMTP: %(error)s", error=str(e)), 502)
    return _ok(_("Correo enviado a %(email)s", email=destinatario))


@demo_bp.route("/admin/demo/correo/preview")
@requiere_admin
@requiere_modo_demo
def correo_preview():
    try:
        asunto, texto, html = ServicioDemo.previsualizar_correo(request.args.get("plantilla"), _ticket_id_form())
    except (ValueError, TicketNoEncontradoError) as e:
        abort(400, str(e))
    if html is None:
        return f"<pre>{asunto}\n\n{texto}</pre>"
    return html


@demo_bp.route("/admin/demo/sla", methods=["POST"])
@requiere_admin
@requiere_modo_demo
def sla():
    ticket_id = _ticket_id_form()
    if ticket_id is None:
        return _error(_("Selecciona un ticket"))
    modo = request.form.get("modo")
    try:
        r = ServicioDemo.forzar_sla(ticket_id, modo)
    except (ValueError, TicketNoEncontradoError) as e:
        return _error(str(e))
    if modo == "vencido":
        mensaje = _("Ticket #%(id)s marcado como vencido; se notificó al creador", id=ticket_id)
    else:
        mensaje = _("Ticket #%(id)s marcado como próximo a vencer; se notificó al creador", id=ticket_id)
    if r["tiene_agente"]:
        mensaje += " " + _("y al agente asignado")
    return _ok(mensaje, url=url_for("tickets.detalle", ticket_id=ticket_id), **r)


@demo_bp.route("/admin/demo/sla/verificar", methods=["POST"])
@requiere_admin
@requiere_modo_demo
def sla_verificar():
    r = ServicioDemo.ejecutar_verificacion_sla()
    return _ok(_("Verificación de SLA ejecutada: %(v)s vencidos, %(p)s próximos a vencer (solo se notifican los que no se habían notificado)",
                 v=r["vencidos"], p=r["proximos"]), **r)


@demo_bp.route("/admin/demo/ticket", methods=["POST"])
@requiere_admin
@requiere_modo_demo
def ticket():
    texto = (request.form.get("texto") or "").strip()
    if not texto:
        return _error(_("Escribe el texto del ticket"))
    creador_id = request.form.get("creador_id", type=int) or session["usuario_id"]
    try:
        r = ServicioDemo.crear_ticket(creador_id, texto)
    except ErrorPersistencia as e:
        return _error(str(e), 500)
    mensaje = _("Ticket #%(id)s creado. Categoría: %(categoria)s, prioridad: %(prioridad)s",
                id=r["ticket_id"], categoria=etiqueta(r["categoria"]), prioridad=etiqueta(r["prioridad"]))
    if r["baja_confianza"]:
        mensaje += " " + _("— clasificación de baja confianza, se notificó a los administradores")
    return _ok(mensaje, url=url_for("tickets.detalle", ticket_id=r["ticket_id"]), **r)


@demo_bp.route("/admin/demo/limpiar-notificaciones", methods=["POST"])
@requiere_admin
@requiere_modo_demo
def limpiar_notificaciones():
    r = ServicioDemo.borrar_notificaciones(session["usuario_id"])
    return _ok(_("Se borraron %(n)s notificaciones de tu usuario", n=r["borradas"]), recargar=True)
