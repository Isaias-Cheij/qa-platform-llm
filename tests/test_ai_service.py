"""Suite de pruebas unitarias y de integración para AIService y LLMStrategy.

Verifica la abstracción ``LLMStrategy``, la inyección de dependencias en
``AIService``, el uso por defecto de ``MockLLMStrategy``, el comportamiento de
las estrategias de producción con llamadas HTTP mockeadas (sin acceso real a la
red) y el flujo completo HTTP en ``POST /questions/<slug>/ai-answer``.
"""

import io
import json
from unittest.mock import patch

import pytest

from qa_platform.models import AIAgent, Answer, Category, GeneralUser, Question, Tag
from qa_platform.services.ai_service import AIService
from qa_platform.services.strategies import (
    GeminiLLMStrategy,
    LLMStrategy,
    MockLLMStrategy,
    OpenAILLMStrategy,
)


def _login(client, user) -> None:
    """Simula una sesión activa en Flask para el usuario indicado."""
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


class _FakeHTTPResponse:
    """Respuesta HTTP simulada para evitar peticiones reales en pruebas."""

    def __init__(self, payload: dict) -> None:
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _StubStrategy(LLMStrategy):
    """Estrategia stub para verificar inyección en AIService sin red."""

    def __init__(self, response_text: str = "Respuesta inyectada por stub.") -> None:
        self.response_text = response_text
        self.received_prompts: list[str] = []

    def get_provider_name(self) -> str:
        return "StubLLM"

    def generate(self, prompt: str) -> str:
        self.received_prompts.append(prompt)
        return self.response_text


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


class TestLLMStrategies:
    """Pruebas unitarias para la jerarquía LLMStrategy y sus implementaciones."""

    def test_llm_strategy_is_abstract(self):
        """LLMStrategy no puede instanciarse directamente."""
        with pytest.raises(TypeError):
            LLMStrategy()  # type: ignore[abstract]

    def test_mock_strategy_generates_contextual_response(self):
        """MockLLMStrategy genera respuesta determinista sin llamadas de red."""
        strategy = MockLLMStrategy()
        prompt = "Título: Prueba Strategy\nCategoría: Python\nDetalle:\nContenido."

        result = strategy.generate(prompt)

        assert strategy.get_provider_name() == "MockLLM"
        assert "Respuesta generada por el Agente IA" in result
        assert "Prueba Strategy" in result
        assert "Python" in result

    def test_mock_strategy_rejects_empty_prompt(self):
        """MockLLMStrategy lanza ValueError ante un prompt vacío."""
        strategy = MockLLMStrategy()
        with pytest.raises(ValueError):
            strategy.generate("   ")

    def test_gemini_strategy_calls_mocked_endpoint(self):
        """GeminiLLMStrategy invoca la API REST y extrae el texto generado."""
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Respuesta generada por Gemini mockeado."}]
                    }
                }
            ]
        }
        strategy = GeminiLLMStrategy(api_key="fake-gemini-key")

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse(payload),
        ) as mock_urlopen:
            result = strategy.generate("Explica el patrón Strategy.")

        mock_urlopen.assert_called_once()
        assert strategy.get_provider_name() == "Gemini"
        assert result == "Respuesta generada por Gemini mockeado."

    def test_openai_strategy_calls_mocked_endpoint(self):
        """OpenAILLMStrategy invoca Chat Completions y extrae el mensaje."""
        payload = {
            "choices": [
                {"message": {"content": "Respuesta generada por OpenAI mockeado."}}
            ]
        }
        strategy = OpenAILLMStrategy(api_key="fake-openai-key")

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse(payload),
        ) as mock_urlopen:
            result = strategy.generate("Explica el patrón Strategy.")

        mock_urlopen.assert_called_once()
        assert strategy.get_provider_name() == "OpenAI"
        assert result == "Respuesta generada por OpenAI mockeado."

    def test_production_strategies_reject_empty_api_key(self):
        """Las estrategias de producción exigen una API key no vacía."""
        with pytest.raises(ValueError):
            GeminiLLMStrategy(api_key="  ")
        with pytest.raises(ValueError):
            OpenAILLMStrategy(api_key="")


