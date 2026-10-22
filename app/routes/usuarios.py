from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_babel import gettext as _
from sqlalchemy import select, func

from app.extensions import db
from app.models.enum import Categoria, NivelUsuario, RolUsuario
from app.models.log_auditoria import LogAuditoria
from app.models.ticket import Ticket
from app.routes.decoradores import requiere_admin
from app.services.doble_factor import ServicioDobleFactor
from app.services.exceptions import ErrorPersistencia, OperacionNoPermitidaError, UsuarioNoEncontradoError
from app.services.usuarios import ServicioUsuarios, FILTROS_ESTADO
from app.services.autenticacion import ServicioAutenticacion

usuarios_bp = Blueprint("usuarios", __name__)


def _enum(clase, valor):
    if not valor:
        return None
    try:
        return clase(valor)
    except ValueError:
        return None


@usuarios_bp.route("/admin/usuarios")
@requiere_admin
def listar():
    busqueda = (request.args.get("q") or "").strip()
    rol = _enum(RolUsuario, request.args.get("rol"))
    area = _enum(Categoria, request.args.get("area"))
    estado = request.args.get("estado") if request.args.get("estado") in FILTROS_ESTADO else None
    paginado = ServicioUsuarios.listar(
        busqueda=busqueda, rol=rol, estado=estado, area=area, pagina=request.args.get("pagina", 1, type=int)
    )
    ids = [u.id for u in paginado.items]
    con_2fa = set()
    abiertos = {}
    if ids:
        from app.models.doble_factor import DobleFactor
        con_2fa = set(db.session.execute(
            select(DobleFactor.usuario_id).where(DobleFactor.usuario_id.in_(ids), DobleFactor.activo.is_(True))
        ).scalars())
        abiertos = dict(db.session.execute(
            select(Ticket.agente_id, func.count(Ticket.id))
            .where(Ticket.agente_id.in_(ids), Ticket.fecha_cierre.is_(None)).group_by(Ticket.agente_id)
        ).all())
    return render_template(
        "usuarios.html",
        paginado=paginado,
        usuarios=paginado.items,
        resumen=ServicioUsuarios.resumen(),
        con_2fa=con_2fa,
        abiertos=abiertos,
        filtros={"q": busqueda, "rol": rol.value if rol else "", "area": area.value if area else "", "estado": estado or ""},
    )


@usuarios_bp.route("/admin/usuarios/<int:usuario_id>", methods=["GET", "POST"])
@requiere_admin
def detalle(usuario_id):
    try:
        usuario = ServicioUsuarios.obtener(usuario_id)
    except UsuarioNoEncontradoError:
        abort(404)

    if request.method == "POST":
        try:
            rol = RolUsuario(request.form.get("rol"))
            nivel = NivelUsuario(request.form.get("nivel"))
            area = _enum(Categoria, request.form.get("area_soporte"))
            _usuario, cambio = ServicioUsuarios.actualizar(
                session["usuario_id"], usuario_id, request.form.get("nombre"), rol, nivel, area
            )
            flash(_("Usuario actualizado") if cambio else _("No había cambios que guardar"), "success" if cambio else "info")
        except ValueError as e:
            flash(str(e) if str(e) else _("Datos no válidos"), "danger")
        except (OperacionNoPermitidaError, ErrorPersistencia) as e:
            flash(str(e), "danger")
        return redirect(url_for("usuarios.detalle", usuario_id=usuario_id))

    actividad = db.session.execute(
        select(LogAuditoria).where(LogAuditoria.usuario_id == usuario.id).order_by(LogAuditoria.fecha.desc()).limit(12)
    ).scalars().all()
    estadisticas = {
        "creados": db.session.execute(select(func.count(Ticket.id)).where(Ticket.creador_id == usuario.id)).scalar(),
        "asignados": db.session.execute(select(func.count(Ticket.id)).where(Ticket.agente_id == usuario.id)).scalar(),
        "en_progreso": ServicioUsuarios.carga_actual(usuario.id),
    }
    return render_template(
        "usuario_detalle.html",
        usuario=usuario,
        actividad=actividad,
        estadisticas=estadisticas,
        dos_pasos_activo=ServicioDobleFactor.esta_activo(usuario.id),
        bloqueado=ServicioAutenticacion.esta_bloqueado(usuario),
        es_yo=usuario.id == session["usuario_id"],
        nombre_foto=ServicioAutenticacion.obtener_nombre_archivo_foto(usuario),
    )


def _accion(usuario_id, funcion, mensaje_ok):
    try:
        funcion()
        flash(mensaje_ok, "success")
    except (OperacionNoPermitidaError, UsuarioNoEncontradoError, ErrorPersistencia) as e:
        flash(str(e), "danger")
    destino = request.form.get("volver")
    if destino == "lista":
        return redirect(url_for("usuarios.listar"))
    return redirect(url_for("usuarios.detalle", usuario_id=usuario_id))


@usuarios_bp.route("/admin/usuarios/<int:usuario_id>/activo", methods=["POST"])
@requiere_admin
def cambiar_activo(usuario_id):
    activo = request.form.get("activo") == "1"
    return _accion(
        usuario_id,
        lambda: ServicioUsuarios.cambiar_activo(session["usuario_id"], usuario_id, activo),
        _("Cuenta reactivada") if activo else _("Cuenta desactivada"),
    )


@usuarios_bp.route("/admin/usuarios/<int:usuario_id>/desbloquear", methods=["POST"])
@requiere_admin
def desbloquear(usuario_id):
    return _accion(usuario_id, lambda: ServicioUsuarios.desbloquear(session["usuario_id"], usuario_id),
                   _("Cuenta desbloqueada"))


@usuarios_bp.route("/admin/usuarios/<int:usuario_id>/restablecer-2fa", methods=["POST"])
@requiere_admin
def restablecer_2fa(usuario_id):
    return _accion(usuario_id, lambda: ServicioUsuarios.restablecer_doble_factor(session["usuario_id"], usuario_id),
                   _("Verificación en dos pasos restablecida. El usuario podrá configurarla de nuevo."))


@usuarios_bp.route("/admin/usuarios/<int:usuario_id>/enviar-recuperacion", methods=["POST"])
@requiere_admin
def enviar_recuperacion(usuario_id):
    return _accion(usuario_id, lambda: ServicioUsuarios.enviar_recuperacion(session["usuario_id"], usuario_id),
                   _("Enlace de recuperación enviado al correo del usuario"))
