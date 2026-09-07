from datetime import datetime
from sqlalchemy import select
from app.extensions import db
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.models.transferencia import SolicitudTransferencia
from app.models.enum import EstadoTicket, EstadoSolicitudTransferencia, RolUsuario, AccionAuditoria, TipoSolicitud
from app.services.auditoria import ServicioAuditoria
from app.services.gestor_sla import GestorSLA
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoEnProgresoError, ErrorPersistencia,
    SolicitudDuplicadaError, SolicitudNoEncontradaError,
    SolicitudNoPendienteError, AgenteDestinoInvalidoError,
    AreaDestinoInvalidaError, MotivoRequeridoError,PrioridadDestinoInvalidaError
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
            tipo=TipoSolicitud.REASIGNACION,   
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
    
    @staticmethod
    def escalar_a_area(ticket_id, area_destino, solicitante_id, motivo):
        
        ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError("El ticket no ha sido encontrado")

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError("El ticket debe estar en progreso para solicitar cambio de area")

        solicitud_existente = db.session.execute(
        select(SolicitudTransferencia).where(
                SolicitudTransferencia.ticket_id == ticket.id,
                SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
            )
        ).scalar()
        
        if solicitud_existente:
            raise SolicitudDuplicadaError("Ya hay una solicitud en curso con este ticket")
        if area_destino == ticket.categoria:
            raise AreaDestinoInvalidaError("El area no puede ser la misma")
        if not motivo.strip():
            raise MotivoRequeridoError("La solicitud requiere motivo")
        
        nueva_solicitud = SolicitudTransferencia(
            ticket_id=ticket.id,
            tipo=TipoSolicitud.ESCALAMIENTO,  
            agente_origen_id=ticket.agente_id,
            agente_destino_id=None,
            area_destino=area_destino,
            solicitante_id=solicitante_id,
            motivo=motivo.strip(),
        )
        try:
            db.session.add(nueva_solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido crear la solicitud de escalamiento, error : {e}")
            raise ErrorPersistencia("No se pudo crear la solicitud de escalamiento") from e

        ServicioAuditoria.registrar(
            usuario_id=solicitante_id,
            accion=AccionAuditoria.ESCALAR_AREA,
            detalle=f"Ticket #{ticket.id}: escalamiento solicitado de {ticket.categoria.value} a {area_destino.value}",
        )
        return nueva_solicitud

    @staticmethod
    def aprobar_escalamiento(solicitud_id, actor_id):

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
        
        if solicitud.area_destino is None:
            raise SolicitudNoPendienteError("Esta solicitud no es un escalamiento de área")
        
        ticket.categoria = solicitud.area_destino
        ticket.agente_id = None
        ticket.estado = EstadoTicket.ABIERTO
        
        solicitud.estado = EstadoSolicitudTransferencia.ACEPTADA
        solicitud.fecha_resolucion = datetime.now()
        
        try:
            db.session.add(ticket)
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido aceptar la solicitud de escalamiento, error : {e}")
            raise ErrorPersistencia("No se pudo aceptar la solicitud de escalamiento") from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.APROBAR_ESCALAMIENTO,
            detalle=f"Ticket #{ticket.id}: escalamiento aprobado a {solicitud.area_destino.value} (solicitud #{solicitud.id})",
        )
        return solicitud
        
    @staticmethod
    def rechazar_escalamiento(solicitud_id, actor_id):
        
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
            accion=AccionAuditoria.RECHAZAR_ESCALAMIENTO,
            detalle=f"Solicitud #{solicitud.id} rechazada (ticket #{solicitud.ticket_id})",
        )
        return solicitud

    @staticmethod
    def listar_escalamientos_pendientes():
        query = select(SolicitudTransferencia).where(
            SolicitudTransferencia.area_destino.is_not(None),
            SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
        ).order_by(SolicitudTransferencia.fecha_solicitud)
        return db.session.execute(query).scalars().all()
    
    @staticmethod
    def listar_transferencias_pendientes():
        query = select(SolicitudTransferencia).where(
            SolicitudTransferencia.agente_destino_id.is_not(None),
            SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
        ).order_by(SolicitudTransferencia.fecha_solicitud)
        
        return db.session.execute(query).scalars().all()
    
    @staticmethod
    def cambiar_prioridad(ticket_id, prioridad_destino, solicitante_id, motivo):

        ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError("El ticket no ha sido encontrado")

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError("El ticket debe estar en progreso para solicitar cambio de prioridad")

        solicitud_existente = db.session.execute(
        select(SolicitudTransferencia).where(
                SolicitudTransferencia.ticket_id == ticket.id,
                SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
            )
        ).scalar()
        
        if solicitud_existente:
            raise SolicitudDuplicadaError("Ya hay una solicitud en curso con este ticket")
        if prioridad_destino == ticket.prioridad:
            raise PrioridadDestinoInvalidaError("La prioridad no puede ser la misma")
        if not motivo.strip():
            raise MotivoRequeridoError("La solicitud requiere motivo")
        
        nueva_solicitud = SolicitudTransferencia(
                ticket_id=ticket.id,
                tipo=TipoSolicitud.CAMBIO_PRIORIDAD,
                agente_origen_id=ticket.agente_id,
                agente_destino_id=None,
                area_destino=None,
                prioridad_destino=prioridad_destino,
                solicitante_id=solicitante_id,
                motivo=motivo.strip(),
            )
        try:
            db.session.add(nueva_solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido crear la solicitud de cambio de prioridad, error : {e}")
            raise ErrorPersistencia("No se pudo crear la solicitud de cambio de prioridad") from e

        ServicioAuditoria.registrar(
            usuario_id=solicitante_id,
            accion=AccionAuditoria.CAMBIAR_PRIORIDAD,
            detalle=f"Ticket #{ticket.id}: cambio de prioridad solicitado de {ticket.prioridad.value} a {prioridad_destino.value}",
        )
        return nueva_solicitud

    @staticmethod
    def aprobar_cambio_prioridad(solicitud_id, actor_id):

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
        
        if solicitud.tipo != TipoSolicitud.CAMBIO_PRIORIDAD:
            raise SolicitudNoPendienteError("Esta solicitud no es un cambio de prioridad")
        
        usuario=db.session.execute(select(Usuario).where(Usuario.id==ticket.creador_id)).scalar_one_or_none()
        
        nueva_fecha_limite=GestorSLA.calcular_fecha_limite(solicitud.prioridad_destino, usuario.nivel)
        
        ticket.prioridad = solicitud.prioridad_destino
        ticket.fecha_limite = nueva_fecha_limite

        
        solicitud.estado = EstadoSolicitudTransferencia.ACEPTADA
        solicitud.fecha_resolucion = datetime.now()
        
        try:
            db.session.add(ticket)
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido aceptar la solicitud de cambio de prioridad, error : {e}")
            raise ErrorPersistencia("No se pudo aceptar la solicitud de cambio de prioridad") from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.APROBAR_CAMBIO_PRIORIDAD,
            detalle=f"Ticket #{ticket.id}: cambio de prioridad aprobado a {solicitud.prioridad_destino.value} (solicitud #{solicitud.id})",
        )
        return solicitud
        

    @staticmethod
    def rechazar_cambio_prioridad(solicitud_id, actor_id):
        
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
            accion=AccionAuditoria.RECHAZAR_CAMBIO_PRIORIDAD,
            detalle=f"Solicitud #{solicitud.id} cambio a {solicitud.prioridad_destino.value} rechazada (ticket #{solicitud.ticket_id})",
        )
        return solicitud

    @staticmethod
    def listar_cambios_prioridad_pendientes():

        query = select(SolicitudTransferencia).where(
            SolicitudTransferencia.tipo== TipoSolicitud.CAMBIO_PRIORIDAD,
            SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
        ).order_by(SolicitudTransferencia.fecha_solicitud)
        
        return db.session.execute(query).scalars().all()
