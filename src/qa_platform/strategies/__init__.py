"""Paquete de estrategias LLM aplicando el patrón Strategy."""

from qa_platform.strategies.base import LLMProviderError, LLMStrategy
from qa_platform.strategies.gemini_strategy import GeminiLLMStrategy
from qa_platform.strategies.local_strategy import LocalLLMStrategy
from qa_platform.strategies.mock_strategy import MockLLMStrategy
from qa_platform.strategies.openai_strategy import OpenAILLMStrategy
from qa_platform.strategies.selector import SUPPORTED_PROVIDERS, get_llm_strategy

__all__ = [
    "GeminiLLMStrategy",
    "LLMProviderError",
    "LLMStrategy",
    "LocalLLMStrategy",
    "MockLLMStrategy",
    "OpenAILLMStrategy",
    "SUPPORTED_PROVIDERS",
    "get_llm_strategy",
]
