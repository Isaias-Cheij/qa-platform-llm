"""Paquete de estrategias LLM aplicando el patrón Strategy."""

from qa_platform.strategies.base import LLMProviderError, LLMStrategy
from qa_platform.strategies.mock_strategy import MockLLMStrategy

__all__ = [
    "LLMProviderError",
    "LLMStrategy",
    "MockLLMStrategy",
]
