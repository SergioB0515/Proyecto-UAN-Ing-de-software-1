"""Pruebas de la cobertura de los tickets de un agente ausente.

Cierra el hueco que la 3.1 dejo documentado: un ticket ya asignado a un agente
que luego se declara ausente seguia avisandole solo a el.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models.enum import AccionAuditoria, Categoria, EstadoTicket, Prioridad, RolUsuario
from app.models.log_auditoria import LogAuditoria
from app.models.notificacion import Notificacion
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app import notificaciones_i18n as notif
from app.services.disponibilidad import ServicioDisponibilidad
from app.services.exceptions import AgenteDestinoInvalidoError, CoberturaNoRequeridaError
from app.services.gestor_sla import GestorSLA
from app.services.tickets import ServicioTickets
from tests.fabricas import crear_ticket, crear_usuario

AREA = Categoria.INFRAESTRUCTURA


@pytest.fixture
def admin():
    return crear_usuario(rol=RolUsuario.ADMIN)


@pytest.fixture(autouse=True)
def area_aislada(admin):
    """Desactiva los agentes que otros archivos de test sembraron en el area.

    La base de pruebas se comparte entre archivos, asi que sin esto los avisos
    de cobertura llegarian a agentes ajenos a la prueba y los conteos dejarian
    de ser deterministas.
    """
    previos = db.session.execute(
        select(Usuario).where(Usuario.rol == RolUsuario.AGENTE, Usuario.area_soporte == AREA)
    ).scalars().all()
    original = [(u, u.activo) for u in previos]
    for usuario, _activo in original:
        usuario.activo = False
    db.session.commit()

    yield

    # Los agentes creados por la prueba se desactivan para no alterar las
    # sugerencias de asignacion de los archivos que corren despues.
    nuevos = db.session.execute(
        select(Usuario).where(
            Usuario.rol == RolUsuario.AGENTE,
            Usuario.id.notin_({u.id for u, _a in original} or {0}),
        )
    ).scalars().all()
    for agente_creado in nuevos:
        agente_creado.activo = False
    for usuario, activo in original:
        usuario.activo = activo
    db.session.commit()


@pytest.fixture
def creador():
    return crear_usuario(rol=RolUsuario.FINAL)


@pytest.fixture
def titular():
    return crear_usuario(rol=RolUsuario.AGENTE, area=AREA)


@pytest.fixture
def companero():
    return crear_usuario(rol=RolUsuario.AGENTE, area=AREA)


def _notificaciones(usuario_id, plantilla):
    return db.session.execute(
        select(Notificacion).where(
            Notificacion.usuario_id == usuario_id, Notificacion.mensaje == plantilla
        )
    ).scalars().all()


def _ticket_asignado(creador, agente, estado=EstadoTicket.EN_PROGRESO, horas_sla=24, creado_hace_horas=1):
    return crear_ticket(creador, categoria=AREA, estado=estado, agente=agente,
                        creado_hace_horas=creado_hace_horas, horas_sla=horas_sla)


# ----------------------------------------------------------------- marcado

def test_marcar_ausente_marca_los_tickets_vivos(admin, creador, titular):
    abierto = _ticket_asignado(creador, titular)
    cerrado = _ticket_asignado(creador, titular, estado=EstadoTicket.CERRADO)

    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id, motivo="incapacidad")

    db.session.refresh(abierto)
    db.session.refresh(cerrado)
    assert abierto.requiere_cobertura is True
    assert cerrado.requiere_cobertura is False
    # La ausencia no reasigna: el ticket sigue siendo del agente ausente.
    assert abierto.agente_id == titular.id


def test_el_aviso_de_cobertura_va_al_companero_disponible(admin, creador, titular, companero):
    ticket = _ticket_asignado(creador, titular)

    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)

    avisos = _notificaciones(companero.id, notif.COBERTURA_REQUERIDA)
    assert [a.ticket_id for a in avisos] == [ticket.id]
    assert not _notificaciones(titular.id, notif.COBERTURA_REQUERIDA)


def test_sin_nadie_disponible_el_aviso_sube_al_administrador(admin, creador, titular):
    ticket = _ticket_asignado(creador, titular)

    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)

    avisos = _notificaciones(admin.id, notif.COBERTURA_REQUERIDA)
    assert ticket.id in {a.ticket_id for a in avisos}


def test_una_ausencia_programada_no_marca_nada_todavia(admin, creador, titular):
    ticket = _ticket_asignado(creador, titular)

    ServicioDisponibilidad.marcar_ausente(
        admin.id, titular.id,
        desde=datetime.now() + timedelta(days=2),
        hasta=datetime.now() + timedelta(days=5),
    )

    db.session.refresh(ticket)
    assert ticket.requiere_cobertura is False


def test_al_volver_el_agente_se_limpia_la_marca(admin, creador, titular):
    ticket = _ticket_asignado(creador, titular)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)
    db.session.refresh(ticket)
    assert ticket.requiere_cobertura is True

    ServicioDisponibilidad.marcar_disponible(admin.id, titular.id)

    db.session.refresh(ticket)
    assert ticket.requiere_cobertura is False


# --------------------------------------------------------------- tomar

def test_tomar_cobertura_reasigna_y_limpia_la_marca(admin, creador, titular, companero):
    ticket = _ticket_asignado(creador, titular)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)

    ServicioTickets.tomar_cobertura(ticket.id, companero.id)

    db.session.refresh(ticket)
    assert ticket.agente_id == companero.id
    assert ticket.requiere_cobertura is False
    assert ticket.fecha_asignacion is not None
    assert _notificaciones(titular.id, notif.COBERTURA_TOMADA)

    logs = db.session.execute(
        select(LogAuditoria).where(LogAuditoria.accion == AccionAuditoria.TOMAR_COBERTURA)
    ).scalars().all()
    assert any(f"#{ticket.id}" in (l.detalle or "") for l in logs)


def test_tomar_cobertura_de_un_ticket_abierto_lo_pone_en_progreso(admin, creador, titular, companero):
    ticket = _ticket_asignado(creador, titular, estado=EstadoTicket.ABIERTO)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)

    ServicioTickets.tomar_cobertura(ticket.id, companero.id)

    db.session.refresh(ticket)
    assert ticket.estado == EstadoTicket.EN_PROGRESO


def test_no_se_puede_cubrir_un_ticket_que_no_lo_necesita(creador, titular, companero):
    ticket = _ticket_asignado(creador, titular)

    with pytest.raises(CoberturaNoRequeridaError):
        ServicioTickets.tomar_cobertura(ticket.id, companero.id)


def test_un_agente_ausente_no_puede_tomar_la_cobertura(admin, creador, titular, companero):
    ticket = _ticket_asignado(creador, titular)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)
    ServicioDisponibilidad.marcar_ausente(admin.id, companero.id)

    with pytest.raises(AgenteDestinoInvalidoError):
        ServicioTickets.tomar_cobertura(ticket.id, companero.id)


def test_un_agente_de_otra_area_no_puede_tomar_la_cobertura(admin, creador, titular):
    ticket = _ticket_asignado(creador, titular)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)
    ajeno = crear_usuario(rol=RolUsuario.AGENTE, area=Categoria.SEGURIDAD)

    with pytest.raises(AgenteDestinoInvalidoError):
        ServicioTickets.tomar_cobertura(ticket.id, ajeno.id)


def test_un_agente_inactivo_no_puede_tomar_la_cobertura(admin, creador, titular):
    ticket = _ticket_asignado(creador, titular)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)
    inactivo = crear_usuario(rol=RolUsuario.AGENTE, area=AREA, activo=False)

    with pytest.raises(AgenteDestinoInvalidoError):
        ServicioTickets.tomar_cobertura(ticket.id, inactivo.id)


def test_el_administrador_puede_cubrir_el_ticket_el_mismo(admin, creador, titular):
    ticket = _ticket_asignado(creador, titular)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)

    ServicioTickets.tomar_cobertura(ticket.id, admin.id, actor_id=admin.id)

    db.session.refresh(ticket)
    assert ticket.agente_id == admin.id
    assert ticket.requiere_cobertura is False


# ------------------------------------------------------------- listados y SLA

def test_listar_pendientes_filtra_por_area_y_ordena_por_riesgo(admin, creador, titular):
    tranquilo = _ticket_asignado(creador, titular, horas_sla=48, creado_hace_horas=1)
    urgente = _ticket_asignado(creador, titular, horas_sla=4, creado_hace_horas=3)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)

    ids = [t.id for t in ServicioTickets.listar_pendientes_cobertura(area=AREA)]
    assert ids.index(urgente.id) < ids.index(tranquilo.id)

    otra_area = ServicioTickets.listar_pendientes_cobertura(area=Categoria.SEGURIDAD)
    assert tranquilo.id not in {t.id for t in otra_area}


def test_el_aviso_de_sla_de_un_ticket_de_agente_ausente_llega_al_area(admin, creador, titular, companero):
    ticket = _ticket_asignado(creador, titular, horas_sla=1, creado_hace_horas=5)
    ServicioDisponibilidad.marcar_ausente(admin.id, titular.id)
    # La marca se limpia a mano para comprobar que el propio aviso de SLA la
    # vuelve a poner: es el camino que se usa cuando la ausencia se activa por
    # fecha y nadie llamo a marcar_ausente en ese momento.
    ticket.requiere_cobertura = False
    ticket.notificado_vencido = False
    db.session.commit()

    GestorSLA.verificar_y_notificar_vencimientos()

    db.session.refresh(ticket)
    assert ticket.requiere_cobertura is True
    avisos = _notificaciones(companero.id, notif.SLA_VENCIDO_AREA)
    assert ticket.id in {a.ticket_id for a in avisos}
    # El agente ausente igual recibe el suyo, para encontrarlo al volver.
    assert ticket.id in {a.ticket_id for a in _notificaciones(titular.id, notif.SLA_VENCIDO_AGENTE)}
