from datetime import datetime

import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoEnProgresoError,
    SolicitudDuplicadaError, SolicitudNoEncontradaError,
    SolicitudNoPendienteError, AgenteDestinoInvalidoError,
)
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.transferencia import SolicitudTransferencia
from app.models.enum import (
    RolUsuario, NivelUsuario, Categoria, EstadoTicket, EstadoSolicitudTransferencia,
)


EMAIL_ADMIN = "prueba_solicitudes_admin@empresa.com"
EMAIL_NORMAL = "prueba_solicitudes_normal@empresa.com"
EMAIL_AGENTE_ORIGEN = "prueba_solicitudes_agente_origen@empresa.com"
EMAIL_AGENTE_DESTINO = "prueba_solicitudes_agente_destino@empresa.com"
EMAIL_AGENTE_OTRA_AREA = "prueba_solicitudes_agente_otra_area@empresa.com"

TEXTO_TICKET_PERMISOS = "no puedo entrar a mi correo"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL, EMAIL_AGENTE_ORIGEN,
                  EMAIL_AGENTE_DESTINO, EMAIL_AGENTE_OTRA_AREA):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba Solicitudes",
        email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Solicitudes",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Origen",
        email=EMAIL_AGENTE_ORIGEN,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
        area_soporte=Categoria.PERMISOS,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Destino",
        email=EMAIL_AGENTE_DESTINO,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
        area_soporte=Categoria.PERMISOS,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Otra Area",
        email=EMAIL_AGENTE_OTRA_AREA,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
        area_soporte=Categoria.REDES,
    )


def _crear_ticket_en_progreso(creador, agente):
    ticket = ServicioTickets.crear_ticket(creador=creador, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id,
        nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id,
        agente_id=agente.id,
    )
    return ticket


def test_crear_solicitud_valida():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)

    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id,
        agente_destino_id=destino.id,
        solicitante_id=origen.id,
        motivo="Me voy de vacaciones",
    )

    assert solicitud is not None, "se esperaba que la solicitud se creara exitosamente"
    assert solicitud.estado == EstadoSolicitudTransferencia.PENDIENTE, (
        f"se esperaba estado PENDIENTE, se obtuvo {solicitud.estado}"
    )
    assert solicitud.agente_origen_id == origen.id and solicitud.agente_destino_id == destino.id, (
        f"origen/destino no coinciden: origen={solicitud.agente_origen_id}, "
        f"destino={solicitud.agente_destino_id}"
    )


def test_crear_solicitud_ticket_inexistente():
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    with pytest.raises(TicketNoEncontradoError):
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=999999,
            agente_destino_id=destino.id,
            solicitante_id=origen.id,
        )


def test_crear_solicitud_ticket_no_en_progreso():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)

    with pytest.raises(TicketNoEnProgresoError):
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket.id,
            agente_destino_id=destino.id,
            solicitante_id=origen.id,
        )


def test_crear_solicitud_duplicada():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)

    ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )

    with pytest.raises(SolicitudDuplicadaError):
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
        )


def test_crear_solicitud_agente_destino_inexistente():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()

    ticket = _crear_ticket_en_progreso(normal, origen)

    with pytest.raises(AgenteDestinoInvalidoError):
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket.id, agente_destino_id=999999, solicitante_id=origen.id,
        )


def test_crear_solicitud_destino_no_es_agente():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()

    ticket = _crear_ticket_en_progreso(normal, origen)

    with pytest.raises(AgenteDestinoInvalidoError):
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket.id, agente_destino_id=normal.id, solicitante_id=origen.id,
        )


def test_crear_solicitud_destino_otra_area():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    otra_area = Usuario.query.filter_by(email=EMAIL_AGENTE_OTRA_AREA).first()

    ticket = _crear_ticket_en_progreso(normal, origen)

    with pytest.raises(AgenteDestinoInvalidoError):
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket.id, agente_destino_id=otra_area.id, solicitante_id=origen.id,
        )


def test_crear_solicitud_auto_transferencia():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()

    ticket = _crear_ticket_en_progreso(normal, origen)

    with pytest.raises(AgenteDestinoInvalidoError):
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket.id, agente_destino_id=origen.id, solicitante_id=origen.id,
        )


