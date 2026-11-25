"""Contrato abstracto del patrón Strategy para proveedores de LLM."""

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any


class LLMProviderError(RuntimeError):
    """Error de dominio al comunicarse con un proveedor de LLM."""


def validate_prompt(prompt: str) -> str:
    """Valida que el prompt sea una cadena de texto no vacía y la limpia."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("El prompt debe ser una cadena no vacía.")
    return prompt.strip()


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: int,
    provider: str,
) -> dict[str, Any]:
    """Envía una petición HTTP POST con cuerpo JSON y devuelve el objeto decodificado.

    Args:
        url: Endpoint del proveedor LLM.
        payload: Diccionario serializable a JSON.
        headers: Encabezados HTTP de la petición.
        timeout: Tiempo máximo de espera en segundos.
        provider: Nombre del proveedor para enriquecer los mensajes de error.

    Returns:
        Diccionario JSON devuelto por el servidor.

    Raises:
        LLMProviderError: Ante errores de red, timeout o JSON inválido.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read().decode("utf-8")
            data = json.loads(raw_body)
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        raise LLMProviderError(
            f"Error al comunicarse con el proveedor {provider}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise LLMProviderError(
            f"Respuesta inesperada del proveedor {provider}: "
            "se esperaba un objeto JSON."
        )
    return data


class LLMStrategy(ABC):
    """Interfaz Strategy para desacoplar la generación de respuestas con LLM.

    Cada proveedor concreto (Mock, Gemini, OpenAI, modelos locales) debe
    implementar este contrato para poder intercambiarse en tiempo de ejecución
    sin modificar a ``AIAgent`` ni a la lógica del dominio.
    """

    @abstractmethod
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Genera una respuesta de texto a partir de un prompt y contexto.

        Args:
            prompt: Consigna o pregunta principal enviada al modelo.
            context: Información adicional (categoría, etiquetas, instrucciones).

        Returns:
            Texto generado por el modelo de lenguaje.

        Raises:
            ValueError: Si ``prompt`` es vacío.
            LLMProviderError: Si falla la comunicación o la respuesta es inválida.
        """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Devuelve el nombre identificador del proveedor LLM.

        Returns:
            Nombre legible del proveedor (por ejemplo ``'MockLLM'``,
            ``'Gemini'``, ``'OpenAI'`` o ``'LocalLLM'``).
        """
