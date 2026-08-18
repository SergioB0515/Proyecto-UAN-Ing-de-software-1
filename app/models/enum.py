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