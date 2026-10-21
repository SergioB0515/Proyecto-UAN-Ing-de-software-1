from datetime import datetime
from app.extensions import db


class DobleFactor(db.Model):
    __tablename__ = "doble_factor"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), unique=True, nullable=False)
    secreto = db.Column(db.String(64), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=False)
    codigos_respaldo = db.Column(db.Text, nullable=False, default="[]")
    ultimo_paso = db.Column(db.Integer, nullable=True)
    intentos_fallidos = db.Column(db.Integer, nullable=False, default=0)
    bloqueado_hasta = db.Column(db.DateTime, nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)
    fecha_activacion = db.Column(db.DateTime, nullable=True)
