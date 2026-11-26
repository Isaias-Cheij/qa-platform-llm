"""Selector en tiempo de ejecución de estrategias LLM según configuración."""

import os
from typing import Any

from flask import current_app, has_app_context

from qa_platform.strategies.base import LLMStrategy
from qa_platform.strategies.gemini_strategy import GeminiLLMStrategy
from qa_platform.strategies.local_strategy import LocalLLMStrategy
from qa_platform.strategies.mock_strategy import MockLLMStrategy
from qa_platform.strategies.openai_strategy import OpenAILLMStrategy

SUPPORTED_PROVIDERS = ("mock", "gemini", "openai", "local")


def _resolve_setting(key: str, default: str | None = None) -> str | None:
    """Obtiene una clave de configuración desde Flask o variables de entorno.

    En modo ``TESTING`` prioriza estrictamente ``current_app.config`` para
    evitar que variables reales del sistema afecten las pruebas unitarias.
    """
    if has_app_context():
        cfg_val = current_app.config.get(key)
        if bool(current_app.config.get("TESTING", False)):
            return cfg_val if cfg_val is not None else default
        return cfg_val or os.getenv(key) or default
    return os.getenv(key) or default


def get_llm_strategy(provider: str | None = None, **kwargs: Any) -> LLMStrategy:
    """Instancia la estrategia LLM concreta acorde a ``LLM_PROVIDER``.

    Args:
        provider: Nombre explícito del proveedor (``'mock'``, ``'gemini'``,
            ``'openai'`` o ``'local'``). Si es ``None``, se lee de
            ``current_app.config['LLM_PROVIDER']`` o de la variable de entorno
            ``LLM_PROVIDER`` (por defecto ``'mock'``).
        **kwargs: Parámetros adicionales reenviados al constructor de la
            estrategia seleccionada (por ejemplo ``canned_response``,
            ``api_key`` o ``model``).

    Returns:
        Instancia concreta que implementa ``LLMStrategy``.

    Raises:
        ValueError: Si el proveedor solicitado no está soportado o faltan
            credenciales obligatorias para ese proveedor.
    """
    raw_provider = (
        provider if provider is not None else _resolve_setting("LLM_PROVIDER", "mock")
    )
    normalized = (raw_provider or "mock").strip().lower()

    if normalized == "mock":
        return MockLLMStrategy(**kwargs)

    if normalized == "gemini":
        api_key = kwargs.pop("api_key", _resolve_setting("GEMINI_API_KEY"))
        model = kwargs.pop("model", _resolve_setting("GEMINI_MODEL"))
        return GeminiLLMStrategy(api_key=api_key, model=model, **kwargs)

    if normalized == "openai":
        api_key = kwargs.pop("api_key", _resolve_setting("OPENAI_API_KEY"))
        model = kwargs.pop("model", _resolve_setting("OPENAI_MODEL"))
        return OpenAILLMStrategy(api_key=api_key, model=model, **kwargs)

    if normalized == "local":
        endpoint_url = kwargs.pop("endpoint_url", _resolve_setting("LOCAL_LLM_URL"))
        model_name = kwargs.pop("model_name", _resolve_setting("LOCAL_LLM_MODEL"))
        return LocalLLMStrategy(
            endpoint_url=endpoint_url,
            model_name=model_name,
            **kwargs,
        )

    raise ValueError(
        f"Proveedor LLM no soportado: {raw_provider!r}. "
        f"Opciones válidas: {', '.join(SUPPORTED_PROVIDERS)}."
    )
