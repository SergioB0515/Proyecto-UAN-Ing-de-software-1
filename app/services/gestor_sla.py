from flask_babel import gettext as _
from app.models.enum import Prioridad,NivelUsuario,EstadoTicket
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.exceptions import NoHayTickets
from app.extensions import db
from sqlalchemy import select
from datetime import datetime, timedelta
from app.services.notificaciones import ServicioNotificaciones
from app.services.disponibilidad import ServicioDisponibilidad
from app import notificaciones_i18n as notif
HORAS_SLA_NORMAL={
    Prioridad.ALTA : 4,
    Prioridad.MEDIA : 24,
    Prioridad.BAJA : 72 
}

# Fraccion del SLA que un ticket puede consumir sin dueño antes de que el
# sistema avise al administrador. 0.5 = la mitad del plazo.
UMBRAL_SIN_ASIGNAR = 0.5

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

        # Un ticket en espera tiene el reloj detenido: no vence mientras la
        # pelota este del lado del solicitante, asi que queda fuera de las dos
        # listas en vez de acumular tiempo que no es responsabilidad de soporte.
        query = select(Ticket).where(
            Ticket.estado.notin_([EstadoTicket.CERRADO, EstadoTicket.EN_ESPERA])
        )

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
    def segundos_en_pausa(ticket, ahora=None):
        """Segundos que el reloj de SLA de este ticket ha estado detenido.

        Suma las pausas ya cerradas (sla_segundos_pausados, que es tambien lo
        que se le sumo a fecha_limite) mas la pausa en curso si la hay.
        """
        acumulados = ticket.sla_segundos_pausados or 0
        if ticket.sla_pausado_desde is None:
            return float(acumulados)
        ahora = ahora or datetime.now()
        en_curso = (ahora - ticket.sla_pausado_desde).total_seconds()
        return float(acumulados) + max(0.0, en_curso)

    @staticmethod
    def consumo_sla(ticket, ahora=None):
        """Fraccion del plazo de SLA ya consumida por el ticket.

        0.0 recien creado, 1.0 justo al vencer, mayor que 1.0 si ya vencio.
        Devuelve None si al ticket le faltan fechas con que calcularlo.

        Las pausas no cuentan ni arriba ni abajo de la fraccion: del plazo
        total se descuentan las pausas que ya se le sumaron a fecha_limite, y
        del tiempo transcurrido se descuenta todo el tiempo en pausa. El
        resultado es que el porcentaje se congela mientras el ticket espera.
        """
        if ticket.fecha_limite is None or ticket.fecha_creacion is None:
            return None

        ahora = ahora or datetime.now()
        acumulados = float(ticket.sla_segundos_pausados or 0)
        segundos_totales = (ticket.fecha_limite - ticket.fecha_creacion).total_seconds() - acumulados

        if segundos_totales <= 0:
            return 1.0

        transcurrido = (ahora - ticket.fecha_creacion).total_seconds()
        transcurrido -= GestorSLA.segundos_en_pausa(ticket, ahora)
        return max(0.0, transcurrido) / segundos_totales

    @staticmethod
    def pausar_reloj(ticket, ahora=None):
        """Detiene el reloj de SLA. No hace commit: lo hace quien la llama.

        Idempotente: si ya estaba pausado no mueve la marca, para que dos
        pausas seguidas no borren el inicio real de la espera.
        """
        if ticket.sla_pausado_desde is not None:
            return 0.0
        ticket.sla_pausado_desde = ahora or datetime.now()
        return 0.0

    @staticmethod
    def reanudar_reloj(ticket, ahora=None):
        """Vuelve a poner en marcha el reloj y corre fecha_limite.

        El plazo se desplaza exactamente lo que duro la espera, de modo que el
        agente recupera el tiempo que estuvo esperando al solicitante y no
        hereda un ticket que vencio mientras no dependia de el. Devuelve los
        segundos que duro la pausa. No hace commit.
        """
        if ticket.sla_pausado_desde is None:
            return 0.0

        ahora = ahora or datetime.now()
        pausa = max(0.0, (ahora - ticket.sla_pausado_desde).total_seconds())
        ticket.sla_segundos_pausados = int((ticket.sla_segundos_pausados or 0) + pausa)
        if ticket.fecha_limite is not None:
            ticket.fecha_limite = ticket.fecha_limite + timedelta(seconds=pausa)
        ticket.sla_pausado_desde = None

        # El plazo se movio, asi que los avisos de SLA vuelven a armarse: si no,
        # un ticket que ya habia avisado de vencido nunca volveria a avisar.
        if ticket.fecha_limite is not None and ticket.fecha_limite > ahora:
            ticket.notificado_vencido = False
            consumo = GestorSLA.consumo_sla(ticket, ahora)
            if consumo is not None and consumo <= 0.80:
                ticket.notificado_proximo_vencer = False

        return pausa

    @staticmethod
    def clave_riesgo(ticket, ahora=None):
        """Clave de ordenamiento: primero lo mas cerca de vencer.

        Los cerrados van siempre al final. Entre dos tickets con el mismo
        consumo de SLA desempata la prioridad y luego el id, para que el orden
        sea estable entre recargas de la pagina.
        """
        from app.services.tickets import ORDEN_PRIORIDAD

        ahora = ahora or datetime.now()
        cerrado = 1 if ticket.estado == EstadoTicket.CERRADO else 0
        consumo = GestorSLA.consumo_sla(ticket, ahora)
        consumo_para_orden = consumo if consumo is not None else -1
        return (cerrado, -consumo_para_orden, ORDEN_PRIORIDAD[ticket.prioridad], ticket.id)

    @staticmethod
    def _avisar_area(ticket, plantilla_area):
        """Avisa de un ticket sin dueño a quien corresponda.

        Va a los agentes activos y disponibles del area del ticket. Si el area
        se quedo sin nadie disponible, el aviso sube al administrador: antes
        este caso no le llegaba a nadie, porque la notificacion de SLA solo se
        enviaba al agente asignado.

        Devuelve la cantidad de agentes del area que recibieron el aviso (0 si
        hubo que escalar al admin).
        """
        disponibles = ServicioDisponibilidad.agentes_disponibles(ticket.categoria)

        if disponibles:
            for agente in disponibles:
                ServicioNotificaciones.crear(
                    usuario_id=agente.id,
                    mensaje=plantilla_area,
                    ticket_id=ticket.id,
                )
            return len(disponibles)

        for admin in ServicioDisponibilidad.admins_activos():
            ServicioNotificaciones.crear(
                usuario_id=admin.id,
                mensaje=notif.AREA_SIN_COBERTURA,
                ticket_id=ticket.id,
            )
        return 0

    @staticmethod
    def _avisar_agente_o_area(ticket, plantilla_agente, plantilla_area):
        """Avisa al agente asignado, o al area si ese agente esta ausente.

        Cierra el hueco que quedo abierto en la 3.1: un ticket ya asignado a un
        agente que despues se declaro ausente seguia avisandole solo a el, que
        por definicion no esta leyendo. Ahora el aviso tambien llega al area y
        el ticket queda marcado como pendiente de cobertura.
        """
        agente = db.session.get(Usuario, ticket.agente_id) if ticket.agente_id else None

        if agente is not None:
            ServicioNotificaciones.crear(
                usuario_id=agente.id,
                mensaje=plantilla_agente,
                ticket_id=ticket.id,
            )
            if ServicioDisponibilidad.esta_disponible(agente) and agente.activo:
                return
            ticket.requiere_cobertura = True
            db.session.add(ticket)

        GestorSLA._avisar_area(ticket, plantilla_area)

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
                    GestorSLA._avisar_agente_o_area(
                        ticket, notif.SLA_PROXIMO_AGENTE, notif.SLA_PROXIMO_AREA
                    )
                else:
                    GestorSLA._avisar_area(ticket, notif.SLA_PROXIMO_AREA)
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
                    GestorSLA._avisar_agente_o_area(
                        ticket, notif.SLA_VENCIDO_AGENTE, notif.SLA_VENCIDO_AREA
                    )
                else:
                    GestorSLA._avisar_area(ticket, notif.SLA_VENCIDO_AREA)
                ticket.notificado_vencido = True
                db.session.add(ticket)
                from app.services.webhooks import ServicioWebhooks
                ServicioWebhooks.emitir(ServicioWebhooks.EVENTO_SLA_VENCIDO, ticket)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"error : {e}")

        GestorSLA.escalar_tickets_sin_asignar()

    @staticmethod
    def escalar_tickets_sin_asignar(umbral=None):
        """Avisa al administrador de los tickets que envejecen sin dueño.

        Un ticket que ya consumio UMBRAL_SIN_ASIGNAR de su plazo y sigue sin
        agente deja de ser un problema del area y pasa a ser uno de gestion:
        ahi si hace falta que una persona intervenga. El aviso se manda una
        sola vez por ticket (bandera notificado_sin_asignar), con el mismo
        patron de deduplicacion que ya usan las otras dos banderas de SLA.

        Devuelve la lista de tickets escalados en esta pasada.
        """
        umbral = UMBRAL_SIN_ASIGNAR if umbral is None else umbral
        ahora = datetime.now()

        candidatos = db.session.execute(
            select(Ticket).where(
                Ticket.estado.notin_([EstadoTicket.CERRADO, EstadoTicket.EN_ESPERA]),
                Ticket.agente_id.is_(None),
                Ticket.notificado_sin_asignar.is_(False),
            )
        ).scalars().all()

        admins = ServicioDisponibilidad.admins_activos()
        escalados = []

        for ticket in candidatos:
            consumo = GestorSLA.consumo_sla(ticket, ahora)
            if consumo is None or consumo < umbral:
                continue

            for admin in admins:
                ServicioNotificaciones.crear(
                    usuario_id=admin.id,
                    mensaje=notif.SIN_ASIGNAR_ENVEJECIDO,
                    ticket_id=ticket.id,
                )

            ticket.notificado_sin_asignar = True
            db.session.add(ticket)
            escalados.append(ticket)

        if escalados:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"No se pudo marcar el escalamiento de tickets sin asignar, error: {e}")
                return []

        return escalados
