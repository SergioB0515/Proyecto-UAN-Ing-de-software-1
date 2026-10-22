from datetime import datetime

from app.extensions import db


class EncuestaSatisfaccion(db.Model):
    __tablename__ = "encuestas_satisfaccion"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, unique=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    agente_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    puntuacion = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.String(500), nullable=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)
