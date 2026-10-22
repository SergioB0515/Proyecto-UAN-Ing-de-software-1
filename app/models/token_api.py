from datetime import datetime

from app.extensions import db


class TokenApi(db.Model):
    __tablename__ = "tokens_api"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    nombre = db.Column(db.String(80), nullable=False)
    prefijo = db.Column(db.String(16), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)
    expira = db.Column(db.DateTime, nullable=True)
    ultimo_uso = db.Column(db.DateTime, nullable=True)
    revocado = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def vigente(self):
        return not self.revocado and (self.expira is None or self.expira > datetime.now())
