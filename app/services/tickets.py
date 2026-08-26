from app.Models.enum import Categoria,Prioridad,EstadoTicket
from app.Models.ticket import Ticket
from app.Models.comentario import Comentario
from app.services.clasificador import ClasificadorTickets
from app.services.gestor_sla import GestorSLA
from app.services.exceptions import TransicionInvalidaError,AgenteYaAsignadoError,TicketNoEncontradoError,TicketNoEnProgresoError,ComentarioVacioError
from app import db
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
            print(f"El ticket se ha resgistrado con exito")
            return True,nuevo_ticket
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido realizar el guardado u registro error : {e}")  
            return False,None
    @staticmethod
    def listar_tickets_por_area(area):
        tickets_del_area = Ticket.query.filter_by(categoria=area).all()
        return sorted(tickets_del_area, key=lambda ticket: ORDEN_PRIORIDAD[ticket.prioridad])
    @staticmethod
    def cambiar_estado(ticket_id, nuevo_estado, agente_id=None):
        
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar() 
       
        if not ticket:
            raise TicketNoEncontradoError("El ticket no a sido encontrado")
       
        if nuevo_estado not in TRANSICIONES_VALIDAS[ticket.estado]:
            raise TransicionInvalidaError("La transicion no es valida")
       
        if nuevo_estado == EstadoTicket.EN_PROGRESO:
       
            if agente_id is not None and ticket.agente_id is not None and agente_id != ticket.agente_id:
                raise AgenteYaAsignadoError("Este ticket ya tiene un agente asignado")        
       
            if agente_id is None and ticket.agente_id is None:
                raise TransicionInvalidaError("Se requiere un agente_id para pasar a EN_PROGRESO")
       
            if agente_id is not None:
                ticket.agente_id = agente_id
       
        ticket.estado = nuevo_estado
       
        try:
            db.session.add(ticket)
            db.session.commit()
            print(f"El estado del Ticket a sido cambiado con exito")
            return True,ticket.estado
       
        except Exception as e:
            db.session.rollback()
            db.session.refresh(ticket)
            print(f"No se ha podido realizar el guardado u registro error : {e}")  
            return False,None
    @staticmethod
    def reasignar_agente(ticket_id, nuevo_agente_id):
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError("El ticket no a sido encontrado")
        
        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError("Este ticket no esta en un estado valido para su reasignacion")
        if nuevo_agente_id == ticket.agente_id:
            raise AgenteYaAsignadoError("Este ticket ya tiene asignado a este mismo agente")
        
        ticket.agente_id = nuevo_agente_id
        try:
            db.session.add(ticket)
            db.session.commit()
            print(f"El agente del ticket a sido reasignado correctamente")
            return True,ticket.agente_id
       
        except Exception as e:
            db.session.rollback()
            db.session.refresh(ticket)
            print(f"No se ha podido realizar la reasignacion error : {e}")  
            return False,None
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
            print(f"El comentario agregado correctamente")
            return True,nuevo_comentario
       
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido agregar el comentario : {e}")  
            return False,None
        
        
    