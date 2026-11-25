"""Estrategias de generación de texto para el servicio de Agente IA.

Implementa el patrón Strategy mediante la interfaz abstracta ``LLMStrategy`` y
sus implementaciones concretas: ``MockLLMStrategy`` para desarrollo/testing sin
llamadas de red, y ``GeminiLLMStrategy`` / ``OpenAILLMStrategy`` para producción.
"""

import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

DEFAULT_SYSTEM_PROMPT = (
    "Eres un asistente técnico experto en desarrollo de software y arquitectura. "
    "Responde con claridad, rigor académico y ejemplos prácticos."
)


def _post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    """Ejecuta una petición HTTP POST JSON y devuelve la respuesta decodificada.

    Args:
        url: Endpoint HTTP destino.
        payload: Cuerpo serializable a JSON.
        headers: Cabeceras HTTP de la petición.

    Returns:
        Diccionario decodificado desde la respuesta JSON del proveedor.

    Raises:
        urllib.error.URLError: Si ocurre un error de red o HTTP.
        ValueError: Si la respuesta no es JSON válido.
    """
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_prompt_field(prompt: str, prefix: str) -> str | None:
    """Extrae el valor de una línea con prefijo conocido dentro del prompt."""
    for line in prompt.splitlines():
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip()
            return value or None
    return None


class LLMStrategy(ABC):
    """Interfaz abstracta para proveedores de generación de texto con LLM."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Genera una respuesta en texto plano a partir de un prompt contextual.

        Args:
            prompt: Prompt estructurado con el contexto de la consulta.

        Returns:
            Texto generado por el modelo o simulador.

        Raises:
            ValueError: Si ``prompt`` está vacío o la respuesta es inválida.
        """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Devuelve el nombre identificador del proveedor de la estrategia.

        Returns:
            Nombre legible del proveedor (ej. ``'MockLLM'``, ``'Gemini'``).
        """


class MockLLMStrategy(LLMStrategy):
    """Estrategia simulada y determinista para desarrollo local y testing."""

    def get_provider_name(self) -> str:
        """Devuelve el nombre del proveedor simulado.

        Returns:
            Cadena ``'MockLLM'``.
        """
        return "MockLLM"

    def generate(self, prompt: str) -> str:
        """Genera una respuesta técnica simulada sin realizar llamadas de red.

        Args:
            prompt: Prompt contextual armado para la pregunta.

        Returns:
            Respuesta estructurada adaptada al título y categoría si están
            presentes en el prompt.

        Raises:
            ValueError: Si ``prompt`` es vacío o solo contiene espacios.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("El prompt debe ser una cadena no vacía.")

        title = _extract_prompt_field(prompt, "Título:")
        category = _extract_prompt_field(prompt, "Categoría:") or "General"
        tags = _extract_prompt_field(prompt, "Etiquetas:")

        context_parts: list[str] = []
        if title:
            context_parts.append(f"'{title}' en la categoría '{category}'")
        else:
            context_parts.append(f"tu consulta en la categoría '{category}'")

        if tags and tags != "Sin etiquetas":
            context_parts.append(f"considerando las etiquetas {tags}")

        context_clause = " ".join(context_parts)
        return (
            f"Respuesta generada por el Agente IA: Hola, respecto a tu duda sobre "
            f"{context_clause}, te sugiero seguir estos pasos:\n\n"
            "1. Revisar la definición y contratos del componente involucrado.\n"
            "2. Aislar el problema en un caso mínimo reproducible para validar "
            "entradas y salidas esperadas.\n"
            "3. Cubrir el comportamiento esperado con pruebas unitarias antes de "
            "integrar cambios."
        )


class GeminiLLMStrategy(LLMStrategy):
    """Estrategia de producción que consulta la API REST de Google Gemini."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-2.0-flash",
    ) -> None:
        """Inicializa la estrategia con la clave de API de Gemini.

        Args:
            api_key: Clave válida para autenticar contra la API de Gemini.
            model: Identificador del modelo Gemini a invocar.

        Raises:
            ValueError: Si ``api_key`` está vacía.
        """
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Se requiere una api_key válida para GeminiLLMStrategy.")
        self._api_key = api_key.strip()
        self._model = model

    def get_provider_name(self) -> str:
        """Devuelve el nombre del proveedor Gemini.

        Returns:
            Cadena ``'Gemini'``.
        """
        return "Gemini"

    def generate(self, prompt: str) -> str:
        """Envía el prompt a la API de Gemini y devuelve el texto generado.

        Args:
            prompt: Prompt contextual de la pregunta.

        Returns:
            Respuesta en texto generada por Gemini.

        Raises:
            ValueError: Si el prompt está vacío o Gemini no devuelve texto.
            urllib.error.URLError: Si falla la comunicación HTTP.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("El prompt debe ser una cadena no vacía.")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._api_key}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        data = _post_json(url, payload, {"Content-Type": "application/json"})

        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = str(parts[0].get("text", "") if parts else "").strip()
        if not text:
            raise ValueError("El proveedor Gemini devolvió una respuesta vacía.")
        return text


class OpenAILLMStrategy(LLMStrategy):
    """Estrategia de producción que consulta la API Chat Completions de OpenAI."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-4o-mini",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        """Inicializa la estrategia con la clave de API de OpenAI.

        Args:
            api_key: Clave válida para autenticar contra la API de OpenAI.
            model: Modelo OpenAI a invocar.
            system_prompt: Instrucción de sistema para contextualizar respuestas.

        Raises:
            ValueError: Si ``api_key`` está vacía.
        """
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Se requiere una api_key válida para OpenAILLMStrategy.")
        self._api_key = api_key.strip()
        self._model = model
        self._system_prompt = system_prompt

    def get_provider_name(self) -> str:
        """Devuelve el nombre del proveedor OpenAI.

        Returns:
            Cadena ``'OpenAI'``.
        """
        return "OpenAI"

    def generate(self, prompt: str) -> str:
        """Envía el prompt a la API de OpenAI y devuelve el texto generado.

        Args:
            prompt: Prompt contextual de la pregunta.

        Returns:
            Respuesta en texto generada por OpenAI.

        Raises:
            ValueError: Si el prompt está vacío o OpenAI no devuelve texto.
            urllib.error.URLError: Si falla la comunicación HTTP.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("El prompt debe ser una cadena no vacía.")

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        data = _post_json(url, payload, headers)

        choices = data.get("choices") or []
        text = str(
            choices[0].get("message", {}).get("content", "") if choices else ""
        ).strip()
        if not text:
            raise ValueError("El proveedor OpenAI devolvió una respuesta vacía.")
        return text
