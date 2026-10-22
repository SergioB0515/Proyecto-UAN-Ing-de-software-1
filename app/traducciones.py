
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
        "activar_2fa": _("Activar verificación en dos pasos"),
        "desactivar_2fa": _("Desactivar verificación en dos pasos"),
        "verificacion_2fa_fallida": _("Verificación en dos pasos fallida"),
        "uso_codigo_respaldo": _("Uso de código de respaldo"),
        "regenerar_codigos_respaldo": _("Regenerar códigos de respaldo"),
        "solicitar_recuperacion": _("Solicitud de recuperación de contraseña"),
        "restablecer_contrasena": _("Restablecer contraseña"),
        "editar_usuario": _("Editar usuario"),
        "desactivar_usuario": _("Desactivar usuario"),
        "reactivar_usuario": _("Reactivar usuario"),
        "restablecer_2fa_admin": _("Restablecer verificación en dos pasos (admin)"),
        "crear_articulo": _("Crear artículo"),
        "editar_articulo": _("Editar artículo"),
        "publicar_articulo": _("Publicar artículo"),
        "archivar_articulo": _("Archivar artículo"),
        "subir_adjunto": _("Subir adjunto"),
        "eliminar_adjunto": _("Eliminar adjunto"),
        "agregar_nota_interna": _("Agregar nota interna"),
        "crear_respuesta_predefinida": _("Crear respuesta rápida"),
        "editar_respuesta_predefinida": _("Editar respuesta rápida"),
        "eliminar_respuesta_predefinida": _("Eliminar respuesta rápida"),
        "responder_encuesta": _("Responder encuesta"),
        "crear_token_api": _("Crear token de API"),
        "revocar_token_api": _("Revocar token de API"),
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
