"""
Pruebas de ServicioMetricas.metricas_por_agente

Que verifica:
1. Cuenta correctamente tickets_cerrados dentro de la ventana de dias.
2. Excluye tickets cerrados fuera de la ventana.
3. Calcula tiempo_promedio_resolucion_horas con datos conocidos.
4. Ignora tickets sin fecha_asignacion en el promedio, pero los cuenta
   en tickets_cerrados y en cumplimiento_sla (caso defensivo).
5. Calcula cumplimiento_sla correctamente (mezcla de a tiempo/tarde).
6. Devuelve None en tiempo_promedio y cumplimiento_sla si no hay cerrados.
7. Filtro por area trae a todos los agentes de esa area.
8. Sin agente_id ni area -> ValueError.

Nota de aislamiento: los tests que hacen aritmetica exacta (promedios,
proporciones) usan un agente dedicado via _crear_agente_aislado(), no
EMAIL_AGENTE_1/2 -- la DB de tests es compartida entre funciones del mismo
modulo (fixture scope="module"), y reutilizar un agente entre tests con
aserciones de igualdad exacta arrastra tickets de tests anteriores al
calculo. EMAIL_AGENTE_1/2 solo se usan donde no importa la cifra exacta
(test_filtro_por_area_trae_todos_los_agentes).
"""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.metricas import ServicioMetricas
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket, Prioridad

EMAIL_ADMIN = "prueba_metricas_agente_admin@empresa.com"
EMAIL_NORMAL = "prueba_metricas_agente_normal@empresa.com"
EMAIL_AGENTE_1 = "prueba_metricas_agente_1@empresa.com"
EMAIL_AGENTE_2 = "prueba_metricas_agente_2@empresa.com"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL, EMAIL_AGENTE_1, EMAIL_AGENTE_2):
        u = Usuario.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
    db.session.commit()

    admin = Usuario(
        nombre="Admin Prueba Metricas Agente", email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN, nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Metricas Agente", email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!", rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente 1 Metricas", email=EMAIL_AGENTE_1,
        contrasena="ClaveSegura123!", rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id, area_soporte=Categoria.PERMISOS,
    )
    ServicioAutenticacion.registrar(
        nombre="Agente 2 Metricas", email=EMAIL_AGENTE_2,
        contrasena="ClaveSegura123!", rol=RolUsuario.AGENTE,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id, area_soporte=Categoria.PERMISOS,
    )


def _crear_agente_aislado(sufijo):
    """Agente con email unico por test -- necesario cuando el test hace
    aritmetica exacta (promedios, proporciones) sobre metricas_por_agente,
    ya que la DB de tests es compartida entre funciones del mismo modulo."""
    email = f"prueba_metricas_agente_{sufijo}@empresa.com"
    agente = Usuario(
        nombre=f"Agente Aislado {sufijo}", email=email,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.AGENTE, nivel=NivelUsuario.NORMAL, area_soporte=Categoria.PERMISOS,
    )
    db.session.add(agente)
    db.session.commit()
    return agente


