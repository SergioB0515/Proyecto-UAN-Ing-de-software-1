from datetime import datetime
from sqlalchemy import select
from app.extensions import db
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.models.transferencia import SolicitudTransferencia
from app.models.enum import EstadoTicket, EstadoSolicitudTransferencia, RolUsuario, AccionAuditoria
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoEnProgresoError, ErrorPersistencia,
    SolicitudDuplicadaError, SolicitudNoEncontradaError,
    SolicitudNoPendienteError, AgenteDestinoInvalidoError,
)


class ServicioSolicitudesTransferencia:

    @staticmethod
    def crear_solicitud(ticket_id, agente_destino_id, solicitante_id, motivo=None):
        ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError("El ticket no ha sido encontrado")

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError("El ticket debe estar en progreso para solicitar transferencia")

        solicitud_existente = db.session.execute(
        select(SolicitudTransferencia).where(
                SolicitudTransferencia.ticket_id == ticket.id,
                SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
            )
        ).scalar()
        if solicitud_existente:
            raise SolicitudDuplicadaError("Ya hay una solicitud en curso con este ticket")

        agente_destino = db.session.execute(select(Usuario).where(Usuario.id == agente_destino_id)).scalar()

        if agente_destino is None:
            raise AgenteDestinoInvalidoError("El agente destinatario no existe")
        if agente_destino.rol != RolUsuario.AGENTE:
            raise AgenteDestinoInvalidoError("El destinarario no es un agente")
        if agente_destino.area_soporte != ticket.categoria:
            raise AgenteDestinoInvalidoError("El agente no pertenece al area correcta")
        if agente_destino.id == ticket.agente_id:
            raise AgenteDestinoInvalidoError("El agente destinatario no puede ser el mismo")
        
        nueva_solicitud = SolicitudTransferencia(
            ticket_id=ticket.id,
            agente_origen_id=ticket.agente_id,
            agente_destino_id=agente_destino_id,
            solicitante_id=solicitante_id,
            motivo=motivo,
        )

        try:
            db.session.add(nueva_solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido crear la solicitud de transferencia, error : {e}")
            raise ErrorPersistencia("No se pudo crear la solicitud de transferencia") from e

        ServicioAuditoria.registrar(
            usuario_id=solicitante_id,
            accion=AccionAuditoria.SOLICITAR_TRANSFERENCIA,
            detalle=f"Ticket #{ticket.id}: solicitud a agente {agente_destino_id}",
        )
        return nueva_solicitud

    @staticmethod
    def aceptar_solicitud(solicitud_id, actor_id):
        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        if not solicitud:
            raise SolicitudNoEncontradaError("La solicitud no ha sido encontrada")

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError("La solicitud ya fue resuelta")

        ticket = db.session.execute(select(Ticket).where(Ticket.id == solicitud.ticket_id)).scalar()

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError("El ticket no tiene el estado permitido")
        
        
        
        ticket.agente_id = solicitud.agente_destino_id
        solicitud.estado = EstadoSolicitudTransferencia.ACEPTADA
        solicitud.fecha_resolucion = datetime.now()

        try:
            db.session.add(ticket)
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido aceptar la solicitud, error : {e}")
            raise ErrorPersistencia("No se pudo aceptar la solicitud") from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.ACEPTAR_TRANSFERENCIA,
            detalle=f"Ticket #{ticket.id}: {solicitud.agente_origen_id} -> {solicitud.agente_destino_id} (solicitud #{solicitud.id})",
        )
        return solicitud

    @staticmethod
    def rechazar_solicitud(solicitud_id, actor_id):
        
        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        
        if not solicitud:
            raise SolicitudNoEncontradaError("La solicitud no ha sido encontrada")

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError("La solicitud ya fue resuelta")
        
        solicitud.estado = EstadoSolicitudTransferencia.RECHAZADA
        solicitud.fecha_resolucion = datetime.now()

        try:
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido rechazar la solicitud, error : {e}")
            raise ErrorPersistencia("No se pudo rechazar la solicitud") from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.RECHAZAR_TRANSFERENCIA,
            detalle=f"Solicitud #{solicitud.id} rechazada (ticket #{solicitud.ticket_id})",
        )
        return solicitud

    @staticmethod
    def cancelar_solicitud(solicitud_id, actor_id):

        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        
        if not solicitud:
            raise SolicitudNoEncontradaError("La solicitud no ha sido encontrada")

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError("La solicitud ya fue resuelta")
        
        solicitud.estado = EstadoSolicitudTransferencia.CANCELADA
        solicitud.fecha_resolucion = datetime.now()

        try:
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido cancelar la solicitud, error : {e}")
            raise ErrorPersistencia("No se pudo cancelar la solicitud") from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.CANCELAR_TRANSFERENCIA,
            detalle=f"Solicitud #{solicitud.id} cancelada (ticket #{solicitud.ticket_id})",
        )
        return solicitud
    @staticmethod
    def listar_pendientes_para_agente(agente_id):
        query = select(SolicitudTransferencia).where(
            SolicitudTransferencia.agente_destino_id == agente_id,
            SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
        ).order_by(SolicitudTransferencia.fecha_solicitud)
        return db.session.execute(query).scalars().all()