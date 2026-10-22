from datetime import datetime

from app.extensions import db


class SeguidorTicket(db.Model):
    __tablename__ = "seguidores_ticket"
    __table_args__ = (db.UniqueConstraint("ticket_id", "usuario_id", name="uq_seguidor_ticket_usuario"),)
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)
