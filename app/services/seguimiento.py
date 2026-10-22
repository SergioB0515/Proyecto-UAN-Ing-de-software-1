from flask_babel import gettext as _
from sqlalchemy import select, delete

from app.extensions import db
from app.models.seguidor_ticket import SeguidorTicket
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.exceptions import ErrorPersistencia, PermisoDenegadoError, TicketNoEncontradoError


class ServicioSeguimiento:

    @staticmethod
    def sigue(ticket_id, usuario_id):
        return db.session.execute(
            select(SeguidorTicket.id).where(SeguidorTicket.ticket_id == ticket_id, SeguidorTicket.usuario_id == usuario_id)
        ).first() is not None

    @staticmethod
    def ids_seguidores(ticket_id):
        return set(db.session.execute(
            select(SeguidorTicket.usuario_id).where(SeguidorTicket.ticket_id == ticket_id)
        ).scalars())

    @staticmethod
    def seguidores(ticket_id):
        return db.session.execute(
            select(Usuario).join(SeguidorTicket, SeguidorTicket.usuario_id == Usuario.id)
            .where(SeguidorTicket.ticket_id == ticket_id).order_by(Usuario.nombre)
        ).scalars().all()

    @staticmethod
    def seguir(ticket_id, usuario):
        from app.services.permisos import ServicioPermisos

        ticket = db.session.get(Ticket, ticket_id)
        if ticket is None:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
        if not ServicioPermisos.es_personal(usuario):
            raise PermisoDenegadoError(_("Solo agentes y administradores pueden seguir tickets"))
        if ServicioSeguimiento.sigue(ticket_id, usuario.id):
            return False
        db.session.add(SeguidorTicket(ticket_id=ticket_id, usuario_id=usuario.id))
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo seguir el ticket, error: {e}")
            raise ErrorPersistencia(_("No se pudo seguir el ticket")) from e
        return True

    @staticmethod
    def dejar_de_seguir(ticket_id, usuario_id):
        resultado = db.session.execute(
            delete(SeguidorTicket).where(SeguidorTicket.ticket_id == ticket_id, SeguidorTicket.usuario_id == usuario_id)
        )
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo dejar de seguir el ticket, error: {e}")
            raise ErrorPersistencia(_("No se pudo dejar de seguir el ticket")) from e
        return resultado.rowcount > 0

    @staticmethod
    def tickets_seguidos(usuario_id):
        return db.session.execute(
            select(Ticket).join(SeguidorTicket, SeguidorTicket.ticket_id == Ticket.id)
            .where(SeguidorTicket.usuario_id == usuario_id).order_by(Ticket.fecha_creacion.desc())
        ).scalars().all()
