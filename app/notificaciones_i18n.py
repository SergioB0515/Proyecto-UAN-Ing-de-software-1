
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
        CLASIFICACION_PENDIENTE:_( "El ticket #%(id)s necesita revision de categoria", id=m)
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
