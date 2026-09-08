
from flask_babel import gettext as _


def _mapa_etiquetas():

    return {
        "infraestructura": _("Infraestructura"),
        "redes": _("Redes"),
        "permisos": _("Permisos"),
        "cuentas_contrasenas": _("Cuentas y contraseñas"),
        "seguridad": _("Seguridad"),
        "software": _("Software"),
        "otros": _("Otros"),
        "final": _("Usuario final"),
        "agente": _("Agente"),
        "admin": _("Admin"),
        "normal": _("Normal"),
        "vip": "VIP",
        "alta": _("Alta"),
        "media": _("Media"),
        "baja": _("Baja"),
        "abierto": _("Abierto"),
        "en_progreso": _("En progreso"),
        "cerrado": _("Cerrado"),
        "pendiente": _("Pendiente"),
        "aceptada": _("Aceptada"),
        "rechazada": _("Rechazada"),
        "cancelada": _("Cancelada"),
        "reasignacion": _("Reasignación"),
        "escalamiento": _("Escalamiento"),
        "cambio_prioridad": _("Cambio de prioridad"),
        "crear_ticket": _("Crear ticket"),
        "cambiar_estado": _("Cambiar estado"),
        "reasignar_agente": _("Reasignar agente"),
        "agregar_comentario": _("Agregar comentario"),
        "login_exitoso": _("Login exitoso"),
        "login_fallido": _("Login fallido"),
        "cuenta_bloqueada": _("Cuenta bloqueada"),
        "desbloqueo_usuario": _("Desbloqueo usuario"),
        "registro_exitoso": _("Registro exitoso"),
        "cambio_contrasena": _("Cambio de contraseña"),
        "cambio_nombre": _("Cambio de nombre"),
        "solicitar_transferencia": _("Solicitar transferencia"),
        "aceptar_transferencia": _("Aceptar transferencia"),
        "rechazar_transferencia": _("Rechazar transferencia"),
        "cancelar_transferencia": _("Cancelar transferencia"),
        "escalar_area": _("Escalar área"),
        "aprobar_escalamiento": _("Aprobar escalamiento"),
        "rechazar_escalamiento": _("Rechazar escalamiento"),
        "cambiar_prioridad": _("Cambiar prioridad"),
        "aprobar_cambio_prioridad": _("Aprobar cambio de prioridad"),
        "rechazar_cambio_prioridad": _("Rechazar cambio de prioridad"),
    }


def formato_fecha(valor, con_hora=True):

    if valor is None:
        return "—"
    if not hasattr(valor, "strftime"):
        return valor
    return valor.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")


def etiqueta(valor):

    if valor is None:
        return ""
    if hasattr(valor, "value"):
        valor = valor.value
    clave = str(valor).lower()
    return _mapa_etiquetas().get(clave, valor)
