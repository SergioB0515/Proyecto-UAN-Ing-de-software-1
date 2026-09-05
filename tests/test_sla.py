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
