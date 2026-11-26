"""Servicio de generación automática de respuestas mediante Agente IA.

Integra la jerarquía polimórfica ``AIAgent`` con el paquete oficial de
estrategias ``qa_platform.strategies`` (Issue #32), delegando la construcción
del contexto y generación de texto en ``AIAgent.answer_question()`` sin
duplicar contratos ni condicionales de proveedor.
"""

import logging

from qa_platform.extensions import db
from qa_platform.factories import AIAgentFactory
from qa_platform.models.answer import Answer
from qa_platform.models.author import AIAgent
from qa_platform.models.question import Question
from qa_platform.strategies import (
    LLMProviderError,
    LLMStrategy,
    MockLLMStrategy,
    get_llm_strategy,
)

logger = logging.getLogger(__name__)

DEFAULT_BOT_IDENTIFIER = "qa-ai-assistant"
DEFAULT_BOT_NAME = "Agente IA"
DEFAULT_SYSTEM_PROMPT = (
    "Eres un asistente técnico experto en desarrollo de software y arquitectura. "
    "Responde con claridad, rigor académico y ejemplos prácticos."
)


class AIService:
    """Servicio de dominio encargado de generar respuestas automáticas con IA.

    Attributes:
        strategy: Estrategia concreta que implementa ``LLMStrategy`` para
            generar el cuerpo de la respuesta.
    """

    def __init__(self, strategy: LLMStrategy | None = None) -> None:
        """Inicializa el servicio inyectando la estrategia LLM oficial.

        Args:
            strategy: Implementación concreta de ``qa_platform.strategies.LLMStrategy``.
                Si no se provee ninguna, asigna ``MockLLMStrategy()`` por defecto.
        """
        self.strategy: LLMStrategy = (
            strategy if strategy is not None else MockLLMStrategy()
        )

    @classmethod
    def from_config(cls) -> "AIService":
        """Construye un ``AIService`` usando ``get_llm_strategy()`` del entorno.

        Returns:
            Instancia de ``AIService`` configurada según ``LLM_PROVIDER`` en
            ``current_app.config`` o variables de entorno.
        """
        return cls(strategy=get_llm_strategy())

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

        Inyecta ``self.strategy`` en el ``AIAgent`` del sistema y delega la
        generación de la entidad ``Answer`` a ``agent.answer_question(question)``.
        Si el proveedor externo falla con ``LLMProviderError``, recurre a
        ``MockLLMStrategy`` como respaldo para mantener operativo el flujo web.

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

        agent = self._get_or_create_agent()
        agent.set_strategy(self.strategy)

        try:
            answer = agent.answer_question(question)
        except LLMProviderError as exc:
            logger.warning(
                "Fallo del proveedor %s; usando MockLLMStrategy como fallback: %s",
                self.strategy.get_provider_name(),
                exc,
            )
            agent.set_strategy(MockLLMStrategy())
            answer = agent.answer_question(question)

        answer.is_ai_generated = True
        db.session.add(answer)
        db.session.commit()
        return answer
