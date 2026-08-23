from flask import Flask
from app.extensions import db

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///proyecto.db"
    db.init_app(app)

    from app.Models.usuario import Usuario
    from app.Models.ticket import Ticket
    from app.Models.comentario import Comentario
    from app.Models.log_auditoria import LogAuditoria

    return app