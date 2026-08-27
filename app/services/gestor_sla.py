from app.Models.enum import Prioridad,NivelUsuario,EstadoTicket
from app.Models.ticket import Ticket
from app.services.exceptions import NoHayTickets
from app import db
from sqlalchemy import select
from datetime import datetime, timedelta
HORAS_SLA_NORMAL={
    Prioridad.ALTA : 4,
    Prioridad.MEDIA : 24,
    Prioridad.BAJA : 72 
}

HORAS_SLA_VIP={
    Prioridad.ALTA : 1.5,
    Prioridad.MEDIA : 4.5,
    Prioridad.BAJA : 10.5
}    
    
class GestorSLA:
    @staticmethod
    def calcular_fecha_limite(prioridad, nivel_usuario):
        if nivel_usuario==NivelUsuario.VIP:
            tabla_horas = HORAS_SLA_VIP
            horas = tabla_horas[prioridad]
            return datetime.now() + timedelta(hours=horas)
        else:
            tabla_horas = HORAS_SLA_NORMAL
            horas = tabla_horas[prioridad]
            return datetime.now() + timedelta(hours=horas)
    @staticmethod
    def ajustar_prioridad_por_nivel(prioridad_base, nivel_usuario):
        if nivel_usuario == NivelUsuario.VIP:
            return Prioridad.ALTA
        else:
            return prioridad_base           
    @staticmethod
    def verificar_vencimientos():
        tickets_vencidos=[]
        tickets_proximos_a_vencer=[]
        tickets=db.session.execute(select(Ticket).where(Ticket.estado !=EstadoTicket.CERRADO)).scalars().all()

        for ticket in tickets:
            tiempo_total = ticket.fecha_limite - ticket.fecha_creacion
            tiempo_restante = ticket.fecha_limite - datetime.now()
            porcentaje_restante = tiempo_restante/tiempo_total
            
            if tiempo_restante.total_seconds() <= 0:
                tickets_vencidos.append(ticket)
                
            elif porcentaje_restante <= 0.20 :
                tickets_proximos_a_vencer.append(ticket)
        return tickets_vencidos,tickets_proximos_a_vencer