class TestAIServiceUnit:
    """Pruebas unitarias para AIService con inyección de LLMStrategy."""

    def test_ai_service_defaults_to_mock_strategy(self):
        """Si no se pasa estrategia en __init__, asigna MockLLMStrategy."""
        service = AIService()
        assert isinstance(service.strategy, MockLLMStrategy)

    def test_build_prompt_contains_question_context(self, db, question):
        """El prompt contextual incluye título, categoría, etiquetas y cuerpo."""
        prompt = AIService._build_prompt(question)

        assert "¿Cómo implementar Strategy en Flask?" in prompt
        assert "Arquitectura" in prompt
        assert "python" in prompt
        assert "flask" in prompt
        assert "distintos proveedores de LLM" in prompt

    def test_ai_service_generates_answer_with_default_mock_strategy(self, db, question):
        """AIService().generate_answer_for_question persiste Answer con MockLLM."""
        service = AIService()
        answer = service.generate_answer_for_question(question)

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

    def test_ai_service_delegates_to_injected_strategy(self, db, question):
        """AIService delega la generación a la estrategia inyectada en __init__."""
        stub = _StubStrategy("Usa una interfaz LLMStrategy inyectada por constructor.")
        service = AIService(strategy=stub)

        answer = service.generate_answer_for_question(question)

        assert len(stub.received_prompts) == 1
        assert "¿Cómo implementar Strategy en Flask?" in stub.received_prompts[0]
        assert answer.body == "Usa una interfaz LLMStrategy inyectada por constructor."
        assert answer.is_ai_generated is True
        assert service.strategy.get_provider_name() == "StubLLM"

    def test_ai_service_reuses_existing_agent(self, db, question):
        """Generar múltiples respuestas reutiliza el mismo AIAgent del sistema."""
        service = AIService()
        first = service.generate_answer_for_question(question)
        second = service.generate_answer_for_question(question)

        assert first.author_id == second.author_id
        agents = db.session.scalars(db.select(AIAgent)).all()
        assert len(agents) == 1

    def test_from_config_uses_mock_in_testing_and_selects_configured_provider(
        self, app, db, question
    ):
        """from_config selecciona MockLLM en testing y Gemini/OpenAI si hay clave."""
        default_service = AIService.from_config()
        assert isinstance(default_service.strategy, MockLLMStrategy)

        app.config["GEMINI_API_KEY"] = "fake-gemini-key"
        app.config["LLM_PROVIDER"] = "gemini"
        gemini_service = AIService.from_config()
        assert isinstance(gemini_service.strategy, GeminiLLMStrategy)

        payload = {
            "candidates": [
                {"content": {"parts": [{"text": "Respuesta vía from_config."}]}}
            ]
        }
        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse(payload),
        ) as mock_urlopen:
            answer = gemini_service.generate_answer_for_question(question)

        mock_urlopen.assert_called_once()
        assert answer.body == "Respuesta vía from_config."

        app.config["GEMINI_API_KEY"] = None
        app.config["OPENAI_API_KEY"] = "fake-openai-key"
        app.config["LLM_PROVIDER"] = "openai"
        openai_service = AIService.from_config()
        assert isinstance(openai_service.strategy, OpenAILLMStrategy)

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
            AIService().generate_answer_for_question(unsaved)


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

    def test_post_generate_ai_answer_uses_injected_strategy_without_network(
        self, client, db, author, question
    ):
        """La ruta web usa la estrategia devuelta por AIService.from_config()."""
        stub = _StubStrategy("Respuesta controlada por estrategia inyectada.")
        _login(client, author)

        with patch(
            "qa_platform.web.questions.AIService.from_config",
            return_value=AIService(strategy=stub),
        ):
            response = client.post(f"/questions/{question.slug}/ai-answer")

        assert response.status_code == 302
        assert len(stub.received_prompts) == 1

        detail_html = client.get(f"/questions/{question.slug}").get_data(as_text=True)
        assert "Respuesta controlada por estrategia inyectada." in detail_html

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
