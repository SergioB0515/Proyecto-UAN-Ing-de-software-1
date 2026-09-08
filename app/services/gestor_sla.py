from flask_babel import gettext as _
from app.models.enum import Prioridad,NivelUsuario,EstadoTicket
from app.models.ticket import Ticket
from app.services.exceptions import NoHayTickets
from app.extensions import db
from sqlalchemy import select
from datetime import datetime, timedelta
from app.services.notificaciones import ServicioNotificaciones
from app import notificaciones_i18n as notif
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
    def verificar_vencimientos(creador_id=None):
        tickets_vencidos = []
        tickets_proximos_a_vencer = []

        query = select(Ticket).where(Ticket.estado != EstadoTicket.CERRADO)

        if creador_id is not None:
            query = query.where(Ticket.creador_id == creador_id)

        tickets = db.session.execute(query).scalars().all()

        ahora = datetime.now()

        for ticket in tickets:
            if ticket.fecha_limite is None or ticket.fecha_creacion is None:
                continue

            tiempo_restante = ticket.fecha_limite - ahora

            if tiempo_restante.total_seconds() <= 0:
                tickets_vencidos.append(ticket)
                continue

            tiempo_total = ticket.fecha_limite - ticket.fecha_creacion
            segundos_totales = tiempo_total.total_seconds()

            if segundos_totales <= 0:

                tickets_proximos_a_vencer.append(ticket)
                continue

            porcentaje_restante = tiempo_restante.total_seconds() / segundos_totales
            if porcentaje_restante <= 0.20:
                tickets_proximos_a_vencer.append(ticket)

        return tickets_vencidos, tickets_proximos_a_vencer
    
    @staticmethod
    def verificar_y_notificar_vencimientos():
        vencidos, proximos = GestorSLA.verificar_vencimientos()

        for ticket in proximos:
            if not ticket.notificado_proximo_vencer:
                ServicioNotificaciones.crear(
                    usuario_id=ticket.creador_id,
                    mensaje=notif.SLA_PROXIMO_CREADOR,
                    ticket_id=ticket.id,
                )
                if ticket.agente_id is not None:
                    ServicioNotificaciones.crear(
                        usuario_id=ticket.agente_id,
                        mensaje=notif.SLA_PROXIMO_AGENTE,
                        ticket_id=ticket.id,
                    )
                ticket.notificado_proximo_vencer = True
                db.session.add(ticket)

        for ticket in vencidos:
            if not ticket.notificado_vencido:
                ServicioNotificaciones.crear(
                    usuario_id=ticket.creador_id,
                    mensaje=notif.SLA_VENCIDO_CREADOR,
                    ticket_id=ticket.id,
                )
                if ticket.agente_id is not None:
                    ServicioNotificaciones.crear(
                        usuario_id=ticket.agente_id,
                        mensaje=notif.SLA_VENCIDO_AGENTE,
                        ticket_id=ticket.id,
                    )
                ticket.notificado_vencido = True
                db.session.add(ticket)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"error : {e}")


