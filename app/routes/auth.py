from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.services.autenticacion import ServicioAutenticacion, ResultadoLogin
from app.services.exceptions import ErrorPersistencia
from app.routes.decoradores import requiere_login, requiere_admin
from sqlalchemy import select
from app.models.usuario import Usuario
from app.services.tickets import ServicioTickets
from app.services.gestor_sla import GestorSLA
from app.extensions import db
auth_bp = Blueprint("auth", __name__)
from app.models.enum import RolUsuario,NivelUsuario,Categoria

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        contrasena = request.form["contrasena"]
        ip = request.remote_addr

        usuario, resultado = ServicioAutenticacion.iniciar_sesion(email, contrasena, ip)
        
        if resultado == ResultadoLogin.EXITOSO:
            session['usuario_id'] = usuario.id
            session['rol'] = usuario.rol
            session['area_soporte'] = usuario.area_soporte.value if usuario.area_soporte is not None else None
            if usuario.rol == RolUsuario.ADMIN:
                return redirect(url_for("metricas.mostrar_metricas"))
            elif usuario.rol == RolUsuario.AGENTE:
                return redirect(url_for("tickets.listar_por_area", area=usuario.area_soporte.value))
            else:
                return redirect(url_for("auth.dashboard"))


        elif resultado in (ResultadoLogin.USUARIO_NO_EXISTE, ResultadoLogin.CREDENCIALES_INVALIDAS):
            
            flash("usuario o contraseña incorrectos","danger")
            return redirect(url_for('auth.login'))
        elif resultado == ResultadoLogin.ERROR_INTERNO:
            flash("Ocurrio un error interno, intentelo mas tarde ","danger")
            return redirect(url_for('auth.login'))
        elif resultado == ResultadoLogin.IP_BLOQUEADA:
            flash("Se ha detectado un error externo, contacte con soporte", "danger")
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
    usuario_id = session['usuario_id']
    tickets = ServicioTickets.listar_tickets_por_creador(usuario_id)
    
    vencidos, proximos = GestorSLA.verificar_vencimientos(creador_id=usuario_id)
    ids_vencidos={t.id for t in vencidos}
    ids_proximos={t.id for t in proximos}

    return render_template(
        "dashboard.html",
        tickets=tickets,
        ids_vencidos=ids_vencidos,
        ids_proximos=ids_proximos,
        )

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
            
        if rol==RolUsuario.AGENTE and area_raw is None:
            flash("UN agente debe tener un area especifica", "danger")
            return redirect(url_for("auth.registro"))
        
        admin_id = session["usuario_id"]

        try:
            usuario_creado = ServicioAutenticacion.registrar(
                nombre=nombre, email=email, contrasena=contrasena,
                rol=rol, admin_id=admin_id, area_soporte=area_raw, nivel=nivel
            )
        except ValueError as e:                         
            flash(str(e), "danger")
            return redirect(url_for("auth.registro"))
        except ErrorPersistencia:
            flash("No se pudo registrar el usuario por un error interno, intente más tarde", "danger")
            return redirect(url_for("auth.registro"))

        if usuario_creado is None:
            flash("Ya existe un usuario con ese email", "danger")
            return redirect(url_for("auth.registro"))

        flash("Usuario registrado con éxito", "success")
        return redirect(url_for("metricas.mostrar_metricas"))

    return render_template("registro.html")

@auth_bp.route("/perfil", methods=["GET"])
@requiere_login
def perfil():
    usuario_id = session['usuario_id']
    usuario = db.session.execute(select(Usuario).where(Usuario.id == usuario_id)).scalar_one_or_none()
    estadisticas = ServicioTickets.obtener_estadisticas_personales(usuario)
    nombre_foto = ServicioAutenticacion.obtener_nombre_archivo_foto(usuario)

    return render_template("perfil.html", usuario=usuario, estadisticas=estadisticas, nombre_foto=nombre_foto)


@auth_bp.route("/perfil/cambiar-contrasena", methods=["POST"])
@requiere_login
def cambiar_contrasena():
    usuario_id = session['usuario_id']

    usuario = db.session.execute(select(Usuario).where(Usuario.id == usuario_id)).scalar_one_or_none()

    contrasena_actual = request.form.get("contrasena_actual")
    contrasena_nueva = request.form.get("contrasena_nueva")

    try:
        ServicioAutenticacion.cambiar_contrasena(usuario, contrasena_actual, contrasena_nueva)

        flash("Contraseña cambiada con exito", "success")
    except ValueError as e:
       
        flash(str(e), "danger")
    except ErrorPersistencia as e:
        flash(str(e), "danger")

    return redirect(url_for("auth.perfil"))

@auth_bp.route("/perfil/cambiar-nombre", methods=["POST"])
@requiere_login
def cambiar_nombre():
    usuario_id = session['usuario_id']
    usuario = db.session.execute(select(Usuario).where(Usuario.id == usuario_id)).scalar_one_or_none()

    nombre_nuevo = request.form.get("nombre_nuevo")

    try:
        ServicioAutenticacion.cambiar_nombre(usuario, nombre_nuevo)
        flash("Nombre actualizado con éxito", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except ErrorPersistencia as e:
        flash(str(e), "danger")

    return redirect(url_for("auth.perfil"))

@auth_bp.route("/perfil/foto", methods=["POST"])
@requiere_login
def subir_foto():
    usuario_id = session['usuario_id']
    usuario = db.session.execute(select(Usuario).where(Usuario.id == usuario_id)).scalar_one_or_none()

    archivo = request.files.get("foto")

    try:
        ServicioAutenticacion.subir_foto_perfil(usuario, archivo)
        flash("Foto de perfil actualizada", "success")
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("auth.perfil"))
