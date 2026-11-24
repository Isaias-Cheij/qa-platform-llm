"""Paquete de modelos de dominio de qa-platform.

Importar los modelos aquí garantiza que SQLAlchemy los registre en su
metadata antes de que se ejecute ``db.create_all()`` o Alembic detecte
cambios de esquema.
"""

from qa_platform.models.author import Admin, AIAgent, Author, GeneralUser, User

__all__ = ["Admin", "AIAgent", "Author", "GeneralUser", "User"]
