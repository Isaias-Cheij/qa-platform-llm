"""Estrategia concreta para el proveedor Google Gemini."""

import os

from qa_platform.strategies.base import (
    LLMProviderError,
    LLMStrategy,
    post_json,
    validate_prompt,
)

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


class GeminiLLMStrategy(LLMStrategy):
    """Estrategia LLM que invoca la API REST de Google Gemini."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        timeout: int = 45,
    ) -> None:
        """Inicializa la estrategia de Gemini leyendo credenciales del entorno.

        Args:
            api_key: Clave de API de Google Gemini; si se omite se lee de
                ``GEMINI_API_KEY``.
            model: Identificador del modelo Gemini a utilizar.
            max_tokens: Límite máximo de tokens de salida.
            timeout: Tiempo máximo de espera HTTP en segundos.

        Raises:
            ValueError: Si no se dispone de una ``GEMINI_API_KEY`` válida.
        """
        resolved_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
        if not isinstance(resolved_key, str) or not resolved_key.strip():
            raise ValueError(
                "Se requiere GEMINI_API_KEY para utilizar GeminiLLMStrategy."
            )

        resolved_model = model or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        self._api_key = resolved_key.strip()
        self.model = resolved_model.strip()
        self.max_tokens = max_tokens
        self.timeout = timeout

    def generate_response(self, prompt: str, context: str = "") -> str:
        """Genera una respuesta consultando la API ``generateContent`` de Gemini.

        Args:
            prompt: Consigna o pregunta principal.
            context: Contexto adicional antepuesto al prompt si no está vacío.

        Returns:
            Texto generado por el modelo Gemini.

        Raises:
            ValueError: Si ``prompt`` es vacío.
            LLMProviderError: Si falla la llamada HTTP o la respuesta viene vacía.
        """
        clean_prompt = validate_prompt(prompt)
        clean_context = context.strip() if isinstance(context, str) else ""
        full_text = (
            f"{clean_context}\n\n{clean_prompt}" if clean_context else clean_prompt
        )

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": full_text}]}],
            "generationConfig": {"maxOutputTokens": self.max_tokens},
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

        data = post_json(
            url,
            payload,
            headers=headers,
            timeout=self.timeout,
            provider=self.get_provider_name(),
        )

        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text_parts = [
            str(part.get("text", "")).strip()
            for part in parts
            if isinstance(part, dict)
            and not part.get("thought")
            and str(part.get("text", "")).strip()
        ]
        clean_text = "\n".join(text_parts).strip()
        if not clean_text:
            raise LLMProviderError("El proveedor Gemini devolvió una respuesta vacía.")
        return clean_text

    def get_provider_name(self) -> str:
        """Devuelve el nombre identificador ``'Gemini'``."""
        return "Gemini"
