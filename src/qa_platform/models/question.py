"""Modelo de dominio Question para qa-platform.

Define la entidad central de pregunta publicada por un autor. Cada pregunta
pertenece a una categoría y puede tener múltiples etiquetas asociadas.
"""

from datetime import UTC, datetime

from qa_platform.extensions import db
from qa_platform.models.tag import question_tags


class Question(db.Model):
    """Representa una pregunta publicada en la plataforma.

    Attributes:
        id: Clave primaria autoincrementada.
        title: Título de la pregunta.
        slug: Versión URL-friendly del título, única e indexada.
        body: Cuerpo completo de la pregunta en texto libre.
        user_id: FK hacia el autor (tabla ``authors``).
        category_id: FK hacia la categoría temática.
        created_at: Marca de tiempo UTC de creación.
        updated_at: Marca de tiempo UTC de última modificación.
        author: Relación many-to-one con el autor de la pregunta.
        category: Relación many-to-one con la categoría temática.
        tags: Relación many-to-many con las etiquetas asignadas.
    """

    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    slug = db.Column(
        db.String(170),
        nullable=False,
        unique=True,
        index=True,
    )
    body = db.Column(db.Text, nullable=False)
    # FK hacia la tabla ``authors`` (jerarquía STI de Author).
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("authors.id"),
        nullable=False,
    )
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=False,
    )
    # Se usa lambda para garantizar evaluación diferida en cada inserción.
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # onupdate no acepta lambda directamente: se pasa la función callable.
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    author = db.relationship(
        "Author",
        back_populates="questions",
        foreign_keys=[user_id],
    )
    category = db.relationship(
        "Category",
        back_populates="questions",
    )
    tags = db.relationship(
        "Tag",
        secondary=question_tags,
        back_populates="questions",
        lazy="dynamic",
    )
    answers = db.relationship(
        "Answer",
        back_populates="question",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Devuelve una representación legible de la pregunta para depuración.

        Returns:
            Cadena con el id y slug de la pregunta.
        """
        return f"<Question id={self.id} slug={self.slug!r}>"
