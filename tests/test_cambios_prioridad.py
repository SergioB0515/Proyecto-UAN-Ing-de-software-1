"""
Pruebas de ServicioSolicitudesTransferencia -- cambio de prioridad (v1.8.5)

Que verifica:
1-7.   cambiar_prioridad: caso valido, ticket inexistente, ticket no en
       progreso, misma prioridad, motivo vacio, solicitud duplicada (mismo
       tipo), solicitud duplicada cruzada contra una transferencia normal
       ya pendiente sobre el mismo ticket.
8-9.   aprobar_cambio_prioridad: caso valido con creador NORMAL (SLA normal),
       caso valido con creador VIP (SLA vip) -- este ultimo es la prueba de
       regresion del bug donde se usaba usuario.rol en vez de usuario.nivel
       al recalcular la fecha limite.
10-12. aprobar_cambio_prioridad: solicitud inexistente, ya resuelta, ticket
       que dejo de estar en progreso mientras seguia pendiente.
13-14. rechazar_cambio_prioridad: caso valido (no toca el ticket), ya resuelta.
15.    listar_cambios_prioridad_pendientes: solo trae tipo CAMBIO_PRIORIDAD
       pendientes, nunca transferencias normales ni escalamientos de area.

Nota: "no puedo entrar a mi correo" clasifica como PERMISOS, con prioridad
base BAJA (ver PRIORIDAD_BASE_POR_CATEGORIA en app/services/tickets.py).
"""
from datetime import datetime

import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoEnProgresoError,
    PrioridadDestinoInvalidaError, MotivoRequeridoError, SolicitudDuplicadaError,
    SolicitudNoEncontradaError, SolicitudNoPendienteError,
)
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import (
    RolUsuario, NivelUsuario, Categoria, Prioridad, EstadoTicket, EstadoSolicitudTransferencia,
)


EMAIL_ADMIN = "prueba_cambios_prioridad_admin@empresa.com"
EMAIL_NORMAL = "prueba_cambios_prioridad_normal@empresa.com"
EMAIL_VIP = "prueba_cambios_prioridad_vip@empresa.com"
EMAIL_AGENTE = "prueba_cambios_prioridad_agente@empresa.com"

TEXTO_TICKET_PERMISOS = "no puedo entrar a mi correo"  # PERMISOS, base BAJA


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL, EMAIL_VIP, EMAIL_AGENTE):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba Cambios Prioridad",
        email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Cambios Prioridad",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Usuario VIP Cambios Prioridad",
        email=EMAIL_VIP,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.VIP,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Cambios Prioridad",
        email=EMAIL_AGENTE,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
        area_soporte=Categoria.PERMISOS,
    )


def _crear_ticket_en_progreso(creador, agente):
    """Helper local: crea un ticket de PERMISOS y lo deja EN_PROGRESO con
    `agente` como responsable."""
    ticket = ServicioTickets.crear_ticket(creador=creador, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id,
        agente_id=agente.id,
    )
    return ticket


# ---------------------------------------------------------------------------
# cambiar_prioridad
# ---------------------------------------------------------------------------

def test_cambiar_prioridad_valido():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    assert ticket.prioridad == Prioridad.BAJA, (
        f"precondicion: se esperaba BAJA (base de PERMISOS, creador normal), se obtuvo {ticket.prioridad}"
    )

    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id,
        prioridad_destino=Prioridad.ALTA,
        solicitante_id=agente.id,
        motivo="Este ticket es mas urgente de lo que parecia",
    )

    assert solicitud is not None, "se esperaba que la solicitud se creara exitosamente"
    assert solicitud.estado == EstadoSolicitudTransferencia.PENDIENTE, (
        f"se esperaba estado PENDIENTE, se obtuvo {solicitud.estado}"
    )
    assert solicitud.prioridad_destino == Prioridad.ALTA, (
        f"se esperaba prioridad_destino ALTA, se obtuvo {solicitud.prioridad_destino}"
    )


def test_cambiar_prioridad_ticket_inexistente():
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    with pytest.raises(TicketNoEncontradoError):
        ServicioSolicitudesTransferencia.cambiar_prioridad(
            ticket_id=999999, prioridad_destino=Prioridad.ALTA,
            solicitante_id=agente.id, motivo="motivo cualquiera",
        )


def test_cambiar_prioridad_ticket_no_en_progreso():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    # queda ABIERTO, nunca paso por cambiar_estado

    with pytest.raises(TicketNoEnProgresoError):
        ServicioSolicitudesTransferencia.cambiar_prioridad(
            ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
            solicitante_id=agente.id, motivo="motivo cualquiera",
        )


