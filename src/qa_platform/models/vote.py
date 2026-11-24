"""Modelo de dominio Vote para qa-platform.

Define el registro de votos positivos (+1) o negativos (-1) emitidos por
usuarios humanos sobre preguntas o respuestas, garantizando mediante
restricciones de aplicación y base de datos un único voto por usuario
en cada publicación.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from qa_platform.extensions import db

UPVOTE = 1
DOWNVOTE = -1
VALID_VOTE_VALUES = (DOWNVOTE, UPVOTE)


class Vote(db.Model):
    """Representa un voto (+1 o -1) emitido por un usuario sobre una publicación.

    Un voto apunta exclusivamente a una pregunta (``question_id``) o a una
    respuesta (``answer_id``), nunca a ambas ni a ninguna.

    Attributes:
        id: Clave primaria autoincrementada.
        value: Valor entero del voto (``1`` positivo o ``-1`` negativo).
        user_id: FK hacia el autor votante (tabla ``authors``).
        question_id: FK opcional hacia la pregunta votada.
        answer_id: FK opcional hacia la respuesta votada.
        created_at: Marca de tiempo UTC de emisión del voto.
        user: Relación many-to-one con el usuario votante.
        question: Relación many-to-one con la pregunta votada.
        answer: Relación many-to-one con la respuesta votada.
    """

    __tablename__ = "votes"
    __table_args__ = (
        db.CheckConstraint("value IN (-1, 1)", name="ck_votes_valid_value"),
        # Garantiza en BD que el voto pertenezca a una pregunta O a una respuesta.
        db.CheckConstraint(
            "(question_id IS NOT NULL AND answer_id IS NULL) "
            "OR (question_id IS NULL AND answer_id IS NOT NULL)",
            name="ck_votes_single_target",
        ),
        db.UniqueConstraint("user_id", "question_id", name="uq_votes_user_question"),
        db.UniqueConstraint("user_id", "answer_id", name="uq_votes_user_answer"),
    )

    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer, nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("authors.id"),
        nullable=False,
        index=True,
    )
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    answer_id = db.Column(
        db.Integer,
        db.ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    user = db.relationship(
        "Author",
        back_populates="votes",
        foreign_keys=[user_id],
    )
    question = db.relationship(
        "Question",
        back_populates="votes",
        foreign_keys=[question_id],
    )
    answer = db.relationship(
        "Answer",
        back_populates="votes",
        foreign_keys=[answer_id],
    )

    def __init__(self, *, value: int, **kwargs: Any) -> None:
        """Inicializa un voto validando valor, destino exclusivo y votante humano.

        Args:
            value: Valor del voto (debe ser ``1`` o ``-1``).
            **kwargs: Argumentos adicionales para SQLAlchemy (``user``/``user_id``
                y exactamente uno de ``question``/``question_id`` o
                ``answer``/``answer_id``).

        Raises:
            ValueError: Si ``value`` no es ``1`` ni ``-1`` (o es booleano), o si
                no se especifica exactamente una publicación destino.
            PermissionError: Si el votante es un agente de IA.
        """
        # bool es subclase de int en Python (True == 1), por eso se excluye.
        if isinstance(value, bool) or value not in VALID_VOTE_VALUES:
            raise ValueError("El valor del voto debe ser 1 (positivo) o -1 (negativo).")

        has_question = (
            kwargs.get("question_id") is not None or kwargs.get("question") is not None
        )
        has_answer = (
            kwargs.get("answer_id") is not None or kwargs.get("answer") is not None
        )
        if has_question == has_answer:
            raise ValueError(
                "El voto debe asociarse exclusivamente a una pregunta o a "
                "una respuesta."
            )

        voter = kwargs.get("user")
        if voter is not None and voter.is_agent():
            raise PermissionError("Solo los usuarios registrados pueden emitir votos.")

        super().__init__(value=value, **kwargs)

    def get_value(self) -> int:
        """Devuelve el valor numérico del voto (``1`` o ``-1``).

        Returns:
            Valor entero del voto.
        """
        return self.value

    def __repr__(self) -> str:
        """Devuelve una representación legible del voto para depuración.

        Returns:
            Cadena con el id, usuario votante y valor con signo.
        """
        return f"<Vote id={self.id} user_id={self.user_id} value={self.value:+d}>"
