from sqlalchemy import select, func, or_, and_
from datetime import datetime, timedelta
from flask_babel import gettext as _
from app.extensions import db
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.models.enum import RolUsuario,EstadoTicket
from app.services.gestor_sla import GestorSLA
from app.models.correccion_clasificacion import CorreccionClasificacion
import os, json

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
                Ticket.fecha_limite >= hace_30_dias,
                Ticket.fecha_limite < datetime.now(),
                or_(
                    and_(Ticket.fecha_cierre.isnot(None), Ticket.fecha_cierre > Ticket.fecha_limite),
                    Ticket.fecha_cierre.is_(None),
                )
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
        
    @staticmethod
    def metricas_por_agente(area=None, agente_id=None, dias=30):

        hace_n_dias = datetime.now() - timedelta(days=dias)


        if agente_id is not None:
            agentes = db.session.execute(
                select(Usuario).where(Usuario.id == agente_id)
            ).scalars().all()

        elif area is not None:
            agentes = db.session.execute(
                select(Usuario).where(
                    Usuario.area_soporte == area,
                    Usuario.rol == RolUsuario.AGENTE
                )
            ).scalars().all()

        else:
            raise ValueError("Debe especificarse agente_id o area")

        resultado = []

        for agente in agentes:

            tickets_del_agente = db.session.execute(
                select(Ticket).where(
                    Ticket.agente_id == agente.id,
                    Ticket.estado == EstadoTicket.CERRADO,
                    Ticket.fecha_cierre >= hace_n_dias,
                )
            ).scalars().all()

            tickets_cerrados = len(tickets_del_agente)

 
            duraciones = [
                t.fecha_cierre - t.fecha_asignacion
                for t in tickets_del_agente
                if t.fecha_asignacion is not None
            ]

            tiempo_promedio_resolucion_horas = (
                (sum(duraciones, timedelta()) / len(duraciones)).total_seconds() / 3600
                if duraciones
                else None
            )


            cumplimiento_sla = (
                sum(
                    1
                    for t in tickets_del_agente
                    if t.fecha_cierre <= t.fecha_limite
                ) / tickets_cerrados
                if tickets_cerrados > 0
                else None
            )

            resultado.append({
                "agente_id": agente.id,
                "nombre": agente.nombre,
                "tickets_cerrados": tickets_cerrados,
                "tiempo_promedio_resolucion_horas": tiempo_promedio_resolucion_horas,
                "cumplimiento_sla": cumplimiento_sla,
            })

        return resultado

    @staticmethod
    def comparativa_area(agente_id, area, dias=30):
        """Compara al agente con sus pares del área: promedio de SLA, puesto en el
        ranking del área y una insignia de nivel según su cumplimiento de SLA."""

        metricas_area = ServicioMetricas.metricas_por_agente(area=area, dias=dias)

        con_sla = [m for m in metricas_area if m["cumplimiento_sla"] is not None]
        promedio_sla = (
            sum(m["cumplimiento_sla"] for m in con_sla) / len(con_sla)
            if con_sla else None
        )

        ranking = sorted(con_sla, key=lambda m: m["cumplimiento_sla"], reverse=True)
        posicion = next(
            (i for i, m in enumerate(ranking, start=1) if m["agente_id"] == agente_id),
            None,
        )

        metricas_agente = next((m for m in metricas_area if m["agente_id"] == agente_id), None)
        sla_agente = metricas_agente["cumplimiento_sla"] if metricas_agente else None

        nivel_clave = None
        if sla_agente is not None:
            if sla_agente >= 0.9:
                nivel_clave = "oro"
            elif sla_agente >= 0.75:
                nivel_clave = "plata"
            elif sla_agente >= 0.5:
                nivel_clave = "bronce"
            else:
                nivel_clave = "bajo"

        niveles = {
            "oro": _("Excelente"),
            "plata": _("Muy bueno"),
            "bronce": _("Aceptable"),
            "bajo": _("Necesita mejorar"),
        }

        return {
            "promedio_sla": promedio_sla,
            "posicion": posicion,
            "total_agentes": len(ranking),
            "nivel_clave": nivel_clave,
            "nivel_texto": niveles.get(nivel_clave),
        }

    @staticmethod
    def obtener_metricas_confianza_clasificador(dias=30):


        RUTA_METADATA = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "ml_artifacts", "metadata.json"
        )

        hace_n_dias = datetime.now() - timedelta(days=dias)

        tickets_en_revision = db.session.execute(select(func.count()).select_from(Ticket).where(
            Ticket.clasificacion_baja_confianza == True
        )).scalar()


        correcciones_ventana = db.session.execute(select(func.count()).select_from(CorreccionClasificacion).where(
            CorreccionClasificacion.fecha >= hace_n_dias
        )).scalar()


        tickets_creados_ventana = db.session.execute(select(func.count()).select_from(Ticket).where(
            Ticket.fecha_creacion >= hace_n_dias
        )).scalar()

      
        tasa_correccion_30d = ( correcciones_ventana / tickets_creados_ventana
            if tickets_creados_ventana > 0 
            else None
        )


        exactitud_produccion_30d = (1 - tasa_correccion_30d
            if tasa_correccion_30d is not None
            else None
            )

       
        exactitud_laboratorio = None
        fecha_entrenamiento_modelo = None
        if os.path.exists(RUTA_METADATA):
            with open(RUTA_METADATA, "r", encoding="utf-8" ) as f:
                metadata = json.load(f)
            exactitud_laboratorio = metadata.get("exactitud_en_prueba")
            fecha_entrenamiento_modelo = metadata.get("fecha_entrenamiento")

        return {
            "tickets_en_revision": tickets_en_revision,
            "tasa_correccion_30d": tasa_correccion_30d,
            "exactitud_produccion_30d": exactitud_produccion_30d,
            "exactitud_laboratorio": exactitud_laboratorio,
            "fecha_entrenamiento_modelo": fecha_entrenamiento_modelo,
        }
        
    @staticmethod
    def _panorama_area(categoria):
        """Agentes de un área con su carga actual (tickets EN_PROGRESO) y sus
        métricas de desempeño (últimos 30 días), para sugerir/justificar un agente."""

        agentes = db.session.execute(
            select(Usuario).where(
                Usuario.area_soporte == categoria, Usuario.rol == RolUsuario.AGENTE
            )
        ).scalars().all()

        if not agentes:
            return [], {}, {}

        cargas = {}
        for agente in agentes:
            cargas[agente.id] = db.session.execute(
                select(func.count()).select_from(Ticket).where(
                    Ticket.agente_id == agente.id,
                    Ticket.estado == EstadoTicket.EN_PROGRESO,
                )
            ).scalar()

        dict_de_metricas = ServicioMetricas.metricas_por_agente(area=categoria)
        metricas_por_id = {m["agente_id"]: m for m in dict_de_metricas}

        return agentes, cargas, metricas_por_id

    @staticmethod
    def _clave_orden_sugerencia(cargas, metricas_por_id):
        def clave_orden(agente):
            carga = cargas[agente.id]
            cumplimiento = metricas_por_id.get(agente.id, {}).get("cumplimiento_sla")
            cumplimiento_para_orden = cumplimiento if cumplimiento is not None else -1
            return (carga, -cumplimiento_para_orden)
        return clave_orden

    @staticmethod
    def sugerir_agente(categoria):

        agentes, cargas, metricas_por_id = ServicioMetricas._panorama_area(categoria)
        if not agentes:
            return None

        clave_orden = ServicioMetricas._clave_orden_sugerencia(cargas, metricas_por_id)
        return sorted(agentes, key=clave_orden)[0]

    @staticmethod
    def detalle_sugerencia_agente(categoria):
        """Igual que sugerir_agente, pero además explica el motivo de la elección
        y expone la carga/desempeño del agente elegido, para mostrarlo en el
        detalle del ticket."""

        agentes, cargas, metricas_por_id = ServicioMetricas._panorama_area(categoria)
        if not agentes:
            return None

        clave_orden = ServicioMetricas._clave_orden_sugerencia(cargas, metricas_por_id)
        ganador = sorted(agentes, key=clave_orden)[0]

        carga_ganador = cargas[ganador.id]
        metricas_ganador = metricas_por_id.get(ganador.id, {
            "tickets_cerrados": 0,
            "tiempo_promedio_resolucion_horas": None,
            "cumplimiento_sla": None,
        })

        otras_cargas = [cargas[a.id] for a in agentes if a.id != ganador.id]

        if not otras_cargas:
            motivo = _("Es el único agente disponible en esta área")
        elif any(c == carga_ganador for c in otras_cargas):
            motivo = _(
                "Comparte la carga de trabajo más baja del área (%(n)s tickets en progreso) "
                "y tiene el mejor cumplimiento de SLA entre quienes están en ese caso",
                n=carga_ganador,
            )
        else:
            promedio_otros = round(sum(otras_cargas) / len(otras_cargas), 1)
            motivo = _(
                "Tiene la carga de trabajo más baja del área (%(n)s tickets en progreso) "
                "frente a un promedio de %(prom)s en el resto del equipo",
                n=carga_ganador, prom=promedio_otros,
            )

        return {
            "agente": ganador,
            "carga_actual": carga_ganador,
            "tickets_cerrados_30d": metricas_ganador["tickets_cerrados"],
            "tiempo_promedio_resolucion_horas": metricas_ganador["tiempo_promedio_resolucion_horas"],
            "cumplimiento_sla": metricas_ganador["cumplimiento_sla"],
            "motivo": motivo,
            "total_agentes_area": len(agentes),
        }