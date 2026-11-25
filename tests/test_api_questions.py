"""Pruebas funcionales para la API REST JSON de preguntas (/api/questions)."""

import pytest

from qa_platform.models import Answer, Category, GeneralUser, Question, Tag


def _login(client, user) -> None:
    """Autentica al cliente de pruebas con la sesión firmada del usuario."""
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


@pytest.fixture()
def author(db):
    """Crea y persiste un usuario autor de preguntas."""
    user = GeneralUser(
        username="api_author",
        email="api_author@example.com",
        display_name="Autor API",
        password="Password123",
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def other_user(db):
    """Crea y persiste un segundo usuario sin permisos sobre preguntas ajenas."""
    user = GeneralUser(
        username="api_other",
        email="api_other@example.com",
        display_name="Otro Usuario",
        password="Password123",
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def category(db):
    """Crea y persiste una categoría de prueba."""
    cat = Category(name="Python", slug="python", description="Consultas de Python")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture()
def second_category(db):
    """Crea y persiste una segunda categoría de prueba."""
    cat = Category(name="Flask", slug="flask", description="Framework web Flask")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture()
def sample_question(db, author, category):
    """Crea y persiste una pregunta con etiqueta y respuesta."""
    tag = Tag(name="sqlalchemy", slug="sqlalchemy")
    db.session.add(tag)

    question = Question(
        title="¿Cómo configurar relaciones en SQLAlchemy?",
        slug="como-configurar-relaciones-en-sqlalchemy",
        body="Necesito definir una relación many-to-many con tabla puente.",
        user_id=author.id,
        category_id=category.id,
    )
    question.tags.append(tag)
    db.session.add(question)
    db.session.flush()

    answer = Answer(
        body="Usá db.relationship con secondary=tabla_intermedia.",
        question=question,
        author=author,
        is_accepted=True,
    )
    db.session.add(answer)
    db.session.commit()
    return question


class TestApiQuestionsListAndDetail:
    """Pruebas de lectura para GET /api/questions y GET /api/questions/<id>."""

    def test_list_questions_empty(self, client, db):
        """GET /api/questions devuelve 200 con lista vacía cuando no hay datos."""
        response = client.get("/api/questions")

        assert response.status_code == 200
        assert response.is_json
        assert response.json == {"items": [], "total": 0}

    def test_list_questions_returns_items_and_supports_filters(
        self, client, db, author, category, second_category, sample_question
    ):
        """GET /api/questions devuelve preguntas serializadas y filtra por params."""
        other_q = Question(
            title="¿Cómo registrar Blueprints en Flask?",
            slug="como-registrar-blueprints-en-flask",
            body="Quiero separar rutas en módulos.",
            user_id=author.id,
            category_id=second_category.id,
        )
        db.session.add(other_q)
        db.session.commit()

        all_resp = client.get("/api/questions")
        assert all_resp.status_code == 200
        assert all_resp.json["total"] == 2

        by_cat = client.get(f"/api/questions?category_id={second_category.id}")
        assert by_cat.status_code == 200
        assert by_cat.json["total"] == 1
        assert by_cat.json["items"][0]["id"] == other_q.id

        by_tag = client.get("/api/questions?tag=sqlalchemy")
        assert by_tag.status_code == 200
        assert by_tag.json["total"] == 1
        assert by_tag.json["items"][0]["id"] == sample_question.id

        by_query = client.get("/api/questions?q=Blueprints")
        assert by_query.status_code == 200
        assert by_query.json["total"] == 1
        assert by_query.json["items"][0]["id"] == other_q.id

    def test_list_questions_invalid_category_param_returns_400(self, client, db):
        """GET /api/questions?category_id=abc devuelve HTTP 400."""
        response = client.get("/api/questions?category_id=abc")

        assert response.status_code == 400
        assert "error" in response.json

    def test_get_question_detail_returns_200_with_answers(
        self, client, sample_question
    ):
        """GET /api/questions/<id> devuelve 200 con detalle completo y respuestas."""
        response = client.get(f"/api/questions/{sample_question.id}")

        assert response.status_code == 200
        data = response.json
        assert data["id"] == sample_question.id
        assert data["title"] == sample_question.title
        assert data["category"]["slug"] == "python"
        assert data["tags"][0]["slug"] == "sqlalchemy"
        assert data["answers_count"] == 1
        assert len(data["answers"]) == 1
        assert data["answers"][0]["is_accepted"] is True

    def test_get_question_not_found_returns_404(self, client, db):
        """GET /api/questions/<id> inexistente devuelve HTTP 404."""
        response = client.get("/api/questions/99999")

        assert response.status_code == 404
        assert "error" in response.json


class TestApiQuestionsCreate:
    """Pruebas de creación para POST /api/questions."""

    def test_create_question_requires_authentication(self, client, db, category):
        """POST /api/questions sin sesión activa devuelve HTTP 401 JSON."""
        response = client.post(
            "/api/questions",
            json={
                "title": "Pregunta sin autenticar",
                "body": "No debería guardarse.",
                "category_id": category.id,
            },
        )

        assert response.status_code == 401
        assert response.is_json
        assert "error" in response.json

    def test_create_question_valid_returns_201_and_generates_unique_slug(
        self, client, db, author, category
    ):
        """POST /api/questions válido crea la pregunta con etiquetas y slug único."""
        _login(client, author)
        payload = {
            "title": "Cómo usar Application Factory",
            "body": "Quiero inicializar extensiones sin importaciones circulares.",
            "category_id": category.id,
            "tags": ["flask", "arquitectura", "flask"],
        }

        first = client.post("/api/questions", json=payload)
        second = client.post("/api/questions", json=payload)

        assert first.status_code == 201
        assert first.json["slug"] == "cómo-usar-application-factory"
        assert first.json["author"]["id"] == author.id
        assert len(first.json["tags"]) == 2

        assert second.status_code == 201
        assert second.json["slug"] != first.json["slug"]
        assert db.session.query(Question).count() == 2

    @pytest.mark.parametrize(
        "payload",
        [
            {"title": "abc", "body": "Cuerpo válido", "category_id": 1},
            {"title": "Título válido largo", "body": "", "category_id": 1},
            {"title": "Título válido largo", "body": "Cuerpo válido"},
            {
                "title": "Título válido largo",
                "body": "Cuerpo válido",
                "category_id": 9999,
            },
        ],
    )
    def test_create_question_invalid_payload_returns_400(
        self, client, author, category, payload
    ):
        """POST /api/questions con datos inválidos o categoría inexistente da 400."""
        _login(client, author)
        data = dict(payload)
        if data.get("category_id") == 1:
            data["category_id"] = category.id

        response = client.post("/api/questions", json=data)

        assert response.status_code == 400
        assert "errors" in response.json

    def test_create_question_non_json_returns_400(self, client, author):
        """POST /api/questions sin cuerpo JSON válido devuelve HTTP 400."""
        _login(client, author)
        response = client.post("/api/questions", data="texto plano")

        assert response.status_code == 400
        assert "error" in response.json


class TestApiQuestionsUpdateAndDelete:
    """Pruebas de actualización (PATCH) y borrado (DELETE) en /api/questions/<id>."""

    def test_patch_question_updates_fields_for_owner(
        self, client, db, author, second_category, sample_question
    ):
        """PATCH /api/questions/<id> permite al autor actualizar parcialmente."""
        _login(client, author)
        response = client.patch(
            f"/api/questions/{sample_question.id}",
            json={
                "title": "Relaciones many-to-many en SQLAlchemy 2",
                "category_id": second_category.id,
                "tags": "orm, flask",
            },
        )

        assert response.status_code == 200
        assert response.json["title"] == "Relaciones many-to-many en SQLAlchemy 2"
        assert response.json["category"]["id"] == second_category.id
        assert {tag["slug"] for tag in response.json["tags"]} == {"orm", "flask"}

    def test_patch_question_forbidden_for_non_owner(
        self, client, other_user, sample_question
    ):
        """PATCH /api/questions/<id> por otro usuario devuelve HTTP 403."""
        _login(client, other_user)
        response = client.patch(
            f"/api/questions/{sample_question.id}",
            json={"title": "Intento de edición ajena"},
        )

        assert response.status_code == 403
        assert "error" in response.json

    def test_patch_question_not_found_returns_404(self, client, author):
        """PATCH /api/questions/<id> inexistente devuelve HTTP 404."""
        _login(client, author)
        response = client.patch("/api/questions/99999", json={"title": "No existe"})

        assert response.status_code == 404

    def test_delete_question_removes_resource_for_owner(
        self, client, db, author, sample_question
    ):
        """DELETE /api/questions/<id> elimina la pregunta del autor y da 200."""
        _login(client, author)
        response = client.delete(f"/api/questions/{sample_question.id}")

        assert response.status_code == 200
        assert response.json["id"] == sample_question.id
        assert db.session.get(Question, sample_question.id) is None

        follow_up = client.get(f"/api/questions/{sample_question.id}")
        assert follow_up.status_code == 404

    def test_delete_question_forbidden_for_non_owner(
        self, client, db, other_user, sample_question
    ):
        """DELETE /api/questions/<id> por otro usuario devuelve HTTP 403."""
        _login(client, other_user)
        response = client.delete(f"/api/questions/{sample_question.id}")

        assert response.status_code == 403
        assert db.session.get(Question, sample_question.id) is not None

    def test_delete_question_requires_auth_and_returns_404_when_missing(
        self, client, author, sample_question
    ):
        """DELETE exige sesión (401) y devuelve 404 si el recurso no existe."""
        anon = client.delete(f"/api/questions/{sample_question.id}")
        assert anon.status_code == 401

        _login(client, author)
        missing = client.delete("/api/questions/99999")
        assert missing.status_code == 404
