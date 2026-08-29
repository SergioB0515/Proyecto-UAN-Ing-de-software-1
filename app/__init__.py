from flask import Flask
from app.extensions import db
from app.config import Config
from app.routes import auth_bp
from app.routes.tickets import tickets_bp
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    from app.models.usuario import Usuario
    from app.models.ticket import Ticket
    from app.models.comentario import Comentario
    from app.models.log_auditoria import LogAuditoria
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp)
    return app