from flask import Flask
from flask_babel import Babel
from app.extensions import db


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test_proyecto.db"
    app.config["LANGUAGES"] = ["es", "en"]
    db.init_app(app)

    # Los servicios usan flask_babel.gettext para sus mensajes; sin esta
    # inicializacion, llamarlos fuera de una request revienta con KeyError.
    Babel(app, default_locale="es")

    from app.traducciones import etiqueta, formato_fecha
    app.jinja_env.filters["etiqueta"] = etiqueta
    app.jinja_env.globals["etiqueta"] = etiqueta
    app.jinja_env.filters["fecha"] = formato_fecha

    from app.notificaciones_i18n import render as _render_notif
    app.jinja_env.filters["notif_msg"] = lambda n: _render_notif(n.mensaje, n.ticket_id)

    # Importar TODOS los modelos para que db.metadata este completo antes de
    # create_all(); si falta alguno, su tabla/columnas no se crean y los tests
    # fallan con "no such column" / "no such table".
    from app.models.usuario import Usuario
    from app.models.ticket import Ticket
    from app.models.comentario import Comentario
    from app.models.log_auditoria import LogAuditoria
    from app.models.intento_login_fallido import IntentoLoginFallido
    from app.models.ip_bloqueada import IPBloqueada
    from app.models.notificacion import Notificacion
    from app.models.transferencia import SolicitudTransferencia

    with app.app_context():
        # drop_all + create_all garantiza un esquema fresco en cada corrida,
        # sin depender de borrar el archivo .db (que ademas vive en instance/).
        db.drop_all()
        db.create_all()

    return app