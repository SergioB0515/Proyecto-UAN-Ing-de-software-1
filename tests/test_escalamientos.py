"""
Pruebas de ServicioSolicitudesTransferencia -- escalamiento entre areas (v1.8)

Que verifica:
1-7.   escalar_a_area: caso valido, ticket inexistente, ticket no en
       progreso, area destino igual a la actual, motivo vacio, solicitud
       duplicada (mismo tipo), solicitud duplicada cruzada contra una
       transferencia normal ya pendiente sobre el mismo ticket.
8-11.  aprobar_escalamiento: caso valido (categoria/agente/estado del
       ticket mutan correctamente), solicitud inexistente, solicitud ya
       resuelta, ticket que dejo de estar en progreso mientras el
       escalamiento seguia pendiente (condicion de carrera simulada).
12-13. rechazar_escalamiento: caso valido (no toca el ticket), ya resuelta.
14.    listar_escalamientos_pendientes: solo trae escalamientos PENDIENTES,
       nunca transferencias normales ni escalamientos ya resueltos.

Nota: "no puedo entrar a mi correo" clasifica como PERMISOS (ver
tests/test_solicitudes.py y tests/test_clasificador.py).
"""
import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoEnProgresoError,
    AreaDestinoInvalidaError, MotivoRequeridoError, SolicitudDuplicadaError,
    SolicitudNoEncontradaError, SolicitudNoPendienteError,
)
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import (
    RolUsuario, NivelUsuario, Categoria, EstadoTicket, EstadoSolicitudTransferencia,
)


EMAIL_ADMIN = "prueba_escalamientos_admin@empresa.com"
EMAIL_NORMAL = "prueba_escalamientos_normal@empresa.com"
EMAIL_AGENTE_PERMISOS = "prueba_escalamientos_agente_permisos@empresa.com"
EMAIL_AGENTE_PERMISOS_2 = "prueba_escalamientos_agente_permisos_2@empresa.com"

TEXTO_TICKET_PERMISOS = "no puedo entrar a mi correo"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL, EMAIL_AGENTE_PERMISOS, EMAIL_AGENTE_PERMISOS_2):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba Escalamientos",
        email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Escalamientos",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Permisos",
        email=EMAIL_AGENTE_PERMISOS,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
        area_soporte=Categoria.PERMISOS,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Permisos 2",
        email=EMAIL_AGENTE_PERMISOS_2,
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
# escalar_a_area
# ---------------------------------------------------------------------------

def test_escalar_a_area_valido():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()

    ticket = _crear_ticket_en_progreso(normal, agente)

    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id,
        area_destino=Categoria.REDES,
        solicitante_id=agente.id,
        motivo="Este problema es de red, no de permisos",
    )

    assert solicitud is not None, "se esperaba que la solicitud se creara exitosamente"
    assert solicitud.estado == EstadoSolicitudTransferencia.PENDIENTE, (
        f"se esperaba estado PENDIENTE, se obtuvo {solicitud.estado}"
    )
    assert solicitud.area_destino == Categoria.REDES, (
        f"se esperaba area_destino REDES, se obtuvo {solicitud.area_destino}"
    )
    assert solicitud.agente_destino_id is None, (
        "un escalamiento no debe tener agente_destino_id, se esperaba None, "
        f"se obtuvo {solicitud.agente_destino_id}"
    )


def test_escalar_a_area_ticket_inexistente():
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()

    with pytest.raises(TicketNoEncontradoError):
        ServicioSolicitudesTransferencia.escalar_a_area(
            ticket_id=999999, area_destino=Categoria.REDES,
            solicitante_id=agente.id, motivo="motivo cualquiera",
        )


def test_escalar_a_area_ticket_no_en_progreso():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    # queda ABIERTO, nunca paso por cambiar_estado

    with pytest.raises(TicketNoEnProgresoError):
        ServicioSolicitudesTransferencia.escalar_a_area(
            ticket_id=ticket.id, area_destino=Categoria.REDES,
            solicitante_id=agente.id, motivo="motivo cualquiera",
        )


