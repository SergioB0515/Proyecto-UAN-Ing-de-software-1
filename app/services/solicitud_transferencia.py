from flask_babel import gettext as _
from datetime import datetime
from sqlalchemy import select
from app.extensions import db
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.notificaciones import ServicioNotificaciones
from app.models.transferencia import SolicitudTransferencia
from app.models.enum import EstadoTicket, EstadoSolicitudTransferencia, RolUsuario, AccionAuditoria, TipoSolicitud
from app.services.auditoria import ServicioAuditoria
from app import notificaciones_i18n as notif
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
            raise TicketNoEncontradoError(_("El ticket no ha sido encontrado"))

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError(_("El ticket debe estar en progreso para solicitar transferencia"))

        solicitud_existente = db.session.execute(
        select(SolicitudTransferencia).where(
                SolicitudTransferencia.ticket_id == ticket.id,
                SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
            )
        ).scalar()
        if solicitud_existente:
            raise SolicitudDuplicadaError(_("Ya hay una solicitud en curso con este ticket"))

        agente_destino = db.session.execute(select(Usuario).where(Usuario.id == agente_destino_id)).scalar()

        if agente_destino is None:
            raise AgenteDestinoInvalidoError(_("El agente destinatario no existe"))
        if agente_destino.rol != RolUsuario.AGENTE:
            raise AgenteDestinoInvalidoError(_("El destinarario no es un agente"))
        if agente_destino.area_soporte != ticket.categoria:
            raise AgenteDestinoInvalidoError(_("El agente no pertenece al area correcta"))
        if agente_destino.id == ticket.agente_id:
            raise AgenteDestinoInvalidoError(_("El agente destinatario no puede ser el mismo"))
        
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
            raise ErrorPersistencia(_("No se pudo crear la solicitud de transferencia")) from e

        ServicioAuditoria.registrar(
            usuario_id=solicitante_id,
            accion=AccionAuditoria.SOLICITAR_TRANSFERENCIA,
            detalle=_("Ticket #%(p1)s: solicitud a agente %(p2)s", p1=ticket.id, p2=agente_destino_id),
        )
        
        ServicioNotificaciones.crear(
            usuario_id=agente_destino_id,
            mensaje=notif.TRANSFERENCIA_NUEVA,
            ticket_id=ticket.id,
        )
        
        return nueva_solicitud

    @staticmethod
    def aceptar_solicitud(solicitud_id, actor_id):
        
        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        if not solicitud:
            raise SolicitudNoEncontradaError(_("La solicitud no ha sido encontrada"))

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError(_("La solicitud ya fue resuelta"))

        ticket = db.session.execute(select(Ticket).where(Ticket.id == solicitud.ticket_id)).scalar()

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError(_("El ticket no tiene el estado permitido"))
        
        
        
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
            raise ErrorPersistencia(_("No se pudo aceptar la solicitud")) from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.ACEPTAR_TRANSFERENCIA,
            detalle=_("Ticket #%(p1)s: %(p2)s -> %(p3)s (solicitud #%(p4)s)", p1=ticket.id, p2=solicitud.agente_origen_id, p3=solicitud.agente_destino_id, p4=solicitud.id),
        )
        ServicioNotificaciones.crear(
            usuario_id=solicitud.solicitante_id,
            mensaje=notif.TRANSFERENCIA_ACEPTADA,
            ticket_id=ticket.id,
        )
        return solicitud

    @staticmethod
    def rechazar_solicitud(solicitud_id, actor_id):
        
        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        
        if not solicitud:
            raise SolicitudNoEncontradaError(_("La solicitud no ha sido encontrada"))

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError(_("La solicitud ya fue resuelta"))
        
        solicitud.estado = EstadoSolicitudTransferencia.RECHAZADA
        solicitud.fecha_resolucion = datetime.now()

        try:
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido rechazar la solicitud, error : {e}")
            raise ErrorPersistencia(_("No se pudo rechazar la solicitud")) from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.RECHAZAR_TRANSFERENCIA,
            detalle=_("Solicitud #%(p1)s rechazada (ticket #%(p2)s)", p1=solicitud.id, p2=solicitud.ticket_id),
        )
        
        ServicioNotificaciones.crear(
            usuario_id=solicitud.solicitante_id,
            mensaje=notif.TRANSFERENCIA_RECHAZADA,
            ticket_id=solicitud.ticket_id,
        )
        return solicitud

    @staticmethod
    def cancelar_solicitud(solicitud_id, actor_id):

        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        
        if not solicitud:
            raise SolicitudNoEncontradaError(_("La solicitud no ha sido encontrada"))

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError(_("La solicitud ya fue resuelta"))
        
        solicitud.estado = EstadoSolicitudTransferencia.CANCELADA
        solicitud.fecha_resolucion = datetime.now()

        try:
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido cancelar la solicitud, error : {e}")
            raise ErrorPersistencia(_("No se pudo cancelar la solicitud")) from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.CANCELAR_TRANSFERENCIA,
            detalle=_("Solicitud #%(p1)s cancelada (ticket #%(p2)s)", p1=solicitud.id, p2=solicitud.ticket_id),
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
            raise TicketNoEncontradoError(_("El ticket no ha sido encontrado"))

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError(_("El ticket debe estar en progreso para solicitar cambio de area"))

        solicitud_existente = db.session.execute(
        select(SolicitudTransferencia).where(
                SolicitudTransferencia.ticket_id == ticket.id,
                SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
            )
        ).scalar()
        
        if solicitud_existente:
            raise SolicitudDuplicadaError(_("Ya hay una solicitud en curso con este ticket"))
        if area_destino == ticket.categoria:
            raise AreaDestinoInvalidaError(_("El area no puede ser la misma"))
        if not motivo.strip():
            raise MotivoRequeridoError(_("La solicitud requiere motivo"))
        
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
            raise ErrorPersistencia(_("No se pudo crear la solicitud de escalamiento")) from e

        ServicioAuditoria.registrar(
            usuario_id=solicitante_id,
            accion=AccionAuditoria.ESCALAR_AREA,
            detalle=_("Ticket #%(p1)s: escalamiento solicitado de %(p2)s a %(p3)s", p1=ticket.id, p2=ticket.categoria.value, p3=area_destino.value),
        )
        
        admins = db.session.execute(select(Usuario).where(Usuario.rol == RolUsuario.ADMIN)).scalars().all()
        for admin in admins:
            ServicioNotificaciones.crear(
            usuario_id=admin.id,
            mensaje=notif.ESCALAMIENTO_PENDIENTE,
            ticket_id=ticket.id,
            )
        
        return nueva_solicitud

    @staticmethod
    def aprobar_escalamiento(solicitud_id, actor_id):

        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        if not solicitud:
            raise SolicitudNoEncontradaError(_("La solicitud no ha sido encontrada"))

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError(_("La solicitud ya fue resuelta"))

        ticket = db.session.execute(select(Ticket).where(Ticket.id == solicitud.ticket_id)).scalar()

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError(_("El ticket no tiene el estado permitido"))
        
        if solicitud.area_destino is None:
            raise SolicitudNoPendienteError(_("Esta solicitud no es un escalamiento de área"))
        
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
            raise ErrorPersistencia(_("No se pudo aceptar la solicitud de escalamiento")) from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.APROBAR_ESCALAMIENTO,
            detalle=_("Ticket #%(p1)s: escalamiento aprobado a %(p2)s (solicitud #%(p3)s)", p1=ticket.id, p2=solicitud.area_destino.value, p3=solicitud.id),
        )
        ServicioNotificaciones.crear(
            usuario_id=solicitud.solicitante_id,
            mensaje=notif.ESCALAMIENTO_APROBADO,
            ticket_id=ticket.id,
        )
        
        return solicitud
        
    @staticmethod
    def rechazar_escalamiento(solicitud_id, actor_id):
        
        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        
        if not solicitud:
            raise SolicitudNoEncontradaError(_("La solicitud no ha sido encontrada"))

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError(_("La solicitud ya fue resuelta"))
        
        solicitud.estado = EstadoSolicitudTransferencia.RECHAZADA
        solicitud.fecha_resolucion = datetime.now()

        try:
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido rechazar la solicitud, error : {e}")
            raise ErrorPersistencia(_("No se pudo rechazar la solicitud")) from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.RECHAZAR_ESCALAMIENTO,
            detalle=_("Solicitud #%(p1)s rechazada (ticket #%(p2)s)", p1=solicitud.id, p2=solicitud.ticket_id),
        )
        
        ServicioNotificaciones.crear(
            usuario_id=solicitud.solicitante_id,
            mensaje=notif.ESCALAMIENTO_RECHAZADO,
            ticket_id=solicitud.ticket_id,
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
    def listar_por_ticket(ticket_id):
        """Todas las solicitudes (de cualquier tipo/estado) de un ticket,
        de la más reciente a la más antigua."""
        query = select(SolicitudTransferencia).where(
            SolicitudTransferencia.ticket_id == ticket_id,
        ).order_by(SolicitudTransferencia.fecha_solicitud.desc())
        return db.session.execute(query).scalars().all()
    
    @staticmethod
    def cambiar_prioridad(ticket_id, prioridad_destino, solicitante_id, motivo):

        ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError(_("El ticket no ha sido encontrado"))

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError(_("El ticket debe estar en progreso para solicitar cambio de prioridad"))

        solicitud_existente = db.session.execute(
        select(SolicitudTransferencia).where(
                SolicitudTransferencia.ticket_id == ticket.id,
                SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
            )
        ).scalar()
        
        if solicitud_existente:
            raise SolicitudDuplicadaError(_("Ya hay una solicitud en curso con este ticket"))
        if prioridad_destino == ticket.prioridad:
            raise PrioridadDestinoInvalidaError(_("La prioridad no puede ser la misma"))
        if not motivo.strip():
            raise MotivoRequeridoError(_("La solicitud requiere motivo"))
        
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
            raise ErrorPersistencia(_("No se pudo crear la solicitud de cambio de prioridad")) from e

        ServicioAuditoria.registrar(
            usuario_id=solicitante_id,
            accion=AccionAuditoria.CAMBIAR_PRIORIDAD,
            detalle=_("Ticket #%(p1)s: cambio de prioridad solicitado de %(p2)s a %(p3)s", p1=ticket.id, p2=ticket.prioridad.value, p3=prioridad_destino.value),
        )
        
        admins = db.session.execute(select(Usuario).where(Usuario.rol == RolUsuario.ADMIN)).scalars().all()
        for admin in admins:
            ServicioNotificaciones.crear(
                usuario_id=admin.id,
                mensaje=notif.PRIORIDAD_PENDIENTE,
                ticket_id=ticket.id,
            )
            
        return nueva_solicitud

    @staticmethod
    def aprobar_cambio_prioridad(solicitud_id, actor_id):

        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        if not solicitud:
            raise SolicitudNoEncontradaError(_("La solicitud no ha sido encontrada"))

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError(_("La solicitud ya fue resuelta"))

        ticket = db.session.execute(select(Ticket).where(Ticket.id == solicitud.ticket_id)).scalar()

        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError(_("El ticket no tiene el estado permitido"))
        
        if solicitud.tipo != TipoSolicitud.CAMBIO_PRIORIDAD:
            raise SolicitudNoPendienteError(_("Esta solicitud no es un cambio de prioridad"))
        
        usuario=db.session.execute(select(Usuario).where(Usuario.id==ticket.creador_id)).scalar_one_or_none()
        
        nueva_fecha_limite=GestorSLA.calcular_fecha_limite(solicitud.prioridad_destino, usuario.nivel)
        
        ticket.prioridad = solicitud.prioridad_destino
        ticket.fecha_limite = nueva_fecha_limite

        ticket.notificado_proximo_vencer = False
        ticket.notificado_vencido = False
        
        solicitud.estado = EstadoSolicitudTransferencia.ACEPTADA
        solicitud.fecha_resolucion = datetime.now()
        
        try:
            db.session.add(ticket)
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido aceptar la solicitud de cambio de prioridad, error : {e}")
            raise ErrorPersistencia(_("No se pudo aceptar la solicitud de cambio de prioridad")) from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.APROBAR_CAMBIO_PRIORIDAD,
            detalle=_("Ticket #%(p1)s: cambio de prioridad aprobado a %(p2)s (solicitud #%(p3)s)", p1=ticket.id, p2=solicitud.prioridad_destino.value, p3=solicitud.id),
        )
        
        ServicioNotificaciones.crear(
            usuario_id=solicitud.solicitante_id,
            mensaje=notif.PRIORIDAD_APROBADO,
            ticket_id=ticket.id,
        )
        return solicitud
        

    @staticmethod
    def rechazar_cambio_prioridad(solicitud_id, actor_id):
        
        solicitud = db.session.execute(
            select(SolicitudTransferencia).where(SolicitudTransferencia.id == solicitud_id)
        ).scalar()
        
        if not solicitud:
            raise SolicitudNoEncontradaError(_("La solicitud no ha sido encontrada"))

        if solicitud.estado != EstadoSolicitudTransferencia.PENDIENTE:
            raise SolicitudNoPendienteError(_("La solicitud ya fue resuelta"))
        
        solicitud.estado = EstadoSolicitudTransferencia.RECHAZADA
        solicitud.fecha_resolucion = datetime.now()

        try:
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido rechazar la solicitud, error : {e}")
            raise ErrorPersistencia(_("No se pudo rechazar la solicitud")) from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.RECHAZAR_CAMBIO_PRIORIDAD,
            detalle=_("Solicitud #%(p1)s cambio a %(p2)s rechazada (ticket #%(p3)s)", p1=solicitud.id, p2=solicitud.prioridad_destino.value, p3=solicitud.ticket_id),
        )
        
        ServicioNotificaciones.crear(
            usuario_id=solicitud.solicitante_id,
            mensaje=notif.PRIORIDAD_RECHAZADO,
            ticket_id=solicitud.ticket_id,
        )
        return solicitud

    @staticmethod
    def listar_cambios_prioridad_pendientes():

        query = select(SolicitudTransferencia).where(
            SolicitudTransferencia.tipo== TipoSolicitud.CAMBIO_PRIORIDAD,
            SolicitudTransferencia.estado == EstadoSolicitudTransferencia.PENDIENTE,
        ).order_by(SolicitudTransferencia.fecha_solicitud)
        
        return db.session.execute(query).scalars().all()
