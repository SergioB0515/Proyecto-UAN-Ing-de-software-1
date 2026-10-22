from datetime import datetime

from app.extensions import db
from app.models.enum import Categoria


class Articulo(db.Model):
    __tablename__ = "articulos"
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(160), nullable=False)
    resumen = db.Column(db.String(300), nullable=True)
    contenido = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.Enum(Categoria), nullable=False)
    etiquetas = db.Column(db.String(300), nullable=True)
    publicado = db.Column(db.Boolean, nullable=False, default=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.now)
    fecha_actualizacion = db.Column(db.DateTime, nullable=False, default=datetime.now)
    vistas = db.Column(db.Integer, nullable=False, default=0)
    votos_utiles = db.Column(db.Integer, nullable=False, default=0)
    votos_no_utiles = db.Column(db.Integer, nullable=False, default=0)
    resoluciones = db.Column(db.Integer, nullable=False, default=0)

    @property
    def lista_etiquetas(self):
        return [e.strip() for e in (self.etiquetas or "").split(",") if e.strip()]

    @property
    def utilidad(self):
        total = (self.votos_utiles or 0) + (self.votos_no_utiles or 0)
        return None if total == 0 else (self.votos_utiles or 0) / total


class VotoArticulo(db.Model):
    __tablename__ = "votos_articulo"
    __table_args__ = (db.UniqueConstraint("articulo_id", "usuario_id", name="uq_voto_articulo_usuario"),)
    id = db.Column(db.Integer, primary_key=True)
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulos.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    util = db.Column(db.Boolean, nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)
