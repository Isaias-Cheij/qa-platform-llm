"""Suite de pruebas de integracion web para las vistas de preguntas.

Verifica el renderizado del listado, el detalle por slug, el envio exitoso
del formulario de creacion y la validacion de campos incompletos.
Reutiliza las fixtures compartidas de conftest.py.
"""

import pytest

from qa_platform.models.author import GeneralUser
from qa_platform.models.category import Category
from qa_platform.models.question import Question

# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_and_session(client, db):
    """Crea un usuario y simula una sesion activa via la cookie de sesion.

    Args:
        client: Cliente HTTP de pruebas de Flask.
        db: Fixture de base de datos de conftest.

    Returns:
        Tupla (user, client) con el usuario creado y el cliente autenticado.
    """
    u = GeneralUser(
        username="viewtester",
        email="viewtester@example.com",
        password="password1234",
    )
    db.session.add(u)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = u.id

    return u, client


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
def question(db, user_and_session, category):
    """Crea y persiste una Question de prueba vinculada al usuario de sesion.

    Args:
        db: Fixture de base de datos de conftest.
        user_and_session: Fixture que provee el usuario autenticado.
        category: Fixture que provee la categoria.

    Returns:
        Instancia de Question persistida.
    """
    user, _ = user_and_session
    q = Question(
        title="Como usar Flask correctamente?",
        slug="como-usar-flask-correctamente",
        body="Quiero entender el patron Application Factory.",
        user_id=user.id,
        category_id=category.id,
    )
    db.session.add(q)
    db.session.commit()
    return q


# ---------------------------------------------------------------------------
# Tests de listado
# ---------------------------------------------------------------------------


class TestQuestionListView:
    """Pruebas de la vista GET /questions."""

    def test_list_returns_200(self, client, db):
        """Verifica que el listado de preguntas responde HTTP 200."""
        response = client.get("/questions/")
        assert response.status_code == 200

    def test_list_shows_question_title(self, client, question):
        """Verifica que el titulo de la pregunta aparece en el listado."""
        response = client.get("/questions/")
        assert b"Como usar Flask correctamente?" in response.data


# ---------------------------------------------------------------------------
# Tests de detalle
# ---------------------------------------------------------------------------


class TestQuestionDetailView:
    """Pruebas de la vista GET /questions/<slug>."""

    def test_detail_returns_200(self, client, question):
        """Verifica que el detalle de una pregunta existente responde HTTP 200."""
        response = client.get(f"/questions/{question.slug}")
        assert response.status_code == 200

    def test_detail_shows_body(self, client, question):
        """Verifica que el cuerpo de la pregunta aparece en el detalle."""
        response = client.get(f"/questions/{question.slug}")
        assert b"Application Factory" in response.data

    def test_detail_404_for_unknown_slug(self, client, db):
        """Verifica que una pregunta inexistente responde HTTP 404."""
        response = client.get("/questions/slug-que-no-existe")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de creacion
# ---------------------------------------------------------------------------


class TestCreateQuestionView:
    """Pruebas de las vistas GET/POST /questions/new."""

    def test_create_form_returns_200_authenticated(self, user_and_session, category):
        """Verifica que el formulario de creacion responde 200
        para usuario autenticado."""
        _, auth_client = user_and_session
        response = auth_client.get("/questions/new")
        assert response.status_code == 200

    def test_create_redirects_unauthenticated(self, client, db):
        """Verifica que un usuario no autenticado es redirigido al intentar crear."""
        response = client.get("/questions/new")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_post_valid_form_creates_question_and_redirects(
        self, user_and_session, category
    ):
        """Verifica que un POST valido crea la pregunta y redirige al detalle (302)."""
        _, auth_client = user_and_session
        response = auth_client.post(
            "/questions/new",
            data={
                "title": "Como instalar Flask con uv?",
                "body": "Necesito saber como configurar el entorno virtual.",
                "category_id": category.id,
                "tags": "python, flask",
            },
        )
        assert response.status_code == 302
        assert "/questions/" in response.headers["Location"]

    def test_post_missing_title_returns_400(self, user_and_session, category):
        """Verifica que un POST con titulo corto devuelve HTTP 400 con error."""
        _, auth_client = user_and_session
        response = auth_client.post(
            "/questions/new",
            data={
                "title": "Hola",  # menos de 5 caracteres
                "body": "Contenido valido para la pregunta.",
                "category_id": category.id,
            },
        )
        assert response.status_code == 400

    def test_post_missing_body_returns_400(self, user_and_session, category):
        """Verifica que un POST sin body devuelve HTTP 400 con error."""
        _, auth_client = user_and_session
        response = auth_client.post(
            "/questions/new",
            data={
                "title": "Una pregunta valida con titulo",
                "body": "",
                "category_id": category.id,
            },
        )
        assert response.status_code == 400
