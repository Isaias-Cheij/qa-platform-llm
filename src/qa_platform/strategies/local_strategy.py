"""Estrategia concreta para modelos LLM locales (Ollama / servidor local)."""

import os

from qa_platform.strategies.base import (
    LLMProviderError,
    LLMStrategy,
    post_json,
    validate_prompt,
)

DEFAULT_LOCAL_LLM_URL = "http://localhost:11434/api/generate"
DEFAULT_LOCAL_LLM_MODEL = "llama3"


class LocalLLMStrategy(LLMStrategy):
    """Estrategia LLM para inferencia privada mediante servidor HTTP local."""

    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        model_name: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        """Inicializa la estrategia local leyendo endpoint y modelo del entorno.

        Args:
            endpoint_url: URL del servidor local (por defecto Ollama).
            model_name: Nombre del modelo cargado en el servidor local.
            timeout_seconds: Tiempo máximo de espera HTTP en segundos.
        """
        resolved_url = (
            endpoint_url or os.getenv("LOCAL_LLM_URL") or DEFAULT_LOCAL_LLM_URL
        )
        resolved_model = (
            model_name or os.getenv("LOCAL_LLM_MODEL") or DEFAULT_LOCAL_LLM_MODEL
        )
        self.endpoint_url = resolved_url.strip()
        self.model_name = resolved_model.strip()
        self.timeout_seconds = timeout_seconds

    def generate_response(self, prompt: str, context: str = "") -> str:
        """Genera una respuesta consultando el endpoint local configurado.

        Args:
            prompt: Consigna o pregunta principal.
            context: Contexto adicional antepuesto al prompt si no está vacío.

        Returns:
            Texto generado por el modelo local.

        Raises:
            ValueError: Si ``prompt`` es vacío.
            LLMProviderError: Si falla la llamada HTTP o la respuesta viene vacía.
        """
        clean_prompt = validate_prompt(prompt)
        clean_context = context.strip() if isinstance(context, str) else ""
        full_text = (
            f"{clean_context}\n\n{clean_prompt}" if clean_context else clean_prompt
        )

        payload = {
            "model": self.model_name,
            "prompt": full_text,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}

        data = post_json(
            self.endpoint_url,
            payload,
            headers=headers,
            timeout=self.timeout_seconds,
            provider=self.get_provider_name(),
        )

        clean_text = str(data.get("response", "")).strip()
        if not clean_text:
            raise LLMProviderError(
                "El proveedor LocalLLM devolvió una respuesta vacía."
            )
        return clean_text

    def get_provider_name(self) -> str:
        """Devuelve el nombre identificador ``'LocalLLM'``."""
        return "LocalLLM"
