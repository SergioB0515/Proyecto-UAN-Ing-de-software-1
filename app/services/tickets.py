from flask_babel import gettext as _
from app.traducciones import etiqueta
from app.models.enum import Categoria,Prioridad,EstadoTicket,AccionAuditoria,RolUsuario
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.models.comentario import Comentario
from app.services.clasificador import ClasificadorTickets
from app.services.gestor_sla import GestorSLA
from app.services.exceptions import TransicionInvalidaError,AgenteYaAsignadoError,TicketNoEncontradoError,TicketNoEnProgresoError,ComentarioVacioError,ErrorPersistencia,ClasificacionYaConfirmadaError,PermisoDenegadoError,MotivoRequeridoError,CoberturaNoRequeridaError,AgenteDestinoInvalidoError
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
ORDEN_POR_PRIORIDAD = "prioridad"
ORDEN_POR_RIESGO = "riesgo"
ORDENES_VALIDOS = (ORDEN_POR_PRIORIDAD, ORDEN_POR_RIESGO)

ORDEN_PRIORIDAD={
    Prioridad.ALTA : 0,
    Prioridad.MEDIA : 1,
    Prioridad.BAJA : 2,
}
TRANSICIONES_VALIDAS={
    EstadoTicket.ABIERTO : [EstadoTicket.EN_PROGRESO,EstadoTicket.CERRADO],  
    EstadoTicket.EN_PROGRESO : [EstadoTicket.EN_ESPERA,EstadoTicket.CERRADO],
    EstadoTicket.EN_ESPERA : [EstadoTicket.EN_PROGRESO,EstadoTicket.CERRADO],
    EstadoTicket.CERRADO : [EstadoTicket.EN_PROGRESO]
}

