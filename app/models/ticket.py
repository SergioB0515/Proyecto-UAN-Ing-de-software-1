from datetime import datetime
from app.extensions import db
from app.models.enum import Categoria, Prioridad, EstadoTicket

class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    radicado = db.Column(db.String(150), nullable=True)
    texto = db.Column(db.String(1200), nullable=False)
    categoria = db.Column(db.Enum(Categoria), nullable=False)
    prioridad = db.Column(db.Enum(Prioridad), nullable=False)
    estado = db.Column(db.Enum(EstadoTicket), nullable=False)
    creador_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    agente_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)
    fecha_limite= db.Column(db.DateTime, nullable=False)
    fecha_cierre = db.Column(db.DateTime, nullable=True)