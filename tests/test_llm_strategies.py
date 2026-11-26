"""Pruebas unitarias y de integración para el patrón Strategy de proveedores LLM.

Verifica la interfaz abstracta ``LLMStrategy``, ``MockLLMStrategy``, las
estrategias concretas (Gemini, OpenAI y modelo local) usando mocks de red sin
llamadas reales a internet, el selector por ``LLM_PROVIDER`` y la delegación
polimórfica en tiempo de ejecución desde ``AIAgent``.
"""

import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from qa_platform.factories import AIAgentFactory
from qa_platform.models import Answer, Category, GeneralUser, Question, Tag
from qa_platform.strategies import (
    GeminiLLMStrategy,
    LLMProviderError,
    LLMStrategy,
    LocalLLMStrategy,
    MockLLMStrategy,
    OpenAILLMStrategy,
    get_llm_strategy,
)


class _FakeHTTPResponse:
    """Respuesta HTTP mínima compatible con ``with urllib.request.urlopen(...)``."""

    def __init__(self, payload: dict) -> None:
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


# ---------------------------------------------------------------------------
# Tests de interfaz abstracta y MockLLMStrategy
# ---------------------------------------------------------------------------


class TestLLMStrategyInterfaceAndMock:
    """Pruebas para el contrato abstracto ``LLMStrategy`` y ``MockLLMStrategy``."""

    def test_cannot_instantiate_abstract_llm_strategy(self):
        """LLMStrategy es abstracta y no puede instanciarse directamente."""
        with pytest.raises(TypeError):
            LLMStrategy()  # type: ignore[abstract]

    def test_mock_strategy_deterministic_response_and_provider_name(self):
        """MockLLMStrategy es determinista y soporta respuesta fija opcional."""
        strategy = MockLLMStrategy()
        assert strategy.get_provider_name() == "MockLLM"

        out1 = strategy.generate_response(
            "¿Qué es el patrón Strategy?", context="Patrones GoF"
        )
        out2 = strategy.generate_response(
            "¿Qué es el patrón Strategy?", context="Patrones GoF"
        )
        assert out1 == out2
        assert "[MockLLM]" in out1
        assert "¿Qué es el patrón Strategy?" in out1
        assert "Patrones GoF" in out1

        canned = MockLLMStrategy(canned_response="Respuesta fija de prueba.")
        assert canned.generate_response("Cualquier prompt") == (
            "Respuesta fija de prueba."
        )

    @pytest.mark.parametrize("bad_prompt", ["", "   ", "\n\t"])
    def test_mock_strategy_rejects_empty_prompt(self, bad_prompt):
        """Un prompt vacío debe lanzar ValueError."""
        strategy = MockLLMStrategy()
        with pytest.raises(ValueError):
            strategy.generate_response(bad_prompt)


# ---------------------------------------------------------------------------
# Tests de estrategias concretas (Gemini, OpenAI, Local)
# ---------------------------------------------------------------------------


