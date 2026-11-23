"""Paquete de modelos de dominio de qa-platform.

Importar los modelos aqui garantiza que SQLAlchemy los registre en su
metadata antes de que se ejecute ``db.create_all()``.
"""

from qa_platform.models.user import User

__all__ = ["User"]
