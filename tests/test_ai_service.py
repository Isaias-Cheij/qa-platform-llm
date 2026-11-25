"""Suite de pruebas unitarias y de integración para AIService y ruta AI Answer.

Verifica la construcción contextual de prompts, la generación de respuestas
simuladas en modo fallback (sin API key), la invocación mockeada a APIs LLM
externas sin realizar llamadas reales a la red, el manejo de errores externos y
el flujo completo HTTP en ``POST /questions/<slug>/ai-answer``.
"""

import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from qa_platform.models import AIAgent, Answer, Category, GeneralUser, Question, Tag
from qa_platform.services.ai_service import AIService


def _login(client, user) -> None:
    """Simula una sesión activa en Flask para el usuario indicado."""
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


@pytest.fixture()
def author(db):
    """Crea y persiste un usuario humano autor de preguntas de prueba."""
    user = GeneralUser(
        username="ai_tester",
        email="ai_tester@example.com",
        display_name="Tester IA",
        password="Password123",
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def category(db):
    """Crea y persiste una categoría de prueba."""
    cat = Category(
        name="Arquitectura",
        slug="arquitectura",
        description="Patrones de diseño y arquitectura",
    )
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture()
def question(db, author, category):
    """Crea y persiste una pregunta con etiquetas para pruebas de IA."""
    tag_python = Tag(name="python", slug="python")
    tag_flask = Tag(name="flask", slug="flask")
    db.session.add_all([tag_python, tag_flask])

    q = Question(
        title="¿Cómo implementar Strategy en Flask?",
        slug="como-implementar-strategy-en-flask",
        body="Necesito alternar entre distintos proveedores de LLM.",
        user_id=author.id,
        category_id=category.id,
    )
    q.tags.append(tag_python)
    q.tags.append(tag_flask)
    db.session.add(q)
    db.session.commit()
    return q


class TestAIServiceUnit:
    """Pruebas unitarias para AIService sin llamadas reales de red."""

    def test_build_prompt_contains_question_context(self, db, question):
        """El prompt contextual incluye título, categoría, etiquetas y cuerpo."""
        prompt = AIService._build_prompt(question)

        assert "¿Cómo implementar Strategy en Flask?" in prompt
        assert "Arquitectura" in prompt
        assert "python" in prompt
        assert "flask" in prompt
        assert "distintos proveedores de LLM" in prompt

    def test_ai_service_generates_answer(self, db, question):
        """generate_answer_for_question persiste Answer con is_ai_generated=True."""
        answer = AIService.generate_answer_for_question(question)

        assert answer.id is not None
        assert answer.is_ai_generated is True
        assert answer.question_id == question.id
        assert isinstance(answer.author, AIAgent)
        assert answer.author.is_agent() is True
        assert "¿Cómo implementar Strategy en Flask?" in answer.body
        assert "Arquitectura" in answer.body

        saved = db.session.get(Answer, answer.id)
        assert saved is not None
        assert saved.is_ai_generated is True

    def test_ai_service_reuses_existing_agent(self, db, question):
        """Generar múltiples respuestas reutiliza el mismo AIAgent del sistema."""
        first = AIService.generate_answer_for_question(question)
        second = AIService.generate_answer_for_question(question)

        assert first.author_id == second.author_id
        agents = db.session.scalars(db.select(AIAgent)).all()
        assert len(agents) == 1

    def test_ai_service_calls_mocked_gemini_when_api_key_present(
        self, app, db, question
    ):
        """Usa el proveedor Gemini mockeado cuando existe GEMINI_API_KEY."""
        fake_response_body = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        "Define una clase abstracta LLMStrategy "
                                        "e inyecta implementaciones concretas."
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        ).encode("utf-8")

        class _FakeHTTPResponse:
            def __init__(self, payload: bytes) -> None:
                self._buf = io.BytesIO(payload)

            def read(self) -> bytes:
                return self._buf.read()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

        app.config["GEMINI_API_KEY"] = "fake-gemini-key"
        app.config["LLM_PROVIDER"] = "gemini"

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse(fake_response_body),
        ) as mock_urlopen:
            answer = AIService.generate_answer_for_question(question)

        mock_urlopen.assert_called_once()
        assert answer.is_ai_generated is True
        assert "LLMStrategy" in answer.body

    def test_ai_service_falls_back_when_external_api_fails(self, app, db, question):
        """Si la API externa falla, recurre limpiamente al fallback local."""
        app.config["OPENAI_API_KEY"] = "fake-openai-key"
        app.config["LLM_PROVIDER"] = "openai"

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timeout simulado"),
        ) as mock_urlopen:
            answer = AIService.generate_answer_for_question(question)

        mock_urlopen.assert_called_once()
        assert answer.is_ai_generated is True
        assert "Respuesta generada por el Agente IA" in answer.body

    def test_ai_service_rejects_unpersisted_question(self, db):
        """Lanza ValueError si la pregunta aún no fue persistida."""
        unsaved = Question(
            title="Pregunta sin guardar",
            slug="pregunta-sin-guardar",
            body="Cuerpo cualquiera",
            user_id=1,
            category_id=1,
        )
        with pytest.raises(ValueError):
            AIService.generate_answer_for_question(unsaved)


class TestAIAnswerWebRoute:
    """Pruebas de integración HTTP para POST /questions/<slug>/ai-answer."""

    def test_detail_renders_generate_ai_button_for_logged_in_user(
        self, client, author, question
    ):
        """Un usuario autenticado ve el botón para generar respuesta con IA."""
        _login(client, author)
        response = client.get(f"/questions/{question.slug}")
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert f'action="/questions/{question.slug}/ai-answer"' in html
        assert "Generar Respuesta con IA" in html

    def test_post_generate_ai_answer_route(self, client, db, author, question):
        """POST /questions/<slug>/ai-answer redirige (302) y muestra la respuesta."""
        _login(client, author)
        response = client.post(f"/questions/{question.slug}/ai-answer")

        assert response.status_code == 302
        assert response.headers["Location"].endswith(f"/questions/{question.slug}")

        detail_resp = client.get(f"/questions/{question.slug}")
        html = detail_resp.get_data(as_text=True)

        assert detail_resp.status_code == 200
        assert "¡Respuesta de IA generada con éxito!" in html
        assert "Respuesta de Agente IA" in html
        assert "badge-ai" in html
        assert "Respuesta generada por el Agente IA" in html

        saved_answers = db.session.scalars(
            db.select(Answer).filter_by(question_id=question.id, is_ai_generated=True)
        ).all()
        assert len(saved_answers) == 1

    def test_post_generate_ai_answer_unauthenticated_redirects_to_login(
        self, client, db, question
    ):
        """Un visitante anónimo es redirigido al login y no se crea respuesta."""
        response = client.post(f"/questions/{question.slug}/ai-answer")

        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]
        assert question.answers.count() == 0

    def test_post_generate_ai_answer_unknown_question_returns_404(self, client, author):
        """Solicitar respuesta IA para un slug inexistente devuelve HTTP 404."""
        _login(client, author)
        response = client.post("/questions/no-existe-esta-pregunta/ai-answer")
        assert response.status_code == 404
