"""
Pruebas de sincronizacion de Ticket.fecha_asignacion en los 5 puntos donde
agente_id cambia:
1. cambiar_estado -> EN_PROGRESO (toma/asignacion inicial)
2. reasignar_agente (admin reasigna directo)
3. aceptar_solicitud (transferencia agente-a-agente, tipo REASIGNACION)
4. aprobar_escalamiento (limpia agente al escalar de area)
5. aceptar_apelacion (limpia agente al reabrir por apelacion)
"""
import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.services.apelacion import ServicioApelaciones
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket

EMAIL_ADMIN = "prueba_fecha_asignacion_admin@empresa.com"
EMAIL_NORMAL = "prueba_fecha_asignacion_normal@empresa.com"
EMAIL_AGENTE_1 = "prueba_fecha_asignacion_agente1@empresa.com"
EMAIL_AGENTE_2 = "prueba_fecha_asignacion_agente2@empresa.com"

TEXTO_TICKET_PERMISOS = "no puedo entrar a mi correo"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL, EMAIL_AGENTE_1, EMAIL_AGENTE_2):
        u = Usuario.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
    db.session.commit()

    admin = Usuario(
        nombre="Admin Prueba Fecha Asignacion",
        email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Fecha Asignacion", email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!", rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente 1 Fecha Asignacion", email=EMAIL_AGENTE_1,
        contrasena="ClaveSegura123!", rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
        area_soporte=Categoria.PERMISOS,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente 2 Fecha Asignacion", email=EMAIL_AGENTE_2,
        contrasena="ClaveSegura123!", rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
        area_soporte=Categoria.PERMISOS,
    )


def test_cambiar_estado_en_progreso_pone_fecha_asignacion():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_1).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    assert ticket.fecha_asignacion is None, "un ticket recien creado no debe tener fecha_asignacion"

    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )
    db.session.refresh(ticket)
    assert ticket.fecha_asignacion is not None, (
        "al pasar a EN_PROGRESO con agente_id, fecha_asignacion debe quedar poblada"
    )


def test_reasignar_agente_actualiza_fecha_asignacion():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE_1).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_2).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente_1.id, agente_id=agente_1.id,
    )
    db.session.refresh(ticket)
    fecha_original = ticket.fecha_asignacion
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    ServicioTickets.reasignar_agente(
        ticket_id=ticket.id, nuevo_agente_id=agente_2.id, actor_id=admin.id,
    )
    db.session.refresh(ticket)
    assert ticket.fecha_asignacion is not None
    assert ticket.fecha_asignacion != fecha_original, (
        "reasignar_agente debe actualizar fecha_asignacion, no dejar la del agente anterior"
    )


def test_aceptar_solicitud_transferencia_actualiza_fecha_asignacion():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE_1).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_2).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente_1.id, agente_id=agente_1.id,
    )
    db.session.refresh(ticket)
    fecha_original = ticket.fecha_asignacion

    solicitud = ServicioSolicitudesTransferencia.crear_solicitud(
        ticket_id=ticket.id, agente_destino_id=agente_2.id,
        solicitante_id=agente_1.id, motivo="me voy de vacaciones",
    )
    ServicioSolicitudesTransferencia.aceptar_solicitud(solicitud.id, agente_2.id)

    db.session.refresh(ticket)
    assert ticket.agente_id == agente_2.id
    assert ticket.fecha_asignacion is not None
    assert ticket.fecha_asignacion != fecha_original, (
        "aceptar una transferencia debe actualizar fecha_asignacion al nuevo agente"
    )


def test_aprobar_escalamiento_limpia_fecha_asignacion():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_1).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )
    db.session.refresh(ticket)
    assert ticket.fecha_asignacion is not None

    solicitud = ServicioSolicitudesTransferencia.escalar_a_area(
        ticket_id=ticket.id, area_destino=Categoria.REDES,
        solicitante_id=agente.id, motivo="es de red, no de permisos",
    )
    ServicioSolicitudesTransferencia.aprobar_escalamiento(solicitud.id, admin.id)

    db.session.refresh(ticket)
    assert ticket.agente_id is None
    assert ticket.fecha_asignacion is None, (
        "al aprobar un escalamiento, fecha_asignacion debe limpiarse junto con agente_id"
    )


def test_aceptar_apelacion_limpia_fecha_asignacion():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_1).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.CERRADO, actor_id=agente.id,
    )
    db.session.refresh(ticket)
    assert ticket.fecha_asignacion is not None

    apelacion = ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket.id, solicitante_id=normal.id, motivo="no resolvieron nada",
    )
    ServicioApelaciones.aceptar_apelacion(apelacion_id=apelacion.id, actor_id=admin.id)

    db.session.refresh(ticket)
    assert ticket.agente_id is None
    assert ticket.fecha_asignacion is None, (
        "al aceptar una apelacion, fecha_asignacion debe limpiarse junto con agente_id"
    )
    
def test_reabrir_mismo_agente_si_actualiza_fecha_asignacion():
    """Decision de diseño explicita: reabrir un ticket resetea
    fecha_asignacion igual que resetea fecha_cierre, incluso si es
    el mismo agente que ya lo tenia -- una reapertura es un ciclo de
    trabajo nuevo, no continuacion del anterior. No debe agregarse un
    guard tipo AgenteYaAsignadoError aqui (a diferencia de
    reasignar_agente, donde si tiene sentido)."""
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE_1).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PERMISOS)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.CERRADO, actor_id=agente.id,
    )
    db.session.refresh(ticket)
    fecha_cierre_ciclo = ticket.fecha_asignacion

    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,  # mismo agente reabriendo
    )
    db.session.refresh(ticket)
    assert ticket.agente_id == agente.id
    assert ticket.fecha_asignacion != fecha_cierre_ciclo, (
        "reabrir debe actualizar fecha_asignacion incluso con el mismo agente"
    )