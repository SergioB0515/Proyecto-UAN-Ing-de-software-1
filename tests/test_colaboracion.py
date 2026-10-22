import pytest
from sqlalchemy import select

from app import notificaciones_i18n as notif
from app.extensions import db
from app.models.enum import Categoria, EstadoSolicitudTransferencia, EstadoTicket, RolUsuario, TipoSolicitud
from app.models.notificacion import Notificacion
from app.models.transferencia import SolicitudTransferencia
from app.services.exceptions import PermisoDenegadoError, RespuestaNoEncontradaError
from app.services.permisos import ServicioPermisos
from app.services.respuestas_predefinidas import ServicioRespuestasPredefinidas, aplicar_variables
from app.services.seguimiento import ServicioSeguimiento
from app.services.tickets import ServicioTickets
from tests.fabricas import crear_ticket, crear_usuario


def _notificaciones(usuario_id, plantilla):
    return db.session.execute(
        select(Notificacion).where(Notificacion.usuario_id == usuario_id, Notificacion.mensaje == plantilla)
    ).scalars().all()


@pytest.fixture
def escenario():
    creador = crear_usuario()
    agente = crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)
    ticket = crear_ticket(creador, categoria=Categoria.REDES, estado=EstadoTicket.EN_PROGRESO, agente=agente)
    return creador, agente, ticket


def test_permisos_de_lectura(escenario):
    creador, agente, ticket = escenario
    assert ServicioPermisos.puede_ver_ticket(creador, ticket)
    assert ServicioPermisos.puede_ver_ticket(agente, ticket)
    assert ServicioPermisos.puede_ver_ticket(crear_usuario(RolUsuario.ADMIN), ticket)
    assert ServicioPermisos.puede_ver_ticket(crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES), ticket)
    assert not ServicioPermisos.puede_ver_ticket(crear_usuario(), ticket)
    assert not ServicioPermisos.puede_ver_ticket(crear_usuario(RolUsuario.AGENTE, area=Categoria.SEGURIDAD), ticket)


def test_agente_destino_de_transferencia_puede_ver(escenario):
    _creador, agente, ticket = escenario
    otro = crear_usuario(RolUsuario.AGENTE, area=Categoria.SEGURIDAD)
    db.session.add(SolicitudTransferencia(
        ticket_id=ticket.id, tipo=TipoSolicitud.REASIGNACION, agente_origen_id=agente.id,
        agente_destino_id=otro.id, solicitante_id=agente.id, estado=EstadoSolicitudTransferencia.PENDIENTE,
    ))
    db.session.commit()
    assert ServicioPermisos.puede_ver_ticket(otro, ticket)


def test_nota_interna_oculta_al_usuario_final(escenario):
    creador, agente, ticket = escenario
    ServicioTickets.agregar_comentario(ticket.id, agente.id, "Respuesta pública")
    ServicioTickets.agregar_comentario(ticket.id, agente.id, "Nota privada del equipo", interno=True)
    publicos = ServicioTickets.listar_comentarios(ticket.id)
    todos = ServicioTickets.listar_comentarios(ticket.id, incluir_internos=True)
    assert [c.texto for c in publicos] == ["Respuesta pública"]
    assert len(todos) == 2 and todos[1].interno


def test_usuario_final_no_crea_notas_internas(escenario):
    creador, _agente, ticket = escenario
    with pytest.raises(PermisoDenegadoError):
        ServicioTickets.agregar_comentario(ticket.id, creador.id, "intento", interno=True)


def test_notificaciones_de_comentarios(escenario):
    creador, agente, ticket = escenario
    ServicioTickets.agregar_comentario(ticket.id, agente.id, "Ya lo reviso")
    assert len(_notificaciones(creador.id, notif.COMENTARIO_NUEVO_CREADOR)) == 1
    ServicioTickets.agregar_comentario(ticket.id, creador.id, "Gracias, sigue fallando")
    assert len(_notificaciones(agente.id, notif.COMENTARIO_NUEVO_AGENTE)) == 1
    ServicioTickets.agregar_comentario(ticket.id, agente.id, "nota", interno=True)
    assert len(_notificaciones(creador.id, notif.COMENTARIO_NUEVO_CREADOR)) == 1


def test_seguidores_reciben_actividad(escenario):
    creador, agente, ticket = escenario
    supervisor = crear_usuario(RolUsuario.ADMIN)
    assert ServicioSeguimiento.seguir(ticket.id, supervisor) is True
    assert ServicioSeguimiento.seguir(ticket.id, supervisor) is False
    ServicioTickets.agregar_comentario(ticket.id, agente.id, "avance")
    ServicioTickets.cambiar_estado(ticket.id, EstadoTicket.CERRADO, actor_id=agente.id)
    assert len(_notificaciones(supervisor.id, notif.ACTIVIDAD_SEGUIDOR)) == 2
    assert ServicioSeguimiento.dejar_de_seguir(ticket.id, supervisor.id) is True
    assert not ServicioSeguimiento.sigue(ticket.id, supervisor.id)


def test_usuario_final_no_puede_seguir(escenario):
    _creador, _agente, ticket = escenario
    with pytest.raises(PermisoDenegadoError):
        ServicioSeguimiento.seguir(ticket.id, crear_usuario())


def test_respuestas_privadas_y_compartidas():
    a1 = crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)
    a2 = crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)
    privada = ServicioRespuestasPredefinidas.crear(a1.id, "Mi plantilla", "Hola {nombre}", compartida=False)
    compartida = ServicioRespuestasPredefinidas.crear(a1.id, "Del equipo", "Hola equipo {ticket}", categoria=Categoria.SEGURIDAD)
    visibles_a2 = {r.id for r in ServicioRespuestasPredefinidas.listar_para(a2.id)}
    assert compartida.id in visibles_a2 and privada.id not in visibles_a2
    assert compartida.id not in {r.id for r in ServicioRespuestasPredefinidas.listar_para(a2.id, categoria=Categoria.REDES)}
    with pytest.raises(RespuestaNoEncontradaError):
        ServicioRespuestasPredefinidas.obtener_para(privada.id, a2.id)
    with pytest.raises(PermisoDenegadoError):
        ServicioRespuestasPredefinidas.eliminar(a2.id, compartida.id)
    ServicioRespuestasPredefinidas.registrar_uso(compartida.id, a2.id)
    db.session.refresh(compartida)
    assert compartida.usos == 1


def test_usuario_final_no_crea_respuestas():
    with pytest.raises(PermisoDenegadoError):
        ServicioRespuestasPredefinidas.crear(crear_usuario().id, "Título", "Contenido válido")


def test_aplicar_variables():
    assert aplicar_variables("Hola {nombre}, ticket {ticket}", nombre="Ana", ticket=7) == "Hola Ana, ticket #7"
