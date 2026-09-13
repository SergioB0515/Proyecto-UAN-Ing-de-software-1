from flask import Flask, session, has_request_context
from app.extensions import db, socketio
from flask_socketio import join_room
from app.config import Config
from app.routes.auth import auth_bp
from app.routes.tickets import tickets_bp
from app.routes.metricas import metricas_bp
from app.routes.auditoria import auditoria_bp
from app.routes.solicitudes import solicitudes_bp
from app.routes.apelacion import apelaciones_bp
from flask_wtf import CSRFProtect
from flask_babel import Babel
from app.services.gestor_sla import GestorSLA
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from app.services.notificaciones import ServicioNotificaciones
from sqlalchemy import delete
from threading import Lock
import os
from app.routes.palabra_clave import palabras_clave_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    csrf = CSRFProtect(app)

    socketio.init_app(app, async_mode="threading")

    @socketio.on("connect")
    def handle_connect():
        if "usuario_id" in session:
            join_room(f"usuario_{session['usuario_id']}")

    def get_locale():

        if not has_request_context():
            return app.config.get("BABEL_DEFAULT_LOCALE", "es")
        return session.get("idioma", "es")

    babel = Babel(app, locale_selector=get_locale, default_locale="es",
                   default_translation_directories="translations")

    from app.traducciones import etiqueta, formato_fecha
    app.jinja_env.filters["etiqueta"] = etiqueta
    app.jinja_env.globals["etiqueta"] = etiqueta
    app.jinja_env.filters["fecha"] = formato_fecha

    from app.notificaciones_i18n import render as _render_notif, catalogo_cliente as _catalogo_notif
    app.jinja_env.filters["notif_msg"] = lambda n: _render_notif(n.mensaje, n.ticket_id)

    from app.models.usuario import Usuario
    from app.models.ticket import Ticket
    from app.models.comentario import Comentario
    from app.models.log_auditoria import LogAuditoria
    from app.models.intento_login_fallido import IntentoLoginFallido
    from app.models.ip_bloqueada import IPBloqueada
    from app.models.notificacion import Notificacion
    from app.models.palabra_clave import PalabraClave
    from app.models.correccion_clasificacion import CorreccionClasificacion

    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(metricas_bp)
    app.register_blueprint(auditoria_bp)
    app.register_blueprint(solicitudes_bp)
    app.register_blueprint(palabras_clave_bp)
    app.register_blueprint(apelaciones_bp)
    
    if app.config.get("CLASIFICADOR_ML_ACTIVO"):
        with app.app_context():
            from app.services import clasificacion_avanzada
            clasificacion_avanzada.inicializar()
            
    @app.context_processor
    def inject_notificaciones():
        if "usuario_id" not in session:
            return {}
        usuario_id = session["usuario_id"]
        no_leidas = ServicioNotificaciones.listar_no_leidas(usuario_id)
        return {
            "notificaciones_recientes": ServicioNotificaciones.listar_para_usuario(usuario_id),
            "notificaciones_no_leidas": len(no_leidas),
            "notificaciones_no_leidas_lista": [
                {
                    "id": n.id,
                    "mensaje": _render_notif(n.mensaje, n.ticket_id),
                    "ticket_id": n.ticket_id,
                    "fecha": n.fecha.isoformat(),
                }
                for n in no_leidas
            ],
            "notif_catalogo": _catalogo_notif(),
        }

    @app.context_processor
    def inject_usuario_actual():
        if "usuario_id" not in session:
            return {}
        usuario = db.session.get(Usuario, session["usuario_id"])
        if usuario is None:
            return {}
        partes = [p for p in usuario.nombre.split() if p]
        iniciales = "".join(p[0] for p in partes[:2]).upper() or "?"
        from app.services.autenticacion import ServicioAutenticacion
        nombre_foto = ServicioAutenticacion.obtener_nombre_archivo_foto(usuario)
        return {
            "usuario_actual": usuario,
            "usuario_iniciales": iniciales,
            "usuario_nombre_foto": nombre_foto,
        }

    def limpiar_intentos_login_viejos():
        with app.app_context():
            limite = datetime.now() - timedelta(hours=1)
            db.session.execute(delete(IntentoLoginFallido).where(IntentoLoginFallido.fecha< limite)) 
            try:
                db.session.commit()
                print("Limpieza de intentos de login viejos completada")
            except Exception as e:
                db.session.rollback()
                print(f"No se pudo limpiar intentos de login viejos, error: {e}")
                
    def reentrenar_clasificador_job():
        with app.app_context():
            if not app.config.get("CLASIFICADOR_ML_ACTIVO"):
                return
            try:
                from app.services.reentrenamiento import reentrenar_si_mejora
                reentrenar_si_mejora()
            except Exception as e:
                print(f"No se pudo completar el reentrenamiento periódico, error: {e}")
                
    def verificar_vencimientos_sla():
        with app.app_context():
            try:
                GestorSLA.verificar_y_notificar_vencimientos()
                print("Verificacion de vencimientos SLA completada")
            except Exception as e:
                print(f"No se pudo verificar vencimientos SLA, error: {e}")

    def _iniciar_scheduler():

        if getattr(app, "scheduler", None) is not None:
            return
        if not app.config.get("SCHEDULER_ACTIVO", True):
            return

        intervalo = app.config.get("SLA_INTERVALO_MINUTOS", 30)
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            verificar_vencimientos_sla,
            "interval",
            minutes=intervalo,
            next_run_time=datetime.now(),
            id="verificar_vencimientos_sla",
            replace_existing=True,
        )
        scheduler.add_job(
            limpiar_intentos_login_viejos,
            "interval",
            minutes=90,
            id="limpiar_intentos_login_viejos",
            replace_existing=True,
        )
        scheduler.add_job(
            reentrenar_clasificador_job,
            "interval",
            hours=app.config.get("REENTRENAMIENTO_INTERVALO_HORAS", 24),
            id="reentrenar_clasificador",
            replace_existing=True,
        )
        scheduler.start()
        app.scheduler = scheduler
        print(f"Scheduler SLA iniciado (cada {intervalo} min)")

    app.scheduler = None
    _lock_scheduler = Lock()

    @app.before_request
    def _asegurar_scheduler():
        if app.scheduler is None and app.config.get("SCHEDULER_ACTIVO", True):
            with _lock_scheduler:
                _iniciar_scheduler()
    

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        _iniciar_scheduler()
    
    return app