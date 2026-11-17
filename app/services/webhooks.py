"""Webhooks salientes firmados.

Cada evento relevante de un ticket se puede reenviar a un sistema externo
(un canal de Slack con un intermediario, un inventario, un monitor) mediante
un POST con el cuerpo en JSON.

El punto delicado de un webhook no es enviarlo, es que quien lo recibe pueda
creerlo: la URL suele ser publica y cualquiera podria enviarle un POST
diciendo que un ticket critico se cerro. Por eso cada envio va firmado con
HMAC-SHA256 sobre "<timestamp>.<cuerpo>" usando el secreto compartido del
webhook, y el timestamp viaja dentro de la firma para que una copia capturada
no se pueda reenviar mas tarde (replay).

El receptor valida asi:

    import hmac, hashlib
    t, v1 = (p.split("=", 1)[1] for p in cabecera.split(","))
    esperado = hmac.new(secreto.encode(), f"{t}.{cuerpo_crudo}".encode(),
                        hashlib.sha256).hexdigest()
    valido = hmac.compare_digest(esperado, v1) and abs(time.time() - int(t)) < 300

La emision nunca interrumpe la operacion que la disparo: si el destino esta
caido, se registra el fallo y el ticket sigue su curso. Tras
MAX_FALLOS entregas fallidas seguidas el webhook se desactiva solo, para no
gastar hilos y timeouts en una URL que ya no existe.
"""

import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime
from ipaddress import ip_address
from urllib.parse import urlparse

from flask import current_app
from flask_babel import gettext as _
from sqlalchemy import select

from app.extensions import db
from app.models.enum import AccionAuditoria
from app.models.webhook import EntregaWebhook, Webhook
from app.services.auditoria import ServicioAuditoria
from app.services.exceptions import (
    ErrorPersistencia,
    WebhookInvalidoError,
    WebhookNoEncontradoError,
)

MAX_WEBHOOKS = 10
MAX_FALLOS = 10
MAX_INTENTOS = 3
TIMEOUT_SEGUNDOS = 5
ESPERA_ENTRE_INTENTOS = 2
LIMITE_ENTREGAS_GUARDADAS = 50


