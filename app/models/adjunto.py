from datetime import datetime

from app.extensions import db


class Adjunto(db.Model):
    __tablename__ = "adjuntos"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    comentario_id = db.Column(db.Integer, db.ForeignKey("comentarios.id"), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    nombre_original = db.Column(db.String(255), nullable=False)
    nombre_guardado = db.Column(db.String(80), nullable=False, unique=True)
    tipo_mime = db.Column(db.String(120), nullable=False)
    tamano = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)

    @property
    def extension(self):
        return self.nombre_guardado.rsplit(".", 1)[-1].lower()

    @property
    def es_imagen(self):
        return self.extension in ("png", "jpg", "jpeg", "gif", "webp")
