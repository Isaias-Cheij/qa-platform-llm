"""Paquete de modelos de dominio de qa-platform.

Importar los modelos aqui garantiza que SQLAlchemy los registre en su
metadata antes de que se ejecute ``db.create_all()`` o Alembic detecte
cambios de esquema.
"""

from qa_platform.models.answer import Answer
from qa_platform.models.author import Admin, AIAgent, Author, GeneralUser, User
from qa_platform.models.category import Category
from qa_platform.models.question import Question
from qa_platform.models.tag import Tag, question_tags
from qa_platform.models.vote import Vote

__all__ = [
    "Admin",
    "AIAgent",
    "Answer",
    "Author",
    "GeneralUser",
    "User",
    "Category",
    "Tag",
    "question_tags",
    "Question",
    "Vote",
]