def _crear_ticket_cerrado(agente_id, creador_id, fecha_asignacion, fecha_cierre, fecha_limite):
    """Ticket insertado directo (sin pasar por ServicioTickets) para controlar
    exactamente las fechas -- necesario para probar el calculo de promedios
    y de cumplimiento de SLA con valores conocidos."""
    ticket = Ticket(
        texto="ticket de prueba metricas agente",
        categoria=Categoria.PERMISOS,
        prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.CERRADO,
        creador_id=creador_id,
        agente_id=agente_id,
        fecha_creacion=fecha_asignacion - timedelta(hours=1),
        fecha_asignacion=fecha_asignacion,
        fecha_limite=fecha_limite,
        fecha_cierre=fecha_cierre,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def test_cuenta_solo_dentro_de_la_ventana():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = _crear_agente_aislado("ventana")
    ahora = datetime.now()

    _crear_ticket_cerrado(
        agente.id, normal.id,
        fecha_asignacion=ahora - timedelta(days=5),
        fecha_cierre=ahora - timedelta(days=3),   # dentro de 30 dias
        fecha_limite=ahora - timedelta(days=2),   # cerro a tiempo
    )
    _crear_ticket_cerrado(
        agente.id, normal.id,
        fecha_asignacion=ahora - timedelta(days=60),
        fecha_cierre=ahora - timedelta(days=45),  # fuera de 30 dias
        fecha_limite=ahora - timedelta(days=44),
    )

    resultado = ServicioMetricas.metricas_por_agente(agente_id=agente.id, dias=30)
    assert len(resultado) == 1
    assert resultado[0]["tickets_cerrados"] == 1, (
        f"solo el ticket dentro de la ventana de 30 dias debe contar, se obtuvo {resultado[0]}"
    )


def test_tiempo_promedio_resolucion_con_valores_conocidos():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = _crear_agente_aislado("promedio")
    ahora = datetime.now()

    # 2 horas y 4 horas de duracion -> promedio esperado 3.0
    _crear_ticket_cerrado(
        agente.id, normal.id,
        fecha_asignacion=ahora - timedelta(days=1, hours=2),
        fecha_cierre=ahora - timedelta(days=1),
        fecha_limite=ahora + timedelta(days=1),
    )
    _crear_ticket_cerrado(
        agente.id, normal.id,
        fecha_asignacion=ahora - timedelta(days=1, hours=4),
        fecha_cierre=ahora - timedelta(days=1),
        fecha_limite=ahora + timedelta(days=1),
    )

    resultado = ServicioMetricas.metricas_por_agente(agente_id=agente.id, dias=30)
    assert resultado[0]["tickets_cerrados"] == 2
    assert abs(resultado[0]["tiempo_promedio_resolucion_horas"] - 3.0) < 0.01, (
        f"se esperaba promedio de 3.0 horas, se obtuvo {resultado[0]['tiempo_promedio_resolucion_horas']}"
    )


def test_ticket_sin_fecha_asignacion_no_entra_al_promedio_pero_si_a_cerrados():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = _crear_agente_aislado("sin_fecha_asignacion")
    ahora = datetime.now()

    ticket = Ticket(
        texto="ticket sin fecha_asignacion (caso legado)",
        categoria=Categoria.PERMISOS, prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.CERRADO, creador_id=normal.id, agente_id=agente.id,
        fecha_creacion=ahora - timedelta(days=2),
        fecha_asignacion=None,
        fecha_limite=ahora - timedelta(days=1),
        fecha_cierre=ahora - timedelta(hours=12),
    )
    db.session.add(ticket)
    db.session.commit()

    resultado = ServicioMetricas.metricas_por_agente(agente_id=agente.id, dias=30)
    assert resultado[0]["tickets_cerrados"] == 1
    assert resultado[0]["tiempo_promedio_resolucion_horas"] is None, (
        "sin ningun dato de fecha_asignacion, el promedio debe quedar en None, no en 0"
    )


def test_cumplimiento_sla_mezcla_a_tiempo_y_tarde():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    agente = _crear_agente_aislado("cumplimiento_sla")
    ahora = datetime.now()

    # a tiempo: fecha_cierre <= fecha_limite
    _crear_ticket_cerrado(
        agente.id, normal.id,
        fecha_asignacion=ahora - timedelta(hours=5),
        fecha_cierre=ahora - timedelta(hours=3),
        fecha_limite=ahora - timedelta(hours=2),
    )
    # tarde: fecha_cierre > fecha_limite
    _crear_ticket_cerrado(
        agente.id, normal.id,
        fecha_asignacion=ahora - timedelta(hours=5),
        fecha_cierre=ahora - timedelta(hours=1),
        fecha_limite=ahora - timedelta(hours=2),
    )

    resultado = ServicioMetricas.metricas_por_agente(agente_id=agente.id, dias=30)
    assert resultado[0]["tickets_cerrados"] == 2
    assert abs(resultado[0]["cumplimiento_sla"] - 0.5) < 0.01, (
        f"se esperaba 0.5 (1 de 2 a tiempo), se obtuvo {resultado[0]['cumplimiento_sla']}"
    )


def test_sin_tickets_cerrados_devuelve_none():
    agente = _crear_agente_aislado("vacio")

    resultado = ServicioMetricas.metricas_por_agente(agente_id=agente.id, dias=30)
    assert resultado[0]["tickets_cerrados"] == 0
    assert resultado[0]["tiempo_promedio_resolucion_horas"] is None
    assert resultado[0]["cumplimiento_sla"] is None


def test_filtro_por_area_trae_todos_los_agentes():
    resultado = ServicioMetricas.metricas_por_agente(area=Categoria.PERMISOS, dias=30)
    ids_encontrados = {r["agente_id"] for r in resultado}
    agente_1 = Usuario.query.filter_by(email=EMAIL_AGENTE_1).first()
    agente_2 = Usuario.query.filter_by(email=EMAIL_AGENTE_2).first()
    assert agente_1.id in ids_encontrados
    assert agente_2.id in ids_encontrados


def test_sin_agente_id_ni_area_lanza_value_error():
    with pytest.raises(ValueError):
        ServicioMetricas.metricas_por_agente()