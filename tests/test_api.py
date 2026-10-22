from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.enum import Categoria, EstadoTicket, RolUsuario
from app.services.exceptions import TokenApiInvalidoError
from app.services.tokens_api import LimitadorPeticiones, MAX_TOKENS_ACTIVOS, ServicioTokensApi
from tests.fabricas import crear_ticket, crear_usuario


@pytest.fixture(scope="module")
def cliente(app):
    from app.routes.api import api_bp
    from app.routes.colaboracion import colaboracion_bp
    from app.routes.conocimiento import conocimiento_bp
    from app.routes.tickets import tickets_bp
    from app.routes.auth import auth_bp
    for bp in (api_bp, colaboracion_bp, conocimiento_bp, tickets_bp, auth_bp):
        if bp.name not in app.blueprints:
            app.register_blueprint(bp)
    return app.test_client()


def test_token_se_guarda_hasheado_y_autentica():
    usuario = crear_usuario()
    token, crudo = ServicioTokensApi.crear(usuario.id, "Integración", dias=30)
    assert crudo.startswith("tk_") and token.token_hash != crudo and len(token.token_hash) == 64
    assert crudo.startswith(token.prefijo)
    t, u = ServicioTokensApi.autenticar(crudo)
    assert u.id == usuario.id and t.ultimo_uso is not None


def test_token_revocado_expirado_o_cuenta_inactiva():
    usuario = crear_usuario()
    token, crudo = ServicioTokensApi.crear(usuario.id, "Uno", dias=7)
    ServicioTokensApi.revocar(usuario.id, token.id)
    with pytest.raises(TokenApiInvalidoError):
        ServicioTokensApi.autenticar(crudo)
    token2, crudo2 = ServicioTokensApi.crear(usuario.id, "Dos", dias=7)
    token2.expira = datetime.now() - timedelta(minutes=1)
    db.session.commit()
    with pytest.raises(TokenApiInvalidoError):
        ServicioTokensApi.autenticar(crudo2)
    _t3, crudo3 = ServicioTokensApi.crear(usuario.id, "Tres", dias=None)
    usuario.activo = False
    db.session.commit()
    with pytest.raises(TokenApiInvalidoError):
        ServicioTokensApi.autenticar(crudo3)
    with pytest.raises(TokenApiInvalidoError):
        ServicioTokensApi.autenticar("tk_inventado")


def test_no_revoca_tokens_ajenos():
    dueno, otro = crear_usuario(), crear_usuario()
    token, _crudo = ServicioTokensApi.crear(dueno.id, "Ajeno", dias=7)
    with pytest.raises(TokenApiInvalidoError):
        ServicioTokensApi.revocar(otro.id, token.id)


def test_limite_de_tokens_activos():
    usuario = crear_usuario()
    for i in range(MAX_TOKENS_ACTIVOS):
        ServicioTokensApi.crear(usuario.id, f"Token {i}", dias=7)
    with pytest.raises(ValueError):
        ServicioTokensApi.crear(usuario.id, "Uno de más", dias=7)
    with pytest.raises(ValueError):
        ServicioTokensApi.crear(crear_usuario().id, "Duración rara", dias=3)


def test_limitador_ventana_deslizante():
    limitador = LimitadorPeticiones(limite=2, ventana_segundos=60)
    assert limitador.permitir("k", ahora=0)[0]
    assert limitador.permitir("k", ahora=1)[0]
    permitido, espera = limitador.permitir("k", ahora=2)
    assert not permitido and espera > 0
    assert limitador.permitir("k", ahora=61)[0]


def _cabeceras(usuario):
    _t, crudo = ServicioTokensApi.crear(usuario.id, "Pruebas API", dias=7)
    return {"Authorization": f"Bearer {crudo}"}


def test_api_requiere_token(cliente):
    r = cliente.get("/api/v1/yo")
    assert r.status_code == 401 and r.json["error"]["codigo"] == "no_autorizado"


def test_api_usuario_final_solo_ve_lo_suyo(cliente):
    yo, otro = crear_usuario(), crear_usuario()
    mio = crear_ticket(yo)
    ajeno = crear_ticket(otro)
    h = _cabeceras(yo)
    r = cliente.get("/api/v1/tickets?por_pagina=100", headers=h)
    ids = {t["id"] for t in r.json["datos"]}
    assert mio.id in ids and ajeno.id not in ids
    assert cliente.get(f"/api/v1/tickets/{ajeno.id}", headers=h).status_code == 404
    assert cliente.get(f"/api/v1/tickets/{mio.id}", headers=h).status_code == 200
    assert cliente.get("/api/v1/metricas", headers=h).status_code == 403


def test_api_oculta_notas_internas_al_usuario_final(cliente):
    from app.services.tickets import ServicioTickets

    creador = crear_usuario()
    agente = crear_usuario(RolUsuario.AGENTE, area=Categoria.REDES)
    ticket = crear_ticket(creador, estado=EstadoTicket.EN_PROGRESO, agente=agente)
    ServicioTickets.agregar_comentario(ticket.id, agente.id, "secreto interno", interno=True, notificar=False)
    cuerpo = cliente.get(f"/api/v1/tickets/{ticket.id}", headers=_cabeceras(creador)).json
    assert cuerpo["comentarios"] == []
    cuerpo = cliente.get(f"/api/v1/tickets/{ticket.id}", headers=_cabeceras(agente)).json
    assert cuerpo["comentarios"][0]["interno"] is True
    r = cliente.post(f"/api/v1/tickets/{ticket.id}/comentarios", headers=_cabeceras(creador), json={"texto": "x", "interno": True})
    assert r.status_code == 403


def test_api_validaciones(cliente):
    h = _cabeceras(crear_usuario())
    assert cliente.get("/api/v1/tickets?estado=inventado", headers=h).status_code == 400
    assert cliente.post("/api/v1/tickets", headers=h, json={"texto": "corto"}).status_code == 422
    assert cliente.get("/api/v1/no-existe", headers=h).status_code == 404
