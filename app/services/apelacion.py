from flask_babel import gettext as _
from datetime import datetime
from sqlalchemy import select
from app.extensions import db
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.models.apelacion import ApelacionCierre
from app.models.enum import EstadoTicket, EstadoApelacion, RolUsuario, AccionAuditoria
from app.services.auditoria import ServicioAuditoria
from app.services.notificaciones import ServicioNotificaciones
from app import notificaciones_i18n as notif
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoCerradoError, ApelacionDuplicadaError,
    ApelacionNoEncontradaError, ApelacionNoPendienteError, MotivoRequeridoError,
    ErrorPersistencia,
)


class ServicioApelaciones:

    @staticmethod
    def solicitar_apelacion(ticket_id, solicitante_id, motivo):

        ticket = db.session.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar()
        if not ticket:
                    raise TicketNoEncontradoError(_("El ticket no ha sido encontrado"))
        
        if ticket.estado != EstadoTicket.CERRADO:
                    raise TicketNoCerradoError(_("El ticket debe estar cerrado para apelar su cierre"))
        
        if not motivo.strip():
            raise MotivoRequeridoError(_("Se requiere un motivo para apelar el ticket"))
        
        solicitud_existente = db.session.execute(
                select(ApelacionCierre).where(
                        ApelacionCierre.ticket_id == ticket.id,
                        ApelacionCierre.estado == EstadoApelacion.PENDIENTE,
                    )
                ).scalar()
        if solicitud_existente:
                    raise ApelacionDuplicadaError(_("Ya hay una apelacion en curso con este ticket"))
        
                
        nueva_apelacion = ApelacionCierre(
                    ticket_id=ticket.id,
                    solicitante_id=solicitante_id,
                    motivo=motivo.strip()
                )
        try:
                    db.session.add(nueva_apelacion)
                    db.session.commit()
        except Exception as e:
                    db.session.rollback()
                    print(f"No se ha podido crear la apelacion, error : {e}")
                    raise ErrorPersistencia(_("No se pudo crear la apelacion")) from e
        
        ServicioAuditoria.registrar(
                    usuario_id=solicitante_id,
                    accion=AccionAuditoria.SOLICITAR_APELACION,
                    detalle=_("Apelacion iniciada para Ticket #%(p1)s", p1=ticket.id,),
                )
                
        admins = db.session.execute(select(Usuario).where(Usuario.rol == RolUsuario.ADMIN)).scalars().all()
        for admin in admins:
            ServicioNotificaciones.crear(
            usuario_id=admin.id,
            mensaje=notif.APELACION_NUEVA,
            ticket_id=ticket.id,
            )
                
        return nueva_apelacion

    @staticmethod
    def aceptar_apelacion(apelacion_id, actor_id):
        
        solicitud =db.session.execute(select(ApelacionCierre).where(ApelacionCierre.id ==apelacion_id)).scalar()
        if not solicitud:
                    raise ApelacionNoEncontradaError(_("La apelacion no ha sido encontrada"))
        
        if solicitud.estado != EstadoApelacion.PENDIENTE:
                    raise ApelacionNoPendienteError(_("Esta apelacion ya ha sido respondida"))
                
        ticket = db.session.execute(select(Ticket).where(Ticket.id == solicitud.ticket_id)).scalar()
        
        ticket.estado= EstadoTicket.ABIERTO
        ticket.agente_id = None
        ticket.fecha_cierre = None
        ticket.notificado_proximo_vencer = False
        ticket.notificado_vencido = False
        solicitud.estado = EstadoApelacion.ACEPTADA
        solicitud.fecha_resolucion = datetime.now()
        solicitud.resuelto_por_id = actor_id
        
        db.session.add(solicitud)
        try:
            db.session.add(ticket)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido aceptar la apelacion, error : {e}")
            raise ErrorPersistencia(_("No se pudo aceptar la apelacion")) from e
        
        print(f"apelacion del ticket #{ticket.id} aceptada correctamente")
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.ACEPTAR_APELACION,
            detalle=f"Apelacion para Ticket #{ticket.id} aceptada",
                            )
        ServicioNotificaciones.crear(
            usuario_id=solicitud.solicitante_id,
            mensaje=notif.APELACION_ACEPTADA,
            ticket_id=solicitud.ticket_id,
                )
        return ticket

    @staticmethod
    def rechazar_apelacion(apelacion_id, actor_id):
        solicitud =db.session.execute(select(ApelacionCierre).where(ApelacionCierre.id ==apelacion_id)).scalar()
        if not solicitud:
                    raise ApelacionNoEncontradaError(_("La apelacion no ha sido encontrada"))
        
        if solicitud.estado != EstadoApelacion.PENDIENTE:
                    raise ApelacionNoPendienteError(_("Esta apelacion ya ha sido respondida"))
                
        solicitud.estado = EstadoApelacion.RECHAZADA
        solicitud.fecha_resolucion = datetime.now()
        solicitud.resuelto_por_id = actor_id
        
        try:
            db.session.add(solicitud)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido rechazar la apelacion, error : {e}")
            raise ErrorPersistencia(_("No se pudo rechazar la apelacion")) from e
        
        print(f"apelacion: {apelacion_id}, rechazada correctamente")
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.RECHAZAR_APELACION,
            detalle=f"Apelacion: {apelacion_id}, rechazada",
                            )
        
        ServicioNotificaciones.crear(
            usuario_id=solicitud.solicitante_id,
            mensaje=notif.APELACION_RECHAZADA,
            ticket_id=solicitud.ticket_id,
        )
        return solicitud



    @staticmethod
    def listar_pendientes():
        query = select(ApelacionCierre).where(ApelacionCierre.estado == EstadoApelacion.PENDIENTE).order_by(ApelacionCierre.fecha_solicitud)
        return db.session.execute(query).scalars().all()