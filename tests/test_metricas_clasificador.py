import os
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, func

from app.extensions import db
from app.services.autenticacion import ServicioAutenticacion
from app.services.metricas import ServicioMetricas
from app.models.usuario import Usuario
from app.models.ticket import Ticket
from app.models.correccion_clasificacion import CorreccionClasificacion
from app.models.enum import RolUsuario, NivelUsuario, Categoria, EstadoTicket, Prioridad

EMAIL_ADMIN = "prueba_confianza_clasificador_admin@empresa.com"
EMAIL_NORMAL = "prueba_confianza_clasificador_normal@empresa.com"


@pytest.fixture(scope="module", autouse=True)
def usuarios_de_prueba():
    for email in (EMAIL_ADMIN, EMAIL_NORMAL):
        u = Usuario.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
    db.session.commit()

    admin = Usuario(
        nombre="Admin Prueba Confianza Clasificador", email=EMAIL_ADMIN,
        contrasena_hash=ServicioAutenticacion._generar_hash("ClaveSegura123!"),
        rol=RolUsuario.ADMIN, nivel=NivelUsuario.NORMAL,
    )
    db.session.add(admin)
    db.session.commit()

    ServicioAutenticacion.registrar(
        nombre="Usuario Normal Confianza Clasificador", email=EMAIL_NORMAL,
        contrasena="ClaveSegura123!", rol=RolUsuario.FINAL,
        nivel=NivelUsuario.NORMAL, admin_id=admin.id,
    )


def _crear_ticket(creador_id, fecha_creacion, baja_confianza=False):
    ticket = Ticket(
        texto="ticket de prueba confianza clasificador",
        categoria=Categoria.PERMISOS,
        prioridad=Prioridad.MEDIA,
        estado=EstadoTicket.ABIERTO,
        creador_id=creador_id,
        fecha_creacion=fecha_creacion,
        fecha_limite=fecha_creacion + timedelta(days=1),
        clasificacion_baja_confianza=baja_confianza,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def _crear_correccion(ticket_id, actor_id, fecha):
    correccion = CorreccionClasificacion(
        ticket_id=ticket_id,
        texto="texto de prueba",
        categoria_original=Categoria.OTROS,
        categoria_correcta=Categoria.PERMISOS,
        actor_id=actor_id,
        fecha=fecha,
    )
    db.session.add(correccion)
    db.session.commit()
    return correccion


def _contar_correcciones_en_ventana(dias):
    hace_n_dias = datetime.now() - timedelta(days=dias)
    return db.session.execute(
        select(func.count()).select_from(CorreccionClasificacion).where(
            CorreccionClasificacion.fecha >= hace_n_dias
        )
    ).scalar()


def _contar_tickets_creados_en_ventana(dias):
    hace_n_dias = datetime.now() - timedelta(days=dias)
    return db.session.execute(
        select(func.count()).select_from(Ticket).where(
            Ticket.fecha_creacion >= hace_n_dias
        )
    ).scalar()


def test_tickets_en_revision_cuenta_baja_confianza():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    ahora = datetime.now()

    antes = ServicioMetricas.obtener_metricas_confianza_clasificador()["tickets_en_revision"]

    _crear_ticket(normal.id, ahora, baja_confianza=True)
    _crear_ticket(normal.id, ahora, baja_confianza=False)

    despues = ServicioMetricas.obtener_metricas_confianza_clasificador()["tickets_en_revision"]

    assert despues - antes == 1, (
        f"solo el ticket baja_confianza=True debe sumar al conteo, delta obtenido: {despues - antes}"
    )


def test_tasa_correccion_30d_con_valores_conocidos():
    normal = Usuario.query.filter_by(email=EMAIL_NORMAL).first()
    admin = Usuario.query.filter_by(email=EMAIL_ADMIN).first()
    ahora = datetime.now()
    dias = 30

    base_creados = _contar_tickets_creados_en_ventana(dias)
    base_correcciones = _contar_correcciones_en_ventana(dias)

    tickets = [_crear_ticket(normal.id, ahora - timedelta(days=1)) for _ in range(3)]
    _crear_ticket(normal.id, ahora - timedelta(days=45))

    _crear_correccion(tickets[0].id, admin.id, fecha=ahora - timedelta(days=2))
    _crear_correccion(tickets[1].id, admin.id, fecha=ahora - timedelta(days=10))
    _crear_correccion(tickets[2].id, admin.id, fecha=ahora - timedelta(days=50))

    esperado_creados = base_creados + 3
    esperado_correcciones = base_correcciones + 2
    tasa_esperada = esperado_correcciones / esperado_creados

    resultado = ServicioMetricas.obtener_metricas_confianza_clasificador(dias=dias)

    assert resultado["tasa_correccion_30d"] is not None
    assert abs(resultado["tasa_correccion_30d"] - tasa_esperada) < 0.001, (
        f"se esperaba tasa {tasa_esperada}, se obtuvo {resultado['tasa_correccion_30d']}"
    )


def test_exactitud_produccion_30d_es_uno_menos_tasa():
    resultado = ServicioMetricas.obtener_metricas_confianza_clasificador(dias=30)
    if resultado["tasa_correccion_30d"] is None:
        pytest.skip("no hay tickets en la ventana en este entorno de prueba")
    esperado = 1 - resultado["tasa_correccion_30d"]
    assert abs(resultado["exactitud_produccion_30d"] - esperado) < 0.0001


def test_tasa_correccion_30d_none_sin_tickets_en_la_ventana():
    resultado = ServicioMetricas.obtener_metricas_confianza_clasificador(dias=0)
    assert resultado["tasa_correccion_30d"] is None
    assert resultado["exactitud_produccion_30d"] is None


def _ruta_metadata_real():
    import app.services.metricas as metricas_mod
    return os.path.join(
        os.path.dirname(os.path.abspath(metricas_mod.__file__)), "..", "ml_artifacts", "metadata.json"
    )


def test_metadata_ausente_devuelve_none():
    if os.path.exists(_ruta_metadata_real()):
        pytest.skip("metadata.json real existe en este entorno -- ver test_metadata_presente_lee_valores_reales")

    resultado = ServicioMetricas.obtener_metricas_confianza_clasificador()
    assert resultado["exactitud_laboratorio"] is None
    assert resultado["fecha_entrenamiento_modelo"] is None


def test_metadata_presente_lee_valores_reales():
    ruta_metadata = _ruta_metadata_real()
    if not os.path.exists(ruta_metadata):
        pytest.skip("metadata.json no existe en este entorno -- ver test_metadata_ausente_devuelve_none")

    with open(ruta_metadata, "r", encoding="utf-8") as f:
        metadata_real = json.load(f)

    resultado = ServicioMetricas.obtener_metricas_confianza_clasificador()
    assert resultado["exactitud_laboratorio"] == metadata_real.get("exactitud_en_prueba")
    assert resultado["fecha_entrenamiento_modelo"] == metadata_real.get("fecha_entrenamiento")