from app import create_app
from app.migraciones import migrar

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        aplicadas = migrar()
        print(f"Migración completada ({len(aplicadas)} cambios).")
