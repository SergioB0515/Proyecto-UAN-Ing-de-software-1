from datetime import datetime, timedelta

from flask_babel import gettext as _
from sqlalchemy import select

from app import notificaciones_i18n as notif
from app.extensions import db
from app.models.encuesta_satisfaccion import EncuestaSatisfaccion
from app.models.enum import AccionAuditoria, EstadoTicket
from app.models.ticket import Ticket
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import (
    EncuestaNoDisponibleError,
    EncuestaYaRespondidaError,
    ErrorPersistencia,
    PermisoDenegadoError,
    TicketNoEncontradoError,
)
from app.services.notificaciones import ServicioNotificaciones

DIAS_PARA_RESPONDER = 14
PUNTUACION_MINIMA = 1
PUNTUACION_MAXIMA = 5


class ServicioEncuestas:

    @staticmethod
    def obtener_por_ticket(ticket_id):
        return db.session.execute(
            select(EncuestaSatisfaccion).where(EncuestaSatisfaccion.ticket_id == ticket_id)
        ).scalar_one_or_none()

    @staticmethod
    def puede_responder(ticket, usuario_id):
        if ticket is None or ticket.creador_id != usuario_id or ticket.estado != EstadoTicket.CERRADO:
            return False
        if ticket.fecha_cierre is None or ticket.fecha_cierre < datetime.now() - timedelta(days=DIAS_PARA_RESPONDER):
            return False
        if ticket.agente_id is None:
            return False
        return ServicioEncuestas.obtener_por_ticket(ticket.id) is None

    @staticmethod
    def responder(ticket_id, usuario_id, puntuacion, comentario=None):
        ticket = db.session.get(Ticket, ticket_id)
        if ticket is None:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
        if ticket.creador_id != usuario_id:
            raise PermisoDenegadoError(_("Solo quien creó el ticket puede calificar la atención"))
        if ServicioEncuestas.obtener_por_ticket(ticket_id) is not None:
            raise EncuestaYaRespondidaError(_("Ya calificaste la atención de este ticket"))
        if not ServicioEncuestas.puede_responder(ticket, usuario_id):
            raise EncuestaNoDisponibleError(_("La encuesta no está disponible para este ticket"))
        try:
            puntuacion = int(puntuacion)
        except (TypeError, ValueError):
            raise ValueError(_("Selecciona una calificación de 1 a 5"))
        if not PUNTUACION_MINIMA <= puntuacion <= PUNTUACION_MAXIMA:
            raise ValueError(_("Selecciona una calificación de 1 a 5"))

        encuesta = EncuestaSatisfaccion(
            ticket_id=ticket_id,
            usuario_id=usuario_id,
            agente_id=ticket.agente_id,
            puntuacion=puntuacion,
            comentario=(comentario or "").strip()[:500] or None,
        )
        db.session.add(encuesta)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo guardar la encuesta, error: {e}")
            raise ErrorPersistencia(_("No se pudo guardar tu calificación")) from e

        ServicioAuditoria.registrar(
            usuario_id=usuario_id,
            accion=AccionAuditoria.RESPONDER_ENCUESTA,
            detalle=_("Ticket #%(p1)s calificado con %(p2)s/5", p1=ticket_id, p2=puntuacion),
        )
        if ticket.agente_id:
            ServicioNotificaciones.crear(usuario_id=ticket.agente_id, mensaje=notif.ENCUESTA_RECIBIDA, ticket_id=ticket_id)
        return encuesta

    @staticmethod
    def resumen(desde=None, agente_id=None, hasta=None):
        query = select(EncuestaSatisfaccion)
        if desde is not None:
            query = query.where(EncuestaSatisfaccion.fecha >= desde)
        if hasta is not None:
            query = query.where(EncuestaSatisfaccion.fecha < hasta)
        if agente_id is not None:
            query = query.where(EncuestaSatisfaccion.agente_id == agente_id)
        encuestas = db.session.execute(query).scalars().all()
        distribucion = {i: 0 for i in range(PUNTUACION_MINIMA, PUNTUACION_MAXIMA + 1)}
        for e in encuestas:
            distribucion[e.puntuacion] = distribucion.get(e.puntuacion, 0) + 1
        total = len(encuestas)
        promedio = round(sum(e.puntuacion for e in encuestas) / total, 2) if total else None
        satisfechos = distribucion[4] + distribucion[5]
        return {
            "total": total,
            "promedio": promedio,
            "csat": round(satisfechos / total * 100, 1) if total else None,
            "distribucion": distribucion,
        }

    @staticmethod
    def recientes(limite=6):
        return db.session.execute(
            select(EncuestaSatisfaccion).where(EncuestaSatisfaccion.comentario.isnot(None))
            .order_by(EncuestaSatisfaccion.fecha.desc()).limit(limite)
        ).scalars().all()
