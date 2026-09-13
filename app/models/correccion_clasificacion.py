from datetime import datetime
from app.extensions import db
from app.models.enum import Categoria


class CorreccionClasificacion(db.Model):
    __tablename__ = "correcciones_clasificacion"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    texto = db.Column(db.String(1200), nullable=False)
    categoria_original = db.Column(db.Enum(Categoria), nullable=False)
    categoria_correcta = db.Column(db.Enum(Categoria), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)