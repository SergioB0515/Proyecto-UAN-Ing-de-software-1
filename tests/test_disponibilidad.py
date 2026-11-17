from datetime import datetime, timedelta

import pytest

from sqlalchemy import select

from app.extensions import db
from app.models.enum import AccionAuditoria, Categoria, EstadoTicket, Prioridad, RolUsuario
from app.models.log_auditoria import LogAuditoria
from app.models.notificacion import Notificacion
from app.models.ticket import Ticket
from app.models.usuario import Usuario
from app.services.disponibilidad import ServicioDisponibilidad
from app.services.exceptions import AusenciaInvalidaError, OperacionNoPermitidaError
from app.services.gestor_sla import GestorSLA, UMBRAL_SIN_ASIGNAR
from app.services.metricas import ServicioMetricas
from app.services.solicitud_transferencia import ServicioSolicitudesTransferencia
from app.services.exceptions import AgenteDestinoInvalidoError
from app.services.tickets import ORDEN_POR_PRIORIDAD, ORDEN_POR_RIESGO, ServicioTickets
from tests.fabricas import crear_ticket, crear_usuario

# El area de pruebas se fija en PERMISOS para no cruzarse con los agentes que
# crean los demas archivos de test (que usan REDES y SOFTWARE).
AREA = Categoria.PERMISOS


@pytest.fixture
def admin():
    return crear_usuario(rol=RolUsuario.ADMIN)


@pytest.fixture(autouse=True)
def area_aislada(admin):
    """Aisla el area de pruebas de los agentes que crean otros archivos de test.

    La base de pruebas es compartida entre archivos, asi que PERMISOS puede
    traer agentes sembrados por otros tests y los conteos de cobertura dejan de
    ser deterministas. Se los desactiva durante el test y se les restaura su
    estado original al terminar.
    """
    previos = db.session.execute(
        select(Usuario).where(Usuario.rol == RolUsuario.AGENTE, Usuario.area_soporte == AREA)
    ).scalars().all()
    estado_original = [(u, u.activo) for u in previos]
    for usuario, _activo in estado_original:
        usuario.activo = False
    db.session.commit()

    yield

    for usuario, activo in estado_original:
        usuario.activo = activo
    db.session.commit()


@pytest.fixture
def agente():
    return crear_usuario(rol=RolUsuario.AGENTE, area=AREA)


@pytest.fixture
def solicitante():
    return crear_usuario(rol=RolUsuario.FINAL)


def _limpiar_notificaciones():
    db.session.query(Notificacion).delete()
    db.session.commit()


# ------------------------------------------------------------- ventana de fechas


def test_agente_nuevo_esta_disponible(agente):
    assert ServicioDisponibilidad.esta_disponible(agente) is True
    assert ServicioDisponibilidad.esta_ausente(agente) is False


def test_ausencia_abierta_deja_al_agente_ausente(admin, agente):
    ServicioDisponibilidad.marcar_ausente(admin.id, agente.id, motivo="vacaciones")

    assert ServicioDisponibilidad.esta_ausente(agente) is True
    assert agente.ausente_hasta is None
    assert agente.motivo_ausencia == "vacaciones"


def test_ausencia_futura_no_afecta_el_presente(admin, agente):
    manana = datetime.now() + timedelta(days=1)
    ServicioDisponibilidad.marcar_ausente(admin.id, agente.id, desde=manana)

    assert ServicioDisponibilidad.esta_disponible(agente) is True
    assert ServicioDisponibilidad.esta_disponible(agente, ahora=manana + timedelta(hours=1)) is False


def test_ausencia_vencida_vuelve_a_dejarlo_disponible(admin, agente):
    ahora = datetime.now()
    ServicioDisponibilidad.marcar_ausente(
        admin.id, agente.id, desde=ahora - timedelta(days=5), hasta=ahora - timedelta(days=1)
    )

    assert ServicioDisponibilidad.esta_disponible(agente) is True
    # ...pero sí estaba ausente dentro de la ventana
    assert ServicioDisponibilidad.esta_disponible(agente, ahora=ahora - timedelta(days=3)) is False


def test_fecha_de_regreso_anterior_a_la_salida_es_invalida(admin, agente):
    ahora = datetime.now()
    with pytest.raises(AusenciaInvalidaError):
        ServicioDisponibilidad.marcar_ausente(
            admin.id, agente.id, desde=ahora, hasta=ahora - timedelta(hours=1)
        )


