"""Pruebas de los webhooks salientes: validacion, firma, reintentos y bitacora.

Ninguna prueba sale a la red: se sustituye ServicioWebhooks._enviar_http, que
es el unico punto donde el servicio toca requests.
"""

import json
import time

import pytest
from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models.enum import AccionAuditoria, Categoria, EstadoTicket, RolUsuario
from app.models.log_auditoria import LogAuditoria
from app.models.usuario import Usuario
from app.models.webhook import EntregaWebhook, Webhook
from app.services.exceptions import WebhookInvalidoError, WebhookNoEncontradoError
from app.services.tickets import ServicioTickets
from app.services.webhooks import MAX_FALLOS, MAX_WEBHOOKS, ServicioWebhooks
from tests.fabricas import crear_ticket, crear_usuario

AREA = Categoria.SOFTWARE
URL = "https://ejemplo.com/hooks/tickets"


@pytest.fixture
def admin():
    return crear_usuario(rol=RolUsuario.ADMIN)


@pytest.fixture
def creador():
    return crear_usuario(rol=RolUsuario.FINAL)

@pytest.fixture(autouse=True)
def agentes_sin_rastro():
    """Desactiva al terminar los agentes creados en esta prueba.

    La base de pruebas se comparte entre archivos y se ejecutan en orden
    alfabetico: un agente de este archivo que quede activo y sin carga le
    cambia el resultado a las pruebas de sugerencia de agente que corren
    despues. Desactivarlo deja el area como estaba.
    """
    previos = {
        u.id for u in db.session.execute(
            select(Usuario).where(Usuario.rol == RolUsuario.AGENTE)
        ).scalars().all()
    }

    yield

    nuevos = db.session.execute(
        select(Usuario).where(
            Usuario.rol == RolUsuario.AGENTE, Usuario.id.notin_(previos or {0})
        )
    ).scalars().all()
    for agente_creado in nuevos:
        agente_creado.activo = False
    db.session.commit()



@pytest.fixture(autouse=True)
def sin_webhooks_previos():
    """Cada prueba arranca sin webhooks: el limite y los conteos son globales."""
    for webhook in db.session.execute(select(Webhook)).scalars().all():
        for entrega in db.session.execute(
            select(EntregaWebhook).where(EntregaWebhook.webhook_id == webhook.id)
        ).scalars().all():
            db.session.delete(entrega)
        db.session.delete(webhook)
    db.session.commit()
    yield


class Envios(list):
    """Lista de peticiones capturadas con la respuesta que debe devolver."""

    def __init__(self):
        super().__init__()
        self.respuestas = {"codigo": 200, "error": None}


@pytest.fixture
def envios(monkeypatch):
    """Captura las peticiones y responde 200 por defecto."""
    capturados = Envios()

    def falso_envio(url, cuerpo, cabeceras):
        capturados.append({"url": url, "cuerpo": cuerpo, "cabeceras": cabeceras})
        return capturados.respuestas["codigo"], capturados.respuestas["error"]

    monkeypatch.setattr(ServicioWebhooks, "_enviar_http", staticmethod(falso_envio))
    return capturados


def _registrar(admin, eventos=None, url=URL, nombre="Canal de guardia"):
    if eventos is None:
        eventos = [ServicioWebhooks.EVENTO_CREADO]
    return ServicioWebhooks.registrar(admin.id, nombre, url, eventos)


# ------------------------------------------------------------- validacion

def test_la_url_tiene_que_ser_http(admin):
    for mala in ("", "ftp://ejemplo.com/x", "ejemplo.com/x", "javascript:alert(1)"):
        with pytest.raises(WebhookInvalidoError):
            _registrar(admin, url=mala)


def test_los_destinos_internos_estan_bloqueados(admin):
    for interna in ("http://localhost:5000/hook", "http://127.0.0.1/hook",
                    "https://192.168.1.10/hook", "http://10.0.0.5/hook"):
        with pytest.raises(WebhookInvalidoError):
            _registrar(admin, url=interna)


def test_los_destinos_internos_se_pueden_habilitar(admin):
    current_app.config["WEBHOOKS_PERMITIR_DESTINOS_LOCALES"] = True
    try:
        webhook = _registrar(admin, url="http://localhost:9000/hook")
        assert webhook.url == "http://localhost:9000/hook"
    finally:
        current_app.config["WEBHOOKS_PERMITIR_DESTINOS_LOCALES"] = False


def test_hace_falta_al_menos_un_evento_valido(admin):
    with pytest.raises(WebhookInvalidoError):
        _registrar(admin, eventos=[])
    with pytest.raises(WebhookInvalidoError):
        _registrar(admin, eventos=["evento.inventado"])


def test_el_nombre_es_obligatorio(admin):
    with pytest.raises(WebhookInvalidoError):
        _registrar(admin, nombre="   ")


