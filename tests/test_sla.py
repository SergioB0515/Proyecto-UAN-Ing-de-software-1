"""
Pruebas de GestorSLA.verificar_vencimientos()

Nota de migracion: la contraseña de prueba paso de "ClaveSegura123" a
"ClaveSegura123!" porque validar_politica_contrasena ahora exige un simbolo
(registrar() fallaba con ValueError antes de llegar a nada de lo que prueba
este archivo).
"""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.gestor_sla import GestorSLA
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.notificacion import Notificacion
from app.models.enum import RolUsuario, NivelUsuario, Categoria, Prioridad, EstadoTicket


EMAIL_NORMAL = "prueba_sla_normal@empresa.com"
EMAIL_ADMIN_PRUEBA = "prueba_admin_sla@empresa.com"


@pytest.fixture(scope="module")
def usuario_normal():
    for email in (EMAIL_NORMAL, EMAIL_ADMIN_PRUEBA):
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            db.session.delete(usuario_existente)
    db.session.commit()

    admin_prueba = Usuario(
        nombre="Admin Prueba SLA",
        email=EMAIL_ADMIN_PRUEBA,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN,
        nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin_prueba)
    db.session.commit()

    return ServicioAutenticacion.registrar(
        nombre="Usuario SLA Prueba",
        email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!",
        rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL,
        admin_id=admin_prueba.id,
    )


def test_verificar_vencimientos(usuario_normal):
    ahora = datetime.now()

    ticket_vencido = Ticket(
        texto="ticket vencido de prueba",
        categoria=Categoria.SOFTWARE,
        prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.ABIERTO,
        creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(hours=30),
        fecha_limite=ahora - timedelta(hours=6),
    )

    ticket_proximo = Ticket(
        texto="ticket proximo a vencer de prueba",
        categoria=Categoria.SOFTWARE,
        prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.EN_PROGRESO,
        creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(hours=18),
        fecha_limite=ahora + timedelta(hours=2),
    )

    ticket_a_salvo = Ticket(
        texto="ticket a salvo de prueba",
        categoria=Categoria.SOFTWARE,
        prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.ABIERTO,
        creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(hours=4),
        fecha_limite=ahora + timedelta(hours=16),
    )

    db.session.add_all([ticket_vencido, ticket_proximo, ticket_a_salvo])
    db.session.commit()

    vencidos, proximos_a_vencer = GestorSLA.verificar_vencimientos()

    ids_vencidos = [t.id for t in vencidos]
    ids_proximos = [t.id for t in proximos_a_vencer]

    assert ticket_vencido.id in ids_vencidos, "el ticket vencido no aparecio en la lista de vencidos"
    assert ticket_proximo.id in ids_proximos, "el ticket proximo a vencer no aparecio en la lista de proximos"
    assert ticket_a_salvo.id not in ids_vencidos and ticket_a_salvo.id not in ids_proximos, (
        "el ticket a salvo no deberia aparecer en ninguna lista"
    )
    assert ticket_vencido.id not in ids_proximos, (
        "el ticket vencido no deberia aparecer tambien en proximos_a_vencer"
    )


def test_verificar_vencimientos_no_truena_con_ventana_cero(usuario_normal):
    """fecha_limite == fecha_creacion (datos raros) no debe provocar
    ZeroDivisionError; el ticket ya pasado se clasifica como vencido."""
    ahora = datetime.now()

    ticket_raro = Ticket(
        texto="ticket con ventana de SLA de cero",
        categoria=Categoria.SOFTWARE,
        prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.ABIERTO,
        creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(hours=1),
        fecha_limite=ahora - timedelta(hours=1),
    )
    db.session.add(ticket_raro)
    db.session.commit()

    vencidos, proximos = GestorSLA.verificar_vencimientos()

    assert ticket_raro.id in [t.id for t in vencidos]
    assert ticket_raro.id not in [t.id for t in proximos]


def test_verificar_y_notificar_vencimientos_crea_notificacion_una_sola_vez(usuario_normal):
    ahora = datetime.now()

    ticket = Ticket(
        texto="ticket para notificar vencimiento",
        categoria=Categoria.SOFTWARE,
        prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.ABIERTO,
        creador_id=usuario_normal.id,
        fecha_creacion=ahora - timedelta(hours=30),
        fecha_limite=ahora - timedelta(hours=6),
    )
    db.session.add(ticket)
    db.session.commit()

    db.session.query(Notificacion).filter(
        Notificacion.usuario_id == usuario_normal.id
    ).delete()
    db.session.commit()

    GestorSLA.verificar_y_notificar_vencimientos()

    notificaciones = (
        db.session.query(Notificacion)
        .filter(Notificacion.ticket_id == ticket.id)
        .all()
    )
    assert len(notificaciones) == 1, "deberia crearse exactamente una notificacion de vencido"
    assert "vencido" in notificaciones[0].mensaje.lower()
    assert ticket.notificado_vencido is True

    # Segunda pasada: la bandera evita duplicados.
    GestorSLA.verificar_y_notificar_vencimientos()

    notificaciones = (
        db.session.query(Notificacion)
        .filter(Notificacion.ticket_id == ticket.id)
        .all()
    )
    assert len(notificaciones) == 1, "no debe duplicar la notificacion en pasadas siguientes"