def test_cambiar_prioridad_misma_prioridad():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = _crear_ticket_en_progreso(normal, agente)  # queda en BAJA

    with pytest.raises(PrioridadDestinoInvalidaError):
        ServicioSolicitudesTransferencia.cambiar_prioridad(
            ticket_id=ticket.id, prioridad_destino=Prioridad.BAJA,  # misma que ya tiene
            solicitante_id=agente.id, motivo="motivo cualquiera",
        )


def test_cambiar_prioridad_motivo_vacio():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = _crear_ticket_en_progreso(normal, agente)

    with pytest.raises(MotivoRequeridoError):
        ServicioSolicitudesTransferencia.cambiar_prioridad(
            ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
            solicitante_id=agente.id, motivo="   ",  # solo espacios
        )


def test_cambiar_prioridad_duplicada():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = _crear_ticket_en_progreso(normal, agente)

    ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
        solicitante_id=agente.id, motivo="Primer intento",
    )

    with pytest.raises(SolicitudDuplicadaError):
        ServicioSolicitudesTransferencia.cambiar_prioridad(
            ticket_id=ticket.id, prioridad_destino=Prioridad.MEDIA,
            solicitante_id=agente.id, motivo="Segundo intento",
        )


def test_cambiar_prioridad_duplicada_contra_transferencia_normal():
    """El chequeo de duplicados sigue siendo compartido entre los tres
    tipos: una transferencia normal (v1.7) pendiente sobre un ticket
    tambien bloquea un intento de cambio de prioridad (v1.8.5) sobre ese
    mismo ticket."""
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ServicioAutenticacion.registrar(
        nombre="Agente Cambios Prioridad 2",
        email="prueba_cambios_prioridad_agente_2@empresa.com",
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=Usuario.query.filter_by(email=EMAIL_ADMIN).first().id,
        area_soporte=Categoria.PERMISOS,
    )
    agente_2 = Usuario.query.filter_by(email="prueba_cambios_prioridad_agente_2@empresa.com").first()

    ticket = _crear_ticket_en_progreso(normal, agente)

    ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=agente_2.id, solicitante_id=agente.id,
    )

    with pytest.raises(SolicitudDuplicadaError):
        ServicioSolicitudesTransferencia.cambiar_prioridad(
            ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
            solicitante_id=agente.id, motivo="No deberia poder crearse",
        )


# ---------------------------------------------------------------------------
# aprobar_cambio_prioridad
# ---------------------------------------------------------------------------

def test_aprobar_cambio_prioridad_valido_usuario_normal():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)  # BAJA
    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
        solicitante_id=agente.id, motivo="Se volvio urgente",
    )

    resultado = ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(solicitud.id, admin.id)

    assert resultado.estado == EstadoSolicitudTransferencia.ACEPTADA, (
        f"se esperaba estado ACEPTADA, se obtuvo {resultado.estado}"
    )

    ticket_actualizado = db.session.get(Ticket, ticket.id)
    assert ticket_actualizado.prioridad == Prioridad.ALTA, (
        f"se esperaba prioridad ALTA tras aprobar, se obtuvo {ticket_actualizado.prioridad}"
    )
    assert ticket_actualizado.agente_id == agente.id, (
        "aprobar un cambio de prioridad no debe tocar el agente asignado, "
        f"se obtuvo agente_id={ticket_actualizado.agente_id}"
    )
    assert ticket_actualizado.estado == EstadoTicket.EN_PROGRESO, (
        "aprobar un cambio de prioridad no debe tocar el estado del ticket, "
        f"se obtuvo {ticket_actualizado.estado}"
    )

    horas_hasta_limite = (ticket_actualizado.fecha_limite - datetime.now()).total_seconds() / 3600
    assert 3.5 <= horas_hasta_limite <= 4.5, (
        f"creador normal + prioridad ALTA deberia dar ~4h de SLA normal, se obtuvo {horas_hasta_limite:.2f}h"
    )


def test_aprobar_cambio_prioridad_valido_usuario_vip_usa_sla_vip():
    """Prueba de regresion: si el bug de usuario.rol vs usuario.nivel
    volviera a aparecer, este test falla porque el SLA le saldria calculado
    como normal (~24h) en vez de vip (~4.5h)."""
    vip = Usuario.query.filter_by(email=EMAIL_VIP).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(vip, agente)
    assert ticket.prioridad == Prioridad.ALTA, (
        f"precondicion: un creador VIP deberia elevar la prioridad a ALTA desde la creacion, se obtuvo {ticket.prioridad}"
    )

    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.MEDIA,
        solicitante_id=agente.id, motivo="Se puede bajar, no es tan critico",
    )

    ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(solicitud.id, admin.id)

    ticket_actualizado = db.session.get(Ticket, ticket.id)
    assert ticket_actualizado.prioridad == Prioridad.MEDIA, (
        f"se esperaba prioridad MEDIA tras aprobar, se obtuvo {ticket_actualizado.prioridad}"
    )

    horas_hasta_limite = (ticket_actualizado.fecha_limite - datetime.now()).total_seconds() / 3600
    assert 4.0 <= horas_hasta_limite <= 5.0, (
        f"creador VIP + prioridad MEDIA deberia dar ~4.5h de SLA vip (no ~24h de SLA normal), "
        f"se obtuvo {horas_hasta_limite:.2f}h"
    )


