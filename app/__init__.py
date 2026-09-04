from flask import Flask
from app.extensions import db
from app.config import Config
from app.routes.auth import auth_bp
from app.routes.tickets import tickets_bp
from app.routes.metricas import metricas_bp
from app.routes.auditoria import auditoria_bp
from flask_wtf import CSRFProtect
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from sqlalchemy import delete
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    csrf = CSRFProtect(app)

    from app.models.usuario import Usuario
    from app.models.ticket import Ticket
    from app.models.comentario import Comentario
    from app.models.log_auditoria import LogAuditoria
    from app.models.intento_login_fallido import IntentoLoginFallido
    from app.models.ip_bloqueada import IPBloqueada

    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(metricas_bp)
    app.register_blueprint(auditoria_bp)


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

    scheduler = BackgroundScheduler()

    scheduler.add_job(limpiar_intentos_login_viejos, 'interval', minutes = 90)
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and not app.debug:
        scheduler.start()

    
    return app