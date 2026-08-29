from functools import wraps
from flask import flash, redirect, session , url_for
from app.models.enum import RolUsuario
def requiere_login(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("Debes iniciar sesión", "warning")
            return redirect(url_for('auth.login'))
    
        return func(*args, **kwargs)
    return wrapper

def requiere_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("Debes iniciar sesión", "warning")
            return redirect(url_for('auth.login'))
        if not session.get('rol') == RolUsuario.ADMIN :
            flash("No tienes permiso para entrar en esta funcion","warning")
            return redirect(url_for('auth.login'))
            
        return func(*args, **kwargs)
    return wrapper