class TestConcreteLLMStrategies:
    """Pruebas para estrategias concretas con peticiones HTTP mockeadas."""

    def test_gemini_strategy_requires_api_key(self, monkeypatch):
        """GeminiLLMStrategy exige GEMINI_API_KEY válida al instanciarse."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValueError):
            GeminiLLMStrategy()
        with pytest.raises(ValueError):
            GeminiLLMStrategy(api_key="   ")

    def test_gemini_strategy_calls_api_and_parses_response(self):
        """GeminiLLMStrategy arma la petición REST y extrae el texto generado."""
        fake_payload = {
            "candidates": [
                {"content": {"parts": [{"text": "Usa composición e interfaces ABC."}]}}
            ]
        }
        strategy = GeminiLLMStrategy(
            api_key="fake-gemini-key", model="gemini-3.5-flash-lite"
        )
        assert strategy.get_provider_name() == "Gemini"

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse(fake_payload),
        ) as mock_open:
            result = strategy.generate_response(
                "¿Cómo aplicar Strategy?", context="Python 3.12"
            )

        assert result == "Usa composición e interfaces ABC."
        req = mock_open.call_args[0][0]
        assert "gemini-3.5-flash-lite:generateContent" in req.full_url
        assert req.get_header("X-goog-api-key") == "fake-gemini-key"
        sent_body = json.loads(req.data.decode("utf-8"))
        text_sent = sent_body["contents"][0]["parts"][0]["text"]
        assert "Python 3.12" in text_sent
        assert "¿Cómo aplicar Strategy?" in text_sent

    def test_gemini_strategy_wraps_network_and_empty_errors(self):
        """Errores HTTP o respuestas vacías de Gemini lanzan LLMProviderError."""
        strategy = GeminiLLMStrategy(api_key="fake-gemini-key")

        with (
            patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("fallo de red"),
            ),
            pytest.raises(LLMProviderError),
        ):
            strategy.generate_response("Hola")

        with (
            patch(
                "urllib.request.urlopen",
                return_value=_FakeHTTPResponse({"candidates": []}),
            ),
            pytest.raises(LLMProviderError),
        ):
            strategy.generate_response("Hola")

    def test_gemini_strategy_ignores_thought_parts(self):
        """Filtra bloques internos de razonamiento (thought=True) de Gemini."""
        fake_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"thought": True, "text": "razonamiento interno"},
                            {"text": "Respuesta final clara."},
                        ]
                    }
                }
            ]
        }
        strategy = GeminiLLMStrategy(api_key="fake-gemini-key")

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse(fake_payload),
        ):
            result = strategy.generate_response("¿Cuánto es 2+2?")

        assert result == "Respuesta final clara."

    def test_openai_strategy_requires_api_key(self, monkeypatch):
        """OpenAILLMStrategy exige OPENAI_API_KEY válida al instanciarse."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ValueError):
            OpenAILLMStrategy()
        with pytest.raises(ValueError):
            OpenAILLMStrategy(api_key=" ")

    def test_openai_strategy_calls_api_and_parses_response(self):
        """OpenAILLMStrategy envía mensajes system/user y extrae el contenido."""
        fake_payload = {
            "choices": [
                {"message": {"content": "Desacopla proveedores detrás de LLMStrategy."}}
            ]
        }
        strategy = OpenAILLMStrategy(api_key="fake-openai-key", model="gpt-4o-mini")
        assert strategy.get_provider_name() == "OpenAI"

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse(fake_payload),
        ) as mock_open:
            result = strategy.generate_response(
                "Explica OCP", context="Ingeniería de Software"
            )

        assert result == "Desacopla proveedores detrás de LLMStrategy."
        req = mock_open.call_args[0][0]
        assert req.full_url == "https://api.openai.com/v1/chat/completions"
        assert req.get_header("Authorization") == "Bearer fake-openai-key"
        sent_body = json.loads(req.data.decode("utf-8"))
        assert sent_body["messages"] == [
            {"role": "system", "content": "Ingeniería de Software"},
            {"role": "user", "content": "Explica OCP"},
        ]

    def test_openai_strategy_wraps_network_and_empty_errors(self):
        """Errores HTTP o choices vacíos de OpenAI lanzan LLMProviderError."""
        strategy = OpenAILLMStrategy(api_key="fake-openai-key")

        with (
            patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")),
            pytest.raises(LLMProviderError),
        ):
            strategy.generate_response("Hola")

        with (
            patch(
                "urllib.request.urlopen",
                return_value=_FakeHTTPResponse({"choices": []}),
            ),
            pytest.raises(LLMProviderError),
        ):
            strategy.generate_response("Hola")

    def test_local_strategy_calls_endpoint_and_handles_errors(self):
        """LocalLLMStrategy consulta el endpoint local y envuelve errores."""
        strategy = LocalLLMStrategy(
            endpoint_url="http://localhost:11434/api/generate",
            model_name="llama3",
        )
        assert strategy.get_provider_name() == "LocalLLM"

        with patch(
            "urllib.request.urlopen",
            return_value=_FakeHTTPResponse({"response": "Respuesta local privada."}),
        ) as mock_open:
            result = strategy.generate_response("¿Qué es Flask?")

        assert result == "Respuesta local privada."
        req = mock_open.call_args[0][0]
        assert req.full_url == "http://localhost:11434/api/generate"

        with (
            patch(
                "urllib.request.urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ),
            pytest.raises(LLMProviderError),
        ):
            strategy.generate_response("¿Qué es Flask?")


# ---------------------------------------------------------------------------
# Tests del selector por variable LLM_PROVIDER
# ---------------------------------------------------------------------------


class TestStrategySelector:
    """Pruebas para ``get_llm_strategy()`` desde entorno y config de Flask."""

    def test_selector_defaults_to_mock_in_testing_app(self, app):
        """En TestingConfig la estrategia por defecto es MockLLMStrategy."""
        strategy = get_llm_strategy()
        assert isinstance(strategy, MockLLMStrategy)
        assert strategy.get_provider_name() == "MockLLM"

    def test_selector_picks_provider_from_env_and_app_config(self, app, monkeypatch):
        """Selecciona la estrategia concreta según LLM_PROVIDER en env y Flask."""
        # Fuera de contexto de app (usando os.getenv)
        with patch(
            "qa_platform.strategies.selector.has_app_context", return_value=False
        ):
            monkeypatch.setenv("LLM_PROVIDER", "mock")
            assert isinstance(get_llm_strategy(), MockLLMStrategy)

            monkeypatch.setenv("LLM_PROVIDER", "local")
            assert isinstance(get_llm_strategy(), LocalLLMStrategy)

        # Dentro de contexto de app (usando app.config)
        app.config["LLM_PROVIDER"] = "gemini"
        app.config["GEMINI_API_KEY"] = "cfg-gemini-key"
        assert isinstance(get_llm_strategy(), GeminiLLMStrategy)

        app.config["LLM_PROVIDER"] = "openai"
        app.config["OPENAI_API_KEY"] = "cfg-openai-key"
        assert isinstance(get_llm_strategy(), OpenAILLMStrategy)

        app.config["LLM_PROVIDER"] = "local"
        assert isinstance(get_llm_strategy(), LocalLLMStrategy)

    def test_selector_rejects_unknown_provider(self, app):
        """Un proveedor desconocido debe lanzar ValueError."""
        app.config["LLM_PROVIDER"] = "proveedor-inexistente"
        with pytest.raises(ValueError):
            get_llm_strategy()


# ---------------------------------------------------------------------------
# Tests de integración con AIAgent y Answer
# ---------------------------------------------------------------------------


class TestAIAgentStrategyIntegration:
    """Pruebas de delegación e intercambio dinámico de estrategias en AIAgent."""

    def test_ai_agent_delegates_and_switches_strategy_at_runtime(self):
        """AIAgent permite inyectar y cambiar la estrategia LLM en caliente."""
        initial = MockLLMStrategy(
            canned_response="Respuesta con estrategia inicial.",
            provider_name="MockA",
        )
        factory = AIAgentFactory(default_strategy=initial)
        agent = factory.create_author(
            "strategy-bot",
            "Bot Strategy",
            system_prompt="Responde académicamente.",
        )

        assert agent.get_current_strategy() == "MockA"
        assert agent.generate_response("¿Qué es SOLID?") == (
            "Respuesta con estrategia inicial."
        )

        replacement = MockLLMStrategy(provider_name="MockB")
        agent.set_strategy(replacement)
        assert agent.get_current_strategy() == "MockB"

        output = agent.generate_response("¿Qué es SOLID?", context="POO")
        assert "[MockB]" in output
        assert "Responde académicamente." in output
        assert "POO" in output

    def test_ai_agent_without_strategy_raises_runtime_error(self):
        """Invocar generate_response sin estrategia configurada lanza RuntimeError."""
        agent = AIAgentFactory().create_author("no-strat-bot", "Bot Sin Estrategia")
        with pytest.raises(RuntimeError):
            agent.generate_response("¿Alguien ahí?")

    def test_ai_agent_answer_question_creates_persisted_answer(self, db):
        """answer_question() produce un Answer polimórfico persistible en BD."""
        user = GeneralUser(
            username="student_q",
            email="student_q@example.com",
            password="Password123",
        )
        cat = Category(name="Patrones", slug="patrones")
        tag = Tag(name="ia-help", slug="ia-help")
        db.session.add_all([user, cat, tag])
        db.session.commit()

        question = Question(
            title="¿Cómo desacoplar llamadas a Gemini y OpenAI?",
            slug="como-desacoplar-gemini-openai",
            body="Busco poder alternar entre proveedores con una variable env.",
            user_id=user.id,
            category_id=cat.id,
        )
        question.tags.append(tag)
        db.session.add(question)
        db.session.commit()

        agent = AIAgentFactory(default_strategy=MockLLMStrategy()).register_author(
            "qa-helper-bot",
            "Agente QA",
            system_prompt="Sé conciso.",
        )

        answer = agent.answer_question(question)
        db.session.add(answer)
        db.session.commit()

        saved = db.session.get(Answer, answer.id)
        assert saved is not None
        assert saved.question_id == question.id
        assert saved.get_author().is_agent() is True
        assert "[MockLLM]" in saved.body
        assert "Patrones" in saved.body
        assert "ia-help" in saved.body
