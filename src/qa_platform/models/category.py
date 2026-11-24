"""Modelo de dominio Category para qa-platform.

Define la entidad de categoría temática a la que pertenece una pregunta.
Una categoría agrupa preguntas bajo un mismo dominio de conocimiento.
"""

from datetime import UTC, datetime

from qa_platform.extensions import db


class Category(db.Model):
    """Representa una categoría temática de preguntas en la plataforma.

    Attributes:
        id: Clave primaria autoincrementada.
        name: Nombre único de la categoría, indexado para búsquedas.
        slug: Versión URL-friendly del nombre, única e indexada.
        description: Descripción opcional de la categoría.
        created_at: Marca de tiempo UTC de creación del registro.
        questions: Relación one-to-many con las preguntas de esta categoría.
    """

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    slug = db.Column(
        db.String(60),
        nullable=False,
        unique=True,
        index=True,
    )
    description = db.Column(db.Text, nullable=True)
    # Se almacena siempre en UTC para consistencia entre entornos.
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    questions = db.relationship(
        "Question",
        back_populates="category",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        """Devuelve una representación legible de la categoría para depuración.

        Returns:
            Cadena con el id y nombre de la categoría.
        """
        return f"<Category id={self.id} name={self.name!r}>"
