"""Suite de pruebas para el modelo User.

Verifica la creacion de tablas, persistencia, consultas y restricciones
unicas del modelo ``User`` usando una base de datos SQLite en memoria para
aislar cada sesion de prueba.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from qa_platform import create_app
from qa_platform.extensions import db as _db
from qa_platform.models.user import User


@pytest.fixture()
def app():
    """Crea una instancia de la aplicacion configurada para pruebas.

    Yields:
        Instancia de Flask con contexto activo y base de datos inicializada.
    """
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    """Expone la instancia de la base de datos dentro del contexto de prueba.

    Args:
        app: Fixture de la aplicacion Flask.

    Returns:
        Instancia de SQLAlchemy vinculada a la app de prueba.
    """
    return _db


class TestUserModel:
    """Pruebas de integracion para el modelo User."""

    def test_tables_are_created(self, db):
        """Verifica que la tabla 'authors' existe y 'users' fue reemplazada."""
        from sqlalchemy import inspect

        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()
        assert "authors" in table_names
        assert "users" not in table_names

    def test_create_and_persist_user(self, db):
        """Verifica que un User se puede instanciar y persistir correctamente."""
        user = User(username="jnacis", email="joaquin@example.com")
        db.session.add(user)
        db.session.commit()

        assert user.id is not None
        assert user.created_at is not None

    def test_query_by_username(self, db):
        """Verifica que un User puede recuperarse filtrando por username."""
        db.session.add(User(username="acheij", email="isaias@example.com"))
        db.session.commit()

        result = db.session.execute(
            db.select(User).filter_by(username="acheij")
        ).scalar_one()

        assert result.email == "isaias@example.com"

    def test_query_by_email(self, db):
        """Verifica que un User puede recuperarse filtrando por email."""
        db.session.add(User(username="jleanza", email="juan@example.com"))
        db.session.commit()

        result = db.session.execute(
            db.select(User).filter_by(email="juan@example.com")
        ).scalar_one()

        assert result.username == "jleanza"

    def test_unique_username_constraint(self, db):
        """Verifica que no se pueden insertar dos Users con el mismo username."""
        db.session.add(User(username="duplicate", email="first@example.com"))
        db.session.commit()

        db.session.add(User(username="duplicate", email="second@example.com"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_unique_email_constraint(self, db):
        """Verifica que no se pueden insertar dos Users con el mismo email."""
        db.session.add(User(username="user_a", email="shared@example.com"))
        db.session.commit()

        db.session.add(User(username="user_b", email="shared@example.com"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_repr(self, db):
        """Verifica el formato de la representacion string del modelo User."""
        user = User(username="repr_user", email="repr@example.com")
        db.session.add(user)
        db.session.commit()

        assert "repr_user" in repr(user)
        assert str(user.id) in repr(user)
