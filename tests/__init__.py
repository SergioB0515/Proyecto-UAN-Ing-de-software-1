from flask import Flask
from app.extensions import db


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test_proyecto.db"
    db.init_app(app)

    from app.models.usuario import Usuario
    from app.models.ticket import Ticket
    from app.models.comentario import Comentario
    from app.models.log_auditoria import LogAuditoria


    with app.app_context():
        db.create_all()

    return app