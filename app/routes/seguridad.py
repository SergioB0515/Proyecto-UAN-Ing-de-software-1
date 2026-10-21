import time

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_babel import gettext as _
from sqlalchemy import select

from app.extensions import db
from app.models.usuario import Usuario
from app.routes.decoradores import requiere_login
from app.services.doble_factor import ServicioDobleFactor
from app.services.recuperacion import ServicioRecuperacion
from app.services.exceptions import (
    CodigoInvalidoError,
    DobleFactorBloqueadoError,
    DobleFactorNoConfiguradoError,
    DobleFactorYaActivoError,
    ErrorPersistencia,
    TokenRecuperacionInvalidoError,
)

seguridad_bp = Blueprint("seguridad", __name__)

SEGUNDOS_PASO_PENDIENTE = 300
MAX_INTENTOS_POR_SESION = 5


def _usuario_actual():
    return db.session.execute(select(Usuario).where(Usuario.id == session["usuario_id"])).scalar_one_or_none()


def _limpiar_pendiente():
    for clave in ("2fa_usuario_id", "2fa_desde", "2fa_intentos"):
        session.pop(clave, None)


@seguridad_bp.route("/login/verificar", methods=["GET", "POST"])
def verificar_login():
    from app.routes.auth import completar_inicio_sesion

    usuario_id = session.get("2fa_usuario_id")
    desde = session.get("2fa_desde", 0)
    if usuario_id is None or time.time() - desde > SEGUNDOS_PASO_PENDIENTE:
        _limpiar_pendiente()
        flash(_("Tu sesión de verificación expiró. Inicia sesión de nuevo."), "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        try:
            ServicioDobleFactor.verificar(usuario_id, request.form.get("codigo", ""))
        except DobleFactorBloqueadoError as e:
            _limpiar_pendiente()
            flash(str(e), "danger")
            return redirect(url_for("auth.login"))
        except CodigoInvalidoError as e:
            session["2fa_intentos"] = session.get("2fa_intentos", 0) + 1
            if session["2fa_intentos"] >= MAX_INTENTOS_POR_SESION:
                _limpiar_pendiente()
                flash(_("Demasiados códigos incorrectos. Inicia sesión de nuevo."), "danger")
                return redirect(url_for("auth.login"))
            flash(str(e), "danger")
            return redirect(url_for("seguridad.verificar_login"))
        except (DobleFactorNoConfiguradoError, ErrorPersistencia) as e:
            _limpiar_pendiente()
            flash(str(e), "danger")
            return redirect(url_for("auth.login"))

        usuario = db.session.get(Usuario, usuario_id)
        _limpiar_pendiente()
        if usuario is None:
            return redirect(url_for("auth.login"))
        return completar_inicio_sesion(usuario)

    return render_template("verificar_2fa.html")


@seguridad_bp.route("/login/verificar/cancelar")
def cancelar_verificacion():
    _limpiar_pendiente()
    return redirect(url_for("auth.login"))


@seguridad_bp.route("/perfil/2fa/iniciar", methods=["POST"])
@requiere_login
def iniciar_2fa():
    try:
        ServicioDobleFactor.iniciar_configuracion(_usuario_actual())
    except DobleFactorYaActivoError as e:
        flash(str(e), "info")
        return redirect(url_for("auth.perfil"))
    except ErrorPersistencia as e:
        flash(str(e), "danger")
        return redirect(url_for("auth.perfil"))
    return redirect(url_for("seguridad.configurar_2fa"))


@seguridad_bp.route("/perfil/2fa/configurar", methods=["GET"])
@requiere_login
def configurar_2fa():
    usuario = _usuario_actual()
    pendiente = ServicioDobleFactor.configuracion_pendiente(usuario)
    if pendiente is None:
        return redirect(url_for("auth.perfil"))
    secreto, uri = pendiente
    secreto_legible = " ".join(secreto[i:i + 4] for i in range(0, len(secreto), 4))
    return render_template("dos_pasos_configurar.html", secreto=secreto_legible, uri=uri, email=usuario.email)


@seguridad_bp.route("/perfil/2fa/confirmar", methods=["POST"])
@requiere_login
def confirmar_2fa():
    try:
        codigos = ServicioDobleFactor.confirmar_configuracion(_usuario_actual(), request.form.get("codigo", ""))
    except CodigoInvalidoError as e:
        flash(str(e), "danger")
        return redirect(url_for("seguridad.configurar_2fa"))
    except (DobleFactorNoConfiguradoError, DobleFactorYaActivoError, ErrorPersistencia) as e:
        flash(str(e), "warning")
        return redirect(url_for("auth.perfil"))

    flash(_("Verificación en dos pasos activada"), "success")
    return render_template("dos_pasos_codigos.html", codigos=codigos, recien_activado=True)


@seguridad_bp.route("/perfil/2fa/regenerar", methods=["POST"])
@requiere_login
def regenerar_codigos():
    try:
        codigos = ServicioDobleFactor.regenerar_codigos_respaldo(_usuario_actual(), request.form.get("codigo", ""))
    except (CodigoInvalidoError, DobleFactorBloqueadoError, DobleFactorNoConfiguradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
        return redirect(url_for("auth.perfil"))

    flash(_("Se generaron nuevos códigos de respaldo; los anteriores ya no sirven"), "success")
    return render_template("dos_pasos_codigos.html", codigos=codigos, recien_activado=False)


@seguridad_bp.route("/perfil/2fa/desactivar", methods=["POST"])
@requiere_login
def desactivar_2fa():
    try:
        ServicioDobleFactor.desactivar(_usuario_actual(), request.form.get("contrasena", ""))
        flash(_("Verificación en dos pasos desactivada"), "info")
    except ValueError as e:
        flash(str(e), "danger")
    except (DobleFactorNoConfiguradoError, ErrorPersistencia) as e:
        flash(str(e), "warning")
    return redirect(url_for("auth.perfil"))


@seguridad_bp.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if session.get("usuario_id"):
        return redirect(url_for("auth.perfil"))

    if request.method == "POST":
        try:
            ServicioRecuperacion.solicitar(request.form.get("email", ""))
        except ErrorPersistencia as e:
            flash(str(e), "danger")
            return redirect(url_for("seguridad.recuperar"))
        flash(_("Si el email está registrado, te enviamos un enlace para restablecer la contraseña. Revisa tu bandeja de entrada."), "info")
        return redirect(url_for("auth.login"))

    return render_template("recuperar.html")


@seguridad_bp.route("/recuperar/<token>", methods=["GET", "POST"])
def restablecer(token):
    try:
        _registro, usuario = ServicioRecuperacion.validar_token(token)
    except TokenRecuperacionInvalidoError as e:
        flash(str(e), "danger")
        return redirect(url_for("seguridad.recuperar"))

    if request.method == "POST":
        try:
            ServicioRecuperacion.restablecer(token, request.form.get("contrasena", ""), request.form.get("confirmacion", ""))
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("seguridad.restablecer", token=token))
        except TokenRecuperacionInvalidoError as e:
            flash(str(e), "danger")
            return redirect(url_for("seguridad.recuperar"))
        except ErrorPersistencia as e:
            flash(str(e), "danger")
            return redirect(url_for("seguridad.restablecer", token=token))

        flash(_("Contraseña restablecida. Ya puedes iniciar sesión."), "success")
        return redirect(url_for("auth.login"))

    return render_template("restablecer.html", email=usuario.email)
