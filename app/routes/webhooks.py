from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_babel import gettext as _

from app.routes.decoradores import requiere_admin
from app.services.exceptions import (
    ErrorPersistencia,
    WebhookInvalidoError,
    WebhookNoEncontradoError,
)
from app.services.webhooks import MAX_FALLOS, MAX_WEBHOOKS, ServicioWebhooks

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("/admin/webhooks", methods=["GET", "POST"])
@requiere_admin
def listar():
    if request.method == "POST":
        try:
            webhook = ServicioWebhooks.registrar(
                actor_id=session["usuario_id"],
                nombre=request.form.get("nombre", ""),
                url=request.form.get("url", ""),
                eventos=request.form.getlist("eventos"),
            )
            flash(_("Webhook «%(nombre)s» registrado. Copia el secreto ahora para configurarlo en el destino.",
                    nombre=webhook.nombre), "success")
            return redirect(url_for("webhooks.detalle", webhook_id=webhook.id))
        except (WebhookInvalidoError, ErrorPersistencia) as e:
            flash(str(e), "danger")
            return redirect(url_for("webhooks.listar"))

    webhooks = ServicioWebhooks.listar()
    return render_template(
        "webhooks.html",
        webhooks=webhooks,
        eventos=ServicioWebhooks.catalogo_eventos(),
        max_webhooks=MAX_WEBHOOKS,
        max_fallos=MAX_FALLOS,
    )


@webhooks_bp.route("/admin/webhooks/<int:webhook_id>")
@requiere_admin
def detalle(webhook_id):
    try:
        webhook = ServicioWebhooks.obtener(webhook_id)
    except WebhookNoEncontradoError as e:
        flash(str(e), "danger")
        return redirect(url_for("webhooks.listar"))

    return render_template(
        "webhook_detalle.html",
        webhook=webhook,
        entregas=ServicioWebhooks.entregas(webhook_id),
        eventos=ServicioWebhooks.catalogo_eventos(),
        max_fallos=MAX_FALLOS,
    )


def _accion(webhook_id, funcion, mensaje_ok):
    try:
        funcion()
        flash(mensaje_ok, "success")
    except (WebhookNoEncontradoError, WebhookInvalidoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("webhooks.detalle", webhook_id=webhook_id))


@webhooks_bp.route("/admin/webhooks/<int:webhook_id>/activo", methods=["POST"])
@requiere_admin
def cambiar_activo(webhook_id):
    activo = request.form.get("activo") == "1"
    return _accion(
        webhook_id,
        lambda: ServicioWebhooks.cambiar_activo(session["usuario_id"], webhook_id, activo),
        _("Webhook activado") if activo else _("Webhook desactivado"),
    )


@webhooks_bp.route("/admin/webhooks/<int:webhook_id>/probar", methods=["POST"])
@requiere_admin
def probar(webhook_id):
    try:
        entrega = ServicioWebhooks.probar(session["usuario_id"], webhook_id)
        if entrega.exito:
            flash(_("Prueba entregada (HTTP %(codigo)s)", codigo=entrega.codigo_http), "success")
        else:
            flash(_("La prueba falló: %(error)s", error=entrega.error or _("sin respuesta")), "warning")
    except (WebhookNoEncontradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("webhooks.detalle", webhook_id=webhook_id))


@webhooks_bp.route("/admin/webhooks/<int:webhook_id>/eliminar", methods=["POST"])
@requiere_admin
def eliminar(webhook_id):
    try:
        ServicioWebhooks.eliminar(session["usuario_id"], webhook_id)
        flash(_("Webhook eliminado"), "success")
    except (WebhookNoEncontradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("webhooks.listar"))
