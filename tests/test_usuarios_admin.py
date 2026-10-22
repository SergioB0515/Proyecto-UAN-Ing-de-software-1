from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.doble_factor import DobleFactor
from app.models.enum import Categoria, EstadoTicket, NivelUsuario, RolUsuario, AccionAuditoria
from app.models.log_auditoria import LogAuditoria
from app.services.exceptions import OperacionNoPermitidaError, UsuarioNoEncontradoError
from app.services.usuarios import ServicioUsuarios
from sqlalchemy import select
from tests.fabricas import crear_ticket, crear_usuario


@pytest.fixture
def admin():
    return crear_usuario(RolUsuario.ADMIN)


def test_actualizar_cambia_datos_y_audita(admin):
    usuario = crear_usuario()
    _u, cambio = ServicioUsuarios.actualizar(admin.id, usuario.id, "Nombre Nuevo", RolUsuario.FINAL, NivelUsuario.VIP)
    assert cambio
    db.session.refresh(usuario)
    assert usuario.nombre == "Nombre Nuevo" and usuario.nivel == NivelUsuario.VIP
    log = db.session.execute(
        select(LogAuditoria).where(LogAuditoria.usuario_id == admin.id, LogAuditoria.accion == AccionAuditoria.EDITAR_USUARIO)
    ).scalars().first()
    assert log is not None and usuario.email in log.detalle


def test_actualizar_sin_cambios_no_audita(admin):
    usuario = crear_usuario()
    _u, cambio = ServicioUsuarios.actualizar(admin.id, usuario.id, usuario.nombre, usuario.rol, usuario.nivel)
    assert cambio is False


def test_agente_requiere_area(admin):
    usuario = crear_usuario()
    with pytest.raises(ValueError):
        ServicioUsuarios.actualizar(admin.id, usuario.id, usuario.nombre, RolUsuario.AGENTE, NivelUsuario.NORMAL, None)


def test_area_se_limpia_si_deja_de_ser_agente(admin):
    agente = crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)
    ServicioUsuarios.actualizar(admin.id, agente.id, agente.nombre, RolUsuario.FINAL, NivelUsuario.NORMAL, Categoria.REDES)
    db.session.refresh(agente)
    assert agente.rol == RolUsuario.FINAL and agente.area_soporte is None


def test_no_cambia_area_de_agente_con_tickets_en_progreso(admin):
    agente = crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)
    crear_ticket(crear_usuario(), estado=EstadoTicket.EN_PROGRESO, agente=agente)
    with pytest.raises(OperacionNoPermitidaError):
        ServicioUsuarios.actualizar(admin.id, agente.id, agente.nombre, RolUsuario.AGENTE, NivelUsuario.NORMAL, Categoria.SEGURIDAD)


def test_admin_no_puede_quitarse_su_rol(admin):
    with pytest.raises(OperacionNoPermitidaError):
        ServicioUsuarios.actualizar(admin.id, admin.id, admin.nombre, RolUsuario.FINAL, NivelUsuario.NORMAL)


def test_no_puede_desactivarse_a_si_mismo(admin):
    with pytest.raises(OperacionNoPermitidaError):
        ServicioUsuarios.cambiar_activo(admin.id, admin.id, False)


def test_desactivar_y_reactivar(admin):
    usuario = crear_usuario()
    ServicioUsuarios.cambiar_activo(admin.id, usuario.id, False)
    db.session.refresh(usuario)
    assert usuario.activo is False
    ServicioUsuarios.cambiar_activo(admin.id, usuario.id, True)
    db.session.refresh(usuario)
    assert usuario.activo is True


def test_no_desactiva_agente_con_trabajo_en_curso(admin):
    agente = crear_usuario(RolUsuario.AGENTE, area=Categoria.SEGURIDAD)
    crear_ticket(crear_usuario(), categoria=Categoria.SEGURIDAD, estado=EstadoTicket.EN_PROGRESO, agente=agente)
    with pytest.raises(OperacionNoPermitidaError):
        ServicioUsuarios.cambiar_activo(admin.id, agente.id, False)


def test_desbloquear_limpia_bloqueo(admin):
    usuario = crear_usuario()
    usuario.intentos_fallidos = 3
    usuario.bloqueado_hasta = datetime.now() + timedelta(hours=4)
    db.session.commit()
    ServicioUsuarios.desbloquear(admin.id, usuario.id)
    db.session.refresh(usuario)
    assert usuario.bloqueado_hasta is None and usuario.intentos_fallidos == 0


def test_restablecer_2fa(admin):
    usuario = crear_usuario()
    with pytest.raises(OperacionNoPermitidaError):
        ServicioUsuarios.restablecer_doble_factor(admin.id, usuario.id)
    db.session.add(DobleFactor(usuario_id=usuario.id, secreto="ABC", activo=True))
    db.session.commit()
    ServicioUsuarios.restablecer_doble_factor(admin.id, usuario.id)
    assert db.session.execute(select(DobleFactor).where(DobleFactor.usuario_id == usuario.id)).first() is None


def test_enviar_recuperacion_rechaza_cuenta_inactiva(admin):
    usuario = crear_usuario(activo=False)
    with pytest.raises(OperacionNoPermitidaError):
        ServicioUsuarios.enviar_recuperacion(admin.id, usuario.id)


def test_listar_filtra_por_estado_y_busqueda(admin):
    inactivo = crear_usuario(nombre="Zacarías Inactivo Único", activo=False)
    pagina = ServicioUsuarios.listar(busqueda="Zacarías Inactivo", estado="inactivos")
    assert [u.id for u in pagina.items] == [inactivo.id]
    assert ServicioUsuarios.listar(busqueda="Zacarías Inactivo", estado="activos").items == []


def test_usuario_inexistente():
    with pytest.raises(UsuarioNoEncontradoError):
        ServicioUsuarios.obtener(999999)