def test_registrar_genera_secreto_y_queda_en_auditoria(admin):
    webhook = _registrar(admin, eventos=[ServicioWebhooks.EVENTO_CREADO, ServicioWebhooks.EVENTO_CERRADO])

    assert len(webhook.secreto) == 64
    assert webhook.activo is True
    assert webhook.lista_eventos == sorted([ServicioWebhooks.EVENTO_CERRADO, ServicioWebhooks.EVENTO_CREADO])

    logs = db.session.execute(
        select(LogAuditoria).where(LogAuditoria.accion == AccionAuditoria.CREAR_WEBHOOK)
    ).scalars().all()
    assert any(webhook.nombre in (l.detalle or "") for l in logs)


def test_hay_un_tope_de_webhooks(admin):
    for i in range(MAX_WEBHOOKS):
        _registrar(admin, nombre=f"Destino {i}")
    with pytest.raises(WebhookInvalidoError):
        _registrar(admin, nombre="Uno más")


def test_obtener_un_webhook_inexistente_falla(admin):
    with pytest.raises(WebhookNoEncontradoError):
        ServicioWebhooks.obtener(999999)


# ------------------------------------------------------------------ firma

def test_la_firma_se_valida_con_el_secreto_correcto():
    cuerpo = json.dumps({"evento": "ping"})
    cabecera, _marca = ServicioWebhooks.firmar(cuerpo, "secreto-compartido")

    assert ServicioWebhooks.verificar(cuerpo, "secreto-compartido", cabecera) is True
    assert ServicioWebhooks.verificar(cuerpo, "otro-secreto", cabecera) is False
    assert ServicioWebhooks.verificar(cuerpo + " ", "secreto-compartido", cabecera) is False
    assert ServicioWebhooks.verificar(cuerpo, "secreto-compartido", "basura") is False


def test_una_firma_vieja_se_rechaza():
    cuerpo = json.dumps({"evento": "ping"})
    cabecera, marca = ServicioWebhooks.firmar(cuerpo, "secreto", marca_tiempo=int(time.time()) - 3600)

    assert ServicioWebhooks.verificar(cuerpo, "secreto", cabecera) is False
    # Sin tolerancia la firma sigue siendo correcta: lo que caduca es la marca.
    assert ServicioWebhooks.verificar(cuerpo, "secreto", cabecera, tolerancia_segundos=None) is True


# ---------------------------------------------------------------- emision

def test_sin_webhooks_no_se_envia_nada(admin, creador, envios):
    ServicioTickets.crear_ticket(creador, "no imprime nada la impresora del piso 3")
    assert list(envios) == []


def test_el_ticket_creado_llega_firmado_al_webhook(admin, creador, envios):
    webhook = _registrar(admin, eventos=[ServicioWebhooks.EVENTO_CREADO])

    ticket = ServicioTickets.crear_ticket(creador, "no tengo permisos en la carpeta compartida")

    assert len(envios) == 1
    envio = envios[0]
    assert envio["url"] == URL
    assert envio["cabeceras"]["X-Tickets-Event"] == ServicioWebhooks.EVENTO_CREADO
    assert ServicioWebhooks.verificar(envio["cuerpo"], webhook.secreto,
                                      envio["cabeceras"]["X-Tickets-Signature"]) is True

    cuerpo = json.loads(envio["cuerpo"])
    assert cuerpo["evento"] == ServicioWebhooks.EVENTO_CREADO
    assert cuerpo["ticket"]["id"] == ticket.id
    assert cuerpo["ticket"]["estado"] == EstadoTicket.ABIERTO.value
    assert cuerpo["ticket"]["creador_id"] == creador.id


def test_solo_se_envian_los_eventos_suscritos(admin, creador, envios):
    _registrar(admin, eventos=[ServicioWebhooks.EVENTO_CERRADO])

    ServicioTickets.crear_ticket(creador, "la vpn se cae cada diez minutos")

    assert list(envios) == []


def test_el_cambio_de_estado_y_el_cierre_se_emiten(admin, creador, envios):
    agente = crear_usuario(rol=RolUsuario.AGENTE, area=AREA)
    ticket = crear_ticket(creador, categoria=AREA, estado=EstadoTicket.EN_PROGRESO, agente=agente)
    _registrar(admin, eventos=[ServicioWebhooks.EVENTO_ESTADO, ServicioWebhooks.EVENTO_CERRADO])

    ServicioTickets.cambiar_estado(ticket.id, EstadoTicket.CERRADO, agente.id)

    eventos = [e["cabeceras"]["X-Tickets-Event"] for e in envios]
    assert eventos == [ServicioWebhooks.EVENTO_ESTADO, ServicioWebhooks.EVENTO_CERRADO]
    cuerpo = json.loads(envios[0]["cuerpo"])
    assert cuerpo["datos"]["estado_anterior"] == EstadoTicket.EN_PROGRESO.value