def test_aprobar_cambio_prioridad_inexistente():
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    with pytest.raises(SolicitudNoEncontradaError):
        ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(999999, admin.id)


def test_aprobar_cambio_prioridad_ya_resuelto():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
        solicitante_id=agente.id, motivo="Se volvio urgente",
    )
    ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(solicitud.id, admin.id)

    with pytest.raises(SolicitudNoPendienteError):
        ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(solicitud.id, admin.id)


def test_aprobar_cambio_prioridad_ticket_ya_no_en_progreso():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
        solicitante_id=agente.id, motivo="Se volvio urgente",
    )

    ticket.estado = EstadoTicket.CERRADO
    db.session.add(ticket)
    db.session.commit()

    with pytest.raises(TicketNoEnProgresoError):
        ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(solicitud.id, admin.id)


# ---------------------------------------------------------------------------
# rechazar_cambio_prioridad
# ---------------------------------------------------------------------------

def test_rechazar_cambio_prioridad_valido():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)  # BAJA
    fecha_limite_original = ticket.fecha_limite

    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
        solicitante_id=agente.id, motivo="Se volvio urgente",
    )

    resultado = ServicioSolicitudesTransferencia.rechazar_cambio_prioridad(solicitud.id, admin.id)

    assert resultado.estado == EstadoSolicitudTransferencia.RECHAZADA, (
        f"se esperaba estado RECHAZADA, se obtuvo {resultado.estado}"
    )

    ticket_sin_cambios = db.session.get(Ticket, ticket.id)
    assert ticket_sin_cambios.prioridad == Prioridad.BAJA, (
        "rechazar un cambio de prioridad no debe modificar la prioridad del ticket, "
        f"se obtuvo {ticket_sin_cambios.prioridad}"
    )
    assert ticket_sin_cambios.fecha_limite == fecha_limite_original, (
        "rechazar un cambio de prioridad no debe recalcular el SLA"
    )


def test_rechazar_cambio_prioridad_ya_resuelto():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    solicitud = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket.id, prioridad_destino=Prioridad.ALTA,
        solicitante_id=agente.id, motivo="Se volvio urgente",
    )
    ServicioSolicitudesTransferencia.rechazar_cambio_prioridad(solicitud.id, admin.id)

    with pytest.raises(SolicitudNoPendienteError):
        ServicioSolicitudesTransferencia.rechazar_cambio_prioridad(solicitud.id, admin.id)


# ---------------------------------------------------------------------------
# listar_cambios_prioridad_pendientes
# ---------------------------------------------------------------------------

def test_listar_cambios_prioridad_pendientes():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    # 1. Un cambio de prioridad pendiente -- SI debe aparecer
    ticket_pendiente = _crear_ticket_en_progreso(normal, agente)
    cambio_pendiente = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket_pendiente.id, prioridad_destino=Prioridad.ALTA,
        solicitante_id=agente.id, motivo="Pendiente de revisar",
    )

    # 2. Un cambio de prioridad ya aprobado -- NO debe aparecer
    ticket_resuelto = _crear_ticket_en_progreso(normal, agente)
    cambio_resuelto = ServicioSolicitudesTransferencia.cambiar_prioridad(
        ticket_id=ticket_resuelto.id, prioridad_destino=Prioridad.MEDIA,
        solicitante_id=agente.id, motivo="Ya resuelto",
    )
    ServicioSolicitudesTransferencia.aprobar_cambio_prioridad(cambio_resuelto.id, admin.id)

    # 3. Un escalamiento de area pendiente -- NO debe aparecer aqui, tiene
    #    su propia lista (listar_escalamientos_pendientes)
    ticket_escalamiento = _crear_ticket_en_progreso(normal, agente)
    escalamiento = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket_escalamiento.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="Es de red",
    )

    pendientes = ServicioSolicitudesTransferencia.listar_cambios_prioridad_pendientes()
    ids_pendientes = {s.id for s in pendientes}

    assert cambio_pendiente.id in ids_pendientes, (
        "el cambio de prioridad PENDIENTE deberia aparecer en el listado"
    )
    assert cambio_resuelto.id not in ids_pendientes, (
        "un cambio de prioridad ya ACEPTADO no deberia aparecer en pendientes"
    )
    assert escalamiento.id not in ids_pendientes, (
        "un escalamiento de area no deberia aparecer en la lista de cambios "
        "de prioridad, aunque este PENDIENTE"
    )