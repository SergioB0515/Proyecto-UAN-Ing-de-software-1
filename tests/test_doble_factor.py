import json
import time

import pytest

from app.extensions import db
from app.models.doble_factor import DobleFactor
from app.models.log_auditoria import LogAuditoria
from app.models.enum import RolUsuario, NivelUsuario, AccionAuditoria
from app.models.usuario import Usuario
from app.services.autenticacion import ServicioAutenticacion
from app.services.doble_factor import ServicioDobleFactor, MAX_INTENTOS_FALLIDOS, PERIODO_SEGUNDOS
from app.services.exceptions import (
    CodigoInvalidoError,
    DobleFactorBloqueadoError,
    DobleFactorNoConfiguradoError,
    DobleFactorYaActivoError,
)
from sqlalchemy import select, func

EMAIL_2FA = "prueba_2fa@empresa.com"
CONTRASENA = "ClaveSegura123!"
SECRETO_RFC = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


def _crear_usuario(email):
    existente = db.session.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()
    if existente:
        registro = ServicioDobleFactor.obtener_registro(existente.id)
        if registro:
            db.session.delete(registro)
        db.session.delete(existente)
        db.session.commit()
    usuario = Usuario(
        nombre="Usuario 2FA", email=email,
        contrasena_hash=ServicioAutenticacion._generar_hash(CONTRASENA),
        rol=RolUsuario.FINAL, nivel=NivelUsuario.NORMAL,
    )
    db.session.add(usuario)
    db.session.commit()
    return usuario


@pytest.fixture
def usuario():
    return _crear_usuario(EMAIL_2FA)


def _activar(usuario):
    secreto, _uri = ServicioDobleFactor.iniciar_configuracion(usuario)
    ahora = time.time()
    codigos = ServicioDobleFactor.confirmar_configuracion(usuario, ServicioDobleFactor.codigo_totp(secreto, ahora), ahora)
    return secreto, codigos


def _contar_logs(usuario_id, accion):
    return db.session.execute(
        select(func.count(LogAuditoria.id)).where(LogAuditoria.usuario_id == usuario_id, LogAuditoria.accion == accion)
    ).scalar()


@pytest.mark.parametrize("instante, esperado", [
    (59, "287082"),
    (1111111109, "081804"),
    (1111111111, "050471"),
    (1234567890, "005924"),
    (2000000000, "279037"),
])
def test_totp_coincide_con_vectores_rfc_6238(instante, esperado):
    assert ServicioDobleFactor.codigo_totp(SECRETO_RFC, instante) == esperado


def test_secreto_generado_es_base32_de_160_bits():
    secreto = ServicioDobleFactor.generar_secreto()
    assert len(secreto) == 32
    assert set(secreto) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


def test_uri_aprovisionamiento_contiene_datos_necesarios():
    uri = ServicioDobleFactor.uri_aprovisionamiento("ABC", "a@b.com")
    assert uri.startswith("otpauth://totp/")
    assert "secret=ABC" in uri and "issuer=Tickets%20IT" in uri and "digits=6" in uri and "period=30" in uri


def test_iniciar_configuracion_deja_registro_inactivo(usuario):
    secreto, uri = ServicioDobleFactor.iniciar_configuracion(usuario)
    registro = ServicioDobleFactor.obtener_registro(usuario.id)
    assert registro is not None and not registro.activo
    assert registro.secreto == secreto
    assert ServicioDobleFactor.esta_activo(usuario.id) is False
    assert ServicioDobleFactor.configuracion_pendiente(usuario)[0] == secreto


def test_confirmar_con_codigo_incorrecto_no_activa(usuario):
    ServicioDobleFactor.iniciar_configuracion(usuario)
    with pytest.raises(CodigoInvalidoError):
        ServicioDobleFactor.confirmar_configuracion(usuario, "000000", 0)
    assert ServicioDobleFactor.esta_activo(usuario.id) is False


def test_confirmar_sin_iniciar_falla(usuario):
    with pytest.raises(DobleFactorNoConfiguradoError):
        ServicioDobleFactor.confirmar_configuracion(usuario, "123456")


def test_activar_genera_codigos_y_audita(usuario):
    antes = _contar_logs(usuario.id, AccionAuditoria.ACTIVAR_2FA)
    _secreto, codigos = _activar(usuario)
    assert ServicioDobleFactor.esta_activo(usuario.id)
    assert len(codigos) == 8 and len(set(codigos)) == 8
    assert all(len(c) == 9 and c[4] == "-" for c in codigos)
    registro = ServicioDobleFactor.obtener_registro(usuario.id)
    assert all(c not in registro.codigos_respaldo for c in codigos), "los codigos no deben guardarse en claro"
    assert ServicioDobleFactor.codigos_restantes(usuario.id) == 8
    assert _contar_logs(usuario.id, AccionAuditoria.ACTIVAR_2FA) == antes + 1


