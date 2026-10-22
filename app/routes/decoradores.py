from functools import wraps
from flask import flash, redirect, session, url_for
from flask_babel import gettext as _
from app.extensions import db
from app.models.enum import RolUsuario
from app.models.usuario import Usuario


def _sesion_valida():
    if 'usuario_id' not in session:
        flash(_("Debes iniciar sesión"), "warning")
        return redirect(url_for('auth.login'))
    usuario = db.session.get(Usuario, session['usuario_id'])
    if usuario is None or not usuario.activo:
        session.clear()
        flash(_("Tu cuenta no está activa. Contacta a un administrador."), "warning")
        return redirect(url_for('auth.login'))
    if session.get('rol') != usuario.rol:
        session['rol'] = usuario.rol
        session['area_soporte'] = usuario.area_soporte.value if usuario.area_soporte is not None else None
    return None


def requiere_login(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        respuesta = _sesion_valida()
        if respuesta is not None:
            return respuesta
        return func(*args, **kwargs)
    return wrapper


def requiere_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        respuesta = _sesion_valida()
        if respuesta is not None:
            return respuesta
        if not session.get('rol') == RolUsuario.ADMIN:
            flash(_("No tienes permiso para entrar en esta funcion"), "warning")
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return wrapper


def requiere_personal(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        respuesta = _sesion_valida()
        if respuesta is not None:
            return respuesta
        if session.get('rol') not in (RolUsuario.ADMIN, RolUsuario.AGENTE):
            flash(_("No tienes permiso para entrar en esta funcion"), "warning")
            return redirect(url_for('auth.dashboard'))
        return func(*args, **kwargs)
    return wrapper
