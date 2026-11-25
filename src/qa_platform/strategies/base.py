"""Contrato abstracto del patrón Strategy para proveedores de LLM."""

from abc import ABC, abstractmethod


class LLMProviderError(RuntimeError):
    """Error de dominio al comunicarse con un proveedor de LLM."""


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
