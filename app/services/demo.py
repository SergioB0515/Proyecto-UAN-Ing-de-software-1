from datetime import datetime, timedelta

from flask_babel import gettext as _
from sqlalchemy import select, delete

from app.extensions import db
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.models.notificacion import Notificacion
from app.models.enum import EstadoTicket
from app.services.notificaciones import ServicioNotificaciones
from app.services.gestor_sla import GestorSLA
from app.services.tickets import ServicioTickets
from app.services.exceptions import TicketNoEncontradoError
from app import notificaciones_i18n as notif


def plantillas_notificacion():
    return {
        nombre: valor
        for nombre, valor in vars(notif).items()
        if nombre.isupper() and isinstance(valor, str) and valor != notif.MARCADOR
    }


def plantillas_correo():
    return {
        nombre: valor
        for nombre, valor in plantillas_notificacion().items()
        if valor in ServicioNotificaciones.PLANTILLAS_CON_CORREO
    }


class ServicioDemo:

    @staticmethod
    def _obtener_ticket(ticket_id):
        if ticket_id:
            ticket = db.session.get(Ticket, ticket_id)
            if ticket is None:
                raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
            return ticket
        return db.session.execute(
            select(Ticket).order_by(Ticket.id.desc()).limit(1)
        ).scalar()

    @staticmethod
    def enviar_notificacion(usuario_id, nombre_plantilla, ticket_id=None):
        plantilla = plantillas_notificacion().get(nombre_plantilla)
        if plantilla is None:
            raise ValueError(_("Plantilla de notificación inválida"))
        ticket = ServicioDemo._obtener_ticket(ticket_id)
        ServicioNotificaciones.crear(
            usuario_id=usuario_id,
            mensaje=plantilla,
            ticket_id=ticket.id if ticket else None,
        )
        return {
            "ticket_id": ticket.id if ticket else None,
            "con_correo": plantilla in ServicioNotificaciones.PLANTILLAS_CON_CORREO,
        }

    @staticmethod
    def contexto_correo(nombre_plantilla, ticket_id=None):
        plantilla = plantillas_correo().get(nombre_plantilla)
        if plantilla is None:
            raise ValueError(_("Plantilla de correo inválida"))
        ticket = ServicioDemo._obtener_ticket(ticket_id)
        contexto = ServicioNotificaciones._contexto_correo(ticket) if ticket else None
        return plantilla, (ticket.id if ticket else None), contexto

    @staticmethod
    def previsualizar_correo(nombre_plantilla, ticket_id=None):
        plantilla, tid, contexto = ServicioDemo.contexto_correo(nombre_plantilla, ticket_id)
        return ServicioNotificaciones.construir_correo(plantilla, tid, contexto)

    @staticmethod
    def enviar_correo(destinatario, nombre_plantilla, ticket_id=None):
        plantilla, tid, contexto = ServicioDemo.contexto_correo(nombre_plantilla, ticket_id)
        ServicioNotificaciones.enviar_correo_sincrono(destinatario, plantilla, tid, contexto)
        return {"ticket_id": tid}

    @staticmethod
    def forzar_sla(ticket_id, modo):
        ticket = db.session.get(Ticket, ticket_id)
        if ticket is None:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
        if ticket.estado == EstadoTicket.CERRADO:
            raise ValueError(_("El ticket está cerrado; el SLA solo aplica a tickets abiertos o en progreso"))

        ahora = datetime.now()
        if modo == "vencido":
            ticket.fecha_limite = ahora - timedelta(minutes=5)
            ticket.notificado_vencido = False
        elif modo == "proximo":
            ticket.fecha_creacion = ahora - timedelta(hours=2)
            ticket.fecha_limite = ahora + timedelta(minutes=10)
            ticket.notificado_proximo_vencer = False
            ticket.notificado_vencido = False
        else:
            raise ValueError(_("Modo de SLA inválido"))

        db.session.commit()
        GestorSLA.verificar_y_notificar_vencimientos()
        return {"ticket_id": ticket.id, "tiene_agente": ticket.agente_id is not None}

    @staticmethod
    def ejecutar_verificacion_sla():
        vencidos, proximos = GestorSLA.verificar_vencimientos()
        GestorSLA.verificar_y_notificar_vencimientos()
        return {"vencidos": len(vencidos), "proximos": len(proximos)}

    @staticmethod
    def crear_ticket(creador_id, texto):
        creador = db.session.get(Usuario, creador_id)
        ticket = ServicioTickets.crear_ticket(creador=creador, texto=texto)
        return {
            "ticket_id": ticket.id,
            "categoria": ticket.categoria.value,
            "prioridad": ticket.prioridad.value,
            "baja_confianza": ticket.clasificacion_baja_confianza,
        }

    @staticmethod
    def borrar_notificaciones(usuario_id):
        resultado = db.session.execute(delete(Notificacion).where(Notificacion.usuario_id == usuario_id))
        db.session.commit()
        return {"borradas": resultado.rowcount}
