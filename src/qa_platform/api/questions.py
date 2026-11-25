"""Blueprint de la API REST JSON para el recurso de preguntas."""

import functools
from collections.abc import Callable
from typing import Any, cast

from flask import Blueprint, g, request

from qa_platform.extensions import db
from qa_platform.models.answer import Answer
from qa_platform.models.category import Category
from qa_platform.models.question import Question
from qa_platform.models.tag import Tag
from qa_platform.services.question_service import (
    generate_unique_slug,
    resolve_or_create_tags,
    validate_question_fields,
)

api_questions_bp = Blueprint("api_questions", __name__, url_prefix="/api")


def _api_login_required[F: Callable[..., Any]](view: F) -> F:
    """Exige sesión autenticada para endpoints JSON devolviendo HTTP 401."""

    @functools.wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if getattr(g, "current_user", None) is None:
            return {"error": "Autenticación requerida."}, 401
        return view(*args, **kwargs)

    return cast(F, wrapped)


def _serialize_question(
    question: Question, *, include_answers: bool = False
) -> dict[str, Any]:
    """Serializa una instancia de ``Question`` a un diccionario JSON."""
    payload: dict[str, Any] = {
        "id": question.id,
        "title": question.title,
        "slug": question.slug,
        "body": question.body,
        "created_at": question.created_at.isoformat(),
        "updated_at": question.updated_at.isoformat(),
        "score": question.calculate_score(),
        "answers_count": question.answers.count(),
        "author": (
            {
                "id": question.author.id,
                "username": getattr(question.author, "username", None),
                "display_name": question.author.display_name,
            }
            if question.author is not None
            else None
        ),
        "category": (
            {
                "id": question.category.id,
                "name": question.category.name,
                "slug": question.category.slug,
            }
            if question.category is not None
            else None
        ),
        "tags": [
            {"id": tag.id, "name": tag.name, "slug": tag.slug}
            for tag in question.tags.order_by(Tag.name.asc()).all()
        ],
    }

    if include_answers:
        answers = db.session.scalars(
            db.select(Answer)
            .filter_by(question_id=question.id)
            .order_by(Answer.is_accepted.desc(), Answer.created_at.asc())
        ).all()
        payload["answers"] = [
            {
                "id": answer.id,
                "body": answer.body,
                "is_accepted": answer.is_accepted,
                "created_at": answer.created_at.isoformat(),
                "score": answer.calculate_score(),
                "author": (
                    {
                        "id": answer.author.id,
                        "display_name": answer.author.display_name,
                        "is_agent": answer.author.is_agent(),
                    }
                    if answer.author is not None
                    else None
                ),
            }
            for answer in answers
        ]

    return payload


@api_questions_bp.get("/questions")
def list_questions() -> Any:
    """Lista las preguntas registradas ordenadas de más reciente a más antigua.

    Admite filtros opcionales por ``category_id``, ``tag`` (slug) y ``q``
    (búsqueda parcial en título).

    Returns:
        Diccionario JSON con ``items`` y ``total`` junto al código HTTP 200.
    """
    stmt = db.select(Question).order_by(Question.created_at.desc())

    category_id_raw = request.args.get("category_id")
    if category_id_raw is not None and category_id_raw.strip() != "":
        try:
            category_id = int(category_id_raw)
        except ValueError:
            return {"error": "El parámetro category_id debe ser numérico."}, 400
        stmt = stmt.filter(Question.category_id == category_id)

    tag_slug = (request.args.get("tag") or "").strip().lower()
    if tag_slug:
        stmt = stmt.join(Question.tags).filter(Tag.slug == tag_slug)

    search_term = (request.args.get("q") or "").strip()
    if search_term:
        stmt = stmt.filter(Question.title.ilike(f"%{search_term}%"))

    questions = db.session.scalars(stmt).all()
    items = [_serialize_question(question) for question in questions]
    return {"items": items, "total": len(items)}, 200


