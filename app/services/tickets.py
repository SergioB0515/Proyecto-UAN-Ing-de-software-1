from flask_babel import gettext as _
from app.traducciones import etiqueta
from app.models.enum import Categoria,Prioridad,EstadoTicket,AccionAuditoria,RolUsuario
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.models.comentario import Comentario
from app.services.clasificador import ClasificadorTickets
from app.services.gestor_sla import GestorSLA
from app.services.exceptions import TransicionInvalidaError,AgenteYaAsignadoError,TicketNoEncontradoError,TicketNoEnProgresoError,ComentarioVacioError,ErrorPersistencia,ClasificacionYaConfirmadaError
from app.extensions import db
from datetime import datetime,timedelta
from app.services.auditoria import ServicioAuditoria
from app.services.notificaciones import ServicioNotificaciones
from app import notificaciones_i18n as notif
from sqlalchemy import select, func,or_,and_
from app.services.clasificacion_avanzada import clasificar_ticket
from app.models.correccion_clasificacion import CorreccionClasificacion

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
        categoria, baja_confianza = clasificar_ticket(texto)
        prioridad_base = PRIORIDAD_BASE_POR_CATEGORIA[categoria]
        prioridad_final =GestorSLA.ajustar_prioridad_por_nivel(prioridad_base,creador.nivel)
        fecha_limite = GestorSLA.calcular_fecha_limite(prioridad_final,creador.nivel)
        nuevo_ticket = Ticket(
            texto=texto,
            categoria=categoria, 
            prioridad=prioridad_final,
            creador_id = creador.id,
            estado=EstadoTicket.ABIERTO,
            fecha_limite=fecha_limite,
            clasificacion_baja_confianza=baja_confianza
        )

        try:
            db.session.add(nuevo_ticket)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido crear el ticket, error : {e}")
            raise ErrorPersistencia(_("No se pudo crear el ticket")) from e
        
        if baja_confianza is True:
            admins = db.session.execute(select(Usuario).where(Usuario.rol == RolUsuario.ADMIN)).scalars().all()
            for admin in admins:
                ServicioNotificaciones.crear(
                    usuario_id=admin.id,
                    mensaje=notif.CLASIFICACION_PENDIENTE,
                    ticket_id=nuevo_ticket.id,
                )
                
        print(f"El ticket se ha resgistrado con exito")
        ServicioAuditoria.registrar(
            usuario_id=creador.id,
            accion=AccionAuditoria.CREAR_TICKET,
            detalle=_("Ticket #%(p1)s creado: categoria=%(p2)s, prioridad=%(p3)s", p1=nuevo_ticket.id, p2=etiqueta(nuevo_ticket.categoria), p3=etiqueta(nuevo_ticket.prioridad)),
        )
        return nuevo_ticket
    
    @staticmethod
    def listar_tickets_por_area(area, estado=None, prioridad=None, fecha_desde=None, fecha_hasta=None, agente_id_propio=None):
        query = select(Ticket).where(Ticket.categoria == area)

        if estado is not None:
            query = query.where(Ticket.estado == estado)

        if prioridad is not None:
            query = query.where(Ticket.prioridad == prioridad)

        if fecha_desde is not None:
            query = query.where(Ticket.fecha_creacion >= fecha_desde)

        if fecha_hasta is not None:
            query = query.where(Ticket.fecha_creacion < fecha_hasta)

        if agente_id_propio is not None:
            query = query.where(or_(Ticket.agente_id.is_(None), Ticket.agente_id == agente_id_propio))

        tickets_del_area = db.session.execute(query).scalars().all()

        return sorted(tickets_del_area, key=lambda ticket: ORDEN_PRIORIDAD[ticket.prioridad])
        
    @staticmethod
    def cambiar_estado(ticket_id, nuevo_estado, actor_id, agente_id=None):
        
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar() 
       
        if not ticket:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
        
        if nuevo_estado not in TRANSICIONES_VALIDAS[ticket.estado]:
            raise TransicionInvalidaError(_("La transicion no es valida"))
       
        if nuevo_estado == EstadoTicket.EN_PROGRESO:
       

            if agente_id is None and ticket.agente_id is None:
                raise TransicionInvalidaError(_("Se requiere un agente_id para pasar a EN_PROGRESO"))
       
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
            raise ErrorPersistencia(_("No se pudo cambiar el estado del ticket")) from e

        print(f"El estado del Ticket a sido cambiado con exito")
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.CAMBIAR_ESTADO,
            detalle=_("Ticket #%(p1)s: %(p2)s -> %(p3)s", p1=ticket.id, p2=etiqueta(estado_anterior), p3=etiqueta(nuevo_estado)),
        )
        
        if nuevo_estado == EstadoTicket.CERRADO:
            if estado_anterior == EstadoTicket.ABIERTO:
                plantilla = notif.CERRADO_SIN_ATENDER
            else:
                plantilla = notif.CERRADO
            ServicioNotificaciones.crear(usuario_id=ticket.creador_id, mensaje=plantilla, ticket_id=ticket.id)
        
        return ticket.estado


    @staticmethod
    def reasignar_agente(ticket_id, nuevo_agente_id, actor_id):
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
        
        if ticket.estado != EstadoTicket.EN_PROGRESO:
            raise TicketNoEnProgresoError(_("Este ticket no esta en un estado valido para su reasignacion"))
        if nuevo_agente_id == ticket.agente_id:
            raise AgenteYaAsignadoError(_("Este ticket ya tiene asignado a este mismo agente"))
        agente_anterior=ticket.agente_id
        ticket.agente_id = nuevo_agente_id
        try:
            db.session.add(ticket)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido realizar la reasignacion, error : {e}")
            raise ErrorPersistencia(_("No se pudo reasignar el agente")) from e

        print(f"El agente del ticket a sido reasignado correctamente")
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.REASIGNAR_AGENTE,
            detalle=_("Ticket #%(p1)s: agente %(p2)s -> %(p3)s", p1=ticket.id, p2=agente_anterior, p3=nuevo_agente_id),
        )
        return ticket.agente_id
    @staticmethod
    def agregar_comentario(ticket_id,autor_id,texto):
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
        
        if not texto.strip():
            raise ComentarioVacioError(_("El comentario no puede estar vacio"))
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
            raise ErrorPersistencia(_("No se pudo agregar el comentario")) from e

        print(f"El comentario agregado correctamente")
        ServicioAuditoria.registrar(
            usuario_id=autor_id,
            accion=AccionAuditoria.AGREGAR_COMENTARIO,
            detalle=_("Se agrego un comentario al ticket #%(p1)s", p1=ticket_id),
        )
        return nuevo_comentario
    @staticmethod
    def listar_tickets_por_creador(usuario_id):
        tickets_del_usuario = Ticket.query.filter_by(creador_id=usuario_id).all()
        return sorted(tickets_del_usuario, key=lambda ticket: ticket.fecha_creacion, reverse=True)
        
    @staticmethod
    def obtener_estadisticas_personales(usuario):

        tickets_creados = db.session.execute(select(func.count()).select_from(Ticket).where(Ticket.creador_id ==usuario.id)).scalar()

        estadisticas = {
            "tickets_creados": tickets_creados,
        }

        if usuario.rol == RolUsuario.AGENTE:
            tickets_tomados = db.session.execute(select(func.count()).select_from(Ticket).where(Ticket.agente_id==usuario.id)).scalar()
            tickets_cerrados = db.session.execute(select(func.count()).select_from(Ticket).where(Ticket.agente_id==usuario.id, Ticket.estado ==EstadoTicket.CERRADO)).scalar()
            estadisticas["tickets_tomados"] = tickets_tomados
            estadisticas["tickets_cerrados"] = tickets_cerrados

        return estadisticas
    
    @staticmethod
    def listar_admin(estado=None, categoria=None, prioridad=None, vista=None, pagina=1, por_pagina=35, sin_paginar=False):
        if vista == "vencidos_actuales":
            vencidos, _ = GestorSLA.verificar_vencimientos()
            return vencidos, None

        if vista == "proximos_actuales":
            _, proximos = GestorSLA.verificar_vencimientos()
            return proximos, None

        if vista == "vencidos_30_dias":
            hace_30_dias = datetime.now() - timedelta(days=30)
            query = select(Ticket).where(
                Ticket.fecha_limite >= hace_30_dias,
                Ticket.fecha_limite < datetime.now(),
                or_(
                    and_(Ticket.fecha_cierre.isnot(None), Ticket.fecha_cierre > Ticket.fecha_limite),
                    Ticket.fecha_cierre.is_(None),
                )
            )
            if sin_paginar:
                return db.session.execute(query).scalars().all(), None
            paginado = db.paginate(query, page=pagina, per_page=por_pagina)
            return paginado.items, paginado

        query = select(Ticket)
        if estado is not None:
            query = query.where(Ticket.estado == estado)
        if categoria is not None:
            query = query.where(Ticket.categoria == categoria)
        if prioridad is not None:
            query = query.where(Ticket.prioridad == prioridad)

        if sin_paginar:
            return db.session.execute(query).scalars().all(), None
        paginado = db.paginate(query, page=pagina, per_page=por_pagina)
        return paginado.items, paginado
    
    @staticmethod
    def confirmar_clasificacion(ticket_id, categoria_nueva, actor_id):

        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError(_("El ticket no ha sido encontrado"))

        if not ticket.clasificacion_baja_confianza:
            raise ClasificacionYaConfirmadaError(_("Este ticket ya tiene confirmada su categoría"))
        
        categoria_original = ticket.categoria
        ticket.categoria = categoria_nueva
        ticket.clasificacion_baja_confianza = False
        
        correccion = CorreccionClasificacion(
             ticket_id=ticket.id,
             texto=ticket.texto,
             categoria_original=categoria_original,
             categoria_correcta=categoria_nueva,
             actor_id=actor_id,
         )
        db.session.add(correccion)

        


        try:
            db.session.add(ticket)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido confirmar la clasificacion, error : {e}")
            raise ErrorPersistencia(_("No se pudo confirmar la clasificación")) from e

        print(f"Clasificacion del ticket #{ticket.id} confirmada correctamente")
        ServicioAuditoria.registrar(
                        usuario_id=actor_id,
                        accion=AccionAuditoria.CONFIRMAR_CLASIFICACION,
                        detalle=f"Ticket #{ticket.id}: categoria confirmada manualmente como {categoria_nueva.value}",
                    )
        return ticket


    @staticmethod
    def listar_pendientes_revision_clasificacion():

        query = select(Ticket).where(Ticket.clasificacion_baja_confianza == True).order_by(Ticket.fecha_creacion)
        return db.session.execute(query).scalars().all()


    