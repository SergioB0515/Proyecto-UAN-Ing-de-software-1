"""
Fixtures compartidas para toda la suite de pytest.

Reemplaza el patron manual que tenian los scripts originales
(`if __name__ == "__main__": app = create_app(); with app.app_context(): ...`)
por un app_context de sesion, usando `tests.create_app()` tal cual ya estaba
configurado (SQLite separada en test_proyecto.db, ver tests/__init__.py).

Se borra el archivo test_proyecto.db al inicio de la sesion de pytest para que
la suite completa arranque desde un estado limpio y reproducible en cada
corrida (los scripts manuales originales no lo hacian y dependian de que cada
uno limpiara sus propios datos por email/marcador antes de correr).
"""
import os

import pytest

from tests import create_app
from app.extensions import db

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "test_proyecto.db")


@pytest.fixture(scope="session")
def app():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    return create_app()


@pytest.fixture(scope="session", autouse=True)
def app_context(app):
    with app.app_context():
        yield