def test_motivo_demasiado_largo_es_invalido(admin, agente):
    with pytest.raises(AusenciaInvalidaError):
        ServicioDisponibilidad.marcar_ausente(admin.id, agente.id, motivo="x" * 200)


def test_solo_los_agentes_tienen_disponibilidad(admin, solicitante):
    with pytest.raises(OperacionNoPermitidaError):
        ServicioDisponibilidad.marcar_ausente(admin.id, solicitante.id)


def test_marcar_disponible_limpia_la_ventana_y_audita(admin, agente):
    ServicioDisponibilidad.marcar_ausente(admin.id, agente.id, motivo="curso")
    ServicioDisponibilidad.marcar_disponible(admin.id, agente.id)

    assert agente.ausente_desde is None
    assert agente.ausente_hasta is None
    assert agente.motivo_ausencia is None

    acciones = db.session.query(LogAuditoria.accion).filter(LogAuditoria.usuario_id == admin.id).all()
    acciones = [a for (a,) in acciones]
    assert AccionAuditoria.MARCAR_AUSENTE in acciones
    assert AccionAuditoria.MARCAR_DISPONIBLE in acciones


def test_marcar_disponible_es_idempotente(admin, agente):
    ServicioDisponibilidad.marcar_disponible(admin.id, agente.id)
    assert ServicioDisponibilidad.esta_disponible(agente) is True


# ------------------------------------------------------------------- cobertura


def test_cobertura_cuenta_disponibles_y_ausentes(admin, agente):
    otro = crear_usuario(rol=RolUsuario.AGENTE, area=AREA)
    ServicioDisponibilidad.marcar_ausente(admin.id, otro.id)

    cobertura = ServicioDisponibilidad.cobertura_area(AREA)

    assert cobertura["activos"] == 2
    assert cobertura["disponibles"] == 1
    assert cobertura["ausentes"] == 1
    assert cobertura["sin_cobertura"] is False


def test_area_sin_nadie_disponible_se_marca_sin_cobertura(admin, agente):
    ServicioDisponibilidad.marcar_ausente(admin.id, agente.id)

    cobertura = ServicioDisponibilidad.cobertura_area(AREA)
    assert cobertura["disponibles"] == 0
    assert cobertura["sin_cobertura"] is True
    assert AREA in ServicioDisponibilidad.areas_sin_cobertura()


def test_agentes_disponibles_excluye_ausentes_e_inactivos(admin, agente):
    ausente = crear_usuario(rol=RolUsuario.AGENTE, area=AREA)
    inactivo = crear_usuario(rol=RolUsuario.AGENTE, area=AREA, activo=False)
    ServicioDisponibilidad.marcar_ausente(admin.id, ausente.id)

    ids = {a.id for a in ServicioDisponibilidad.agentes_disponibles(AREA)}

    assert agente.id in ids
    assert ausente.id not in ids
    assert inactivo.id not in ids


# --------------------------------------------------- sugerencias y transferencias


def test_no_se_sugiere_un_agente_ausente(admin, agente):
    ServicioDisponibilidad.marcar_ausente(admin.id, agente.id)
    assert ServicioMetricas.sugerir_agente(AREA) is None


def test_se_sugiere_al_unico_agente_disponible(admin, agente):
    ausente = crear_usuario(rol=RolUsuario.AGENTE, area=AREA)
    ServicioDisponibilidad.marcar_ausente(admin.id, ausente.id)

    sugerido = ServicioMetricas.sugerir_agente(AREA)
    assert sugerido is not None and sugerido.id == agente.id


def test_un_agente_ausente_no_puede_ser_destino_de_transferencia(admin, agente, solicitante):
    destino = crear_usuario(rol=RolUsuario.AGENTE, area=AREA)
    ticket = crear_ticket(solicitante, categoria=AREA, estado=EstadoTicket.EN_PROGRESO, agente=agente)
    ServicioDisponibilidad.marcar_ausente(admin.id, destino.id)

    with pytest.raises(AgenteDestinoInvalidoError):
        ServicioSolicitudesTransferencia.crear_solicitud(
            ticket_id=ticket.id, agente_destino_id=destino.id, solicitante_id=agente.id, motivo="se va de viaje"
        )


