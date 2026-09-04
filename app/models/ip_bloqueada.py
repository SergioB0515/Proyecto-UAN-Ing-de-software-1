from app.extensions import db

class IPBloqueada(db.Model):
    __tablename__ = "ip_bloqueada"
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(45), nullable=False, unique=True)
    bloqueada_hasta = db.Column(db.DateTime, nullable=False)