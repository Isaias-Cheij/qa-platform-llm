"""Fábrica concreta para la creación de agentes de inteligencia artificial."""

from typing import Any

from qa_platform.factories.author_factory import AuthorFactory
from qa_platform.models.author import AIAgent


class AIAgentFactory(AuthorFactory):
    """Concrete Creator encargado de instanciar ``AIAgent`` con su estrategia LLM."""

    def __init__(self, default_strategy: Any = None) -> None:
        """Inicializa la fábrica con una estrategia LLM por defecto opcional.

        Args:
            default_strategy: Estrategia LLM que se inyectará cuando no se
                especifique una explícitamente al crear el agente.
        """
        self._default_strategy = default_strategy

    def create_author(
        self, identifier: str, display_name: str, **kwargs: Any
    ) -> AIAgent:
        """Crea una instancia de ``AIAgent`` inyectando la estrategia correspondiente.

        Args:
            identifier: Identificador único del bot (``bot_identifier``).
            display_name: Nombre visible del agente en la plataforma.
            **kwargs: Parámetros opcionales como ``version``, ``system_prompt``
                y ``strategy`` (sobrescribe ``default_strategy``).

        Returns:
            Instancia de ``AIAgent`` lista para usar o persistir.
        """
        version = kwargs.get("version", "1.0.0")
        system_prompt = kwargs.get("system_prompt")
        strategy = kwargs.get("strategy", self._default_strategy)

        return AIAgent(
            bot_identifier=identifier,
            display_name=display_name,
            version=version,
            system_prompt=system_prompt,
            strategy=strategy,
        )
