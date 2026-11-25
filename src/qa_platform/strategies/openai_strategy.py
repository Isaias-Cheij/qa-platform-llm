"""Estrategia concreta para el proveedor OpenAI."""

import os

from qa_platform.strategies.base import (
    LLMProviderError,
    LLMStrategy,
    post_json,
    validate_prompt,
)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class OpenAILLMStrategy(LLMStrategy):
    """Estrategia LLM que invoca la API Chat Completions de OpenAI."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        timeout: int = 15,
    ) -> None:
        """Inicializa la estrategia de OpenAI leyendo credenciales del entorno.

        Args:
            api_key: Clave de API de OpenAI; si se omite se lee de
                ``OPENAI_API_KEY``.
            model: Identificador del modelo OpenAI a utilizar.
            temperature: Temperatura de muestreo del modelo.
            timeout: Tiempo máximo de espera HTTP en segundos.

        Raises:
            ValueError: Si no se dispone de una ``OPENAI_API_KEY`` válida.
        """
        resolved_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        if not isinstance(resolved_key, str) or not resolved_key.strip():
            raise ValueError(
                "Se requiere OPENAI_API_KEY para utilizar OpenAILLMStrategy."
            )

        resolved_model = model or os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        self._api_key = resolved_key.strip()
        self.model = resolved_model.strip()
        self.temperature = temperature
        self.timeout = timeout

    def generate_response(self, prompt: str, context: str = "") -> str:
        """Genera una respuesta consultando ``/v1/chat/completions`` de OpenAI.

        Args:
            prompt: Consigna o pregunta principal.
            context: Instrucciones de sistema o contexto adicional opcional.

        Returns:
            Texto generado por el modelo de OpenAI.

        Raises:
            ValueError: Si ``prompt`` es vacío.
            LLMProviderError: Si falla la llamada HTTP o la respuesta viene vacía.
        """
        clean_prompt = validate_prompt(prompt)
        clean_context = context.strip() if isinstance(context, str) else ""

        messages: list[dict[str, str]] = []
        if clean_context:
            messages.append({"role": "system", "content": clean_context})
        messages.append({"role": "user", "content": clean_prompt})

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": messages,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        data = post_json(
            url,
            payload,
            headers=headers,
            timeout=self.timeout,
            provider=self.get_provider_name(),
        )

        choices = data.get("choices") or []
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        clean_text = str(text).strip()
        if not clean_text:
            raise LLMProviderError("El proveedor OpenAI devolvió una respuesta vacía.")
        return clean_text

    def get_provider_name(self) -> str:
        """Devuelve el nombre identificador ``'OpenAI'``."""
        return "OpenAI"
