"""Estrategia simulada (Mock) para pruebas unitarias y desarrollo offline."""

from qa_platform.strategies.base import LLMStrategy


class MockLLMStrategy(LLMStrategy):
    """Implementación determinista de ``LLMStrategy`` sin llamadas de red.

    Permite ejecutar pruebas automatizadas rápidas y desarrollar localmente
    sin requerir credenciales ni conexión a internet.
    """

    def __init__(
        self,
        *,
        canned_response: str | None = None,
        provider_name: str = "MockLLM",
    ) -> None:
        """Inicializa la estrategia Mock con respuesta fija opcional.

        Args:
            canned_response: Texto fijo a devolver si se desea controlar la
                salida exacta en un test; si es ``None``, genera una respuesta
                determinista que refleja el prompt y contexto recibidos.
            provider_name: Nombre de proveedor reportado por la estrategia.
        """
        self._canned_response = canned_response
        self._provider_name = provider_name

    def generate_response(self, prompt: str, context: str = "") -> str:
        """Genera una respuesta determinista sin consultar servicios externos.

        Args:
            prompt: Consigna o pregunta principal.
            context: Contexto adicional opcional.

        Returns:
            Respuesta fija configurada o texto simulado determinista.

        Raises:
            ValueError: Si ``prompt`` no es una cadena no vacía.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("El prompt debe ser una cadena no vacía.")

        clean_prompt = prompt.strip()
        if self._canned_response is not None:
            return self._canned_response

        clean_context = context.strip() if isinstance(context, str) else ""
        response = f"[{self._provider_name}] Respuesta simulada para: {clean_prompt}"
        if clean_context:
            response = f"{response} | Contexto: {clean_context}"
        return response

    def get_provider_name(self) -> str:
        """Devuelve el nombre identificador de esta estrategia simulada."""
        return self._provider_name
