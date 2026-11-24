"""Modelo de dominio Tag y tabla intermedia question_tags para qa-platform.

Define la entidad de etiqueta y la tabla de asociación many-to-many con
preguntas. Las etiquetas permiten categorización transversal de preguntas
más allá de la jerarquía de categorías.
"""

from qa_platform.extensions import db

# Tabla de asociación para la relación many-to-many entre Question y Tag.
# Se define como objeto Table (no como Model) porque no tiene atributos
# propios: es solo una tabla puente administrada por SQLAlchemy.
question_tags = db.Table(
    "question_tags",
    db.Column(
        "question_id",
        db.Integer,
        db.ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "tag_id",
        db.Integer,
        db.ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Tag(db.Model):
    """Representa una etiqueta transversal para clasificar preguntas.

    Attributes:
        id: Clave primaria autoincrementada.
        name: Nombre único de la etiqueta, indexado para búsquedas.
        slug: Versión URL-friendly del nombre, única e indexada.
        questions: Relación many-to-many con las preguntas etiquetadas.
    """

    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(30),
        nullable=False,
        unique=True,
        index=True,
    )
    slug = db.Column(
        db.String(35),
        nullable=False,
        unique=True,
        index=True,
    )

    questions = db.relationship(
        "Question",
        secondary=question_tags,
        back_populates="tags",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        """Devuelve una representación legible de la etiqueta para depuración.

        Returns:
            Cadena con el id y nombre de la etiqueta.
        """
        return f"<Tag id={self.id} name={self.name!r}>"
