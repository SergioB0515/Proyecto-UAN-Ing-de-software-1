from sqlalchemy import select, func
from datetime import datetime, timedelta
from app.extensions import db
from app.Models.ticket import Ticket
from app.Models.usuario import Usuario
from app.Models.enum import RolUsuario
from app.services.gestor_sla import GestorSLA


class ServicioMetricas:

    @staticmethod
    def obtener_metricas():


        resultado_estado = db.session.execute(
            select(Ticket.estado, func.count()).group_by(Ticket.estado)
        ).all()
        tickets_por_estado = {
                estado.name : cantidad for estado , cantidad in resultado_estado
            }


        resultado_categoria = db.session.execute(
            select(Ticket.categoria, func.count()).group_by(Ticket.categoria)
        ).all()
        tickets_por_categoria = {
                estado.name : cantidad for estado , cantidad in resultado_categoria
            }


        resultado_prioridad = db.session.execute(
            select(Ticket.prioridad, func.count()).group_by(Ticket.prioridad)
        ).all()
        tickets_por_prioridad = {
                estado.name : cantidad for estado , cantidad in resultado_prioridad
            }


        vencidos, proximos_a_vencer = GestorSLA.verificar_vencimientos()
        tickets_vencidos_actualmente = len(vencidos)
        tickets_proximos_a_vencer_actualmente = len(proximos_a_vencer)

        hace_30_dias = datetime.now() - timedelta(days=30)
        tickets_vencidos_ultimos_30_dias = db.session.execute(
            select(func.count()).select_from(Ticket).where(
                Ticket.fecha_limite < datetime.now(),
                Ticket.fecha_limite >= hace_30_dias,
            )
        ).scalar()


        cantidad_agentes = db.session.execute(
            select(func.count()).select_from(Usuario).where(
                Usuario.rol==RolUsuario.AGENTE
            )
        ).scalar()

        return {
            "tickets_por_estado": tickets_por_estado,
            "tickets_por_categoria": tickets_por_categoria,
            "tickets_por_prioridad": tickets_por_prioridad,
            "tickets_vencidos_actualmente": tickets_vencidos_actualmente,
            "tickets_proximos_a_vencer_actualmente": tickets_proximos_a_vencer_actualmente,
            "tickets_vencidos_ultimos_30_dias": tickets_vencidos_ultimos_30_dias,
            "cantidad_agentes": cantidad_agentes,
        }