def test_un_webhook_inactivo_no_recibe_nada(admin, creador, envios):
    webhook = _registrar(admin, eventos=[ServicioWebhooks.EVENTO_CREADO])
    ServicioWebhooks.cambiar_activo(admin.id, webhook.id, False)

    ServicioTickets.crear_ticket(creador, "necesito office en el equipo nuevo")

    assert list(envios) == []


# ------------------------------------------------------- entregas y fallos

def test_la_entrega_correcta_queda_en_la_bitacora(admin, envios):
    webhook = _registrar(admin)

    entrega = ServicioWebhooks.probar(admin.id, webhook.id)

    assert entrega.exito is True
    assert entrega.codigo_http == 200
    assert entrega.intentos == 1
    assert entrega.evento == ServicioWebhooks.EVENTO_PRUEBA
    assert ServicioWebhooks.entregas(webhook.id)[0].id == entrega.id
    assert webhook.fallos_consecutivos == 0
    assert webhook.ultimo_codigo == 200


def test_un_error_del_servidor_se_reintenta(admin, envios):
    webhook = _registrar(admin)
    envios.respuestas["codigo"] = 503
    payload = {"evento": "ping"}

    entrega = ServicioWebhooks.entregar(webhook, "ping", payload, intentos=3, espera=0)

    assert entrega.exito is False
    assert entrega.intentos == 3
    assert len(envios) == 3
    assert webhook.fallos_consecutivos == 1


def test_un_error_del_cliente_no_se_reintenta(admin, envios):
    webhook = _registrar(admin)
    envios.respuestas["codigo"] = 404

    entrega = ServicioWebhooks.entregar(webhook, "ping", {"evento": "ping"}, intentos=3, espera=0)

    assert entrega.exito is False
    assert entrega.intentos == 1
    assert len(envios) == 1


def test_sin_respuesta_se_guarda_el_error(admin, envios):
    webhook = _registrar(admin)
    envios.respuestas["codigo"] = None
    envios.respuestas["error"] = "tiempo de espera agotado"

    entrega = ServicioWebhooks.entregar(webhook, "ping", {"evento": "ping"}, intentos=1, espera=0)

    assert entrega.exito is False
    assert entrega.codigo_http is None
    assert "tiempo de espera" in entrega.error


def test_tras_demasiados_fallos_el_webhook_se_desactiva_solo(admin, envios):
    webhook = _registrar(admin)
    envios.respuestas["codigo"] = 500

    for _ in range(MAX_FALLOS):
        ServicioWebhooks.entregar(webhook, "ping", {"evento": "ping"}, intentos=1, espera=0)

    db.session.refresh(webhook)
    assert webhook.fallos_consecutivos == MAX_FALLOS
    assert webhook.activo is False

    logs = db.session.execute(
        select(LogAuditoria).where(LogAuditoria.accion == AccionAuditoria.EDITAR_WEBHOOK)
    ).scalars().all()
    assert any("automáticamente" in (l.detalle or "") for l in logs)


def test_una_entrega_correcta_borra_el_contador_de_fallos(admin, envios):
    webhook = _registrar(admin)
    envios.respuestas["codigo"] = 500
    ServicioWebhooks.entregar(webhook, "ping", {"evento": "ping"}, intentos=1, espera=0)
    assert webhook.fallos_consecutivos == 1

    envios.respuestas["codigo"] = 204
    ServicioWebhooks.entregar(webhook, "ping", {"evento": "ping"}, intentos=1, espera=0)

    db.session.refresh(webhook)
    assert webhook.fallos_consecutivos == 0
    assert webhook.activo is True


def test_reactivar_un_webhook_pone_el_contador_a_cero(admin, envios):
    webhook = _registrar(admin)
    envios.respuestas["codigo"] = 500
    ServicioWebhooks.entregar(webhook, "ping", {"evento": "ping"}, intentos=1, espera=0)

    ServicioWebhooks.cambiar_activo(admin.id, webhook.id, True)

    db.session.refresh(webhook)
    assert webhook.fallos_consecutivos == 0


def test_la_bitacora_no_crece_sin_limite(admin, envios, monkeypatch):
    monkeypatch.setattr("app.services.webhooks.LIMITE_ENTREGAS_GUARDADAS", 3)
    webhook = _registrar(admin)

    for _ in range(6):
        ServicioWebhooks.entregar(webhook, "ping", {"evento": "ping"}, intentos=1, espera=0)

    guardadas = db.session.execute(
        select(EntregaWebhook).where(EntregaWebhook.webhook_id == webhook.id)
    ).scalars().all()
    assert len(guardadas) == 3


def test_eliminar_un_webhook_se_lleva_su_bitacora(admin, envios):
    webhook = _registrar(admin)
    ServicioWebhooks.probar(admin.id, webhook.id)
    webhook_id = webhook.id

    ServicioWebhooks.eliminar(admin.id, webhook_id)

    assert db.session.get(Webhook, webhook_id) is None
    assert ServicioWebhooks.entregas(webhook_id) == []
