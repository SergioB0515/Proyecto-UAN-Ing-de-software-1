from app import create_app
from app.extensions import db
from app.migraciones import migrar

app = create_app()

with app.app_context():
    db.create_all()
    migrar()
    print("Base de datos lista.")
