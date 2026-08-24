from app.Models.enum import Categoria,Prioridad,EstadoTicket
from app.Models.ticket import Ticket
from app.services.clasificador import ClasificadorTickets
from app.services.gestor_sla import GestorSLA
from app import db
PRIORIDAD_BASE_POR_CATEGORIA={
    Categoria.SEGURIDAD : Prioridad.ALTA,
    Categoria.REDES : Prioridad.ALTA,
    Categoria.INFRAESTRUCTURA : Prioridad.MEDIA,
    Categoria.PERMISOS : Prioridad.BAJA,
    Categoria.CUENTAS_CONTRASENAS : Prioridad.BAJA,
    Categoria.SOFTWARE : Prioridad.BAJA,
    Categoria.OTROS : Prioridad.BAJA
}
class ServicioTickets:
    @staticmethod
    def crear_ticket(creador, texto):
        categoria = ClasificadorTickets.clasificar(texto)
        prioridad_base = PRIORIDAD_BASE_POR_CATEGORIA[categoria]
        prioridad_final =GestorSLA.ajustar_prioridad_por_nivel(prioridad_base,creador.nivel)
        fecha_limite = GestorSLA.calcular_fecha_limite(prioridad_final,creador.nivel)
        nuevo_ticket = Ticket(
            texto=texto,
            categoria=categoria, 
            prioridad=prioridad_final,
            creador_id = creador.id,
            estado=EstadoTicket.ABIERTO,
            fecha_limite=fecha_limite
        )
        try:
            db.session.add(nuevo_ticket)
            db.session.commit()
            print(f"El ticket se ha resgistrado con exito")
            return True,nuevo_ticket
        except Exception as e:
            db.session.rollback()
            print(f"No se ha podido realizar el guardado u registro error : {e}")  
            return False,None