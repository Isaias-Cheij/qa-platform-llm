"""Blueprint web de respuestas: publicación y marcación de solución aceptada."""

from typing import Any

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from qa_platform.extensions import db
from qa_platform.models.answer import Answer
from qa_platform.models.question import Question
from qa_platform.web.auth import login_required

answers_bp = Blueprint("answers", __name__)


def get_ordered_answers(question: Question) -> list[Answer]:
    """Obtiene las respuestas de una pregunta ordenadas por aceptación y fecha.

    Prioriza primero la solución aceptada (si existe) y luego ordena el resto
    cronológicamente de la más antigua a la más reciente.

    Args:
        question: Instancia de ``Question`` cuyas respuestas se desean listar.

    Returns:
        Lista ordenada de instancias ``Answer``.
    """
    return list(
        db.session.scalars(
            db.select(Answer)
            .filter_by(question_id=question.id)
            .order_by(Answer.is_accepted.desc(), Answer.created_at.asc())
        ).all()
    )


@answers_bp.post("/questions/<slug>/answers")
@login_required
def create_answer(slug: str) -> Any:
    """Procesa el formulario HTML para publicar una respuesta en una pregunta.

    Args:
        slug: Slug único de la pregunta a responder.

    Returns:
        Redirección al detalle de la pregunta si se publica con éxito,
        HTTP 400 con errores de validación si el cuerpo está vacío, o
        HTTP 404 si la pregunta no existe.
    """
    question = db.session.scalar(db.select(Question).filter_by(slug=slug))
    if question is None:
        return render_template("404.html"), 404

    body = request.form.get("body", "").strip()
    if not body:
        flash("El contenido de la respuesta es obligatorio.", "danger")
        return (
            render_template(
                "questions/detail.html",
                question=question,
                answers=get_ordered_answers(question),
                answer_errors={"body": "El contenido de la respuesta es obligatorio."},
                answer_body=body,
            ),
            400,
        )

    answer = Answer(body=body, question=question, author=g.current_user)
    db.session.add(answer)
    db.session.commit()
    flash("Respuesta publicada exitosamente.", "success")
    return redirect(url_for("questions.question_detail", slug=question.slug))


@answers_bp.post("/answers/<int:answer_id>/accept")
@login_required
def accept_answer(answer_id: int) -> Any:
    """Marca una respuesta existente como solución aceptada de su pregunta.

    Delega la verificación de permisos y unicidad en ``Answer.mark_accepted()``
    para garantizar que solo el autor humano de la pregunta pueda aceptarla.

    Args:
        answer_id: Identificador de la respuesta a marcar como aceptada.

    Returns:
        Redirección al detalle de la pregunta tras persistir, HTTP 403 si el
        usuario autenticado no es el autor de la pregunta, o HTTP 404 si no
        existe la respuesta.
    """
    answer = db.session.get(Answer, answer_id)
    if answer is None:
        return render_template("404.html"), 404

    try:
        answer.mark_accepted(g.current_user)
    except PermissionError:
        flash(
            "Solo el autor de la pregunta puede marcar una respuesta como aceptada.",
            "danger",
        )
        return (
            render_template(
                "questions/detail.html",
                question=answer.question,
                answers=get_ordered_answers(answer.question),
                answer_errors={},
                answer_body="",
            ),
            403,
        )

    db.session.commit()
    flash("Respuesta marcada como solución aceptada.", "success")
    return redirect(url_for("questions.question_detail", slug=answer.question.slug))
