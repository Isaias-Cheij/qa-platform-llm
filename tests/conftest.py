"""Fixtures compartidas para la suite de pruebas con PyTest."""

import pytest

from qa_platform import create_app
from qa_platform.extensions import db as _db


@pytest.fixture
def app():
    """Crea una instancia de Flask en modo testing con base en memoria.

    Yields:
        Instancia de Flask con contexto activo y tablas creadas.
    """
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    """Expone la instancia de SQLAlchemy dentro del contexto de prueba."""
    return _db


@pytest.fixture
def client(app):
    """Devuelve el cliente HTTP de pruebas de Flask."""
    return app.test_client()
