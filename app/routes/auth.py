from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.services.autenticacion import ServicioAutenticacion, ResultadoLogin
from app.routes.decoradores import requiere_login, requiere_admin
from app.services.metricas import ServicioMetricas
auth_bp = Blueprint("auth", __name__)
from app.models.enum import RolUsuario,NivelUsuario,Categoria

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        contrasena = request.form["contrasena"]

        usuario, resultado = ServicioAutenticacion.iniciar_sesion(email, contrasena)

        if resultado == ResultadoLogin.EXITOSO:
            
            session['usuario_id'] = usuario.id
            session['rol'] = usuario.rol
            return redirect(url_for('auth.dashboard'))


        elif resultado in (ResultadoLogin.USUARIO_NO_EXISTE, ResultadoLogin.CREDENCIALES_INVALIDAS):
            
            flash("usuario o contraseña incorrectos","danger")
            return redirect(url_for('auth.login'))

        else:
            if resultado == ResultadoLogin.YA_BLOQUEADO:
                flash(f"Usuario usted se encuentra bloqueado")
                return redirect(url_for('auth.login'))
            else:
                flash(f"Usuario usted ha sido bloqueado")
                return redirect(url_for('auth.login'))          


    return render_template("login.html")

@auth_bp.route("/dashboard")
@requiere_login
def dashboard():
    metricas = ServicioMetricas.obtener_metricas()
    return render_template("dashboard.html", metricas=metricas)

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente", "info")
    return redirect(url_for('auth.login'))
@auth_bp.route("/registro", methods=["GET", "POST"])
@requiere_login
@requiere_admin
def registro():
    if request.method == "POST":
        nombre = request.form["nombre"]
        email = request.form["email"]
        contrasena = request.form["contrasena"]
        rol = RolUsuario(request.form["rol"])
        nivel = NivelUsuario(request.form["nivel"])

        area_raw = request.form.get("area_soporte")

        if area_raw == "":
            area_raw = None
        else:
            area_raw = Categoria(area_raw)
        admin_id = session["usuario_id"]

        exito = ServicioAutenticacion.registrar(
            nombre=nombre, email=email, contrasena=contrasena,
            rol=rol, admin_id=admin_id, area_soporte=area_raw, nivel=nivel
        )

        if exito:
            flash("Usuario registrado con éxito", "success")
            return redirect(url_for("auth.dashboard"))
        else:
            flash("No se pudo registrar el usuario (email duplicado o error interno)", "danger")
            return redirect(url_for("auth.registro"))

    return render_template("registro.html")
