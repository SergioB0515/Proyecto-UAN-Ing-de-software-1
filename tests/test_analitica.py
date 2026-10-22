from datetime import datetime, timedelta

import pytest

from app.models.enum import Categoria, EstadoTicket, Prioridad
from app.models.ticket import Ticket
from app.services.analitica import ServicioAnalitica, _variacion

AHORA = datetime(2026, 6, 15, 12, 0)


def t(id_, creado_hace_h, cerrado_tras_h=None, sla_h=24, categoria=Categoria.REDES):
    creado = AHORA - timedelta(hours=creado_hace_h)
    return Ticket(
        id=id_, texto="x", categoria=categoria, prioridad=Prioridad.MEDIA, creador_id=1,
        estado=EstadoTicket.CERRADO if cerrado_tras_h is not None else EstadoTicket.ABIERTO,
        fecha_creacion=creado, fecha_limite=creado + timedelta(hours=sla_h),
        fecha_cierre=creado + timedelta(hours=cerrado_tras_h) if cerrado_tras_h is not None else None,
    )


def test_kpis_basicos():
    tickets = [t(1, 48, 10), t(2, 30, 29), t(3, 5)]
    kpis = ServicioAnalitica._kpis(tickets, AHORA - timedelta(days=7), AHORA, primeras={})
    assert kpis["creados"] == 3 and kpis["cerrados"] == 2
    assert kpis["mttr_horas"] == 19.5 and kpis["mediana_horas"] == 19.5
    assert kpis["sla_pct"] == 50.0
    assert kpis["primera_respuesta_horas"] is None


def test_primera_respuesta_mediana():
    tickets = [t(1, 10), t(2, 10)]
    primeras = {1: tickets[0].fecha_creacion + timedelta(hours=1), 2: tickets[1].fecha_creacion + timedelta(hours=3)}
    kpis = ServicioAnalitica._kpis(tickets, AHORA - timedelta(days=1), AHORA, primeras)
    assert kpis["primera_respuesta_horas"] == 2.0 and kpis["con_respuesta_pct"] == 100.0


def test_serie_y_pendientes():
    tickets = [t(1, 50, 2), t(2, 26), t(3, 1)]
    serie = ServicioAnalitica._serie(tickets, AHORA - timedelta(days=3), 3)
    assert len(serie["etiquetas"]) == 4
    assert sum(serie["creados"]) == 3 and sum(serie["cerrados"]) == 1
    assert serie["backlog"][-1] == 2


def test_mapa_calor():
    tickets = [t(1, 0), t(2, 0), t(3, 24)]
    mapa = ServicioAnalitica._mapa_calor(tickets, AHORA - timedelta(days=2), AHORA + timedelta(seconds=1))
    assert mapa["matriz"][AHORA.weekday()][AHORA.hour] == 2
    assert mapa["maximo"] == 2


def test_por_categoria_agrupa():
    tickets = [t(1, 5, 1), t(2, 5, categoria=Categoria.SOFTWARE), t(3, 5, categoria=Categoria.SOFTWARE)]
    filas = ServicioAnalitica._por_categoria(tickets, AHORA - timedelta(days=1), AHORA)
    assert filas[0]["categoria"] == "software" and filas[0]["creados"] == 2 and filas[0]["abiertos"] == 2
    assert {f["categoria"] for f in filas} == {"software", "redes"}


@pytest.mark.parametrize("actual, anterior, esperado", [(12, 10, 20.0), (5, 10, -50.0), (3, 0, None), (None, 4, None)])
def test_variacion(actual, anterior, esperado):
    assert _variacion(actual, anterior) == esperado


def test_periodo_normalizado():
    assert ServicioAnalitica.normalizar_periodo("90") == 90
    assert ServicioAnalitica.normalizar_periodo("13") == 30
    assert ServicioAnalitica.normalizar_periodo(None) == 30


def test_panel_completo_no_falla():
    datos = ServicioAnalitica.panel(dias=7)
    for clave in ("kpis", "variaciones", "serie", "por_categoria", "mapa_calor", "agentes", "csat", "base_conocimiento"):
        assert clave in datos
    assert len(datos["serie"]["etiquetas"]) == 8
