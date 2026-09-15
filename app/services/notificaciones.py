import threading
from flask import current_app, render_template
from flask_mail import Message
from datetime import datetime
from sqlalchemy import select, func
from flask_babel import force_locale
from app.extensions import db,socketio, mail
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.notificacion import Notificacion
from app.notificaciones_i18n import render as render_mensaje
from app import notificaciones_i18n as notif


class ServicioNotificaciones:
    LIMITE_POR_USUARIO = 15

    # Idioma usado para renderizar el correo. La app no guarda un idioma
    # preferido por usuario (ver limitación conocida en notificaciones_i18n),
    # así que se usa el idioma por defecto de la app.
    LOCALE_CORREO = "es"

    PLANTILLAS_CON_CORREO = frozenset({
        notif.CERRADO, notif.CERRADO_SIN_ATENDER,
        notif.SLA_PROXIMO_CREADOR, notif.SLA_PROXIMO_AGENTE,
        notif.SLA_VENCIDO_CREADOR, notif.SLA_VENCIDO_AGENTE,
     })

    # Color de acento del correo según la urgencia de la plantilla (coincide
    # con la paleta oro/verde/rojo usada en la app para SLA y cierres).
    _ACENTOS_POR_PLANTILLA = {
        notif.CERRADO: ("#0d6c4a", "#12885f"),
        notif.CERRADO_SIN_ATENDER: ("#c2860f", "#e0b459"),
        notif.SLA_PROXIMO_CREADOR: ("#c2860f", "#e0b459"),
        notif.SLA_PROXIMO_AGENTE: ("#c2860f", "#e0b459"),
        notif.SLA_VENCIDO_CREADOR: ("#8f2318", "#ea4c3b"),
        notif.SLA_VENCIDO_AGENTE: ("#8f2318", "#ea4c3b"),
    }
    _ACENTO_POR_DEFECTO = ("#4235a8", "#6d5df0")

    _COLORES_ESTADO = {
        "abierto": ("rgba(37, 99, 168, 0.22)", "#7fc0ff"),
        "en_progreso": ("rgba(194, 134, 15, 0.22)", "#e0b459"),
        "cerrado": ("rgba(18, 136, 95, 0.22)", "#5be0ac"),
    }
    _COLORES_PRIORIDAD = {
        "alta": ("#d43f2f", "#ffffff"),
        "media": ("rgba(194, 134, 15, 0.22)", "#e0b459"),
        "baja": ("rgba(18, 136, 95, 0.22)", "#5be0ac"),
    }
    _COLOR_CATEGORIA = ("rgba(109, 93, 240, 0.18)", "#8f82f5")

    @staticmethod
    def crear(usuario_id, mensaje, ticket_id=None):
        nueva_notificacion = Notificacion(
            usuario_id=usuario_id,
            mensaje=mensaje,
            ticket_id=ticket_id,
        )

        try:
            db.session.add(nueva_notificacion)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido crear la notificacion, error: {e}")
            return


        if socketio.server is not None:
            socketio.emit("nueva_notificacion", {
                "id": nueva_notificacion.id,
                "mensaje": render_mensaje(nueva_notificacion.mensaje, nueva_notificacion.ticket_id, locale="es"),
                "plantilla": nueva_notificacion.mensaje,
                "ticket_id": nueva_notificacion.ticket_id,
                "fecha": nueva_notificacion.fecha.isoformat(),
                "no_leidas": ServicioNotificaciones.contar_no_leidas(usuario_id),
            }, room=f"usuario_{usuario_id}")

        if mensaje in ServicioNotificaciones.PLANTILLAS_CON_CORREO:
            usuario = db.session.get(Usuario,usuario_id)
            if usuario and usuario.email:
                ticket = db.session.get(Ticket, ticket_id) if ticket_id else None
                contexto_ticket = ServicioNotificaciones._contexto_correo(ticket) if ticket else None
                app_actual= current_app._get_current_object()
                threading.Thread(
                    target=ServicioNotificaciones._enviar_correo,
                    args=(app_actual, usuario.email, mensaje, ticket_id, contexto_ticket),
                    daemon=True
                ).start()

        total = db.session.execute(
            select(func.count()).select_from(Notificacion).where(Notificacion.usuario_id == usuario_id)
        ).scalar()

        if total > ServicioNotificaciones.LIMITE_POR_USUARIO:
            exceso = total - ServicioNotificaciones.LIMITE_POR_USUARIO
            viejas = db.session.execute(
                select(Notificacion)
                .where(Notificacion.usuario_id == usuario_id)
                .order_by(Notificacion.fecha.asc())
                .limit(exceso)
            ).scalars().all()
            for n in viejas:
                db.session.delete(n)
            db.session.commit()

    @staticmethod
    def _contexto_correo(ticket):
        """Extrae del ticket los datos primitivos que necesita el correo, para no
        cruzar el objeto ORM (ligado a la sesión de este hilo) hacia el hilo
        que envía el correo."""

        agente_nombre = None
        if ticket.agente_id:
            agente = db.session.get(Usuario, ticket.agente_id)
            agente_nombre = agente.nombre if agente else None

        return {
            "id": ticket.id,
            "texto": ticket.texto,
            "categoria_valor": ticket.categoria.value,
            "prioridad_valor": ticket.prioridad.value,
            "estado_valor": ticket.estado.value,
            "fecha_limite": ticket.fecha_limite,
            "agente_nombre": agente_nombre,
        }

    @staticmethod
    def _enviar_correo(app, destinatario, mensaje, ticket_id, contexto_ticket):
        with app.app_context():
            try:
                locale = ServicioNotificaciones.LOCALE_CORREO
                texto = render_mensaje(mensaje, ticket_id, locale=locale)
                asunto = f"Sistema de Tickets IT — {texto}"

                html = None
                if contexto_ticket:
                    color_1, color_2 = ServicioNotificaciones._ACENTOS_POR_PLANTILLA.get(
                        mensaje, ServicioNotificaciones._ACENTO_POR_DEFECTO
                    )
                    with force_locale(locale):
                        html = render_template(
                            "email/ticket_notificacion.html",
                            titulo=texto,
                            ticket=contexto_ticket,
                            url_ticket=f"{app.config['BASE_URL']}/tickets/{contexto_ticket['id']}",
                            color_1=color_1,
                            color_2=color_2,
                            idioma=locale,
                            colores_estado=ServicioNotificaciones._COLORES_ESTADO,
                            colores_prioridad=ServicioNotificaciones._COLORES_PRIORIDAD,
                            color_categoria=ServicioNotificaciones._COLOR_CATEGORIA,
                        )

                msg = Message(
                    subject=asunto,
                    recipients=[destinatario],
                    body=texto,
                    html=html,
                )
                mail.send(msg)
            except Exception as e:
                print(f"No se pudo enviar el correo a {destinatario}: {e}")


    @staticmethod
    def listar_para_usuario(usuario_id):
        query = select(Notificacion).where(
            Notificacion.usuario_id == usuario_id,
        ).order_by(Notificacion.fecha.desc())

        return db.session.execute(query).scalars().all()

    @staticmethod
    def listar_no_leidas(usuario_id):
        query = select(Notificacion).where(
            Notificacion.usuario_id == usuario_id,
            Notificacion.leida == False,
        ).order_by(Notificacion.fecha.desc())

        return db.session.execute(query).scalars().all()



    @staticmethod
    def contar_no_leidas(usuario_id):
        query = (
            select(func.count())
            .select_from(Notificacion)
            .where(Notificacion.usuario_id == usuario_id, Notificacion.leida == False)
        )
        return db.session.execute(query).scalar() or 0

    @staticmethod
    def marcar_todas_leidas(usuario_id):
        no_leidas = db.session.execute(
            select(Notificacion).where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.leida == False,
            )
        ).scalars().all()

        for notificacion in no_leidas:
            notificacion.leida = True
            db.session.add(notificacion)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se han podido marcar las notificaciones como leidas, error: {e}")
            return 0

        return len(no_leidas)

    @staticmethod
    def marcar_leida(notificacion_id, usuario_id):
        notificacion = db.session.execute(
            select(Notificacion).where(Notificacion.id == notificacion_id)
        ).scalar_one_or_none()

        if notificacion is None:
            return
        if notificacion.usuario_id != usuario_id:
            return

        notificacion.leida = True

        try:
            db.session.add(notificacion)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido marcar la notificacion como leida, error: {e}")
            return

        return notificacion
