from enum import Enum

class Categoria(str, Enum):
    INFRAESTRUCTURA = "infraestructura"
    REDES = "redes"
    PERMISOS = "permisos"
    CUENTAS_CONTRASENAS = "cuentas_contrasenas"
    SEGURIDAD = "seguridad"
    SOFTWARE = "software"
    OTROS = "otros"

class RolUsuario(str, Enum):
    FINAL = "final"
    AGENTE = "agente"
    ADMIN = "admin"

class NivelUsuario(str, Enum):
    NORMAL = "normal"
    VIP = "vip"

class Prioridad(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"

class EstadoTicket(str, Enum):
    ABIERTO = "abierto"
    EN_PROGRESO = "en_progreso"
    CERRADO = "cerrado"
    
    
class AccionAuditoria(str, Enum):
    CREAR_TICKET = "crear_ticket"
    CAMBIAR_ESTADO = "cambiar_estado"
    REASIGNAR_AGENTE = "reasignar_agente"
    AGREGAR_COMENTARIO = "agregar_comentario"
    LOGIN_EXITOSO = "login_exitoso"
    LOGIN_FALLIDO = "login_fallido"
    CUENTA_BLOQUEADA = "cuenta_bloqueada"
    DESBLOQUEO_USUARIO = "desbloqueo_usuario"
    REGISTRO_EXITOSO ="registro_exitoso"
    CAMBIO_CONTRASENA ="cambio_contrasena"
    CAMBIO_NOMBRE = "cambio_nombre"
    SOLICITAR_TRANSFERENCIA = "solicitar_transferencia"
    ACEPTAR_TRANSFERENCIA = "aceptar_transferencia"
    RECHAZAR_TRANSFERENCIA = "rechazar_transferencia"
    CANCELAR_TRANSFERENCIA = "cancelar_transferencia"
    ESCALAR_AREA = "escalar_area"
    APROBAR_ESCALAMIENTO = "aprobar_escalamiento"
    RECHAZAR_ESCALAMIENTO = "rechazar_escalamiento"
    CAMBIAR_PRIORIDAD = "cambiar_prioridad"
    APROBAR_CAMBIO_PRIORIDAD = "aprobar_cambio_prioridad"
    RECHAZAR_CAMBIO_PRIORIDAD = "rechazar_cambio_prioridad"
    CONFIRMAR_CLASIFICACION = "confirmar_clasificacion"
    CREAR_PALABRA_CLAVE = "crear_palabra_clave"
    EDITAR_PALABRA_CLAVE = "editar_palabra_clave"
    DESACTIVAR_PALABRA_CLAVE = "desactivar_palabra_clave"
    REACTIVAR_PALABRA_CLAVE = "reactivar_palabra_clave"
    SOLICITAR_APELACION = "solicitar_apelacion"
    ACEPTAR_APELACION = "aceptar_apelacion"
    RECHAZAR_APELACION = "rechazar_apelacion"
    
class EstadoSolicitudTransferencia(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    CANCELADA = "cancelada"

class TipoSolicitud(str, Enum):
    REASIGNACION = "reasignacion"
    ESCALAMIENTO = "escalamiento"
    CAMBIO_PRIORIDAD = "cambio_prioridad"

class EstadoApelacion(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
