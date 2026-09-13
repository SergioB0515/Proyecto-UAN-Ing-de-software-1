"""
Pruebas de ServicioApelaciones -- apelacion de cierre de tickets (v2.1)

Que verifica:
1-5.   solicitar_apelacion: caso valido, ticket inexistente, ticket no
       cerrado (abierto), ticket no cerrado (en progreso), motivo vacio,
       apelacion duplicada (ya hay una pendiente sobre el mismo ticket).
6-8.   aceptar_apelacion: caso valido -- el ticket vuelve a ABIERTO SIN
       agente asignado (no el mismo que lo cerro, para evitar que el
       usuario que apelo vuelva a toparse con quien descarto su caso),
       apelacion inexistente, apelacion ya resuelta.
9-10.  rechazar_apelacion: caso valido -- el ticket se queda EXACTAMENTE
       como estaba (CERRADO, con su agente original intacto), apelacion
       ya resuelta.
11.    listar_pendientes: solo trae apelaciones PENDIENTE, nunca
       ACEPTADA ni RECHAZADA.

Nota: estas pruebas cubren ServicioApelaciones directamente, sin pasar
por Flask ni por las rutas -- mismo alcance que el resto de la suite
(test_escalamientos.py, test_solicitudes.py, etc). El bug real que
encontramos en esta sesion (la ruta "rechazar" llamando por error a
aceptar_apelacion()) vivia en app/routes/apelacion.py, NO en el
servicio -- un test de servicio como este nunca lo habria atrapado,
porque nunca ejecuta el codigo de la ruta. Detectar ese tipo de bug
requeriria un test de integracion con app.test_client() haciendo un
POST real a /apelaciones/<id>/rechazar, que este proyecto no usa en
ningun archivo de tests existente. test_rechazar_apelacion_valido si
sirve para blindar el SERVICIO contra una regresion futura si alguien
vuelve a mezclar aceptar/rechazar ahi adentro.
"""
import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.tickets import ServicioTickets
from app.services.apelacion import ServicioApelaciones
from app.services.exceptions import (
    TicketNoEncontradoError, TicketNoCerradoError, MotivoRequeridoError,
    ApelacionDuplicadaError, ApelacionNoEncontradaError, ApelacionNoPendienteError,
)
from app.models.usuario import Usuario
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket, EstadoApelacion


EMAIL_ADMIN = "prueba_apelaciones_admin@empresa.com"
EMAIL_NORMAL = "prueba_apelaciones_normal@empresa.com"
EMAIL_AGENTE = "prueba_apelaciones_agente@empresa.com"

TEXTO_TICKET_PRUEBA = "no puedo entrar a mi correo"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL, EMAIL_AGENTE):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba Apelaciones",
        email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Apelaciones",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente Apelaciones",
        email=EMAIL_AGENTE,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
        area_soporte=Categoria.PERMISOS,
    )


def _crear_ticket_cerrado_con_agente(creador, agente):
    """Helper local: crea un ticket, lo lleva a EN_PROGRESO con `agente`
    como responsable, y lo cierra. Simula el caso real que motiva esta
    feature: un agente cerro el ticket y el usuario no esta de acuerdo."""
    ticket = ServicioTickets.crear_ticket(creador=creador, texto=TEXTO_TICKET_PRUEBA)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.CERRADO, actor_id=agente.id,
    )
    return ticket


# ---------------------------------------------------------------------------
# solicitar_apelacion
# ---------------------------------------------------------------------------

def test_solicitar_apelacion_valido():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = _crear_ticket_cerrado_con_agente(normal, agente)

    apelacion = ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket.id, solicitante_id=normal.id,
        motivo="El agente cerro esto sin revisar el problema real",
    )

    assert apelacion is not None, "se esperaba que la apelacion se creara exitosamente"
    assert apelacion.estado == EstadoApelacion.PENDIENTE, (
        f"se esperaba estado PENDIENTE, se obtuvo {apelacion.estado}"
    )
    assert apelacion.ticket_id == ticket.id
    assert apelacion.solicitante_id == normal.id


def test_solicitar_apelacion_ticket_inexistente():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    with pytest.raises(TicketNoEncontradoError):
        ServicioApelaciones.solicitar_apelacion(
            ticket_id=999999, solicitante_id=normal.id, motivo="motivo cualquiera",
        )


def test_solicitar_apelacion_ticket_abierto():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PRUEBA)
    # queda ABIERTO, nunca paso por cambiar_estado

    with pytest.raises(TicketNoCerradoError):
        ServicioApelaciones.solicitar_apelacion(
            ticket_id=ticket.id, solicitante_id=normal.id, motivo="motivo cualquiera",
        )


def test_solicitar_apelacion_ticket_en_progreso():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = ServicioTickets.crear_ticket(creador=normal, texto=TEXTO_TICKET_PRUEBA)
    ServicioTickets.cambiar_estado(
        ticket_id=ticket.id, nuevo_estado=EstadoTicket.EN_PROGRESO,
        actor_id=agente.id, agente_id=agente.id,
    )

    with pytest.raises(TicketNoCerradoError):
        ServicioApelaciones.solicitar_apelacion(
            ticket_id=ticket.id, solicitante_id=normal.id, motivo="motivo cualquiera",
        )


def test_solicitar_apelacion_motivo_vacio():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = _crear_ticket_cerrado_con_agente(normal, agente)

    with pytest.raises(MotivoRequeridoError):
        ServicioApelaciones.solicitar_apelacion(
            ticket_id=ticket.id, solicitante_id=normal.id, motivo="   ",
        )


