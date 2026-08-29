from app.extensions import db
from app.models.enum import RolUsuario, Categoria, NivelUsuario
class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nombre= db.Column(db.String(100),nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum(RolUsuario), nullable=False)
    area_soporte = db.Column(db.Enum(Categoria), nullable=True)
    nivel = db.Column(db.Enum(NivelUsuario), nullable=False)
    intentos_fallidos = db.Column(db.Integer, nullable=False, default = 0)
    bloqueado_hasta = db.Column(db.DateTime, nullable=True) 
        