import os

import pytest

from tests import create_app
from app.extensions import db

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATHS = (
    os.path.join(REPO_ROOT, "test_proyecto.db"),
    os.path.join(REPO_ROOT, "instance", "test_proyecto.db"),
)


@pytest.fixture(scope="session")
def app():
    for ruta in DB_PATHS:
        if os.path.exists(ruta):
            os.remove(ruta)
    return create_app()


@pytest.fixture(scope="session", autouse=True)
def app_context(app):
    with app.app_context():
        yield
