from app.Models.enum import Prioridad,NivelUsuario
from datetime import datetime, timedelta
HORAS_SLA_NORMAL={
    Prioridad.ALTA : 4,
    Prioridad.MEDIA : 24,
    Prioridad.BAJA : 72 
}

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
