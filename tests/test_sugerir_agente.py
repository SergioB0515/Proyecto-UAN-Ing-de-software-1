from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, func

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.metricas import ServicioMetricas
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket, Prioridad

EMAIL_ADMIN = "prueba_sugerir_agente_admin@empresa.com"
EMAIL_NORMAL = "prueba_sugerir_agente_normal@empresa.com"

CATEGORIA_PRUEBA = Categoria.CUENTAS_CONTRASENAS


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL):
        u = Usuario.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
    db.session.commit()

    admin = Usuario(
        nombre="Admin Prueba Sugerir Agente", email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN, nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Sugerir Agente", email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!", rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
    )


def _crear_agente(sufijo, categoria):
    email = f"prueba_sugerir_agente_{sufijo}@empresa.com"
    agente = Usuario(
        nombre=f"Agente Sugerir {sufijo}", email=email,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.AGENTE, nivel=NivelUsuario.NORMAL, area_soporte=categoria,
    )
    db.session.add(agente)
    db.session.commit()
    return agente


def _crear_ticket_en_progreso(agente_id, creador_id, categoria):
    ticket = Ticket(
        texto="ticket en progreso prueba sugerir agente",
        categoria=categoria, prioridad=Prioridad.BAJA,
        estado=EstadoTicket.EN_PROGRESO,
        creador_id=creador_id, agente_id=agente_id,
        fecha_creacion=datetime.now(), fecha_asignacion=datetime.now(),
        fecha_limite=datetime.now() + timedelta(days=3),
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def _crear_ticket_cerrado_a_tiempo(agente_id, creador_id, categoria):
    ahora = datetime.now()
    ticket = Ticket(
        texto="ticket cerrado a tiempo prueba sugerir agente",
        categoria=categoria, prioridad=Prioridad.BAJA,
        estado=EstadoTicket.CERRADO,
        creador_id=creador_id, agente_id=agente_id,
        fecha_creacion=ahora - timedelta(days=2),
        fecha_asignacion=ahora - timedelta(days=2),
        fecha_limite=ahora - timedelta(days=1),
        fecha_cierre=ahora - timedelta(days=1, hours=1),
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def test_sin_agentes_en_el_area_devuelve_none():
    existentes = db.session.execute(
        select(func.count()).select_from(Usuario).where(
            Usuario.rol == RolUsuario.AGENTE, Usuario.area_soporte == Categoria.OTROS
        )
    ).scalar()
    if existentes > 0:
        pytest.skip(
            f"Categoria.OTROS ya tiene {existentes} agente(s) de otro archivo de prueba -- "
            "este test necesita un area realmente vacia para ser valido"
        )
    assert ServicioMetricas.sugerir_agente(Categoria.OTROS) is None


def test_menor_carga_gana_aunque_el_otro_tenga_buen_historial():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    agente_libre = _crear_agente("libre", CATEGORIA_PRUEBA)
    agente_ocupado = _crear_agente("ocupado", CATEGORIA_PRUEBA)

    _crear_ticket_cerrado_a_tiempo(agente_libre.id, normal.id, CATEGORIA_PRUEBA)

    for _ in range(3):
        _crear_ticket_en_progreso(agente_ocupado.id, normal.id, CATEGORIA_PRUEBA)
    _crear_ticket_cerrado_a_tiempo(agente_ocupado.id, normal.id, CATEGORIA_PRUEBA)

    resultado = ServicioMetricas.sugerir_agente(CATEGORIA_PRUEBA)

    assert resultado is not None
    assert resultado.id == agente_libre.id, (
        f"se esperaba que ganara el agente sin carga, gano el id {resultado.id}"
    )


def test_carga_empatada_desempata_por_cumplimiento():
    CATEGORIA_AISLADA = Categoria.SOFTWARE

    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()

    agente_bueno = _crear_agente("bueno2", CATEGORIA_AISLADA)
    agente_malo = _crear_agente("malo2", CATEGORIA_AISLADA)

    _crear_ticket_cerrado_a_tiempo(agente_bueno.id, normal.id, CATEGORIA_AISLADA)
    _crear_ticket_cerrado_a_tiempo(agente_bueno.id, normal.id, CATEGORIA_AISLADA)

    resultado = ServicioMetricas.sugerir_agente(CATEGORIA_AISLADA)

    assert resultado is not None
    assert resultado.id == agente_bueno.id, (
        f"se esperaba que ganara el agente con mejor cumplimiento, gano el id {resultado.id}"
    )