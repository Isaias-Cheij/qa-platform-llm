"""Servicio de generación automática de respuestas mediante Agente IA.

Encapsula la construcción del prompt contextual, la invocación opcional a un
proveedor LLM externo (OpenAI / Gemini) cuando existe una clave configurada,
y un mecanismo de fallback determinista para entornos de desarrollo y testing
sin acceso a red ni credenciales.
"""

import json
import logging
import os
import urllib.error
import urllib.request

from flask import current_app, has_app_context

from qa_platform.extensions import db
from qa_platform.factories import AIAgentFactory
from qa_platform.models.answer import Answer
from qa_platform.models.author import AIAgent
from qa_platform.models.question import Question

logger = logging.getLogger(__name__)

DEFAULT_BOT_IDENTIFIER = "qa-ai-assistant"
DEFAULT_BOT_NAME = "Agente IA"
DEFAULT_SYSTEM_PROMPT = (
    "Eres un asistente técnico experto en desarrollo de software y arquitectura. "
    "Responde con claridad, rigor académico y ejemplos prácticos."
)


class AIService:
    """Servicio de dominio encargado de generar respuestas automáticas con IA."""

    @staticmethod
    def _build_prompt(question: Question) -> str:
        """Organiza los datos de la pregunta en un prompt técnico estructurado.

        Args:
            question: Instancia de ``Question`` a responder.

        Returns:
            Cadena de prompt lista para enviar a un modelo de lenguaje.
        """
        category_name = question.category.name if question.category else "General"
        tag_names = [tag.name for tag in question.tags]
        tags_line = ", ".join(tag_names) if tag_names else "Sin etiquetas"

        return (
            "Responde de forma clara, precisa y técnica a la siguiente pregunta "
            "de la plataforma Q&A:\n\n"
            f"Título: {question.title}\n"
            f"Categoría: {category_name}\n"
            f"Etiquetas: {tags_line}\n"
            f"Detalle:\n{question.body}\n"
        )

    @staticmethod
    def _get_or_create_agent() -> AIAgent:
        """Obtiene el agente IA del sistema o lo registra si aún no existe.

        Returns:
            Instancia persistida de ``AIAgent``.
        """
        agent = db.session.scalar(
            db.select(AIAgent).filter_by(bot_identifier=DEFAULT_BOT_IDENTIFIER)
        )
        if agent is None:
            agent = AIAgentFactory().register_author(
                DEFAULT_BOT_IDENTIFIER,
                DEFAULT_BOT_NAME,
                commit=False,
                version="1.0.0",
                system_prompt=DEFAULT_SYSTEM_PROMPT,
            )
            db.session.flush()
        return agent

    @staticmethod
    def _resolve_llm_credentials() -> tuple[str, str | None]:
        """Obtiene el proveedor y API key configurados para el entorno actual.

        En modo ``TESTING`` solo considera las claves explícitas de
        ``current_app.config`` para evitar que variables de entorno del equipo
        disparen llamadas HTTP reales durante los tests.

        Returns:
            Tupla ``(provider, api_key)`` donde ``api_key`` es ``None`` si no
            hay credenciales activas.
        """
        if has_app_context():
            cfg = current_app.config
            is_testing = bool(cfg.get("TESTING", False))
            provider = str(cfg.get("LLM_PROVIDER") or "gemini").lower()
            openai_key = cfg.get("OPENAI_API_KEY")
            gemini_key = cfg.get("GEMINI_API_KEY")
            generic_key = cfg.get("LLM_API_KEY")

            if not is_testing:
                openai_key = openai_key or os.getenv("OPENAI_API_KEY")
                gemini_key = gemini_key or os.getenv("GEMINI_API_KEY")
                generic_key = generic_key or os.getenv("LLM_API_KEY")
        else:
            provider = os.getenv("LLM_PROVIDER", "gemini").lower()
            openai_key = os.getenv("OPENAI_API_KEY")
            gemini_key = os.getenv("GEMINI_API_KEY")
            generic_key = os.getenv("LLM_API_KEY")

        if provider == "openai" and (openai_key or generic_key):
            return "openai", (openai_key or generic_key)
        if gemini_key:
            return "gemini", gemini_key
        if openai_key:
            return "openai", openai_key
        if generic_key:
            return provider, generic_key
        return provider, None

    @staticmethod
    def _call_llm_api(prompt: str, *, provider: str, api_key: str) -> str:
        """Invoca la API REST del proveedor LLM configurado sin dependencias extra.

        Args:
            prompt: Prompt contextual armado para la pregunta.
            provider: Proveedor destino (``'openai'`` o ``'gemini'``).
            api_key: Clave de API válida para autenticar la solicitud.

        Returns:
            Texto generado por el modelo de lenguaje.

        Raises:
            ValueError: Si la respuesta de la API no contiene texto utilizable.
            urllib.error.URLError: Si falla la conexión HTTP con el proveedor.
        """
        if provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
        else:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.0-flash:generateContent?key={api_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
            }
            headers = {"Content-Type": "application/json"}

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if provider == "openai":
            choices = data.get("choices") or []
            text = choices[0].get("message", {}).get("content", "") if choices else ""
        else:
            candidates = data.get("candidates") or []
            parts = (
                candidates[0].get("content", {}).get("parts", []) if candidates else []
            )
            text = parts[0].get("text", "") if parts else ""

        clean_text = str(text).strip()
        if not clean_text:
            raise ValueError("El proveedor LLM devolvió una respuesta vacía.")
        return clean_text

    @staticmethod
    def _generate_fallback_answer(question: Question) -> str:
        """Construye una respuesta técnica simulada cuando no hay API key activa.

        Args:
            question: Pregunta sobre la cual generar la orientación simulada.

        Returns:
            Texto de respuesta profesional adaptado al título, categoría y tags.
        """
        category_name = question.category.name if question.category else "General"
        tag_names = [tag.name for tag in question.tags]
        tags_clause = (
            f" considerando las etiquetas {', '.join(tag_names)}" if tag_names else ""
        )

        return (
            f"Respuesta generada por el Agente IA: Hola, respecto a tu duda sobre "
            f"'{question.title}' en la categoría '{category_name}'{tags_clause}, "
            "te sugiero seguir estos pasos:\n\n"
            "1. Revisar la definición y contratos del componente involucrado.\n"
            "2. Aislar el problema en un caso mínimo reproducible para validar "
            "entradas y salidas esperadas.\n"
            "3. Cubrir el comportamiento esperado con pruebas unitarias antes de "
            "integrar cambios."
        )

    @classmethod
    def generate_answer_for_question(cls, question: Question) -> Answer:
        """Genera y persiste una respuesta automática de IA para una pregunta.

        Intenta consultar el proveedor LLM configurado si existe una API key
        disponible; en caso contrario (o si la llamada externa falla), utiliza
        una respuesta simulada determinista como fallback.

        Args:
            question: Instancia persistida de ``Question`` a responder.

        Returns:
            Instancia de ``Answer`` persistida en base de datos con
            ``is_ai_generated=True``.

        Raises:
            ValueError: Si ``question`` es ``None`` o no tiene ``id`` asignado.
        """
        if question is None or question.id is None:
            raise ValueError(
                "La pregunta debe estar persistida antes de generar una respuesta IA."
            )

        prompt = cls._build_prompt(question)
        provider, api_key = cls._resolve_llm_credentials()

        if api_key:
            try:
                answer_body = cls._call_llm_api(
                    prompt, provider=provider, api_key=api_key
                )
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                logger.warning(
                    "Fallo al invocar proveedor LLM (%s); usando fallback local: %s",
                    provider,
                    exc,
                )
                answer_body = cls._generate_fallback_answer(question)
        else:
            answer_body = cls._generate_fallback_answer(question)

        agent = cls._get_or_create_agent()
        answer = Answer(
            body=answer_body,
            question=question,
            author=agent,
            is_ai_generated=True,
        )
        db.session.add(answer)
        db.session.commit()
        return answer
