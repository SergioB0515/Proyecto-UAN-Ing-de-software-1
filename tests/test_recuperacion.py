from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db, mail
from app.models.enum import RolUsuario, NivelUsuario, AccionAuditoria
from app.models.log_auditoria import LogAuditoria
from app.models.token_recuperacion import TokenRecuperacion
from app.models.usuario import Usuario
from app.services.autenticacion import ServicioAutenticacion
from app.services.exceptions import TokenRecuperacionInvalidoError
from app.services.recuperacion import ServicioRecuperacion, MAX_SOLICITUDES_POR_HORA

EMAIL_REC = "prueba_recuperacion@empresa.com"
CONTRASENA = "ClaveSegura123!"
NUEVA = "OtraClave456#"


@pytest.fixture
def usuario():
    existente = db.session.execute(select(Usuario).where(Usuario.email == EMAIL_REC)).scalar_one_or_none()
    if existente:
        for t in db.session.execute(select(TokenRecuperacion).where(TokenRecuperacion.usuario_id == existente.id)).scalars():
            db.session.delete(t)
        db.session.delete(existente)
        db.session.commit()
    u = Usuario(
        nombre="Usuario Recuperacion", email=EMAIL_REC,
        contrasena_hash=ServicioAutenticacion._generar_hash(CONTRASENA),
        rol=RolUsuario.FINAL, nivel=NivelUsuario.NORMAL,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _tokens(usuario_id):
    return db.session.execute(select(TokenRecuperacion).where(TokenRecuperacion.usuario_id == usuario_id)).scalars().all()


def test_email_inexistente_no_crea_token_ni_falla():
    assert ServicioRecuperacion.solicitar("no_existe_nadie@empresa.com", enviar_correo=False) is None


def test_solicitar_guarda_solo_el_hash(usuario):
    token = ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    assert token
    registros = _tokens(usuario.id)
    assert len(registros) == 1
    assert registros[0].token_hash != token and len(registros[0].token_hash) == 64
    assert registros[0].expira > datetime.now()


def test_solicitar_envia_correo_con_enlace(usuario):
    with mail.record_messages() as buzon:
        token = ServicioRecuperacion.solicitar(EMAIL_REC)
    assert len(buzon) == 1
    assert buzon[0].recipients == [EMAIL_REC]
    assert token in buzon[0].body


def test_nueva_solicitud_invalida_el_token_anterior(usuario):
    primero = ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    segundo = ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    with pytest.raises(TokenRecuperacionInvalidoError):
        ServicioRecuperacion.validar_token(primero)
    _registro, u = ServicioRecuperacion.validar_token(segundo)
    assert u.id == usuario.id


def test_limite_de_solicitudes_por_hora(usuario):
    for _i in range(MAX_SOLICITUDES_POR_HORA):
        assert ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    assert ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False) is None


def test_token_inventado_es_invalido(usuario):
    with pytest.raises(TokenRecuperacionInvalidoError):
        ServicioRecuperacion.validar_token("token-que-no-existe")


def test_token_expirado_es_invalido(usuario):
    token = ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    registro = _tokens(usuario.id)[-1]
    registro.expira = datetime.now() - timedelta(minutes=1)
    db.session.commit()
    with pytest.raises(TokenRecuperacionInvalidoError):
        ServicioRecuperacion.validar_token(token)


def test_restablecer_cambia_contrasena_y_consume_token(usuario):
    token = ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    ServicioRecuperacion.restablecer(token, NUEVA, NUEVA)
    db.session.refresh(usuario)
    assert ServicioAutenticacion._verificar_contrasena(NUEVA, usuario.contrasena_hash)
    assert not ServicioAutenticacion._verificar_contrasena(CONTRASENA, usuario.contrasena_hash)
    with pytest.raises(TokenRecuperacionInvalidoError):
        ServicioRecuperacion.restablecer(token, "Tercera789$", "Tercera789$")


def test_restablecer_desbloquea_la_cuenta(usuario):
    usuario.intentos_fallidos = 3
    usuario.bloqueado_hasta = datetime.now() + timedelta(hours=5)
    db.session.commit()
    token = ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    ServicioRecuperacion.restablecer(token, NUEVA, NUEVA)
    db.session.refresh(usuario)
    assert usuario.intentos_fallidos == 0 and usuario.bloqueado_hasta is None


def test_restablecer_valida_politica_y_confirmacion(usuario):
    token = ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    with pytest.raises(ValueError):
        ServicioRecuperacion.restablecer(token, "corta", "corta")
    with pytest.raises(ValueError):
        ServicioRecuperacion.restablecer(token, NUEVA, NUEVA + "x")
    ServicioRecuperacion.validar_token(token)


def test_restablecer_queda_auditado(usuario):
    token = ServicioRecuperacion.solicitar(EMAIL_REC, enviar_correo=False)
    ServicioRecuperacion.restablecer(token, NUEVA, NUEVA)
    acciones = db.session.execute(
        select(LogAuditoria.accion).where(LogAuditoria.usuario_id == usuario.id)
    ).scalars().all()
    assert AccionAuditoria.SOLICITAR_RECUPERACION in acciones
    assert AccionAuditoria.RESTABLECER_CONTRASENA in acciones
