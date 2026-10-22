from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.enum import Categoria, EstadoTicket, RolUsuario
from app.services.encuestas import ServicioEncuestas, DIAS_PARA_RESPONDER
from app.services.exceptions import EncuestaNoDisponibleError, EncuestaYaRespondidaError, PermisoDenegadoError
from tests.fabricas import crear_ticket, crear_usuario


@pytest.fixture
def cerrado():
    agente = crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)
    return crear_ticket(crear_usuario(), estado=EstadoTicket.CERRADO, agente=agente, creado_hace_horas=10, horas_hasta_cierre=5)


def test_responder_y_no_repetir(cerrado):
    assert ServicioEncuestas.puede_responder(cerrado, cerrado.creador_id)
    encuesta = ServicioEncuestas.responder(cerrado.id, cerrado.creador_id, "4", "  Bien  ")
    assert encuesta.puntuacion == 4 and encuesta.comentario == "Bien" and encuesta.agente_id == cerrado.agente_id
    assert not ServicioEncuestas.puede_responder(cerrado, cerrado.creador_id)
    with pytest.raises(EncuestaYaRespondidaError):
        ServicioEncuestas.responder(cerrado.id, cerrado.creador_id, 5)


@pytest.mark.parametrize("valor", [0, 6, "x", None])
def test_puntuacion_fuera_de_rango(cerrado, valor):
    with pytest.raises(ValueError):
        ServicioEncuestas.responder(cerrado.id, cerrado.creador_id, valor)


def test_solo_el_creador(cerrado):
    with pytest.raises(PermisoDenegadoError):
        ServicioEncuestas.responder(cerrado.id, crear_usuario().id, 5)


def test_no_disponible_si_abierto_o_vencida():
    agente = crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)
    abierto = crear_ticket(crear_usuario(), estado=EstadoTicket.EN_PROGRESO, agente=agente)
    with pytest.raises(EncuestaNoDisponibleError):
        ServicioEncuestas.responder(abierto.id, abierto.creador_id, 5)
    viejo = crear_ticket(crear_usuario(), estado=EstadoTicket.CERRADO, agente=agente,
                         creado_hace_horas=(DIAS_PARA_RESPONDER + 2) * 24, horas_hasta_cierre=1)
    assert not ServicioEncuestas.puede_responder(viejo, viejo.creador_id)


def test_resumen_calcula_csat():
    agente = crear_usuario(RolUsuario.AGENTE, area=Categoria.SEGURIDAD)
    for puntuacion in (5, 4, 2):
        t = crear_ticket(crear_usuario(), estado=EstadoTicket.CERRADO, agente=agente, horas_hasta_cierre=0)
        ServicioEncuestas.responder(t.id, t.creador_id, puntuacion)
    resumen = ServicioEncuestas.resumen(agente_id=agente.id)
    assert resumen["total"] == 3
    assert resumen["promedio"] == pytest.approx(3.67, abs=0.01)
    assert resumen["csat"] == pytest.approx(66.7, abs=0.1)
    assert resumen["distribucion"][5] == 1 and resumen["distribucion"][1] == 0
