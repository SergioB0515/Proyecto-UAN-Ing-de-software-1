"""Pruebas del estado EN_ESPERA y del reloj de SLA detenido."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models.enum import AccionAuditoria, Categoria, EstadoTicket, RolUsuario
from app.models.log_auditoria import LogAuditoria
from app.models.notificacion import Notificacion
from app.models.usuario import Usuario
from app import notificaciones_i18n as notif
from app.services.exceptions import MotivoRequeridoError, TransicionInvalidaError
from app.services.gestor_sla import GestorSLA
from app.services.tickets import ServicioTickets
from tests.fabricas import crear_ticket, crear_usuario

# Area propia: CUENTAS_CONTRASENAS y SOFTWARE las usa test_sugerir_agente y
# OTROS necesita quedarse sin agentes para una de sus pruebas.
AREA = Categoria.SEGURIDAD


@pytest.fixture
def creador():
    return crear_usuario(rol=RolUsuario.FINAL)

@pytest.fixture(autouse=True)
def agentes_sin_rastro():
    """Desactiva al terminar los agentes creados en esta prueba.

    La base de pruebas se comparte entre archivos y se ejecutan en orden
    alfabetico: un agente de este archivo que quede activo y sin carga le
    cambia el resultado a las pruebas de sugerencia de agente que corren
    despues. Desactivarlo deja el area como estaba.
    """
    previos = {
        u.id for u in db.session.execute(
            select(Usuario).where(Usuario.rol == RolUsuario.AGENTE)
        ).scalars().all()
    }

    yield

    nuevos = db.session.execute(
        select(Usuario).where(
            Usuario.rol == RolUsuario.AGENTE, Usuario.id.notin_(previos or {0})
        )
    ).scalars().all()
    for agente_creado in nuevos:
        agente_creado.activo = False
    db.session.commit()



@pytest.fixture
def agente():
    return crear_usuario(rol=RolUsuario.AGENTE, area=AREA)


@pytest.fixture
def ticket_en_progreso(creador, agente):
    return crear_ticket(creador, categoria=AREA, estado=EstadoTicket.EN_PROGRESO,
                        agente=agente, creado_hace_horas=2, horas_sla=24)


def _notificaciones(usuario_id, plantilla):
    return db.session.execute(
        select(Notificacion).where(
            Notificacion.usuario_id == usuario_id, Notificacion.mensaje == plantilla
        )
    ).scalars().all()


def _acciones(ticket_id, accion):
    return [
        log for log in db.session.execute(
            select(LogAuditoria).where(LogAuditoria.accion == accion)
        ).scalars().all()
        if f"#{ticket_id}" in (log.detalle or "")
    ]


def test_poner_en_espera_exige_motivo(ticket_en_progreso, agente):
    with pytest.raises(MotivoRequeridoError):
        ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id)

    db.session.refresh(ticket_en_progreso)
    assert ticket_en_progreso.estado == EstadoTicket.EN_PROGRESO
    assert ticket_en_progreso.sla_pausado_desde is None


def test_poner_en_espera_detiene_el_reloj(ticket_en_progreso, agente):
    estado = ServicioTickets.cambiar_estado(
        ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
        motivo="Necesitamos la captura del error",
    )

    assert estado == EstadoTicket.EN_ESPERA
    assert ticket_en_progreso.sla_pausado_desde is not None
    assert ticket_en_progreso.sla_segundos_pausados == 0


def test_un_ticket_abierto_no_puede_ir_a_espera(creador, agente):
    ticket = crear_ticket(creador, categoria=AREA)
    with pytest.raises(TransicionInvalidaError):
        ServicioTickets.cambiar_estado(ticket.id, EstadoTicket.EN_ESPERA, agente.id, motivo="algo")


def test_el_consumo_de_sla_se_congela_durante_la_espera(ticket_en_progreso, agente):
    ahora = datetime.now()
    consumo_antes = GestorSLA.consumo_sla(ticket_en_progreso, ahora)

    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="esperando datos")

    consumo_1h = GestorSLA.consumo_sla(ticket_en_progreso, ahora + timedelta(hours=1))
    consumo_5h = GestorSLA.consumo_sla(ticket_en_progreso, ahora + timedelta(hours=5))

    assert consumo_1h == pytest.approx(consumo_antes, abs=0.01)
    assert consumo_5h == pytest.approx(consumo_antes, abs=0.01)


def test_reanudar_corre_la_fecha_limite_lo_que_duro_la_espera(ticket_en_progreso, agente):
    limite_original = ticket_en_progreso.fecha_limite

    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="esperando datos")
    # Se simula una espera de tres horas moviendo el inicio de la pausa.
    ticket_en_progreso.sla_pausado_desde = datetime.now() - timedelta(hours=3)
    db.session.commit()

    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_PROGRESO, agente.id)

    db.session.refresh(ticket_en_progreso)
    assert ticket_en_progreso.estado == EstadoTicket.EN_PROGRESO
    assert ticket_en_progreso.sla_pausado_desde is None
    assert ticket_en_progreso.sla_segundos_pausados == pytest.approx(3 * 3600, abs=60)
    corrimiento = (ticket_en_progreso.fecha_limite - limite_original).total_seconds()
    assert corrimiento == pytest.approx(3 * 3600, abs=60)


def test_un_ticket_en_espera_no_vence(creador, agente):
    ticket = crear_ticket(creador, categoria=AREA, estado=EstadoTicket.EN_PROGRESO,
                          agente=agente, creado_hace_horas=10, horas_sla=1)

    vencidos_antes, _p = GestorSLA.verificar_vencimientos()
    assert ticket.id in {t.id for t in vencidos_antes}

    ServicioTickets.cambiar_estado(ticket.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="el usuario tiene que probar algo")

    vencidos, proximos = GestorSLA.verificar_vencimientos()
    assert ticket.id not in {t.id for t in vencidos}
    assert ticket.id not in {t.id for t in proximos}


def test_reanudar_vuelve_a_armar_el_aviso_de_vencido(creador, agente):
    ticket = crear_ticket(creador, categoria=AREA, estado=EstadoTicket.EN_PROGRESO,
                          agente=agente, creado_hace_horas=2, horas_sla=4)
    ticket.notificado_vencido = True
    ticket.notificado_proximo_vencer = True
    db.session.commit()

    ServicioTickets.cambiar_estado(ticket.id, EstadoTicket.EN_ESPERA, agente.id, motivo="espera")
    ticket.sla_pausado_desde = datetime.now() - timedelta(hours=6)
    db.session.commit()
    ServicioTickets.cambiar_estado(ticket.id, EstadoTicket.EN_PROGRESO, agente.id)

    db.session.refresh(ticket)
    # La fecha limite se fue seis horas al futuro, asi que el ticket ya no esta
    # vencido y sus banderas de aviso tienen que volver a cero.
    assert ticket.fecha_limite > datetime.now()
    assert ticket.notificado_vencido is False
    assert ticket.notificado_proximo_vencer is False


def test_cerrar_desde_la_espera_tambien_detiene_el_reloj(ticket_en_progreso, agente):
    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="espera")
    ticket_en_progreso.sla_pausado_desde = datetime.now() - timedelta(hours=2)
    db.session.commit()

    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.CERRADO, agente.id)

    db.session.refresh(ticket_en_progreso)
    assert ticket_en_progreso.estado == EstadoTicket.CERRADO
    assert ticket_en_progreso.fecha_cierre is not None
    assert ticket_en_progreso.sla_pausado_desde is None
    assert ticket_en_progreso.sla_segundos_pausados > 0


def test_el_solicitante_recibe_aviso_de_la_espera(ticket_en_progreso, agente, creador):
    antes = len(_notificaciones(creador.id, notif.EN_ESPERA_CREADOR))

    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="falta el número de serie")

    assert len(_notificaciones(creador.id, notif.EN_ESPERA_CREADOR)) == antes + 1


def test_la_respuesta_del_solicitante_reanuda_el_ticket(ticket_en_progreso, agente, creador):
    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="falta el número de serie")

    ServicioTickets.agregar_comentario(ticket_en_progreso.id, creador.id, "Es el ABC-123")

    db.session.refresh(ticket_en_progreso)
    assert ticket_en_progreso.estado == EstadoTicket.EN_PROGRESO
    assert ticket_en_progreso.sla_pausado_desde is None
    assert _notificaciones(agente.id, notif.ESPERA_REANUDADA_AGENTE)


def test_una_nota_interna_del_agente_no_reanuda(ticket_en_progreso, agente):
    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="falta el número de serie")

    ServicioTickets.agregar_comentario(ticket_en_progreso.id, agente.id,
                                       "Pendiente de que responda", interno=True)

    db.session.refresh(ticket_en_progreso)
    assert ticket_en_progreso.estado == EstadoTicket.EN_ESPERA


def test_un_comentario_del_agente_no_reanuda(ticket_en_progreso, agente):
    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="falta el número de serie")

    ServicioTickets.agregar_comentario(ticket_en_progreso.id, agente.id, "Te recuerdo lo pedido")

    db.session.refresh(ticket_en_progreso)
    assert ticket_en_progreso.estado == EstadoTicket.EN_ESPERA


def test_la_auditoria_distingue_pausa_y_reanudacion(ticket_en_progreso, agente):
    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_ESPERA, agente.id,
                                   motivo="falta la captura")
    ServicioTickets.cambiar_estado(ticket_en_progreso.id, EstadoTicket.EN_PROGRESO, agente.id)

    pausas = _acciones(ticket_en_progreso.id, AccionAuditoria.PAUSAR_SLA)
    reanudaciones = _acciones(ticket_en_progreso.id, AccionAuditoria.REANUDAR_SLA)

    assert len(pausas) == 1
    assert "falta la captura" in pausas[0].detalle
    assert len(reanudaciones) == 1
