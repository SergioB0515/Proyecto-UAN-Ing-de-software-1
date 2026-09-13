from flask import Blueprint, render_template, request, session, flash, redirect, url_for
from flask_babel import gettext as _
from app.services.palabra_clave import ServicioPalabraClave
from app.services.exceptions import PalabraClaveDuplicadaError, PalabraClaveNoEncontradaError, ErrorPersistencia
from app.models.enum import Categoria
from app.routes.decoradores import requiere_admin

palabras_clave_bp = Blueprint("palabras_clave", __name__)


@palabras_clave_bp.route("/admin/palabras-clave", methods=["GET"])
@requiere_admin
def listar():
    incluir_inactivas = request.args.get("incluir_inactivas") == "1"
    palabras = ServicioPalabraClave.listar_palabras_clave(incluir_inactivas)
    return render_template("palabras_clave.html", palabras_clave=palabras, incluir_inactivas=incluir_inactivas)


@palabras_clave_bp.route("/admin/palabras-clave", methods=["POST"])
@requiere_admin
def crear():
    actor_id = session["usuario_id"]
    texto = request.form["texto"]
    categoria_raw = request.form.get("categoria")
    peso_raw = request.form.get("peso")

    try:
        categoria = Categoria(categoria_raw)
    except ValueError:
        flash(_("Categoría inválida"), "danger")
        return redirect(url_for("palabras_clave.listar"))

    try:
        peso = float(peso_raw)
        if peso <= 0:
            raise ValueError
    except (TypeError, ValueError):
        flash(_("El peso debe ser un número mayor que cero"), "danger")
        return redirect(url_for("palabras_clave.listar"))

    try:
        ServicioPalabraClave.crear_palabra_clave(texto, categoria, peso, actor_id)
        flash(_("Palabra clave creada"), "success")
    except (PalabraClaveDuplicadaError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("palabras_clave.listar"))


@palabras_clave_bp.route("/admin/palabras-clave/<int:id>/editar", methods=["POST"])
@requiere_admin
def editar(id):
    actor_id = session["usuario_id"]
    texto = request.form["texto"]
    categoria_raw = request.form.get("categoria")
    peso_raw = request.form.get("peso")

    try:
        categoria = Categoria(categoria_raw)
    except ValueError:
        flash(_("Categoría inválida"), "danger")
        return redirect(url_for("palabras_clave.listar"))

    try:
        peso = float(peso_raw)
        if peso <= 0:
            raise ValueError
    except (TypeError, ValueError):
        flash(_("El peso debe ser un número mayor que cero"), "danger")
        return redirect(url_for("palabras_clave.listar"))

    try:
        ServicioPalabraClave.editar_palabra_clave(id, texto, categoria, peso, actor_id)
        flash(_("Palabra clave editada"), "success")
    except (PalabraClaveDuplicadaError, PalabraClaveNoEncontradaError, ErrorPersistencia) as e:
        flash(str(e), "danger")

    return redirect(url_for("palabras_clave.listar"))


@palabras_clave_bp.route("/admin/palabras-clave/<int:id>/desactivar", methods=["POST"])
@requiere_admin
def desactivar(id):
    actor_id = session["usuario_id"]
    try:
        ServicioPalabraClave.desactivar_palabra_clave(id, actor_id)
        flash(_("Palabra clave desactivada"), "success")
    except (PalabraClaveNoEncontradaError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("palabras_clave.listar"))


@palabras_clave_bp.route("/admin/palabras-clave/<int:id>/reactivar", methods=["POST"])
@requiere_admin
def reactivar(id):
    actor_id = session["usuario_id"]
    try:
        ServicioPalabraClave.reactivar_palabra_clave(id, actor_id)
        flash(_("Palabra clave reactivada"), "success")
    except (PalabraClaveDuplicadaError, PalabraClaveNoEncontradaError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    return redirect(url_for("palabras_clave.listar"))