def test_aceptar_solicitud_valida():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )

    resultado = ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud.id, destino.id)

    assert resultado.estado == EstadoSolicitudTransferencia.ACEPTADA, (
        f"se esperaba estado ACEPTADA, se obtuvo {resultado.estado}"
    )
    assert resultado.fecha_resolucion is not None, "se esperaba fecha_resolucion seteada"

    ticket_actualizado = db.session.get(Ticket, ticket.id)
    assert ticket_actualizado.agente_id == destino.id, (
        f"se esperaba que el ticket quedara con agente_id={destino.id}, "
        f"se obtuvo {ticket_actualizado.agente_id}"
    )


def test_aceptar_solicitud_inexistente():
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    with pytest.raises(SolicitudNoEncontradaError):
        ServicioSolicitudesTransferencia.aceptar_solicitud(999999, destino.id)


def test_aceptar_solicitud_ya_resuelta():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )
    ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud.id, destino.id)

    with pytest.raises(SolicitudNoPendienteError):
        ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud.id, destino.id)


def test_aceptar_solicitud_ticket_ya_no_en_progreso():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )

    ticket.estado = EstadoTicket.CERRADO
    db.session.add(ticket)
    db.session.commit()

    with pytest.raises(TicketNoEnProgresoError):
        ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud.id, destino.id)


def test_rechazar_solicitud_valida():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )

    resultado = ServicioSolicitudesTransferencia.rechazar_solicitud(solicitud.id, destino.id)

    assert resultado.estado == EstadoSolicitudTransferencia.RECHAZADA, (
        f"se esperaba estado RECHAZADA, se obtuvo {resultado.estado}"
    )

    ticket_sin_cambios = db.session.get(Ticket, ticket.id)
    assert ticket_sin_cambios.agente_id == origen.id, (
        "rechazar una solicitud no debe modificar el agente del ticket, "
        f"se obtuvo agente_id={ticket_sin_cambios.agente_id}"
    )


def test_rechazar_solicitud_inexistente():
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    with pytest.raises(SolicitudNoEncontradaError):
        ServicioSolicitudesTransferencia.rechazar_solicitud(999999, destino.id)


def test_rechazar_solicitud_ya_resuelta():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )
    ServicioSolicitudesTransferencia.rechazar_solicitud(solicitud.id, destino.id)

    with pytest.raises(SolicitudNoPendienteError):
        ServicioSolicitudesTransferencia.rechazar_solicitud(solicitud.id, destino.id)


def test_cancelar_solicitud_valida():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )

    resultado = ServicioSolicitudesTransferencia.cancelar_solicitud(solicitud.id, origen.id)

    assert resultado.estado == EstadoSolicitudTransferencia.CANCELADA, (
        f"se esperaba estado CANCELADA, se obtuvo {resultado.estado}"
    )


def test_cancelar_solicitud_ya_resuelta():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket = _crear_ticket_en_progreso(normal, origen)
    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )
    ServicioSolicitudesTransferencia.cancelar_solicitud(solicitud.id, origen.id)

    with pytest.raises(SolicitudNoPendienteError):
        ServicioSolicitudesTransferencia.cancelar_solicitud(solicitud.id, origen.id)


def test_listar_pendientes_para_agente():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    origen = Usuario.query.filter_by(email=EMAIL_AGENTE_ORIGEN).first()
    destino = Usuario.query.filter_by(email=EMAIL_AGENTE_DESTINO).first()

    ticket_pendiente = _crear_ticket_en_progreso(normal, origen)
    solicitud_pendiente = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket_pendiente.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )

    ticket_resuelto = _crear_ticket_en_progreso(normal, origen)
    solicitud_resuelta = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket_resuelto.id, agente_destino_id=destino.id, solicitante_id=origen.id,
    )
    ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud_resuelta.id, destino.id)

    pendientes = ServicioSolicitudesTransferencia.listar_pendientes_para_agente(destino.id)
    ids_pendientes = {s.id for s in pendientes}

    assert solicitud_pendiente.id in ids_pendientes, (
        "la solicitud PENDIENTE del agente destino deberia aparecer en el listado"
    )
    assert solicitud_resuelta.id not in ids_pendientes, (
        "una solicitud ya ACEPTADA no deberia aparecer en pendientes"
    )