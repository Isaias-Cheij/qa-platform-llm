"""Pruebas unitarias y de integración para los modelos Answer y Vote.

Verifica la autoría polimórfica de respuestas (usuarios humanos y agentes IA),
las reglas de autorización y unicidad del método ``mark_accepted()``, el
registro de votos (+1 / -1), la restricción de un voto por usuario y
publicación, y las restricciones de integridad en base de datos.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from qa_platform.models import (
    AIAgent,
    Answer,
    Category,
    GeneralUser,
    Question,
    Vote,
)
from qa_platform.models.vote import DOWNVOTE, UPVOTE

# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------


@pytest.fixture()
def question_author(db):
    """Crea y persiste un GeneralUser autor de la pregunta de prueba."""
    user = GeneralUser(
        username="q_author",
        email="q_author@example.com",
        display_name="Autor Pregunta",
        password="Password123",
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def other_user(db):
    """Crea y persiste un segundo GeneralUser para validar permisos y votos."""
    user = GeneralUser(
        username="other_user",
        email="other_user@example.com",
        display_name="Otro Usuario",
        password="Password123",
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def ai_agent(db):
    """Crea y persiste un AIAgent de prueba."""
    agent = AIAgent(
        bot_identifier="qa-bot-helper",
        display_name="Asistente IA",
        version="1.0.0",
    )
    db.session.add(agent)
    db.session.commit()
    return agent


@pytest.fixture()
def category(db):
    """Crea y persiste una Category de prueba."""
    cat = Category(name="Ingeniería", slug="ingenieria", description="IS I")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture()
def question(db, question_author, category):
    """Crea y persiste una Question asociada a ``question_author``."""
    q = Question(
        title="¿Cómo aplicar el patrón Strategy en Python?",
        slug="como-aplicar-patron-strategy-python",
        body="Necesito desacoplar distintos proveedores LLM en Flask.",
        user_id=question_author.id,
        category_id=category.id,
    )
    db.session.add(q)
    db.session.commit()
    return q


# ---------------------------------------------------------------------------
# Tests de Answer y regla de respuesta aceptada
# ---------------------------------------------------------------------------


class TestAnswerModel:
    """Pruebas para el modelo Answer, autoría polimórfica y marcación aceptada."""

    def test_create_answer_by_human_user(self, db, question, other_user):
        """Una respuesta humana se persiste con is_accepted=False por defecto."""
        answer = Answer(
            body="Podés definir una interfaz abstracta con ABC y subclases.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        assert answer.id is not None
        assert answer.is_accepted is False
        assert answer.created_at is not None
        assert answer.updated_at is not None
        assert answer.get_author() is other_user
        assert answer.get_author().is_agent() is False
        assert answer in question.answers.all()
        assert answer in other_user.answers.all()
        assert f"question_id={question.id}" in repr(answer)

    def test_create_answer_by_ai_agent_polymorphism(
        self, db, question, other_user, ai_agent
    ):
        """Un AIAgent y un usuario humano pueden responder la misma pregunta."""
        human_answer = Answer(
            body="Respuesta elaborada por un compañero.",
            question=question,
            author=other_user,
        )
        bot_answer = Answer(
            body="Respuesta automática generada por IA.",
            question=question,
            author=ai_agent,
        )
        db.session.add_all([human_answer, bot_answer])
        db.session.commit()

        answers = question.answers.order_by(Answer.id).all()
        assert len(answers) == 2
        assert [a.get_author().is_agent() for a in answers] == [False, True]
        assert answers[1].get_author().get_identifier() == "qa-bot-helper"

    @pytest.mark.parametrize("invalid_body", ["", "   ", "\n\t"])
    def test_empty_body_raises_value_error(self, question, other_user, invalid_body):
        """El cuerpo de una respuesta no puede estar vacío."""
        with pytest.raises(ValueError):
            Answer(body=invalid_body, question=question, author=other_user)

    def test_mark_accepted_by_question_author(
        self, db, question, question_author, other_user
    ):
        """El autor de la pregunta puede marcar una respuesta como aceptada."""
        answer = Answer(
            body="Solución clara y verificada.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        answer.mark_accepted(question_author)
        db.session.commit()
        db.session.expire_all()

        reloaded = db.session.get(Answer, answer.id)
        assert reloaded is not None
        assert reloaded.is_accepted is True

    def test_mark_accepted_by_non_author_raises_permission_error(
        self, db, question, other_user, ai_agent
    ):
        """Ni otro usuario ni un agente IA pueden marcar una respuesta aceptada."""
        answer = Answer(
            body="Respuesta candidata.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        with pytest.raises(PermissionError):
            answer.mark_accepted(other_user)
        assert answer.is_accepted is False

        with pytest.raises(PermissionError):
            answer.mark_accepted(ai_agent)
        assert answer.is_accepted is False

    def test_mark_accepted_unmarks_previous_accepted_answer(
        self, db, question, question_author, other_user
    ):
        """Al aceptar otra respuesta en la misma pregunta se desmarca la previa."""
        first = Answer(
            body="Primera respuesta.",
            question=question,
            author=other_user,
        )
        second = Answer(
            body="Segunda respuesta más completa.",
            question=question,
            author=other_user,
        )
        db.session.add_all([first, second])
        db.session.commit()

        first.mark_accepted(question_author)
        db.session.commit()
        assert first.is_accepted is True
        assert second.is_accepted is False

        second.mark_accepted(question_author)
        db.session.commit()
        db.session.expire_all()

        reloaded_first = db.session.get(Answer, first.id)
        reloaded_second = db.session.get(Answer, second.id)
        assert reloaded_first.is_accepted is False
        assert reloaded_second.is_accepted is True

    def test_mark_accepted_allows_accepting_ai_agent_answer(
        self, db, question, question_author, ai_agent
    ):
        """El autor de la pregunta puede aceptar una respuesta generada por IA."""
        bot_answer = Answer(
            body="Explicación automática con ejemplo.",
            question=question,
            author=ai_agent,
        )
        db.session.add(bot_answer)
        db.session.commit()

        bot_answer.mark_accepted(question_author)
        db.session.commit()

        assert bot_answer.is_accepted is True


# ---------------------------------------------------------------------------
# Tests de Vote y cálculo de puntaje
# ---------------------------------------------------------------------------


class TestVoteModel:
    """Pruebas para el modelo Vote, unicidad por publicación y validaciones."""

    def test_upvote_and_downvote_on_question_and_score(
        self, db, question, question_author, other_user
    ):
        """Registra votos +1/-1 en Question y calcula la puntuación neta."""
        assert question.calculate_score() == 0

        v_up = Vote(value=UPVOTE, user=other_user, question=question)
        v_down = Vote(value=DOWNVOTE, user=question_author, question=question)
        db.session.add_all([v_up, v_down])
        db.session.commit()

        assert v_up.get_value() == 1
        assert v_down.get_value() == -1
        assert "+1" in repr(v_up)
        assert question.calculate_score() == 0

    def test_upvote_and_downvote_on_answer_and_score(
        self, db, question, question_author, other_user
    ):
        """Registra votos +1/-1 en Answer y calcula la puntuación neta."""
        answer = Answer(
            body="Respuesta evaluable por la comunidad.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        assert answer.calculate_score() == 0

        v1 = Vote(value=UPVOTE, user=question_author, answer=answer)
        v2 = Vote(value=UPVOTE, user=other_user, answer=answer)
        db.session.add_all([v1, v2])
        db.session.commit()

        assert answer.calculate_score() == 2

    def test_unique_vote_per_user_per_question(self, db, question, other_user):
        """Un usuario no puede votar dos veces la misma pregunta."""
        db.session.add(Vote(value=UPVOTE, user=other_user, question=question))
        db.session.commit()

        db.session.add(Vote(value=DOWNVOTE, user=other_user, question=question))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_unique_vote_per_user_per_answer(
        self, db, question, question_author, other_user
    ):
        """Un usuario no puede votar dos veces la misma respuesta."""
        answer = Answer(
            body="Respuesta única para votar.",
            question=question,
            author=question_author,
        )
        db.session.add(answer)
        db.session.commit()

        db.session.add(Vote(value=UPVOTE, user=other_user, answer=answer))
        db.session.commit()

        db.session.add(Vote(value=UPVOTE, user=other_user, answer=answer))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_same_user_can_vote_different_targets(
        self, db, question, question_author, other_user
    ):
        """Un usuario puede votar una pregunta y varias respuestas distintas."""
        a1 = Answer(body="Respuesta A.", question=question, author=question_author)
        a2 = Answer(body="Respuesta B.", question=question, author=question_author)
        db.session.add_all([a1, a2])
        db.session.commit()

        votes = [
            Vote(value=UPVOTE, user=other_user, question=question),
            Vote(value=UPVOTE, user=other_user, answer=a1),
            Vote(value=DOWNVOTE, user=other_user, answer=a2),
        ]
        db.session.add_all(votes)
        db.session.commit()

        assert other_user.votes.count() == 3
        assert question.calculate_score() == 1
        assert a1.calculate_score() == 1
        assert a2.calculate_score() == -1

    @pytest.mark.parametrize("invalid_value", [0, 2, -2, True, False])
    def test_invalid_vote_value_raises_value_error(
        self, question, other_user, invalid_value
    ):
        """Solo se aceptan valores enteros 1 y -1 (excluyendo booleanos)."""
        with pytest.raises(ValueError):
            Vote(value=invalid_value, user=other_user, question=question)

    def test_vote_requires_exactly_one_target(self, db, question, other_user):
        """Un voto debe apuntar a una pregunta o a una respuesta, nunca a ambas."""
        answer = Answer(
            body="Respuesta destino.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        with pytest.raises(ValueError):
            Vote(value=UPVOTE, user=other_user)

        with pytest.raises(ValueError):
            Vote(value=UPVOTE, user=other_user, question=question, answer=answer)

    def test_ai_agent_cannot_vote(self, question, ai_agent):
        """Un agente de IA no tiene permiso para emitir votos."""
        with pytest.raises(PermissionError):
            Vote(value=UPVOTE, user=ai_agent, question=question)

    def test_db_check_constraints_enforced(self, db, question, other_user):
        """Las restricciones CHECK de BD rechazan valores o destinos inválidos."""
        answer = Answer(
            body="Respuesta para validar CHECK.",
            question=question,
            author=other_user,
        )
        db.session.add(answer)
        db.session.commit()

        with pytest.raises(IntegrityError):
            db.session.execute(
                text(
                    "INSERT INTO votes (value, user_id, question_id, answer_id, "
                    "created_at) VALUES (5, :uid, :qid, NULL, CURRENT_TIMESTAMP)"
                ),
                {"uid": other_user.id, "qid": question.id},
            )
            db.session.commit()
        db.session.rollback()

        with pytest.raises(IntegrityError):
            db.session.execute(
                text(
                    "INSERT INTO votes (value, user_id, question_id, answer_id, "
                    "created_at) VALUES (1, :uid, :qid, :aid, CURRENT_TIMESTAMP)"
                ),
                {"uid": other_user.id, "qid": question.id, "aid": answer.id},
            )
            db.session.commit()
        db.session.rollback()
