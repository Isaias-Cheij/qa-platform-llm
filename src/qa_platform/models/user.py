"""Módulo de compatibilidad para re-exportar modelos de usuario.

Mantiene las importaciones existentes desde ``qa_platform.models.user``
apuntando a la jerarquía polimórfica definida en ``qa_platform.models.author``.
"""

from qa_platform.models.author import Admin, GeneralUser, User

__all__ = ["Admin", "GeneralUser", "User"]
