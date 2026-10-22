from sqlalchemy import select

from app.extensions import db
from app.models.enum import RolUsuario, EstadoSolicitudTransferencia, TipoSolicitud
from app.models.seguidor_ticket import SeguidorTicket
from app.models.transferencia import SolicitudTransferencia


class ServicioPermisos:

    @staticmethod
    def es_personal(usuario):
        return usuario is not None and usuario.rol in (RolUsuario.AGENTE, RolUsuario.ADMIN)

    @staticmethod
    def puede_ver_ticket(usuario, ticket):
        if usuario is None or ticket is None:
            return False
        if usuario.rol == RolUsuario.ADMIN or ticket.creador_id == usuario.id:
            return True
        if usuario.rol != RolUsuario.AGENTE:
            return False
        if ticket.agente_id == usuario.id:
            return True
        if usuario.area_soporte is not None and usuario.area_soporte == ticket.categoria:
            return True
        sigue = db.session.execute(
            select(SeguidorTicket.id).where(
                SeguidorTicket.ticket_id == ticket.id, SeguidorTicket.usuario_id == usuario.id
            )
        ).first()
        if sigue:
            return True
        destino_pendiente = db.session.execute(
            select(SolicitudTransferencia.id).where(
                SolicitudTransferencia.ticket_id == ticket.id,
                SolicitudTransferencia.tipo == TipoSolicitud.REASIGNACION,
                SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
                SolicitudTransferencia.agente_destino_id == usuario.id,
            )
        ).first()
        return destino_pendiente is not None

    @staticmethod
    def puede_ver_internos(usuario):
        return ServicioPermisos.es_personal(usuario)

    @staticmethod
    def puede_gestionar_ticket(usuario, ticket):
        if usuario is None or ticket is None:
            return False
        return usuario.rol == RolUsuario.ADMIN or ticket.agente_id == usuario.id
