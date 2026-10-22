from datetime import datetime

from app.extensions import db
from app.models.enum import Categoria


class RespuestaPredefinida(db.Model):
    __tablename__ = "respuestas_predefinidas"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(120), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.Enum(Categoria), nullable=True)
    compartida = db.Column(db.Boolean, nullable=False, default=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    usos = db.Column(db.Integer, nullable=False, default=0)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)
