"""Suite de pruebas para los modelos de dominio Category, Tag y Question.

Verifica la creacion de categorias y etiquetas, asignacion de categorias a
preguntas, relaciones many-to-many con etiquetas y restricciones de unicidad
de slugs. Reutiliza las fixtures definidas en conftest.py.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from qa_platform.models.author import GeneralUser
from qa_platform.models.category import Category
from qa_platform.models.question import Question
from qa_platform.models.tag import Tag

# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------


@pytest.fixture()
def user(db):
    """Crea y persiste un GeneralUser de prueba.

    Args:
        db: Fixture de base de datos de conftest.

    Returns:
        Instancia de GeneralUser persistida.
    """
    u = GeneralUser(
        username="testuser",
        email="testuser@example.com",
        password="secret1234",
    )
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def category(db):
    """Crea y persiste una Category de prueba.

    Args:
        db: Fixture de base de datos de conftest.

    Returns:
        Instancia de Category persistida.
    """
    cat = Category(name="Python", slug="python", description="Todo sobre Python")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture()
def tag_python(db):
    """Crea y persiste un Tag 'python' de prueba.

    Args:
        db: Fixture de base de datos de conftest.

    Returns:
        Instancia de Tag persistida.
    """
    tag = Tag(name="python", slug="python-tag")
    db.session.add(tag)
    db.session.commit()
    return tag


@pytest.fixture()
def tag_flask(db):
    """Crea y persiste un Tag 'flask' de prueba.

    Args:
        db: Fixture de base de datos de conftest.

    Returns:
        Instancia de Tag persistida.
    """
    tag = Tag(name="flask", slug="flask-tag")
    db.session.add(tag)
    db.session.commit()
    return tag


# ---------------------------------------------------------------------------
# Tests de Category
# ---------------------------------------------------------------------------


class TestCategoryModel:
    """Pruebas de integracion para el modelo Category."""

    def test_create_and_persist_category(self, db):
        """Verifica que una Category se persiste correctamente con todos sus campos."""
        cat = Category(name="Django", slug="django", description="Framework web")
        db.session.add(cat)
        db.session.commit()

        assert cat.id is not None
        assert cat.created_at is not None

    def test_query_category_by_slug(self, db, category):
        """Verifica que una Category puede recuperarse filtrando por slug."""
        result = db.session.execute(
            db.select(Category).filter_by(slug="python")
        ).scalar_one()

        assert result.name == "Python"

    def test_unique_category_slug_constraint(self, db, category):
        """Verifica que no se pueden insertar dos categorias con el mismo slug."""
        db.session.add(Category(name="Python2", slug="python"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_unique_category_name_constraint(self, db, category):
        """Verifica que no se pueden insertar dos categorias con el mismo name."""
        db.session.add(Category(name="Python", slug="python-alt"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ---------------------------------------------------------------------------
# Tests de Tag
# ---------------------------------------------------------------------------


class TestTagModel:
    """Pruebas de integracion para el modelo Tag."""

    def test_create_and_persist_tag(self, db):
        """Verifica que un Tag se persiste correctamente."""
        tag = Tag(name="sqlalchemy", slug="sqlalchemy")
        db.session.add(tag)
        db.session.commit()

        assert tag.id is not None

    def test_unique_tag_slug_constraint(self, db, tag_python):
        """Verifica que no se pueden insertar dos tags con el mismo slug."""
        db.session.add(Tag(name="otro", slug="python-tag"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


# ---------------------------------------------------------------------------
# Tests de Question
# ---------------------------------------------------------------------------


class TestQuestionModel:
    """Pruebas de integracion para el modelo Question y sus relaciones."""

    def test_create_question_with_category(self, db, user, category):
        """Verifica que una Question se crea con categoria y autor correctamente."""
        q = Question(
            title="Como usar SQLAlchemy?",
            slug="como-usar-sqlalchemy",
            body="Quiero entender los modelos relacionales.",
            user_id=user.id,
            category_id=category.id,
        )
        db.session.add(q)
        db.session.commit()

        assert q.id is not None
        assert q.created_at is not None
        assert q.updated_at is not None
        assert q.category.name == "Python"
        assert q.author.username == "testuser"

    def test_assign_multiple_tags_to_question(
        self, db, user, category, tag_python, tag_flask
    ):
        """Verifica que se pueden asignar multiples etiquetas a una pregunta."""
        q = Question(
            title="Flask con SQLAlchemy",
            slug="flask-con-sqlalchemy",
            body="Como integrar Flask con SQLAlchemy?",
            user_id=user.id,
            category_id=category.id,
        )
        db.session.add(q)
        db.session.commit()

        q.tags.append(tag_python)
        q.tags.append(tag_flask)
        db.session.commit()

        tag_names = {t.name for t in q.tags}
        assert "python" in tag_names
        assert "flask" in tag_names

    def test_unique_question_slug_constraint(self, db, user, category):
        """Verifica que no se pueden insertar dos preguntas con el mismo slug."""
        q1 = Question(
            title="Pregunta original",
            slug="pregunta-slug-unico",
            body="Cuerpo de la pregunta.",
            user_id=user.id,
            category_id=category.id,
        )
        db.session.add(q1)
        db.session.commit()

        q2 = Question(
            title="Pregunta duplicada",
            slug="pregunta-slug-unico",
            body="Otro cuerpo.",
            user_id=user.id,
            category_id=category.id,
        )
        db.session.add(q2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_author_questions_backref(self, db, user, category):
        """Verifica la relacion inversa: author.questions contiene la pregunta."""
        q = Question(
            title="Pregunta de backref",
            slug="pregunta-backref",
            body="Verificando la relacion inversa.",
            user_id=user.id,
            category_id=category.id,
        )
        db.session.add(q)
        db.session.commit()

        slugs = [aq.slug for aq in user.questions]
        assert "pregunta-backref" in slugs

    def test_category_questions_backref(self, db, user, category):
        """Verifica la relacion inversa: category.questions contiene la pregunta."""
        q = Question(
            title="Pregunta de categoria",
            slug="pregunta-categoria",
            body="Verificando la relacion de categoria.",
            user_id=user.id,
            category_id=category.id,
        )
        db.session.add(q)
        db.session.commit()

        slugs = [cq.slug for cq in category.questions]
        assert "pregunta-categoria" in slugs
