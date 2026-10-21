from datetime import datetime
from app.extensions import db


class TokenRecuperacion(db.Model):
    __tablename__ = "tokens_recuperacion"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)
    expira = db.Column(db.DateTime, nullable=False)
    usado = db.Column(db.Boolean, nullable=False, default=False)