# Estados en los que el ticket sigue vivo para soporte. Se usa para saber que
# tickets hay que cubrir cuando su agente se declara ausente.
ESTADOS_ABIERTOS = (EstadoTicket.ABIERTO, EstadoTicket.EN_PROGRESO, EstadoTicket.EN_ESPERA)
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
        from app.services.webhooks import ServicioWebhooks
        ServicioWebhooks.emitir(ServicioWebhooks.EVENTO_CREADO, nuevo_ticket)
        ServicioAuditoria.registrar(
            usuario_id=creador.id,
            accion=AccionAuditoria.CREAR_TICKET,
            detalle=_("Ticket #%(p1)s creado: categoria=%(p2)s, prioridad=%(p3)s", p1=nuevo_ticket.id, p2=etiqueta(nuevo_ticket.categoria), p3=etiqueta(nuevo_ticket.prioridad)),
        )
        return nuevo_ticket
    
    @staticmethod
    def listar_tickets_por_area(area, estado=None, prioridad=None, fecha_desde=None, fecha_hasta=None,
                                agente_id_propio=None, orden=ORDEN_POR_PRIORIDAD):
        """Tickets de un area, ordenados por prioridad o por riesgo de vencimiento.

        orden=ORDEN_POR_PRIORIDAD mantiene el orden historico (alta, media, baja).
        orden=ORDEN_POR_RIESGO pone primero lo que esta mas cerca de vencer, que es
        lo que el agente necesita ver cuando trabaja la cola: la prioridad sola
        esconde un ticket medio que vence en diez minutos detras de uno alto que
        acaba de entrar.
        """
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

        if orden == ORDEN_POR_RIESGO:
            ahora = datetime.now()
            return sorted(tickets_del_area, key=lambda ticket: GestorSLA.clave_riesgo(ticket, ahora))

        return sorted(tickets_del_area, key=lambda ticket: ORDEN_PRIORIDAD[ticket.prioridad])
        
    @staticmethod
    def cambiar_estado(ticket_id, nuevo_estado, actor_id, agente_id=None, motivo=None):
        
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar() 
       
        if not ticket:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
        
        if nuevo_estado not in TRANSICIONES_VALIDAS[ticket.estado]:
            raise TransicionInvalidaError(_("La transicion no es valida"))

        motivo = (motivo or "").strip()

        # Dejar un ticket en espera para el solicitante congela su SLA, asi que
        # tiene que quedar escrito por que: sin motivo seria una forma facil de
        # esconder un ticket que se esta venciendo.
        if nuevo_estado == EstadoTicket.EN_ESPERA and not motivo:
            raise MotivoRequeridoError(_("Debes indicar qué se le está pidiendo al solicitante"))

        if nuevo_estado == EstadoTicket.EN_PROGRESO:
       

            if agente_id is None and ticket.agente_id is None:
                raise TransicionInvalidaError(_("Se requiere un agente_id para pasar a EN_PROGRESO"))
       
            if agente_id is not None:
                ticket.agente_id = agente_id
                ticket.fecha_asignacion = datetime.now()
                ticket.notificado_sin_asignar = False
                ticket.requiere_cobertura = False
        
        estado_anterior=ticket.estado
        ticket.estado = nuevo_estado

        # El reloj de SLA se detiene al entrar en espera y se reanuda al salir,
        # sin importar si el ticket se reanuda o se cierra: asi fecha_limite
        # refleja siempre solo el tiempo que estuvo en manos de soporte.
        if nuevo_estado == EstadoTicket.EN_ESPERA:
            GestorSLA.pausar_reloj(ticket)
        elif estado_anterior == EstadoTicket.EN_ESPERA:
            GestorSLA.reanudar_reloj(ticket)

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
        detalle = _("Ticket #%(p1)s: %(p2)s -> %(p3)s", p1=ticket.id, p2=etiqueta(estado_anterior), p3=etiqueta(nuevo_estado))
        if motivo:
            detalle = f"{detalle} ({motivo})"
        if nuevo_estado == EstadoTicket.EN_ESPERA:
            accion = AccionAuditoria.PAUSAR_SLA
        elif estado_anterior == EstadoTicket.EN_ESPERA and nuevo_estado == EstadoTicket.EN_PROGRESO:
            accion = AccionAuditoria.REANUDAR_SLA
        else:
            accion = AccionAuditoria.CAMBIAR_ESTADO
        ServicioAuditoria.registrar(usuario_id=actor_id, accion=accion, detalle=detalle)

        if nuevo_estado == EstadoTicket.EN_ESPERA:
            ServicioNotificaciones.crear(
                usuario_id=ticket.creador_id, mensaje=notif.EN_ESPERA_CREADOR, ticket_id=ticket.id
            )

        from app.services.webhooks import ServicioWebhooks
        ServicioWebhooks.emitir(ServicioWebhooks.EVENTO_ESTADO, ticket, {
            "estado_anterior": estado_anterior.value,
            "motivo": motivo or None,
        })
        if nuevo_estado == EstadoTicket.CERRADO:
            ServicioWebhooks.emitir(ServicioWebhooks.EVENTO_CERRADO, ticket)
        
        if nuevo_estado == EstadoTicket.CERRADO:
            if estado_anterior == EstadoTicket.ABIERTO:
                plantilla = notif.CERRADO_SIN_ATENDER
            else:
                plantilla = notif.CERRADO
            ServicioNotificaciones.crear(usuario_id=ticket.creador_id, mensaje=plantilla, ticket_id=ticket.id)

        from app.services.seguimiento import ServicioSeguimiento
        for seguidor_id in ServicioSeguimiento.ids_seguidores(ticket.id) - {actor_id, ticket.creador_id}:
            ServicioNotificaciones.crear(usuario_id=seguidor_id, mensaje=notif.ACTIVIDAD_SEGUIDOR, ticket_id=ticket.id)
        
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
        ticket.fecha_asignacion = datetime.now()
        ticket.notificado_sin_asignar = False
        ticket.requiere_cobertura = False
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
        from app.services.webhooks import ServicioWebhooks
        ServicioWebhooks.emitir(ServicioWebhooks.EVENTO_ASIGNADO, ticket, {"agente_anterior_id": agente_anterior})
        return ticket.agente_id
    @staticmethod
    def agregar_comentario(ticket_id, autor_id, texto, interno=False, notificar=True):
        ticket =db.session.execute(select(Ticket).where(Ticket.id ==ticket_id)).scalar()
        if not ticket:
            raise TicketNoEncontradoError(_("El ticket no a sido encontrado"))
        
        if not texto or not texto.strip():
            raise ComentarioVacioError(_("El comentario no puede estar vacio"))
        if interno:
            autor = db.session.get(Usuario, autor_id)
            if autor is None or autor.rol not in (RolUsuario.AGENTE, RolUsuario.ADMIN):
                raise PermisoDenegadoError(_("Solo agentes y administradores pueden agregar notas internas"))
        nuevo_comentario = Comentario(
            ticket_id = ticket_id,
            autor_id = autor_id,
            texto=texto,
            interno=bool(interno),
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
            accion=AccionAuditoria.AGREGAR_NOTA_INTERNA if interno else AccionAuditoria.AGREGAR_COMENTARIO,
            detalle=(_("Se agrego una nota interna al ticket #%(p1)s", p1=ticket_id) if interno
                     else _("Se agrego un comentario al ticket #%(p1)s", p1=ticket_id)),
        )
        if notificar:
            ServicioTickets._notificar_comentario(ticket, autor_id, bool(interno))

        # Un ticket en espera vuelve a atencion solo que el solicitante
        # responda: si hubiera que reanudarlo a mano, el reloj seguiria
        # detenido mientras la respuesta ya esta ahi esperando al agente.
        if (ticket.estado == EstadoTicket.EN_ESPERA
                and not interno
                and autor_id == ticket.creador_id):
            ServicioTickets.reanudar_por_respuesta(ticket.id, autor_id)

        return nuevo_comentario

    @staticmethod
    def reanudar_por_respuesta(ticket_id, actor_id):
        """Saca de la espera un ticket cuyo solicitante acaba de responder.

        Reusa cambiar_estado para no tener dos caminos que muevan el reloj de
        SLA. Si la reanudacion falla, el comentario ya quedo guardado: se
        registra el fallo y el ticket se queda en espera, nunca se pierde el
        comentario por esto.
        """
        try:
            ServicioTickets.cambiar_estado(
                ticket_id=ticket_id,
                nuevo_estado=EstadoTicket.EN_PROGRESO,
                actor_id=actor_id,
            )
        except (TransicionInvalidaError, TicketNoEncontradoError, ErrorPersistencia) as e:
            print(f"No se pudo reanudar el ticket #{ticket_id} tras la respuesta del solicitante: {e}")
            return None

        ticket = db.session.get(Ticket, ticket_id)
        if ticket is not None and ticket.agente_id is not None and ticket.agente_id != actor_id:
            ServicioNotificaciones.crear(
                usuario_id=ticket.agente_id,
                mensaje=notif.ESPERA_REANUDADA_AGENTE,
                ticket_id=ticket.id,
            )
        return ticket

    @staticmethod
    def listar_pendientes_cobertura(area=None):
        """Tickets vivos marcados como pendientes de cobertura.

        Son los que quedaron en manos de un agente ausente o inactivo. Se
        ordenan por riesgo de vencimiento, que es el criterio con el que hay
        que repartirlos.
        """
        query = select(Ticket).where(
            Ticket.requiere_cobertura.is_(True),
            Ticket.estado.in_(ESTADOS_ABIERTOS),
        )
        if area is not None:
            query = query.where(Ticket.categoria == area)
        tickets = db.session.execute(query).scalars().all()
        ahora = datetime.now()
        return sorted(tickets, key=lambda t: GestorSLA.clave_riesgo(t, ahora))

    @staticmethod
    def tomar_cobertura(ticket_id, agente_id, actor_id=None):
        """Un agente se queda con un ticket que su dueño dejo sin cubrir.

        Es la contraparte del modelo pull para las ausencias: el sistema no
        reparte solo los tickets del agente ausente, pero cualquier agente
        disponible del area (o un administrador) puede tomarlos desde
        /admin/cobertura sin pasar por una solicitud de transferencia, que
        requeriria que el agente ausente la aceptara.
        """
        from app.services.disponibilidad import ServicioDisponibilidad

        actor_id = actor_id if actor_id is not None else agente_id
        ticket = db.session.get(Ticket, ticket_id)
        if ticket is None:
            raise TicketNoEncontradoError(_("El ticket no ha sido encontrado"))
        if not ticket.requiere_cobertura or ticket.estado not in ESTADOS_ABIERTOS:
            raise CoberturaNoRequeridaError(_("Este ticket no necesita cobertura"))

        nuevo = db.session.get(Usuario, agente_id)
        if nuevo is None or not nuevo.activo:
            raise AgenteDestinoInvalidoError(_("El agente destino no es válido"))
        if nuevo.rol not in (RolUsuario.AGENTE, RolUsuario.ADMIN):
            raise AgenteDestinoInvalidoError(_("El agente destino no es válido"))
        if nuevo.rol == RolUsuario.AGENTE:
            if nuevo.area_soporte != ticket.categoria:
                raise AgenteDestinoInvalidoError(_("El agente destino no pertenece al área del ticket"))
            if not ServicioDisponibilidad.esta_disponible(nuevo):
                raise AgenteDestinoInvalidoError(_("El agente destino está ausente"))
        if nuevo.id == ticket.agente_id:
            raise AgenteYaAsignadoError(_("Este ticket ya tiene asignado a este mismo agente"))

        agente_anterior = ticket.agente_id
        ticket.agente_id = nuevo.id
        ticket.fecha_asignacion = datetime.now()
        ticket.requiere_cobertura = False
        ticket.notificado_sin_asignar = False
        if ticket.estado == EstadoTicket.ABIERTO:
            ticket.estado = EstadoTicket.EN_PROGRESO

        try:
            db.session.add(ticket)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            try:
                db.session.refresh(ticket)
            except Exception:
                pass
            print(f"No se pudo tomar la cobertura del ticket, error: {e}")
            raise ErrorPersistencia(_("No se pudo tomar la cobertura del ticket")) from e

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.TOMAR_COBERTURA,
            detalle=_("Ticket #%(p1)s: cobertura tomada por %(p2)s (agente anterior %(p3)s)",
                      p1=ticket.id, p2=nuevo.email, p3=agente_anterior),
        )

        if agente_anterior is not None and agente_anterior != nuevo.id:
            ServicioNotificaciones.crear(
                usuario_id=agente_anterior, mensaje=notif.COBERTURA_TOMADA, ticket_id=ticket.id
            )

        from app.services.webhooks import ServicioWebhooks
        ServicioWebhooks.emitir(ServicioWebhooks.EVENTO_ASIGNADO, ticket, {
            "agente_anterior_id": agente_anterior,
            "motivo": "cobertura",
        })
        return ticket

    @staticmethod
    def _notificar_comentario(ticket, autor_id, interno):
        from app.services.seguimiento import ServicioSeguimiento

        avisados = {autor_id}
        if interno:
            if ticket.agente_id and ticket.agente_id not in avisados:
                ServicioNotificaciones.crear(usuario_id=ticket.agente_id, mensaje=notif.NOTA_INTERNA_NUEVA, ticket_id=ticket.id)
                avisados.add(ticket.agente_id)
        else:
            if autor_id != ticket.creador_id:
                ServicioNotificaciones.crear(usuario_id=ticket.creador_id, mensaje=notif.COMENTARIO_NUEVO_CREADOR, ticket_id=ticket.id)
                avisados.add(ticket.creador_id)
            elif ticket.agente_id:
                ServicioNotificaciones.crear(usuario_id=ticket.agente_id, mensaje=notif.COMENTARIO_NUEVO_AGENTE, ticket_id=ticket.id)
                avisados.add(ticket.agente_id)
        for seguidor_id in ServicioSeguimiento.ids_seguidores(ticket.id) - avisados:
            ServicioNotificaciones.crear(usuario_id=seguidor_id, mensaje=notif.ACTIVIDAD_SEGUIDOR, ticket_id=ticket.id)

    @staticmethod
    def listar_comentarios(ticket_id, incluir_internos=False):
        query = select(Comentario).where(Comentario.ticket_id == ticket_id)
        if not incluir_internos:
            query = query.where(Comentario.interno.is_(False))
        return db.session.execute(query.order_by(Comentario.fecha, Comentario.id)).scalars().all()

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


    