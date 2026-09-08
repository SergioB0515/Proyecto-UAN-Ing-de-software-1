from datetime import datetime
from sqlalchemy import select, func
from app.extensions import db,socketio
from app.models.notificacion import Notificacion
from app.notificaciones_i18n import render as render_mensaje


class ServicioNotificaciones:
    LIMITE_POR_USUARIO = 15

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
        