def test_escalar_a_area_misma_area():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()

    ticket = _crear_ticket_en_progreso(normal, agente)

    with pytest.raises(AreaDestinoInvalidaError):
        ServicioSolicitudesTransferencia.escalar_a_area(
            ticket_id=ticket.id, area_destino=Categoria.PERMISOS,  # misma area del ticket
            solicitante_id=agente.id, motivo="motivo cualquiera",
        )


def test_escalar_a_area_motivo_vacio():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()

    ticket = _crear_ticket_en_progreso(normal, agente)

    with pytest.raises(MotivoRequeridoError):
        ServicioSolicitudesTransferencia.escalar_a_area(
            ticket_id=ticket.id, area_destino=Categoria.REDES,
            solicitante_id=agente.id, motivo="   ",  # solo espacios
        )


def test_escalar_a_area_duplicada():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()

    ticket = _crear_ticket_en_progreso(normal, agente)

    ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="Primer intento",
    )

    with pytest.raises(SolicitudDuplicadaError):
        ServicioSolicitudesTransferencia.escalar_a_area(
            ticket_id=ticket.id, area_destino=Categoria.SEGURIDAD,
            solicitante_id=agente.id, motivo="Segundo intento",
        )


def test_escalar_a_area_duplicada_contra_transferencia_normal():
    """El chequeo de duplicados es compartido: una transferencia normal
    (v1.7) pendiente sobre un ticket tambien debe bloquear un intento de
    escalamiento (v1.8) sobre ese mismo ticket -- ambos tipos viven en la
    misma tabla y se validan con el mismo criterio (ticket_id + PENDIENTE)."""
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS_2).first()

    ticket = _crear_ticket_en_progreso(normal, agente)

    ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=agente_2.id, solicitante_id=agente.id,
    )

    with pytest.raises(SolicitudDuplicadaError):
        ServicioSolicitudesTransferencia.escalar_a_area(
            ticket_id=ticket.id, area_destino=Categoria.REDES,
            solicitante_id=agente.id, motivo="No deberia poder crearse",
        )


# ---------------------------------------------------------------------------
# aprobar_escalamiento
# ---------------------------------------------------------------------------

def test_aprobar_escalamiento_valido():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="Es un problema de red",
    )

    resultado = ServicioSolicitudesTransferencia.aprobar_escalamiento(solicitud.id, admin.id)

    assert resultado.estado == EstadoSolicitudTransferencia.ACEPTADA, (
        f"se esperaba estado ACEPTADA, se obtuvo {resultado.estado}"
    )

    ticket_actualizado = db.session.get(Ticket, ticket.id)
    assert ticket_actualizado.categoria == Categoria.REDES, (
        f"se esperaba categoria REDES tras aprobar, se obtuvo {ticket_actualizado.categoria}"
    )
    assert ticket_actualizado.agente_id is None, (
        "se esperaba que el ticket quedara sin agente asignado tras el escalamiento, "
        f"se obtuvo agente_id={ticket_actualizado.agente_id}"
    )
    assert ticket_actualizado.estado == EstadoTicket.ABIERTO, (
        f"se esperaba estado ABIERTO tras aprobar, se obtuvo {ticket_actualizado.estado}"
    )


def test_aprobar_escalamiento_inexistente():
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    with pytest.raises(SolicitudNoEncontradaError):
        ServicioSolicitudesTransferencia.aprobar_escalamiento(999999, admin.id)


def test_aprobar_escalamiento_ya_resuelto():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="Es un problema de red",
    )
    ServicioSolicitudesTransferencia.aprobar_escalamiento(solicitud.id, admin.id)

    with pytest.raises(SolicitudNoPendienteError):
        ServicioSolicitudesTransferencia.aprobar_escalamiento(solicitud.id, admin.id)


