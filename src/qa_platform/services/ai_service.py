"""Servicio de generación automática de respuestas mediante Agente IA.

Construye el prompt contextual a partir de una pregunta y delega la generación
del texto de respuesta a una estrategia ``LLMStrategy`` inyectada (por defecto
``MockLLMStrategy``), eliminando condicionales directos de proveedor dentro del
servicio de dominio.
"""

import os

from flask import current_app, has_app_context

from qa_platform.extensions import db
from qa_platform.factories import AIAgentFactory
from qa_platform.models.answer import Answer
from qa_platform.models.author import AIAgent
from qa_platform.models.question import Question
from qa_platform.services.strategies import (
    DEFAULT_SYSTEM_PROMPT,
    GeminiLLMStrategy,
    LLMStrategy,
    MockLLMStrategy,
    OpenAILLMStrategy,
)

DEFAULT_BOT_IDENTIFIER = "qa-ai-assistant"
DEFAULT_BOT_NAME = "Agente IA"


def resolve_strategy_from_config() -> LLMStrategy:
    """Selecciona la estrategia LLM concreta según la configuración del entorno.

    En modo ``TESTING`` solo considera claves definidas explícitamente en
    ``current_app.config`` para evitar que variables de entorno locales disparen
    llamadas HTTP reales durante los tests.

    Returns:
        Instancia concreta de ``LLMStrategy`` lista para usar en ``AIService``.
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

    strategy_map: list[tuple[bool, LLMStrategy | None]] = [
        (
            provider == "openai" and bool(openai_key or generic_key),
            OpenAILLMStrategy(str(openai_key or generic_key))
            if (openai_key or generic_key)
            else None,
        ),
        (bool(gemini_key), GeminiLLMStrategy(str(gemini_key)) if gemini_key else None),
        (bool(openai_key), OpenAILLMStrategy(str(openai_key)) if openai_key else None),
        (
            bool(generic_key),
            GeminiLLMStrategy(str(generic_key)) if generic_key else None,
        ),
    ]
    for enabled, strategy in strategy_map:
        if enabled and strategy is not None:
            return strategy

    return MockLLMStrategy()


class AIService:
    """Servicio de dominio encargado de generar respuestas automáticas con IA.

    Attributes:
        strategy: Estrategia concreta que implementa ``LLMStrategy`` para
            generar el cuerpo de la respuesta.
    """

    def __init__(self, strategy: LLMStrategy | None = None) -> None:
        """Inicializa el servicio inyectando la estrategia de generación LLM.

        Args:
            strategy: Implementación concreta de ``LLMStrategy``. Si no se
                provee ninguna, utiliza ``MockLLMStrategy()`` por defecto.
        """
        self.strategy: LLMStrategy = (
            strategy if strategy is not None else MockLLMStrategy()
        )

    @classmethod
    def from_config(cls) -> "AIService":
        """Construye un ``AIService`` resolviendo la estrategia desde la app.

        Returns:
            Instancia de ``AIService`` configurada para el entorno activo.
        """
        return cls(strategy=resolve_strategy_from_config())

    @staticmethod
    def _build_prompt(question: Question) -> str:
        """Organiza los datos de la pregunta en un prompt técnico estructurado.

        Args:
            question: Instancia de ``Question`` a responder.

        Returns:
            Cadena de prompt lista para enviar a la estrategia LLM.
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

    def generate_answer_for_question(self, question: Question) -> Answer:
        """Genera y persiste una respuesta automática de IA para una pregunta.

        Delega la generación del contenido a ``self.strategy.generate(prompt)``
        y asocia el resultado a un autor ``AIAgent`` en la base de datos.

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

        prompt = self._build_prompt(question)
        answer_body = self.strategy.generate(prompt)

        agent = self._get_or_create_agent()
        answer = Answer(
            body=answer_body,
            question=question,
            author=agent,
            is_ai_generated=True,
        )
        db.session.add(answer)
        db.session.commit()
        return answer