# ------------------------------------------------------------ alertas al area


def test_sla_de_ticket_sin_dueno_avisa_a_los_agentes_disponibles(agente, solicitante):
    _limpiar_notificaciones()
    # vencido: creado hace 30 h con un plazo de 24 h
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=30, horas_sla=24)

    GestorSLA.verificar_y_notificar_vencimientos()

    del_agente = db.session.query(Notificacion).filter(
        Notificacion.usuario_id == agente.id, Notificacion.ticket_id == ticket.id
    ).all()
    assert len(del_agente) == 1
    assert "área" in del_agente[0].mensaje or "area" in del_agente[0].mensaje

    del_creador = db.session.query(Notificacion).filter(
        Notificacion.usuario_id == solicitante.id, Notificacion.ticket_id == ticket.id
    ).all()
    assert len(del_creador) == 1, "el creador sigue recibiendo su propio aviso"


def test_sla_no_avisa_al_area_si_el_ticket_ya_tiene_dueno(agente, solicitante):
    _limpiar_notificaciones()
    otro = crear_usuario(rol=RolUsuario.AGENTE, area=AREA)
    ticket = crear_ticket(
        solicitante, categoria=AREA, creado_hace_horas=30, horas_sla=24,
        estado=EstadoTicket.EN_PROGRESO, agente=agente,
    )

    GestorSLA.verificar_y_notificar_vencimientos()

    assert db.session.query(Notificacion).filter(
        Notificacion.usuario_id == otro.id, Notificacion.ticket_id == ticket.id
    ).count() == 0, "si hay dueño, el aviso no se reparte al resto del área"
    assert db.session.query(Notificacion).filter(
        Notificacion.usuario_id == agente.id, Notificacion.ticket_id == ticket.id
    ).count() == 1


def test_area_sin_cobertura_escala_el_aviso_al_admin(admin, agente, solicitante):
    _limpiar_notificaciones()
    ServicioDisponibilidad.marcar_ausente(admin.id, agente.id)
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=30, horas_sla=24)

    GestorSLA.verificar_y_notificar_vencimientos()

    del_admin = db.session.query(Notificacion).filter(
        Notificacion.usuario_id == admin.id, Notificacion.ticket_id == ticket.id
    ).all()
    mensajes = [n.mensaje for n in del_admin]
    assert any("no tiene agentes disponibles" in m for m in mensajes), mensajes
    assert db.session.query(Notificacion).filter(
        Notificacion.usuario_id == agente.id, Notificacion.ticket_id == ticket.id
    ).count() == 0, "a un agente ausente no se le avisa"


def test_el_aviso_al_area_no_se_repite_en_la_siguiente_pasada(agente, solicitante):
    _limpiar_notificaciones()
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=30, horas_sla=24)

    GestorSLA.verificar_y_notificar_vencimientos()
    antes = db.session.query(Notificacion).filter(Notificacion.ticket_id == ticket.id).count()
    GestorSLA.verificar_y_notificar_vencimientos()
    despues = db.session.query(Notificacion).filter(Notificacion.ticket_id == ticket.id).count()

    assert antes == despues


# ------------------------------------------------- edad sin asignar -> admin


def test_ticket_sin_dueno_pasado_el_umbral_se_escala_al_admin(admin, agente, solicitante):
    _limpiar_notificaciones()
    # 60% del plazo consumido: por encima del umbral, pero lejos del vencimiento,
    # asi que no entra en la lista de "proximos a vencer".
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=6, horas_sla=10)

    escalados = GestorSLA.escalar_tickets_sin_asignar()

    assert ticket.id in [t.id for t in escalados]
    assert ticket.notificado_sin_asignar is True
    assert db.session.query(Notificacion).filter(
        Notificacion.usuario_id == admin.id, Notificacion.ticket_id == ticket.id
    ).count() == 1


def test_ticket_joven_sin_dueno_no_se_escala(admin, solicitante):
    _limpiar_notificaciones()
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=1, horas_sla=24)

    escalados = GestorSLA.escalar_tickets_sin_asignar()

    assert ticket.id not in [t.id for t in escalados]
    assert ticket.notificado_sin_asignar is False


