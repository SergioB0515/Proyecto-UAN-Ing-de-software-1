
from flask_babel import gettext, force_locale

MARCADOR = "%(id)s"


CERRADO_SIN_ATENDER = (
    "Tu ticket #%(id)s fue cerrado directamente sin haber sido atendido — "
    "revisa los comentarios para ver el motivo"
)
CERRADO = "Tu ticket #%(id)s fue cerrado"
TRANSFERENCIA_NUEVA = "Nueva solicitud de transferencia para el ticket #%(id)s"
TRANSFERENCIA_ACEPTADA = "Tu solicitud de transferencia del ticket #%(id)s fue aceptada"
TRANSFERENCIA_RECHAZADA = "Tu solicitud de transferencia del ticket #%(id)s fue rechazada"
ESCALAMIENTO_PENDIENTE = "Nuevo escalamiento pendiente de aprobar: ticket #%(id)s"
ESCALAMIENTO_APROBADO = "Tu escalamiento del ticket #%(id)s fue aprobado"
ESCALAMIENTO_RECHAZADO = "Tu escalamiento del ticket #%(id)s fue rechazado"
PRIORIDAD_PENDIENTE = "Nuevo cambio de prioridad pendiente de aprobar: ticket #%(id)s"
PRIORIDAD_APROBADO = "Tu cambio de prioridad del ticket #%(id)s fue aprobado"
PRIORIDAD_RECHAZADO = "Tu cambio de prioridad del ticket #%(id)s fue rechazado"
SLA_PROXIMO_CREADOR = "Tu ticket #%(id)s está próximo a vencer"
SLA_PROXIMO_AGENTE = "El ticket #%(id)s que tienes asignado está próximo a vencer"
SLA_VENCIDO_CREADOR = "Tu ticket #%(id)s está vencido"
SLA_VENCIDO_AGENTE = "El ticket #%(id)s que tienes asignado está vencido"
CLASIFICACION_PENDIENTE = "El ticket #%(id)s necesita revision de categoria"
APELACION_NUEVA = "Nueva apelación pendiente de revisar: ticket #%(id)s"
APELACION_ACEPTADA = "Tu apelación del ticket #%(id)s fue aceptada, el ticket se reabrió"
APELACION_RECHAZADA = "Tu apelación del ticket #%(id)s fue rechazada"
COMENTARIO_NUEVO_CREADOR = "Hay una nueva respuesta en tu ticket #%(id)s"
COMENTARIO_NUEVO_AGENTE = "El solicitante respondió en el ticket #%(id)s"
ACTIVIDAD_SEGUIDOR = "Nueva actividad en el ticket #%(id)s que sigues"
NOTA_INTERNA_NUEVA = "Nueva nota interna en el ticket #%(id)s"
ENCUESTA_RECIBIDA = "Recibiste una calificación de satisfacción en el ticket #%(id)s"
SLA_PROXIMO_AREA = "El ticket #%(id)s de tu área está próximo a vencer y nadie lo ha tomado"
SLA_VENCIDO_AREA = "El ticket #%(id)s de tu área está vencido y nadie lo ha tomado"
AREA_SIN_COBERTURA = "El ticket #%(id)s está por vencer y su área no tiene agentes disponibles"
SIN_ASIGNAR_ENVEJECIDO = "El ticket #%(id)s lleva demasiado tiempo sin agente asignado"
EN_ESPERA_CREADOR = "Tu ticket #%(id)s quedó en espera de tu respuesta"
ESPERA_REANUDADA_AGENTE = "El solicitante respondió el ticket #%(id)s y volvió a atención"
COBERTURA_REQUERIDA = "El ticket #%(id)s se quedó sin agente disponible y necesita cobertura"
COBERTURA_TOMADA = "Otro agente tomó la cobertura del ticket #%(id)s que tenías asignado"