class ServicioWebhooks:

    EVENTO_CREADO = "ticket.creado"
    EVENTO_ASIGNADO = "ticket.asignado"
    EVENTO_ESTADO = "ticket.estado_cambiado"
    EVENTO_CERRADO = "ticket.cerrado"
    EVENTO_SLA_VENCIDO = "sla.vencido"
    EVENTO_COBERTURA = "ticket.cobertura_requerida"
    EVENTO_PRUEBA = "ping"

    EVENTOS = {
        EVENTO_CREADO: "Se registró un ticket nuevo",
        EVENTO_ASIGNADO: "Un ticket cambió de agente",
        EVENTO_ESTADO: "Un ticket cambió de estado",
        EVENTO_CERRADO: "Un ticket se cerró",
        EVENTO_SLA_VENCIDO: "Un ticket pasó su fecha límite",
        EVENTO_COBERTURA: "Un ticket quedó sin agente disponible",
    }

    @staticmethod
    def catalogo_eventos():
        """EVENTOS con las descripciones traducidas al idioma de quien mira.

        Las cadenas se repiten literales aqui, en vez de traducir EVENTOS en la
        plantilla, porque pybabel solo extrae literales dentro de una llamada a
        gettext: con `_(variable)` la cadena no entraria al catalogo y la
        interfaz en ingles mostraria la descripcion en español.
        """
        return {
            ServicioWebhooks.EVENTO_CREADO: _("Se registró un ticket nuevo"),
            ServicioWebhooks.EVENTO_ASIGNADO: _("Un ticket cambió de agente"),
            ServicioWebhooks.EVENTO_ESTADO: _("Un ticket cambió de estado"),
            ServicioWebhooks.EVENTO_CERRADO: _("Un ticket se cerró"),
            ServicioWebhooks.EVENTO_SLA_VENCIDO: _("Un ticket pasó su fecha límite"),
            ServicioWebhooks.EVENTO_COBERTURA: _("Un ticket quedó sin agente disponible"),
        }

    # ------------------------------------------------------------- lectura

    @staticmethod
    def listar(solo_activos=False):
        query = select(Webhook)
        if solo_activos:
            query = query.where(Webhook.activo.is_(True))
        return db.session.execute(query.order_by(Webhook.fecha_creacion.desc())).scalars().all()

    @staticmethod
    def obtener(webhook_id):
        webhook = db.session.get(Webhook, webhook_id)
        if webhook is None:
            raise WebhookNoEncontradoError(_("El webhook no existe"))
        return webhook

    @staticmethod
    def entregas(webhook_id, limite=20):
        return db.session.execute(
            select(EntregaWebhook)
            .where(EntregaWebhook.webhook_id == webhook_id)
            .order_by(EntregaWebhook.fecha.desc())
            .limit(limite)
        ).scalars().all()

    # ------------------------------------------------------------ validacion

    @staticmethod
    def _validar_url(url):
        """Acepta solo http(s) y, por defecto, ningun destino interno.

        Un webhook es una peticion que el servidor hace a donde le digan: sin
        esta validacion, quien pueda crear uno podria usar el servidor para
        tocar servicios de la red interna que desde fuera no son visibles
        (SSRF). Los destinos locales se permiten solo si la instalacion lo
        habilita a proposito, que es lo que hace falta para probar en local.
        """
        url = (url or "").strip()
        if not url:
            raise WebhookInvalidoError(_("La URL es obligatoria"))
        if len(url) > 500:
            raise WebhookInvalidoError(_("La URL es demasiado larga"))

        partes = urlparse(url)
        if partes.scheme not in ("http", "https") or not partes.hostname:
            raise WebhookInvalidoError(_("La URL debe empezar por http:// o https://"))

        permite_locales = bool(current_app.config.get("WEBHOOKS_PERMITIR_DESTINOS_LOCALES", False))
        if permite_locales:
            return url

        host = partes.hostname.lower()
        if host in ("localhost", "localhost.localdomain") or host.endswith(".localhost"):
            raise WebhookInvalidoError(_("No se permiten destinos locales"))
        try:
            direccion = ip_address(host)
        except ValueError:
            return url
        if direccion.is_private or direccion.is_loopback or direccion.is_link_local or direccion.is_reserved:
            raise WebhookInvalidoError(_("No se permiten destinos de la red interna"))
        return url

    @staticmethod
    def _validar_eventos(eventos):
        elegidos = [e for e in (eventos or []) if e in ServicioWebhooks.EVENTOS]
        if not elegidos:
            raise WebhookInvalidoError(_("Elige al menos un evento válido"))
        return sorted(set(elegidos))

    # ----------------------------------------------------------- escritura

    @staticmethod
    def _guardar(mensaje):
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"{mensaje}, error: {e}")
            raise ErrorPersistencia(mensaje) from e

    @staticmethod
    def registrar(actor_id, nombre, url, eventos):
        nombre = (nombre or "").strip()
        if not nombre:
            raise WebhookInvalidoError(_("El nombre es obligatorio"))
        if len(nombre) > 80:
            raise WebhookInvalidoError(_("El nombre no puede superar los 80 caracteres"))

        url = ServicioWebhooks._validar_url(url)
        elegidos = ServicioWebhooks._validar_eventos(eventos)

        if len(ServicioWebhooks.listar()) >= MAX_WEBHOOKS:
            raise WebhookInvalidoError(
                _("No puedes tener más de %(n)s webhooks registrados", n=MAX_WEBHOOKS)
            )

        webhook = Webhook(
            nombre=nombre,
            url=url,
            secreto=secrets.token_hex(32),
            eventos=",".join(elegidos),
            activo=True,
            creado_por_id=actor_id,
        )
        db.session.add(webhook)
        ServicioWebhooks._guardar(_("No se pudo registrar el webhook"))

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.CREAR_WEBHOOK,
            detalle=_("Webhook %(p1)s creado hacia %(p2)s (%(p3)s)",
                      p1=nombre, p2=url, p3=", ".join(elegidos)),
        )
        return webhook

    @staticmethod
    def cambiar_activo(actor_id, webhook_id, activo):
        webhook = ServicioWebhooks.obtener(webhook_id)
        webhook.activo = bool(activo)
        if webhook.activo:
            webhook.fallos_consecutivos = 0
        db.session.add(webhook)
        ServicioWebhooks._guardar(_("No se pudo actualizar el webhook"))

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.EDITAR_WEBHOOK,
            detalle=_("Webhook %(p1)s %(p2)s", p1=webhook.nombre,
                      p2=_("activado") if webhook.activo else _("desactivado")),
        )
        return webhook

    @staticmethod
    def eliminar(actor_id, webhook_id):
        webhook = ServicioWebhooks.obtener(webhook_id)
        nombre = webhook.nombre
        for entrega in ServicioWebhooks.entregas(webhook_id, limite=LIMITE_ENTREGAS_GUARDADAS * 10):
            db.session.delete(entrega)
        db.session.delete(webhook)
        ServicioWebhooks._guardar(_("No se pudo eliminar el webhook"))

        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.ELIMINAR_WEBHOOK,
            detalle=_("Webhook %(p1)s eliminado", p1=nombre),
        )
        return True

    # -------------------------------------------------------------- firma

    @staticmethod
    def firmar(cuerpo, secreto, marca_tiempo=None):
        """Devuelve (cabecera, marca_tiempo) para un cuerpo ya serializado."""
        marca_tiempo = marca_tiempo or int(time.time())
        base = f"{marca_tiempo}.{cuerpo}".encode("utf-8")
        firma = hmac.new(secreto.encode("utf-8"), base, hashlib.sha256).hexdigest()
        return f"t={marca_tiempo},v1={firma}", marca_tiempo

    @staticmethod
    def verificar(cuerpo, secreto, cabecera, tolerancia_segundos=300, ahora=None):
        """Valida una cabecera de firma. La usan las pruebas y el receptor."""
        try:
            partes = dict(p.split("=", 1) for p in (cabecera or "").split(","))
            marca = int(partes["t"])
            recibida = partes["v1"]
        except (ValueError, KeyError):
            return False

        ahora = ahora if ahora is not None else time.time()
        if tolerancia_segundos is not None and abs(ahora - marca) > tolerancia_segundos:
            return False

        esperada, _marca = ServicioWebhooks.firmar(cuerpo, secreto, marca)
        return hmac.compare_digest(esperada.split("v1=")[1], recibida)

    # ------------------------------------------------------------- emision

    @staticmethod
    def _payload(evento, ticket, extra=None):
        cuerpo = {
            "evento": evento,
            "enviado_en": datetime.now().isoformat(timespec="seconds"),
        }
        if ticket is not None:
            cuerpo["ticket"] = {
                "id": ticket.id,
                "texto": ticket.texto,
                "categoria": ticket.categoria.value,
                "prioridad": ticket.prioridad.value,
                "estado": ticket.estado.value,
                "creador_id": ticket.creador_id,
                "agente_id": ticket.agente_id,
                "fecha_creacion": ticket.fecha_creacion.isoformat(timespec="seconds") if ticket.fecha_creacion else None,
                "fecha_limite": ticket.fecha_limite.isoformat(timespec="seconds") if ticket.fecha_limite else None,
                "requiere_cobertura": bool(ticket.requiere_cobertura),
            }
        if extra:
            cuerpo["datos"] = extra
        return cuerpo

    @staticmethod
    def _enviar_http(url, cuerpo, cabeceras):
        """Un unico POST. Aislado para poder sustituirlo en las pruebas.

        Devuelve (codigo_http, error). requests se importa aqui dentro para
        que un entorno sin la libreria siga pudiendo arrancar la aplicacion.
        """
        try:
            import requests

            respuesta = requests.post(
                url, data=cuerpo.encode("utf-8"), headers=cabeceras, timeout=TIMEOUT_SEGUNDOS
            )
            return respuesta.status_code, None
        except Exception as e:
            return None, str(e)[:300]

    @staticmethod
    def entregar(webhook, evento, payload, ticket_id=None, intentos=MAX_INTENTOS, espera=ESPERA_ENTRE_INTENTOS):
        """Envia un evento a un webhook y deja constancia del resultado.

        Reintenta solo los fallos que pueden ser transitorios (sin respuesta o
        error 5xx). Un 4xx significa que el receptor rechazo el mensaje, y
        repetirlo no lo va a cambiar.
        """
        cuerpo = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        inicio = time.time()
        codigo = None
        error = None
        enviados = 0

        for numero in range(1, max(1, intentos) + 1):
            enviados = numero
            cabecera_firma, marca = ServicioWebhooks.firmar(cuerpo, webhook.secreto)
            cabeceras = {
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "SistemaTicketsIT-Webhook/1.0",
                "X-Tickets-Event": evento,
                "X-Tickets-Timestamp": str(marca),
                "X-Tickets-Signature": cabecera_firma,
                "X-Tickets-Delivery": f"{webhook.id}-{int(inicio * 1000)}-{numero}",
            }
            codigo, error = ServicioWebhooks._enviar_http(webhook.url, cuerpo, cabeceras)

            if codigo is not None and 200 <= codigo < 300:
                error = None
                break
            if codigo is not None and 400 <= codigo < 500:
                error = error or f"HTTP {codigo}"
                break
            error = error or f"HTTP {codigo}"
            if numero < intentos and espera:
                time.sleep(espera)

        exito = codigo is not None and 200 <= codigo < 300
        entrega = EntregaWebhook(
            webhook_id=webhook.id,
            evento=evento,
            ticket_id=ticket_id,
            exito=exito,
            codigo_http=codigo,
            intentos=enviados,
            error=None if exito else (error or "")[:300] or None,
            duracion_ms=int((time.time() - inicio) * 1000),
        )
        webhook.ultimo_intento = datetime.now()
        webhook.ultimo_codigo = codigo
        webhook.fallos_consecutivos = 0 if exito else (webhook.fallos_consecutivos or 0) + 1

        desactivado = False
        if not exito and webhook.fallos_consecutivos >= MAX_FALLOS and webhook.activo:
            webhook.activo = False
            desactivado = True

        db.session.add(entrega)
        db.session.add(webhook)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudo registrar la entrega del webhook, error: {e}")
            return entrega

        if desactivado:
            ServicioAuditoria.registrar(
                usuario_id=webhook.creado_por_id,
                accion=AccionAuditoria.EDITAR_WEBHOOK,
                detalle=_("Webhook %(p1)s desactivado automáticamente tras %(p2)s fallos seguidos",
                          p1=webhook.nombre, p2=MAX_FALLOS),
            )

        ServicioWebhooks._podar_entregas(webhook.id)
        return entrega

    @staticmethod
    def _podar_entregas(webhook_id):
        """Deja solo las ultimas entregas: la bitacora no debe crecer sin fin."""
        viejas = db.session.execute(
            select(EntregaWebhook)
            .where(EntregaWebhook.webhook_id == webhook_id)
            .order_by(EntregaWebhook.fecha.desc(), EntregaWebhook.id.desc())
            .offset(LIMITE_ENTREGAS_GUARDADAS)
        ).scalars().all()
        if not viejas:
            return 0
        for entrega in viejas:
            db.session.delete(entrega)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"No se pudieron podar las entregas del webhook, error: {e}")
            return 0
        return len(viejas)

    @staticmethod
    def emitir(evento, ticket=None, extra=None):
        """Avisa a todos los webhooks suscritos a este evento.

        Se llama desde los servicios de dominio, asi que lo primero que hace es
        la consulta mas barata posible: si no hay ningun webhook escuchando
        este evento, no hay payload, ni hilo, ni rastro en la operacion que la
        disparo (que es el caso normal de una instalacion sin webhooks).
        """
        try:
            activos = [w for w in ServicioWebhooks.listar(solo_activos=True) if w.escucha(evento)]
        except Exception as e:
            db.session.rollback()
            print(f"No se pudieron consultar los webhooks, error: {e}")
            return []

        if not activos:
            return []

        payload = ServicioWebhooks._payload(evento, ticket, extra)
        ticket_id = ticket.id if ticket is not None else None

        if not current_app.config.get("WEBHOOKS_EN_HILO", True):
            return [ServicioWebhooks.entregar(w, evento, payload, ticket_id) for w in activos]

        app = current_app._get_current_object()
        ids = [w.id for w in activos]
        threading.Thread(
            target=ServicioWebhooks._entregar_en_hilo,
            args=(app, ids, evento, payload, ticket_id),
            daemon=True,
        ).start()
        return activos

    @staticmethod
    def _entregar_en_hilo(app, ids, evento, payload, ticket_id):
        with app.app_context():
            for webhook_id in ids:
                webhook = db.session.get(Webhook, webhook_id)
                if webhook is None or not webhook.activo:
                    continue
                try:
                    ServicioWebhooks.entregar(webhook, evento, payload, ticket_id)
                except Exception as e:
                    db.session.rollback()
                    print(f"Fallo la entrega del webhook {webhook_id}, error: {e}")

    @staticmethod
    def probar(actor_id, webhook_id):
        """Envia un evento de prueba, en el momento y sin reintentos."""
        webhook = ServicioWebhooks.obtener(webhook_id)
        payload = ServicioWebhooks._payload(ServicioWebhooks.EVENTO_PRUEBA, None, {
            "mensaje": "Envío de prueba desde el panel de webhooks",
            "webhook": webhook.nombre,
        })
        entrega = ServicioWebhooks.entregar(
            webhook, ServicioWebhooks.EVENTO_PRUEBA, payload, intentos=1, espera=0
        )
        ServicioAuditoria.registrar(
            usuario_id=actor_id,
            accion=AccionAuditoria.PROBAR_WEBHOOK,
            detalle=_("Prueba enviada al webhook %(p1)s: %(p2)s", p1=webhook.nombre,
                      p2=(_("correcta") if entrega.exito else _("fallida"))),
        )
        return entrega
