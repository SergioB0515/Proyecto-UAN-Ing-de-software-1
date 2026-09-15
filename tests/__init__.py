import os
from flask import Flask
from flask_babel import Babel
from app.extensions import db,mail
from app.models.apelacion import ApelacionCierre
from app.models.palabra_clave import PalabraClave
from app.models.correccion_clasificacion import CorreccionClasificacion
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test_proyecto.db"
    app.config["LANGUAGES"] = ["es", "en"]
    app.config["MAIL_SUPPRESS_SEND"] = True
    app.config["MAIL_DEFAULT_SENDER"] = "pruebas@empresa.com"
    db.init_app(app)
    mail.init_app(app)

    # Los servicios usan flask_babel.gettext para sus mensajes; sin esta
    # inicializacion, llamarlos fuera de una request revienta con KeyError.
    # default_translation_directories apunta a la carpeta real de traducciones
    # (app/translations), no a la del paquete tests -- sin esto, cualquier
    # prueba que fuerce un locale distinto a "es" nunca encuentra el
    # catalogo compilado y siempre cae al texto original en español.
    Babel(app, default_locale="es",
          default_translation_directories=os.path.join(BASE_DIR, "app", "translations"))

    from app.traducciones import etiqueta, formato_fecha
    app.jinja_env.filters["etiqueta"] = etiqueta
    app.jinja_env.globals["etiqueta"] = etiqueta
    app.jinja_env.filters["fecha"] = formato_fecha

    from app.notificaciones_i18n import render as _render_notif
    app.jinja_env.filters["notif_msg"] = lambda n: _render_notif(n.mensaje, n.ticket_id)

    from app.models.usuario import Usuario
    from app.models.ticket import Ticket
    from app.models.comentario import Comentario
    from app.models.log_auditoria import LogAuditoria
    from app.models.intento_login_fallido import IntentoLoginFallido
    from app.models.ip_bloqueada import IPBloqueada
    from app.models.notificacion import Notificacion
    from app.models.transferencia import SolicitudTransferencia
    from app.models.apelacion import ApelacionCierre
    from app.models.palabra_clave import PalabraClave
    from app.models.correccion_clasificacion import CorreccionClasificacion

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app