def _catalogo_traducido():
    
    _ = gettext
    m = MARCADOR
    return {
        CERRADO_SIN_ATENDER: _(
            "Tu ticket #%(id)s fue cerrado directamente sin haber sido atendido — "
            "revisa los comentarios para ver el motivo", id=m),
        CERRADO: _("Tu ticket #%(id)s fue cerrado", id=m),
        TRANSFERENCIA_NUEVA: _("Nueva solicitud de transferencia para el ticket #%(id)s", id=m),
        TRANSFERENCIA_ACEPTADA: _("Tu solicitud de transferencia del ticket #%(id)s fue aceptada", id=m),
        TRANSFERENCIA_RECHAZADA: _("Tu solicitud de transferencia del ticket #%(id)s fue rechazada", id=m),
        ESCALAMIENTO_PENDIENTE: _("Nuevo escalamiento pendiente de aprobar: ticket #%(id)s", id=m),
        ESCALAMIENTO_APROBADO: _("Tu escalamiento del ticket #%(id)s fue aprobado", id=m),
        ESCALAMIENTO_RECHAZADO: _("Tu escalamiento del ticket #%(id)s fue rechazado", id=m),
        PRIORIDAD_PENDIENTE: _("Nuevo cambio de prioridad pendiente de aprobar: ticket #%(id)s", id=m),
        PRIORIDAD_APROBADO: _("Tu cambio de prioridad del ticket #%(id)s fue aprobado", id=m),
        PRIORIDAD_RECHAZADO: _("Tu cambio de prioridad del ticket #%(id)s fue rechazado", id=m),
        SLA_PROXIMO_CREADOR: _("Tu ticket #%(id)s está próximo a vencer", id=m),
        SLA_PROXIMO_AGENTE: _("El ticket #%(id)s que tienes asignado está próximo a vencer", id=m),
        SLA_VENCIDO_CREADOR: _("Tu ticket #%(id)s está vencido", id=m),
        SLA_VENCIDO_AGENTE: _("El ticket #%(id)s que tienes asignado está vencido", id=m),
        CLASIFICACION_PENDIENTE: _("El ticket #%(id)s necesita revision de categoria", id=m),
        APELACION_NUEVA: _("Nueva apelación pendiente de revisar: ticket #%(id)s", id=m),
        APELACION_ACEPTADA: _("Tu apelación del ticket #%(id)s fue aceptada, el ticket se reabrió", id=m),
        APELACION_RECHAZADA: _("Tu apelación del ticket #%(id)s fue rechazada", id=m),
        COMENTARIO_NUEVO_CREADOR: _("Hay una nueva respuesta en tu ticket #%(id)s", id=m),
        COMENTARIO_NUEVO_AGENTE: _("El solicitante respondió en el ticket #%(id)s", id=m),
        ACTIVIDAD_SEGUIDOR: _("Nueva actividad en el ticket #%(id)s que sigues", id=m),
        NOTA_INTERNA_NUEVA: _("Nueva nota interna en el ticket #%(id)s", id=m),
        ENCUESTA_RECIBIDA: _("Recibiste una calificación de satisfacción en el ticket #%(id)s", id=m),
        SLA_PROXIMO_AREA: _("El ticket #%(id)s de tu área está próximo a vencer y nadie lo ha tomado", id=m),
        SLA_VENCIDO_AREA: _("El ticket #%(id)s de tu área está vencido y nadie lo ha tomado", id=m),
        AREA_SIN_COBERTURA: _("El ticket #%(id)s está por vencer y su área no tiene agentes disponibles", id=m),
        SIN_ASIGNAR_ENVEJECIDO: _("El ticket #%(id)s lleva demasiado tiempo sin agente asignado", id=m),
        EN_ESPERA_CREADOR: _("Tu ticket #%(id)s quedó en espera de tu respuesta", id=m),
        ESPERA_REANUDADA_AGENTE: _("El solicitante respondió el ticket #%(id)s y volvió a atención", id=m),
        COBERTURA_REQUERIDA: _("El ticket #%(id)s se quedó sin agente disponible y necesita cobertura", id=m),
        COBERTURA_TOMADA: _("Otro agente tomó la cobertura del ticket #%(id)s que tenías asignado", id=m),
    }


def render(plantilla, ticket_id, locale=None):

    datos = {"id": "" if ticket_id is None else ticket_id}

    def _hacer():
        traducida = _catalogo_traducido().get(plantilla)
        base = traducida if traducida is not None else plantilla
        try:
            return base % datos
        except (KeyError, ValueError, TypeError):
            return base

    if locale:
        with force_locale(locale):
            return _hacer()
    return _hacer()


def catalogo_cliente():
    
    return _catalogo_traducido()