def test_aprobar_escalamiento_ticket_ya_no_en_progreso():
    """Simula la condicion de carrera: el ticket se cierra (forzado directo
    por SQLAlchemy) mientras el escalamiento seguia PENDIENTE de aprobacion."""
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="Es un problema de red",
    )

    ticket.estado = EstadoTicket.CERRADO
    db.session.add(ticket)
    db.session.commit()

    with pytest.raises(TicketNoEnProgresoError):
        ServicioSolicitudesTransferencia.aprobar_escalamiento(solicitud.id, admin.id)


# ---------------------------------------------------------------------------
# rechazar_escalamiento
# ---------------------------------------------------------------------------

def test_rechazar_escalamiento_valido():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="Es un problema de red",
    )

    resultado = ServicioSolicitudesTransferencia.rechazar_escalamiento(solicitud.id, admin.id)

    assert resultado.estado == EstadoSolicitudTransferencia.RECHAZADA, (
        f"se esperaba estado RECHAZADA, se obtuvo {resultado.estado}"
    )

    ticket_sin_cambios = db.session.get(Ticket, ticket.id)
    assert ticket_sin_cambios.categoria == Categoria.PERMISOS, (
        "rechazar un escalamiento no debe modificar la categoria del ticket, "
        f"se obtuvo {ticket_sin_cambios.categoria}"
    )
    assert ticket_sin_cambios.agente_id == agente.id, (
        "rechazar un escalamiento no debe modificar el agente del ticket, "
        f"se obtuvo agente_id={ticket_sin_cambios.agente_id}"
    )


def test_rechazar_escalamiento_ya_resuelto():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_en_progreso(normal, agente)
    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="Es un problema de red",
    )
    ServicioSolicitudesTransferencia.rechazar_escalamiento(solicitud.id, admin.id)

    with pytest.raises(SolicitudNoPendienteError):
        ServicioSolicitudesTransferencia.rechazar_escalamiento(solicitud.id, admin.id)


# ---------------------------------------------------------------------------
# listar_escalamientos_pendientes
# ---------------------------------------------------------------------------

def test_listar_escalamientos_pendientes():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_PERMISOS_2).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    # 1. Un escalamiento pendiente -- SI debe aparecer
    ticket_pendiente = _crear_ticket_en_progreso(normal, agente)
    escalamiento_pendiente = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket_pendiente.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="Pendiente de revisar",
    )

    # 2. Un escalamiento ya aprobado -- NO debe aparecer
    ticket_resuelto = _crear_ticket_en_progreso(normal, agente)
    escalamiento_resuelto = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket_resuelto.id, area_destino=Categoria.SEGURIDAD,
        solicitante_id=agente.id, motivo="Ya resuelto",
    )
    ServicioSolicitudesTransferencia.aprobar_escalamiento(escalamiento_resuelto.id, admin.id)

    # 3. Una transferencia normal (agente-a-agente) pendiente -- NO debe
    #    aparecer aqui, tiene su propia lista (listar_pendientes_para_agente)
    ticket_transferencia = _crear_ticket_en_progreso(normal, agente)
    transferencia_normal = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket_transferencia.id, agente_destino_id=agente_2.id,
        solicitante_id=agente.id,
    )

    pendientes = ServicioSolicitudesTransferencia.listar_escalamientos_pendientes()
    ids_pendientes = {s.id for s in pendientes}

    assert escalamiento_pendiente.id in ids_pendientes, (
        "el escalamiento PENDIENTE deberia aparecer en el listado"
    )
    assert escalamiento_resuelto.id not in ids_pendientes, (
        "un escalamiento ya ACEPTADO no deberia aparecer en pendientes"
    )
    assert transferencia_normal.id not in ids_pendientes, (
        "una transferencia normal (agente-a-agente) no deberia aparecer en "
        "la lista de escalamientos, aunque este PENDIENTE"
    )