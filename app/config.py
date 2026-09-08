import os

def _bool_env(nombre, por_defecto="0"):
    return os.environ.get(nombre, por_defecto).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "alkleajklsjklseñaskejasklje")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///proyecto.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LANGUAGES = ["es", "en"]


    SLA_INTERVALO_MINUTOS = int(os.environ.get("SLA_INTERVALO_MINUTOS", "30"))

    SCHEDULER_ACTIVO = _bool_env("SCHEDULER_ACTIVO", "1")