import hashlib
import secrets
import threading
from datetime import datetime, timedelta

from flask import current_app, render_template
from jinja2 import TemplateNotFound
from flask_babel import gettext as _
from flask_mail import Message
from sqlalchemy import select, func, update

from app.extensions import db, mail
from app.models.enum import AccionAuditoria
from app.models.token_recuperacion import TokenRecuperacion
from app.models.usuario import Usuario
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import ErrorPersistencia, TokenRecuperacionInvalidoError

MINUTOS_VALIDEZ = 30
MAX_SOLICITUDES_POR_HORA = 3


class ServicioRecuperacion:

    @staticmethod
    def _hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _invalidar_pendientes(usuario_id):
        db.session.execute(
            update(TokenRecuperacion)
            .where(TokenRecuperacion.usuario_id == usuario_id, TokenRecuperacion.usado.is_(False))
            .values(usado=True)
        )

    @staticmethod
    def solicitar(email, enviar_correo=True):
        email = (email or "").strip()
        usuario = db.session.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()
        if usuario is None or not usuario.activo:
            return None

        hace_una_hora = datetime.now() - timedelta(hours=1)
        recientes = db.session.execute(
            select(func.count(TokenRecuperacion.id)).where(
                TokenRecuperacion.usuario_id == usuario.id,
                TokenRecuperacion.fecha_creacion >= hace_una_hora,
            )
        ).scalar()
        if recientes >= MAX_SOLICITUDES_POR_HORA:
            return None

        token = secrets.token_urlsafe(32)
        ServicioRecuperacion._invalidar_pendientes(usuario.id)
        db.session.add(TokenRecuperacion(
            usuario_id=usuario.id,
            token_hash=ServicioRecuperacion._hash(token),
            expira=datetime.now() + timedelta(minutes=MINUTOS_VALIDEZ),
        ))
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo crear el token de recuperación, error: {e}")
            raise ErrorPersistencia(_("No se pudo procesar la solicitud de recuperación")) from e

        ServicioAuditoria.registrar(
            usuario_id=usuario.id,
            accion=AccionAuditoria.SOLICITAR_RECUPERACION,
            detalle=_("Se solicitó recuperar la contraseña de %(p1)s", p1=usuario.email),
        )

        if enviar_correo:
            ServicioRecuperacion._enviar_correo(usuario, token)
        return token

    @staticmethod
    def _enviar_correo(usuario, token):
        enlace = f"{current_app.config.get('BASE_URL', '')}/recuperar/{token}"
        asunto = _("Sistema de Tickets IT — Restablecer contraseña")
        cuerpo = _(
            "Hola %(nombre)s, recibimos una solicitud para restablecer tu contraseña. "
            "Abre este enlace en los próximos %(min)s minutos: %(enlace)s . "
            "Si no fuiste tú, ignora este correo.",
            nombre=usuario.nombre, min=MINUTOS_VALIDEZ, enlace=enlace,
        )
        try:
            html = render_template(
                "email/recuperar_contrasena.html",
                nombre=usuario.nombre, enlace=enlace, minutos=MINUTOS_VALIDEZ,
            )
        except TemplateNotFound:
            html = None

        if not current_app.config.get("MAIL_USERNAME") or current_app.config.get("MAIL_SUPPRESS_SEND"):
            print(f"[recuperacion] Correo no enviado (correo sin configurar o suprimido). Enlace para {usuario.email}: {enlace}")
            if current_app.config.get("MAIL_SUPPRESS_SEND"):
                mail.send(Message(subject=asunto, recipients=[usuario.email], body=cuerpo, html=html,
                                  sender=current_app.config.get("MAIL_DEFAULT_SENDER") or "no-reply@tickets-it.local"))
            return

        app_actual = current_app._get_current_object()
        mensaje = Message(subject=asunto, recipients=[usuario.email], body=cuerpo, html=html)

        def enviar():
            with app_actual.app_context():
                try:
                    mail.send(mensaje)
                except Exception as e:
                    print(f"No se pudo enviar el correo de recuperación a {usuario.email}: {e}")

        threading.Thread(target=enviar, daemon=True).start()

    @staticmethod
    def validar_token(token):
        registro = db.session.execute(
            select(TokenRecuperacion).where(TokenRecuperacion.token_hash == ServicioRecuperacion._hash(token or ""))
        ).scalar_one_or_none()
        if registro is None or registro.usado or registro.expira < datetime.now():
            raise TokenRecuperacionInvalidoError(_("El enlace de recuperación no es válido o ya expiró"))
        usuario = db.session.get(Usuario, registro.usuario_id)
        if usuario is None:
            raise TokenRecuperacionInvalidoError(_("El enlace de recuperación no es válido o ya expiró"))
        return registro, usuario

    @staticmethod
    def restablecer(token, contrasena_nueva, confirmacion=None):
        from app.services.autenticacion import ServicioAutenticacion

        registro, usuario = ServicioRecuperacion.validar_token(token)

        if confirmacion is not None and contrasena_nueva != confirmacion:
            raise ValueError(_("Las contraseñas no coinciden"))
        ServicioAutenticacion.validar_politica_contrasena(contrasena_nueva or "")

        usuario.contrasena_hash = ServicioAutenticacion._generar_hash(contrasena_nueva)
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        registro.usado = True
        ServicioRecuperacion._invalidar_pendientes(usuario.id)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            db.session.refresh(usuario)
            print(f"No se pudo restablecer la contraseña, error: {e}")
            raise ErrorPersistencia(_("No se pudo restablecer la contraseña")) from e

        ServicioAuditoria.registrar(
            usuario_id=usuario.id,
            accion=AccionAuditoria.RESTABLECER_CONTRASENA,
            detalle=_("Se restableció la contraseña de %(p1)s mediante enlace de recuperación", p1=usuario.email),
        )
        return usuario
