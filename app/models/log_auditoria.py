from app.extensions import db
from app.models.enum import AccionAuditoria
from datetime import datetime
class LogAuditoria(db.Model):
    __tablename__ = "log_auditoria"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    accion = db.Column(db.Enum(AccionAuditoria), nullable=False)
    detalle = db.Column(db.String, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)