def test_solicitar_apelacion_duplicada():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()

    ticket = _crear_ticket_cerrado_con_agente(normal, agente)

    ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket.id, solicitante_id=normal.id, motivo="primera apelacion",
    )

    with pytest.raises(ApelacionDuplicadaError):
        ServicioApelaciones.solicitar_apelacion(
            ticket_id=ticket.id, solicitante_id=normal.id, motivo="segunda apelacion",
        )


# ---------------------------------------------------------------------------
# aceptar_apelacion
# ---------------------------------------------------------------------------

def test_aceptar_apelacion_valido():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_cerrado_con_agente(normal, agente)
    apelacion = ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket.id, solicitante_id=normal.id, motivo="no me resolvieron nada",
    )

    ticket_actualizado = ServicioApelaciones.aceptar_apelacion(
        apelacion_id=apelacion.id, actor_id=admin.id,
    )

    assert ticket_actualizado.estado == EstadoTicket.ABIERTO, (
        f"se esperaba que el ticket volviera a ABIERTO, quedo en {ticket_actualizado.estado}"
    )
    assert ticket_actualizado.agente_id is None, (
        "se esperaba que el ticket quedara SIN agente asignado al reabrirse "
        "(para no devolverselo al mismo agente que lo cerro), pero "
        f"agente_id quedo en {ticket_actualizado.agente_id}"
    )
    assert ticket_actualizado.fecha_cierre is None
    assert ticket_actualizado.notificado_proximo_vencer is False
    assert ticket_actualizado.notificado_vencido is False

    db.session.refresh(apelacion)
    assert apelacion.estado == EstadoApelacion.ACEPTADA
    assert apelacion.resuelto_por_id == admin.id
    assert apelacion.fecha_resolucion is not None


def test_aceptar_apelacion_inexistente():
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    with pytest.raises(ApelacionNoEncontradaError):
        ServicioApelaciones.aceptar_apelacion(apelacion_id=999999, actor_id=admin.id)


def test_aceptar_apelacion_ya_resuelta():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_cerrado_con_agente(normal, agente)
    apelacion = ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket.id, solicitante_id=normal.id, motivo="motivo cualquiera",
    )
    ServicioApelaciones.aceptar_apelacion(apelacion_id=apelacion.id, actor_id=admin.id)

    with pytest.raises(ApelacionNoPendienteError):
        ServicioApelaciones.aceptar_apelacion(apelacion_id=apelacion.id, actor_id=admin.id)


# ---------------------------------------------------------------------------
# rechazar_apelacion
# ---------------------------------------------------------------------------

def test_rechazar_apelacion_valido():
    """Este es el test que habria atrapado el bug de la ruta que llamaba
    a aceptar_apelacion() dentro de rechazar(). Verifica el TICKET
    completo, no solo el estado de la apelacion -- si rechazar()
    reabriera el ticket por error, este assert lo revienta."""
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_cerrado_con_agente(normal, agente)
    apelacion = ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket.id, solicitante_id=normal.id, motivo="motivo cualquiera",
    )

    ServicioApelaciones.rechazar_apelacion(apelacion_id=apelacion.id, actor_id=admin.id)

    db.session.refresh(ticket)
    assert ticket.estado == EstadoTicket.CERRADO, (
        "rechazar una apelacion NO debe reabrir el ticket -- se esperaba "
        f"que siguiera CERRADO, quedo en {ticket.estado}"
    )
    assert ticket.agente_id == agente.id, (
        "rechazar una apelacion no debe tocar el agente del ticket -- se "
        f"esperaba {agente.id}, quedo en {ticket.agente_id}"
    )

    db.session.refresh(apelacion)
    assert apelacion.estado == EstadoApelacion.RECHAZADA, (
        f"se esperaba estado RECHAZADA, se obtuvo {apelacion.estado}"
    )
    assert apelacion.resuelto_por_id == admin.id


def test_rechazar_apelacion_ya_resuelta():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket = _crear_ticket_cerrado_con_agente(normal, agente)
    apelacion = ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket.id, solicitante_id=normal.id, motivo="motivo cualquiera",
    )
    ServicioApelaciones.rechazar_apelacion(apelacion_id=apelacion.id, actor_id=admin.id)

    with pytest.raises(ApelacionNoPendienteError):
        ServicioApelaciones.rechazar_apelacion(apelacion_id=apelacion.id, actor_id=admin.id)


# ---------------------------------------------------------------------------
# listar_pendientes
# ---------------------------------------------------------------------------

def test_listar_pendientes_solo_trae_pendientes():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = Usuario.query.filter_by(email=EMAIL_AGENTE).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()

    ticket_pendiente = _crear_ticket_cerrado_con_agente(normal, agente)
    apelacion_pendiente = ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket_pendiente.id, solicitante_id=normal.id, motivo="sigue pendiente",
    )

    ticket_rechazado = _crear_ticket_cerrado_con_agente(normal, agente)
    apelacion_rechazada = ServicioApelaciones.solicitar_apelacion(
        ticket_id=ticket_rechazado.id, solicitante_id=normal.id, motivo="esta se rechaza",
    )
    ServicioApelaciones.rechazar_apelacion(apelacion_id=apelacion_rechazada.id, actor_id=admin.id)

    pendientes = ServicioApelaciones.listar_pendientes()
    ids_pendientes = {a.id for a in pendientes}

    assert apelacion_pendiente.id in ids_pendientes, (
        "la apelacion PENDIENTE deberia aparecer en listar_pendientes()"
    )
    assert apelacion_rechazada.id not in ids_pendientes, (
        "la apelacion ya RECHAZADA no deberia aparecer en listar_pendientes()"
    )