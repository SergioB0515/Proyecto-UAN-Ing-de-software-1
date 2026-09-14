import os
from dotenv import load_dotenv

load_dotenv()


def _bool_env(nombre, por_defecto="0"):
    return os.environ.get(nombre, por_defecto).strip().lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "Falta la variable de entorno SECRET_KEY. Crea un archivo .env en la raiz "
        "del proyecto con SECRET_KEY=<valor>, o expórtala en tu sistema. "
        "Genera un valor con: python -c \"import secrets; print(secrets.token_hex(32))\""
    )


class Config:
    SECRET_KEY = SECRET_KEY
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///proyecto.db")
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'): SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LANGUAGES = ["es", "en"]

    
    REENTRENAMIENTO_INTERVALO_HORAS = float(os.environ.get("REENTRENAMIENTO_INTERVALO_HORAS", "24"))
    SLA_INTERVALO_MINUTOS = int(os.environ.get("SLA_INTERVALO_MINUTOS", "30"))
    SCHEDULER_ACTIVO = _bool_env("SCHEDULER_ACTIVO", "1")
    CLASIFICADOR_ML_ACTIVO = _bool_env("CLASIFICADOR_ML_ACTIVO", "0")