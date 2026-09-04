from app.models.enum import Categoria,Prioridad,EstadoTicket,AccionAuditoria
from app.models.ticket import Ticket
from app.models.comentario import Comentario
from app.services.clasificador import ClasificadorTickets
from app.services.gestor_sla import GestorSLA
from app.services.exceptions import TransicionInvalidaError,AgenteYaAsignadoError,TicketNoEncontradoError,TicketNoEnProgresoError,ComentarioVacioError,ErrorPersistencia
from app.extensions import db
from datetime import datetime
from app.services.auditoria import ServicioAuditoria
from sqlalchemy import select

PRIORIDAD_BASE_POR_CATEGORIA={
    Categoria.SEGURIDAD : Prioridad.ALTA,
    Categoria.REDES : Prioridad.ALTA,
    Categoria.INFRAESTRUCTURA : Prioridad.MEDIA,
    Categoria.PERMISOS : Prioridad.BAJA,
    Categoria.CUENTAS_CONTRASENAS : Prioridad.BAJA,
    Categoria.SOFTWARE : Prioridad.BAJA,
    Categoria.OTROS : Prioridad.BAJA
}
ORDEN_PRIORIDAD={
    Prioridad.ALTA : 0,
    Prioridad.MEDIA : 1,
    Prioridad.BAJA : 2,
}
TRANSICIONES_VALIDAS={
    EstadoTicket.ABIERTO : [EstadoTicket.EN_PROGRESO,EstadoTicket.CERRADO],  
    EstadoTicket.EN_PROGRESO : [EstadoTicket.CERRADO],
    EstadoTicket.CERRADO : [EstadoTicket.EN_PROGRESO]
}
class ServicioTickets:
    @staticmethod
    def crear_ticket(creador, texto):
        categoria = ClasificadorTickets.clasificar(texto)
        prioridad_base = PRIORIDAD_BASE_POR_CATEGORIA[categoria]
        prioridad_final =GestorSLA.ajustar_prioridad_por_nivel(prioridad_base,creador.nivel)
        fecha_limite = GestorSLA.calcular_fecha_limite(prioridad_final,creador.nivel)
        nuevo_ticket = Ticket(
            texto=texto,
            categoria=categoria, 
            prioridad=prioridad_final,
            creador_id = creador.id,
            estado=EstadoTicket.ABIERTO,
            fecha_limite=fecha_limite
        )
        try:
            db.session.add(nuevo_ticket)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido crear el ticket, error : {e}")
            raise ErrorPersistencia("No se pudo crear el ticket") from e

        print(f"El ticket se ha resgistrado con exito")
        ServicioAuditoria.registrar(
            usuario_id=creador.id,
            accion=AccionAuditoria.CREAR_TICKET,
            detalle=f"Ticket #{nuevo_ticket.id} creado: categoria={nuevo_ticket.categoria}, prioridad={nuevo_ticket.prioridad}",
        )
        return nuevo_ticket
    
    @staticmethod
    def listar_tickets_por_area(area, estado=None, prioridad=None, fecha_desde=None, fecha_hasta=None):
        query = select(Ticket).where(Ticket.categoria == area)


        if estado is not None:
            query = query.where(Ticket.estado == estado)

        if prioridad is not None:
            query = query.where(Ticket.prioridad == prioridad)

        if fecha_desde is not None:
            query = query.where(Ticket.fecha_creacion >= fecha_desde)

        if fecha_hasta is not None:
            query = query.where(Ticket.fecha_creacion < fecha_hasta)

        tickets_del_area = db.session.execute(query).scalars().all()


        return sorted(tickets_del_area, key=lambda ticket: ORDEN_PRIORIDAD[ticket.prioridad])
        
    @staticmethod
    def cambiar_estado(ticket_id, nuevo_estado, actor_id, agente_id=None):
        
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar() 
       
        if not ticket:
            raise TicketNoEncontradoError("El ticket no a sido encontrado")
        
        if nuevo_estado not in TRANSICIONES_VALIDAS[ticket.estado]:
            raise TransicionInvalidaError("La transicion no es valida")
       
        if nuevo_estado == EstadoTicket.EN_PROGRESO:
       

            if agente_id is None and ticket.agente_id is None:
                raise TransicionInvalidaError("Se requiere un agente_id para pasar a EN_PROGRESO")
       
            if agente_id is not None:
                ticket.agente_id = agente_id
        
        estado_anterior=ticket.estado
        ticket.estado = nuevo_estado
        if estado_anterior ==   EstadoTicket.CERRADO and nuevo_estado == EstadoTicket.EN_PROGRESO:
            ticket.fecha_cierre = None
        if nuevo_estado == EstadoTicket.CERRADO:
            ticket.fecha_cierre = datetime.now()
       
        try:
            db.session.add(ticket)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido cambiar el estado del ticket, error : {e}")
            raise ErrorPersistencia("No se pudo cambiar el estado del ticket") from e

        print(f"El estado del Ticket a sido cambiado con exito")
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.CAMBIAR_ESTADO,
            detalle=f"Ticket #{ticket.id}: {estado_anterior} -> {nuevo_estado}",
        )
        return ticket.estado


    @staticmethod
    def reasignar_agente(ticket_id, nuevo_agente_id, actor_id):
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError("El ticket no a sido encontrado")
        
        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError("Este ticket no esta en un estado valido para su reasignacion")
        if nuevo_agente_id == ticket.agente_id:
            raise AgenteYaAsignadoError("Este ticket ya tiene asignado a este mismo agente")
        agente_anterior=ticket.agente_id
        ticket.agente_id = nuevo_agente_id
        try:
            db.session.add(ticket)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido realizar la reasignacion, error : {e}")
            raise ErrorPersistencia("No se pudo reasignar el agente") from e

        print(f"El agente del ticket a sido reasignado correctamente")
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.REASIGNAR_AGENTE,
            detalle=f"Ticket #{ticket.id}: agente {agente_anterior} -> {nuevo_agente_id}",
        )
        return ticket.agente_id
    @staticmethod
    def agregar_comentario(ticket_id,autor_id,texto):
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError("El ticket no a sido encontrado")
        
        if not texto.strip():
            raise ComentarioVacioError("El comentario no puede estar vacio")
        nuevo_comentario = Comentario(
            ticket_id = ticket_id,
            autor_id = autor_id,
            texto=texto
        )
        try:
            db.session.add(nuevo_comentario)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido agregar el comentario, error : {e}")
            raise ErrorPersistencia("No se pudo agregar el comentario") from e

        print(f"El comentario agregado correctamente")
        ServicioAuditoria.registrar(
            usuario_id=autor_id,
            accion=AccionAuditoria.AGREGAR_COMENTARIO,
            detalle=f"Se agrego un comentario al ticket #{ticket_id}",
        )
        return nuevo_comentario
    @staticmethod
    def listar_tickets_por_creador(usuario_id):
        tickets_del_usuario = Ticket.query.filter_by(creador_id=usuario_id).all()
        return sorted(tickets_del_usuario, key=lambda ticket: ticket.fecha_creacion, reverse=True)
        
    