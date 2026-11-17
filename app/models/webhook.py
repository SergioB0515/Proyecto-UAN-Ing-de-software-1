from datetime import datetime

from app.extensions import db


class Webhook(db.Model):
    """Destino externo al que el sistema avisa cuando pasa algo con un ticket.

    Los eventos suscritos se guardan como una lista separada por comas en vez
    de una tabla aparte: son pocos, fijos y siempre se leen completos, asi que
    una tabla de union solo agregaria un join a cada emision.

    El secreto es el que se usa para firmar el cuerpo con HMAC-SHA256. Se
    guarda en claro a proposito: a diferencia de una contrasena o de un token
    de API, aqui el sistema necesita el valor original para poder firmar.
    """

    __tablename__ = "webhooks"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    secreto = db.Column(db.String(80), nullable=False)
    eventos = db.Column(db.String(400), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)
    fallos_consecutivos = db.Column(db.Integer, nullable=False, default=0)
    ultimo_intento = db.Column(db.DateTime, nullable=True)
    ultimo_codigo = db.Column(db.Integer, nullable=True)

    @property
    def lista_eventos(self):
        return [e for e in (self.eventos or "").split(",") if e]

    def escucha(self, evento):
        return evento in self.lista_eventos


class EntregaWebhook(db.Model):
    """Bitacora de cada intento de entrega.

    ticket_id no es llave foranea: la bitacora tiene que sobrevivir al ticket
    que la origino, igual que el log de auditoria.
    """

    __tablename__ = "entregas_webhook"

    id = db.Column(db.Integer, primary_key=True)
    webhook_id = db.Column(db.Integer, db.ForeignKey("webhooks.id"), nullable=False)
    evento = db.Column(db.String(40), nullable=False)
    ticket_id = db.Column(db.Integer, nullable=True)
    exito = db.Column(db.Boolean, nullable=False, default=False)
    codigo_http = db.Column(db.Integer, nullable=True)
    intentos = db.Column(db.Integer, nullable=False, default=1)
    error = db.Column(db.String(300), nullable=True)
    duracion_ms = db.Column(db.Integer, nullable=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)
