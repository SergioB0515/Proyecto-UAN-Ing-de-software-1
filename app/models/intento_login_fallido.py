from app.extensions import db
from datetime import datetime

class IntentoLoginFallido(db.Model):
    __tablename__ = "intento_login_fallido"
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(45), nullable=False)  
    email_intentado = db.Column(db.String(150), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)