def test_no_se_puede_iniciar_si_ya_esta_activo(usuario):
    _activar(usuario)
    with pytest.raises(DobleFactorYaActivoError):
        ServicioDobleFactor.iniciar_configuracion(usuario)


def test_verificar_codigo_totp_valido(usuario):
    secreto, _codigos = _activar(usuario)
    instante = time.time() + PERIODO_SEGUNDOS * 2
    assert ServicioDobleFactor.verificar(usuario.id, ServicioDobleFactor.codigo_totp(secreto, instante), instante)


def test_verificar_acepta_un_paso_de_desfase(usuario):
    secreto, _codigos = _activar(usuario)
    instante = time.time() + PERIODO_SEGUNDOS * 3
    codigo_anterior = ServicioDobleFactor.codigo_totp(secreto, instante - PERIODO_SEGUNDOS)
    assert ServicioDobleFactor.verificar(usuario.id, codigo_anterior, instante)


def test_codigo_totp_no_se_puede_reutilizar(usuario):
    secreto, _codigos = _activar(usuario)
    instante = time.time() + PERIODO_SEGUNDOS * 2
    codigo = ServicioDobleFactor.codigo_totp(secreto, instante)
    ServicioDobleFactor.verificar(usuario.id, codigo, instante)
    with pytest.raises(CodigoInvalidoError):
        ServicioDobleFactor.verificar(usuario.id, codigo, instante)


def test_codigo_de_respaldo_sirve_una_sola_vez(usuario):
    _secreto, codigos = _activar(usuario)
    antes = _contar_logs(usuario.id, AccionAuditoria.USO_CODIGO_RESPALDO)
    assert ServicioDobleFactor.verificar(usuario.id, codigos[0].lower().replace("-", " "))
    assert ServicioDobleFactor.codigos_restantes(usuario.id) == 7
    assert _contar_logs(usuario.id, AccionAuditoria.USO_CODIGO_RESPALDO) == antes + 1
    with pytest.raises(CodigoInvalidoError):
        ServicioDobleFactor.verificar(usuario.id, codigos[0])


def test_codigo_incorrecto_audita_fallo(usuario):
    _activar(usuario)
    antes = _contar_logs(usuario.id, AccionAuditoria.VERIFICACION_2FA_FALLIDA)
    with pytest.raises(CodigoInvalidoError):
        ServicioDobleFactor.verificar(usuario.id, "ZZZZ-ZZZZ")
    assert _contar_logs(usuario.id, AccionAuditoria.VERIFICACION_2FA_FALLIDA) == antes + 1


def test_bloqueo_tras_intentos_fallidos_impide_incluso_codigo_correcto(usuario):
    secreto, _codigos = _activar(usuario)
    for _i in range(MAX_INTENTOS_FALLIDOS):
        with pytest.raises(CodigoInvalidoError):
            ServicioDobleFactor.verificar(usuario.id, "AAAA-AAAA")
    instante = time.time() + PERIODO_SEGUNDOS * 2
    with pytest.raises(DobleFactorBloqueadoError):
        ServicioDobleFactor.verificar(usuario.id, ServicioDobleFactor.codigo_totp(secreto, instante), instante)


def test_regenerar_codigos_invalida_los_anteriores(usuario):
    secreto, viejos = _activar(usuario)
    instante = time.time() + PERIODO_SEGUNDOS * 2
    nuevos = ServicioDobleFactor.regenerar_codigos_respaldo(usuario, ServicioDobleFactor.codigo_totp(secreto, instante), instante)
    assert set(nuevos).isdisjoint(viejos)
    with pytest.raises(CodigoInvalidoError):
        ServicioDobleFactor.verificar(usuario.id, viejos[1])
    assert ServicioDobleFactor.verificar(usuario.id, nuevos[0])


def test_desactivar_requiere_contrasena_correcta(usuario):
    _activar(usuario)
    with pytest.raises(ValueError):
        ServicioDobleFactor.desactivar(usuario, "ClaveEquivocada1!")
    assert ServicioDobleFactor.esta_activo(usuario.id)
    ServicioDobleFactor.desactivar(usuario, CONTRASENA)
    assert ServicioDobleFactor.esta_activo(usuario.id) is False
    assert ServicioDobleFactor.obtener_registro(usuario.id) is None


def test_verificar_sin_2fa_activo_falla(usuario):
    with pytest.raises(DobleFactorNoConfiguradoError):
        ServicioDobleFactor.verificar(usuario.id, "123456")
