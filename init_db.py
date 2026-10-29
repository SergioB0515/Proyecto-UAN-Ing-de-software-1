import os

from app import create_app
from app.extensions import db
from app.migraciones import migrar


def _bool_env(nombre, por_defecto="0"):
    return os.environ.get(nombre, por_defecto).strip().lower() in ("1", "true", "yes", "on")


app = create_app()

with app.app_context():
    db.create_all()
    migrar()
    print("Base de datos lista.")

    if _bool_env("SEMBRAR_AL_INICIAR", "0"):
        from app.scripts.seed_palabras_clave import sembrar as sembrar_palabras
        from app.scripts.seed_demo import sembrar as sembrar_demo
        from app.scripts.seed_v3 import sembrar as sembrar_v3

        sembrar_palabras()
        sembrar_demo()
        sembrar_v3()
        print("Siembra verificada.")