def test_ticket_con_dueno_no_se_escala_por_edad(admin, agente, solicitante):
    _limpiar_notificaciones()
    ticket = crear_ticket(
        solicitante, categoria=AREA, creado_hace_horas=9, horas_sla=10,
        estado=EstadoTicket.EN_PROGRESO, agente=agente,
    )

    escalados = GestorSLA.escalar_tickets_sin_asignar()
    assert ticket.id not in [t.id for t in escalados]


def test_el_escalamiento_por_edad_se_avisa_una_sola_vez(admin, solicitante):
    _limpiar_notificaciones()
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=6, horas_sla=10)

    GestorSLA.escalar_tickets_sin_asignar()
    GestorSLA.escalar_tickets_sin_asignar()

    assert db.session.query(Notificacion).filter(
        Notificacion.usuario_id == admin.id, Notificacion.ticket_id == ticket.id
    ).count() == 1


def test_asignar_un_agente_rearma_la_bandera_de_sin_asignar(admin, agente, solicitante):
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=6, horas_sla=10)
    GestorSLA.escalar_tickets_sin_asignar()
    assert ticket.notificado_sin_asignar is True

    ServicioTickets.cambiar_estado(ticket.id, EstadoTicket.EN_PROGRESO, admin.id, agente_id=agente.id)

    assert ticket.notificado_sin_asignar is False


def test_umbral_configurable(solicitante):
    _limpiar_notificaciones()
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=3, horas_sla=10)

    assert ticket.id not in [t.id for t in GestorSLA.escalar_tickets_sin_asignar()]
    assert ticket.id in [t.id for t in GestorSLA.escalar_tickets_sin_asignar(umbral=0.2)]


# -------------------------------------------------------------- cola por riesgo


def test_consumo_sla_mide_la_fraccion_del_plazo(solicitante):
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=5, horas_sla=10)
    consumo = GestorSLA.consumo_sla(ticket)
    assert 0.45 < consumo < 0.55


def test_consumo_sla_pasa_de_uno_cuando_esta_vencido(solicitante):
    ticket = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=20, horas_sla=10)
    assert GestorSLA.consumo_sla(ticket) > 1


def test_orden_por_riesgo_pone_primero_lo_que_esta_mas_cerca_de_vencer(solicitante):
    # El de prioridad BAJA esta al 90% del plazo; el ALTA apenas empezo.
    urgente_pero_baja = crear_ticket(
        solicitante, categoria=AREA, prioridad=Prioridad.BAJA, creado_hace_horas=9, horas_sla=10
    )
    nuevo_pero_alta = crear_ticket(
        solicitante, categoria=AREA, prioridad=Prioridad.ALTA, creado_hace_horas=1, horas_sla=10
    )

    por_riesgo = ServicioTickets.listar_tickets_por_area(AREA, orden=ORDEN_POR_RIESGO)
    ids_riesgo = [t.id for t in por_riesgo]
    assert ids_riesgo.index(urgente_pero_baja.id) < ids_riesgo.index(nuevo_pero_alta.id)

    por_prioridad = ServicioTickets.listar_tickets_por_area(AREA, orden=ORDEN_POR_PRIORIDAD)
    ids_prioridad = [t.id for t in por_prioridad]
    assert ids_prioridad.index(nuevo_pero_alta.id) < ids_prioridad.index(urgente_pero_baja.id)


def test_orden_por_riesgo_manda_los_cerrados_al_final(solicitante):
    cerrado = crear_ticket(
        solicitante, categoria=AREA, creado_hace_horas=20, horas_sla=10,
        estado=EstadoTicket.CERRADO, horas_hasta_cierre=2,
    )
    abierto = crear_ticket(solicitante, categoria=AREA, creado_hace_horas=1, horas_sla=100)

    ids = [t.id for t in ServicioTickets.listar_tickets_por_area(AREA, orden=ORDEN_POR_RIESGO)]
    assert ids.index(abierto.id) < ids.index(cerrado.id)


def test_el_orden_por_defecto_sigue_siendo_por_prioridad(solicitante):
    baja = crear_ticket(solicitante, categoria=AREA, prioridad=Prioridad.BAJA, creado_hace_horas=9, horas_sla=10)
    alta = crear_ticket(solicitante, categoria=AREA, prioridad=Prioridad.ALTA, creado_hace_horas=1, horas_sla=10)

    ids = [t.id for t in ServicioTickets.listar_tickets_por_area(AREA)]
    assert ids.index(alta.id) < ids.index(baja.id)
