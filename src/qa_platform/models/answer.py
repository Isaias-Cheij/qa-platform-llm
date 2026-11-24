"""Modelo de dominio Answer para qa-platform.

Define la entidad de respuesta asociada a una pregunta y a cualquier emisor
polimórfico de la jerarquía ``Author`` (usuario humano o agente de IA),
incluyendo la regla de negocio de marcación como respuesta aceptada.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from qa_platform.extensions import db

if TYPE_CHECKING:
    from qa_platform.models.author import Author


class Answer(db.Model):
    """Representa una respuesta publicada para una pregunta en la plataforma.

    Attributes:
        id: Clave primaria autoincrementada.
        body: Contenido de la respuesta.
        question_id: FK hacia la pregunta respondida (tabla ``questions``).
        author_id: FK polimórfica hacia el autor (tabla ``authors``).
        is_accepted: Indica si fue marcada como solución aceptada.
        created_at: Marca de tiempo UTC de creación.
        updated_at: Marca de tiempo UTC de última actualización.
        question: Relación many-to-one con la pregunta asociada.
        author: Relación many-to-one con el autor polimórfico.
    """

    __tablename__ = "answers"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # FK hacia la tabla única ``authors`` para admitir usuarios humanos y bots IA.
    author_id = db.Column(
        db.Integer,
        db.ForeignKey("authors.id"),
        nullable=False,
        index=True,
    )
    is_accepted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    question = db.relationship(
        "Question",
        back_populates="answers",
    )
    author = db.relationship(
        "Author",
        back_populates="answers",
        foreign_keys=[author_id],
    )
    votes = db.relationship(
        "Vote",
        back_populates="answer",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __init__(
        self,
        *,
        body: str,
        is_accepted: bool = False,
        **kwargs: Any,
    ) -> None:
        """Inicializa una respuesta validando que el cuerpo no esté vacío.

        Args:
            body: Texto de la respuesta.
            is_accepted: Estado inicial de aceptación (por defecto ``False``).
            **kwargs: Argumentos adicionales para SQLAlchemy (ej. ``question``,
                ``question_id``, ``author``, ``author_id``).

        Raises:
            ValueError: Si ``body`` no es una cadena no vacía.
        """
        if not isinstance(body, str) or not body.strip():
            raise ValueError("El cuerpo de la respuesta debe ser una cadena no vacía.")
        clean_body = body.strip()

        super().__init__(
            body=clean_body,
            is_accepted=is_accepted,
            **kwargs,
        )

    def mark_accepted(self, requester: Author) -> None:
        """Marca esta respuesta como solución aceptada de su pregunta.

        Solo el autor humano de la pregunta asociada puede ejecutar esta acción.
        Al aceptar esta respuesta, cualquier otra respuesta previamente marcada
        como aceptada en la misma pregunta queda desmarcada.

        Args:
            requester: Autor que solicita marcar la respuesta como aceptada.

        Raises:
            ValueError: Si la respuesta no está asociada a ninguna pregunta.
            PermissionError: Si ``requester`` es ``None``, es un agente de IA
                o no coincide con el autor de la pregunta.
        """
        if self.question is None:
            raise ValueError(
                "La respuesta debe estar asociada a una pregunta para aceptarla."
            )

        # Solo el autor humano de la pregunta tiene permiso para aceptar respuestas.
        if requester is None or requester.is_agent():
            raise PermissionError(
                "Solo el autor de la pregunta puede marcar una respuesta como aceptada."
            )

        if self.question.user_id is not None:
            is_owner = (
                requester.id is not None and requester.id == self.question.user_id
            )
        else:
            is_owner = requester is self.question.author

        if not is_owner:
            raise PermissionError(
                "Solo el autor de la pregunta puede marcar una respuesta como aceptada."
            )

        # Se garantiza a lo sumo una respuesta aceptada por pregunta.
        for sibling in self.question.answers:
            if sibling is not self and sibling.is_accepted:
                sibling.is_accepted = False

        self.is_accepted = True

    def get_author(self) -> Author:
        """Devuelve el autor polimórfico que publicó la respuesta.

        Returns:
            Instancia concreta de ``Author`` (usuario humano o ``AIAgent``).
        """
        return self.author

    def calculate_score(self) -> int:
        """Calcula la puntuación neta de la respuesta sumando sus votos.

        Returns:
            Suma entera de los valores (+1 / -1) de todos los votos asociados.
        """
        return sum(vote.value for vote in self.votes)

    def __repr__(self) -> str:
        """Devuelve una representación legible de la respuesta para depuración.

        Returns:
            Cadena con el id, pregunta asociada y estado de aceptación.
        """
        return (
            f"<Answer id={self.id} question_id={self.question_id} "
            f"accepted={self.is_accepted}>"
        )
