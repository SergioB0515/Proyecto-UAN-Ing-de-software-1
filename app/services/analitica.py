from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median

from sqlalchemy import select, or_, func

from app.extensions import db
from app.models.articulo import Articulo
from app.models.comentario import Comentario
from app.models.encuesta_satisfaccion import EncuestaSatisfaccion
from app.models.enum import Categoria, EstadoTicket, Prioridad, RolUsuario
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.encuestas import ServicioEncuestas

PERIODOS_VALIDOS = (7, 30, 90, 180)


def _horas(inicio, fin):
    if inicio is None or fin is None:
        return None
    return max((fin - inicio).total_seconds() / 3600, 0)


def _redondear(valor, decimales=1):
    return None if valor is None else round(valor, decimales)


def _variacion(actual, anterior):
    if actual is None or anterior in (None, 0):
        return None
    return round((actual - anterior) / anterior * 100, 1)


class ServicioAnalitica:

    @staticmethod
    def normalizar_periodo(dias):
        try:
            dias = int(dias)
        except (TypeError, ValueError):
            return 30
        return dias if dias in PERIODOS_VALIDOS else 30

    @staticmethod
    def _tickets(desde, hasta, categoria=None):
        query = select(Ticket).where(
            Ticket.fecha_creacion < hasta,
            or_(Ticket.fecha_cierre.is_(None), Ticket.fecha_cierre >= desde, Ticket.fecha_creacion >= desde),
        )
        if categoria is not None:
            query = query.where(Ticket.categoria == categoria)
        return db.session.execute(query).scalars().all()

    @staticmethod
    def _primeras_respuestas(tickets):
        if not tickets:
            return {}
        por_id = {t.id: t for t in tickets}
        filas = db.session.execute(
            select(Comentario.ticket_id, Comentario.autor_id, Comentario.fecha)
            .where(Comentario.ticket_id.in_(list(por_id)), Comentario.interno.is_(False))
            .order_by(Comentario.fecha)
        ).all()
        primeras = {}
        for ticket_id, autor_id, fecha in filas:
            if ticket_id in primeras:
                continue
            if autor_id != por_id[ticket_id].creador_id:
                primeras[ticket_id] = fecha
        return primeras

    @staticmethod
    def _kpis(tickets, desde, hasta, primeras=None):
        creados = [t for t in tickets if desde <= t.fecha_creacion < hasta]
        cerrados = [t for t in tickets if t.fecha_cierre is not None and desde <= t.fecha_cierre < hasta]
        tiempos = [h for h in (_horas(t.fecha_creacion, t.fecha_cierre) for t in cerrados) if h is not None]
        a_tiempo = [t for t in cerrados if t.fecha_cierre <= t.fecha_limite]
        respuesta = []
        if primeras is not None:
            respuesta = [
                _horas(t.fecha_creacion, primeras[t.id]) for t in creados if t.id in primeras
            ]
        return {
            "creados": len(creados),
            "cerrados": len(cerrados),
            "mttr_horas": _redondear(sum(tiempos) / len(tiempos)) if tiempos else None,
            "mediana_horas": _redondear(median(tiempos)) if tiempos else None,
            "sla_pct": _redondear(len(a_tiempo) / len(cerrados) * 100) if cerrados else None,
            "primera_respuesta_horas": _redondear(median(respuesta)) if respuesta else None,
            "con_respuesta_pct": _redondear(len(respuesta) / len(creados) * 100) if creados else None,
        }

    @staticmethod
    def _serie(tickets, desde, dias):
        etiquetas, creados, cerrados, backlog = [], [], [], []
        inicio = desde.replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(dias + 1):
            dia = inicio + timedelta(days=i)
            fin = dia + timedelta(days=1)
            etiquetas.append(dia.strftime("%Y-%m-%d"))
            creados.append(sum(1 for t in tickets if dia <= t.fecha_creacion < fin))
            cerrados.append(sum(1 for t in tickets if t.fecha_cierre and dia <= t.fecha_cierre < fin))
            backlog.append(sum(
                1 for t in tickets
                if t.fecha_creacion < fin and (t.fecha_cierre is None or t.fecha_cierre >= fin)
            ))
        return {"etiquetas": etiquetas, "creados": creados, "cerrados": cerrados, "backlog": backlog}

    @staticmethod
    def _por_categoria(tickets, desde, hasta):
        filas = []
        for categoria in Categoria:
            propios = [t for t in tickets if t.categoria == categoria]
            kpis = ServicioAnalitica._kpis(propios, desde, hasta)
            abiertos = sum(1 for t in propios if t.estado != EstadoTicket.CERRADO)
            if kpis["creados"] or kpis["cerrados"] or abiertos:
                filas.append({"categoria": categoria.value, "abiertos": abiertos, **kpis})
        filas.sort(key=lambda f: -f["creados"])
        return filas

    @staticmethod
    def _mapa_calor(tickets, desde, hasta):
        matriz = [[0] * 24 for _i in range(7)]
        for t in tickets:
            if desde <= t.fecha_creacion < hasta:
                matriz[t.fecha_creacion.weekday()][t.fecha_creacion.hour] += 1
        maximo = max((max(fila) for fila in matriz), default=0)
        return {"matriz": matriz, "maximo": maximo}

    @staticmethod
    def _ranking_agentes(desde, hasta, categoria=None):
        query = select(Usuario).where(Usuario.rol == RolUsuario.AGENTE)
        if categoria is not None:
            query = query.where(Usuario.area_soporte == categoria)
        agentes = db.session.execute(query.order_by(Usuario.nombre)).scalars().all()
        if not agentes:
            return []
        ids = [a.id for a in agentes]
        cerrados = db.session.execute(
            select(Ticket).where(
                Ticket.agente_id.in_(ids), Ticket.fecha_cierre.isnot(None),
                Ticket.fecha_cierre >= desde, Ticket.fecha_cierre < hasta,
            )
        ).scalars().all()
        carga = dict(db.session.execute(
            select(Ticket.agente_id, func.count(Ticket.id))
            .where(Ticket.agente_id.in_(ids), Ticket.estado == EstadoTicket.EN_PROGRESO)
            .group_by(Ticket.agente_id)
        ).all())
        csat = defaultdict(list)
        for agente_id, puntuacion in db.session.execute(
            select(EncuestaSatisfaccion.agente_id, EncuestaSatisfaccion.puntuacion)
            .where(EncuestaSatisfaccion.agente_id.in_(ids), EncuestaSatisfaccion.fecha >= desde)
        ).all():
            csat[agente_id].append(puntuacion)

        por_agente = defaultdict(list)
        for t in cerrados:
            por_agente[t.agente_id].append(t)

        filas = []
        for agente in agentes:
            propios = por_agente.get(agente.id, [])
            tiempos = [h for h in (_horas(t.fecha_asignacion or t.fecha_creacion, t.fecha_cierre) for t in propios) if h is not None]
            a_tiempo = sum(1 for t in propios if t.fecha_cierre <= t.fecha_limite)
            puntuaciones = csat.get(agente.id, [])
            filas.append({
                "id": agente.id,
                "nombre": agente.nombre,
                "area": agente.area_soporte.value if agente.area_soporte else None,
                "activo": agente.activo,
                "cerrados": len(propios),
                "carga": carga.get(agente.id, 0),
                "mttr_horas": _redondear(sum(tiempos) / len(tiempos)) if tiempos else None,
                "sla_pct": _redondear(a_tiempo / len(propios) * 100) if propios else None,
                "csat": _redondear(sum(puntuaciones) / len(puntuaciones), 2) if puntuaciones else None,
                "encuestas": len(puntuaciones),
            })
        filas.sort(key=lambda f: (-f["cerrados"], f["mttr_horas"] if f["mttr_horas"] is not None else 10 ** 6))
        return filas

    @staticmethod
    def _base_conocimiento(limite=5):
        articulos = db.session.execute(
            select(Articulo).where(Articulo.publicado.is_(True)).order_by(Articulo.vistas.desc()).limit(limite)
        ).scalars().all()
        totales = db.session.execute(
            select(
                func.count(Articulo.id), func.coalesce(func.sum(Articulo.vistas), 0),
                func.coalesce(func.sum(Articulo.resoluciones), 0),
                func.coalesce(func.sum(Articulo.votos_utiles), 0),
                func.coalesce(func.sum(Articulo.votos_no_utiles), 0),
            ).where(Articulo.publicado.is_(True))
        ).one()
        votos = totales[3] + totales[4]
        return {
            "publicados": totales[0],
            "vistas": totales[1],
            "resoluciones": totales[2],
            "utilidad_pct": _redondear(totales[3] / votos * 100) if votos else None,
            "top": [
                {"id": a.id, "titulo": a.titulo, "vistas": a.vistas, "resoluciones": a.resoluciones,
                 "utilidad": _redondear(a.utilidad * 100) if a.utilidad is not None else None}
                for a in articulos
            ],
        }

    @staticmethod
    def panel(dias=30, categoria=None, ahora=None):
        dias = ServicioAnalitica.normalizar_periodo(dias)
        ahora = ahora or datetime.now()
        desde = ahora - timedelta(days=dias)
        desde_anterior = desde - timedelta(days=dias)

        tickets = ServicioAnalitica._tickets(desde_anterior, ahora, categoria)
        primeras = ServicioAnalitica._primeras_respuestas(
            [t for t in tickets if t.fecha_creacion >= desde_anterior]
        )
        actual = ServicioAnalitica._kpis(tickets, desde, ahora, primeras)
        anterior = ServicioAnalitica._kpis(tickets, desde_anterior, desde, primeras)
        variaciones = {clave: _variacion(actual[clave], anterior[clave]) for clave in actual}

        backlog = sum(1 for t in tickets if t.estado != EstadoTicket.CERRADO)
        vencidos = sum(1 for t in tickets if t.estado != EstadoTicket.CERRADO and t.fecha_limite < ahora)
        prioridades = {p.value: sum(1 for t in tickets if t.prioridad == p and desde <= t.fecha_creacion < ahora) for p in Prioridad}

        return {
            "dias": dias,
            "desde": desde,
            "hasta": ahora,
            "categoria": categoria.value if categoria else None,
            "kpis": actual,
            "anterior": anterior,
            "variaciones": variaciones,
            "backlog": backlog,
            "vencidos": vencidos,
            "serie": ServicioAnalitica._serie(tickets, desde, dias),
            "por_categoria": ServicioAnalitica._por_categoria(tickets, desde, ahora),
            "por_prioridad": prioridades,
            "mapa_calor": ServicioAnalitica._mapa_calor(tickets, desde, ahora),
            "agentes": ServicioAnalitica._ranking_agentes(desde, ahora, categoria),
            "csat": ServicioEncuestas.resumen(desde=desde),
            "csat_anterior": ServicioEncuestas.resumen(desde=desde_anterior, hasta=desde),
            "comentarios_csat": ServicioEncuestas.recientes(),
            "base_conocimiento": ServicioAnalitica._base_conocimiento(),
        }
