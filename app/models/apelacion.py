from datetime import datetime
from app.extensions import db
from app.models.enum import EstadoApelacion

class ApelacionCierre(db.Model):
    __tablename__ = "apelaciones_cierre"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    solicitante_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    motivo = db.Column(db.String(500), nullable=False)
    estado = db.Column(db.Enum(EstadoApelacion), nullable=False, default=EstadoApelacion.PENDIENTE)
    fecha_solicitud = db.Column(db.DateTime, nullable=False, default=datetime.now)
    fecha_resolucion = db.Column(db.DateTime, nullable=True)
    resuelto_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)