from app.extensions import db
from datetime import datetime
class Comentario(db.Model):
    __tablename__= "comentarios"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    texto = db.Column(db.String, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)