@api_questions_bp.get("/questions/<int:question_id>")
def get_question(question_id: int) -> Any:
    """Obtiene el detalle completo de una pregunta por su identificador.

    Args:
        question_id: Clave primaria de la pregunta solicitada.

    Returns:
        JSON de la pregunta con sus respuestas (HTTP 200) o HTTP 404.
    """
    question = db.session.get(Question, question_id)
    if question is None:
        return {"error": "Pregunta no encontrada."}, 404
    return _serialize_question(question, include_answers=True), 200


@api_questions_bp.post("/questions")
@_api_login_required
def create_question() -> Any:
    """Crea una nueva pregunta a partir de un payload JSON autenticado.

    Returns:
        JSON de la pregunta creada con HTTP 201, o HTTP 400 ante errores de
        formato o validación.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"error": "El cuerpo debe ser un objeto JSON válido."}, 400

    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "").strip()
    category_id_raw = payload.get("category_id")

    errors, category_id = validate_question_fields(
        title=title,
        body=body,
        category_id_raw=category_id_raw,
    )

    raw_tags = payload.get("tags", [])
    if raw_tags is not None and not isinstance(raw_tags, (str, list)):
        errors["tags"] = "El campo tags debe ser una lista o cadena separada por comas."

    if errors:
        return {"errors": errors}, 400

    question = Question(
        title=title,
        slug=generate_unique_slug(title),
        body=body,
        user_id=g.current_user.id,
        category_id=category_id,
    )
    if raw_tags:
        for tag in resolve_or_create_tags(raw_tags):
            question.tags.append(tag)

    db.session.add(question)
    db.session.commit()
    return _serialize_question(question), 201


@api_questions_bp.patch("/questions/<int:question_id>")
@_api_login_required
def update_question(question_id: int) -> Any:
    """Actualiza parcialmente una pregunta existente si pertenece al usuario.

    Args:
        question_id: Clave primaria de la pregunta a modificar.

    Returns:
        JSON actualizado (HTTP 200), o HTTP 400/403/404 según corresponda.
    """
    question = db.session.get(Question, question_id)
    if question is None:
        return {"error": "Pregunta no encontrada."}, 404

    if question.user_id != g.current_user.id:
        return {"error": "No tenés permiso para modificar esta pregunta."}, 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"error": "El cuerpo debe ser un objeto JSON válido."}, 400

    has_title = "title" in payload
    has_body = "body" in payload
    has_category = "category_id" in payload
    has_tags = "tags" in payload

    title = str(payload.get("title") or "").strip() if has_title else None
    body = str(payload.get("body") or "").strip() if has_body else None
    category_id_raw = payload.get("category_id") if has_category else None

    errors, category_id = validate_question_fields(
        title=title,
        body=body,
        category_id_raw=category_id_raw,
        check_title=has_title,
        check_body=has_body,
        check_category=has_category,
    )

    raw_tags = payload.get("tags") if has_tags else None
    if has_tags and raw_tags is not None and not isinstance(raw_tags, (str, list)):
        errors["tags"] = "El campo tags debe ser una lista o cadena separada por comas."

    if errors:
        return {"errors": errors}, 400

    if has_title and title is not None:
        question.title = title
    if has_body and body is not None:
        question.body = body
    if has_category and category_id is not None:
        question.category = db.session.get(Category, category_id)
    if has_tags:
        for existing_tag in list(question.tags):
            question.tags.remove(existing_tag)
        if raw_tags:
            for tag in resolve_or_create_tags(raw_tags):
                question.tags.append(tag)

    db.session.commit()
    return _serialize_question(question), 200


@api_questions_bp.delete("/questions/<int:question_id>")
@_api_login_required
def delete_question(question_id: int) -> Any:
    """Elimina una pregunta existente si pertenece al usuario autenticado.

    Args:
        question_id: Clave primaria de la pregunta a eliminar.

    Returns:
        Confirmación JSON con HTTP 200, o HTTP 403/404 según corresponda.
    """
    question = db.session.get(Question, question_id)
    if question is None:
        return {"error": "Pregunta no encontrada."}, 404

    if question.user_id != g.current_user.id:
        return {"error": "No tenés permiso para eliminar esta pregunta."}, 403

    db.session.delete(question)
    db.session.commit()
    return {"message": "Pregunta eliminada.", "id": question_id}, 200
