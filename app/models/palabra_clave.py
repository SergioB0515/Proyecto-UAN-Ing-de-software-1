from app.extensions import db
from app.models.enum import Categoria

class PalabraClave(db.Model):
    __tablename__ = "palabras_clave"

    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.Enum(Categoria), nullable=False)
    texto = db.Column(db.String(120), nullable=False)
    peso = db.Column(db.Float, nullable=False, default=1.0)
    activa = db.Column(db.Boolean, nullable=False, default=True)