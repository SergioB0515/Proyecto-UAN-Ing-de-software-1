from datetime import datetime
from app.extensions import db
from app.models.enum import EstadoSolicitudTransferencia

class SolicitudTransferencia(db.Model):
    __tablename__ = "solicitudes_transferencia"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)


    agente_origen_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    agente_destino_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    solicitante_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    estado = db.Column(db.Enum(EstadoSolicitudTransferencia), nullable=False,
                        default=EstadoSolicitudTransferencia.PENDIENTE)
    motivo = db.Column(db.String(500), nullable=True)

    fecha_solicitud = db.Column(db.DateTime, nullable=False, default=datetime.now)
    fecha_resolucion = db.Column(db.DateTime, nullable=True)