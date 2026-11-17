from flask import Blueprint, render_template, request, session
from flask_babel import gettext as _

from app.extensions import db
from app.models.usuario import Usuario
from app.routes.decoradores import requiere_login
from app.services.busqueda import MIN_TERMINO, ServicioBusqueda

busqueda_bp = Blueprint("busqueda", __name__)


@busqueda_bp.route("/buscar")
@requiere_login
def buscar():
    usuario = db.session.get(Usuario, session["usuario_id"])
    termino = request.args.get("q", "")
    resultado = ServicioBusqueda.buscar(usuario, termino)
    return render_template(
        "busqueda.html",
        resultado=resultado,
        termino=termino,
        min_termino=MIN_TERMINO,
    )
