"""Blueprint web de preguntas: listado, detalle y creacion de preguntas."""

import re
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
from qa_platform.models.category import Category
from qa_platform.models.question import Question
from qa_platform.models.tag import Tag
from qa_platform.services.ai_service import AIService
from qa_platform.web.answers import get_ordered_answers
from qa_platform.web.auth import login_required

questions_bp = Blueprint("questions", __name__, url_prefix="/questions")


def _slugify(text: str) -> str:
    """Convierte un texto en un slug URL-friendly.

    Convierte a minusculas, elimina caracteres no alfanumericos y reemplaza
    espacios consecutivos por guiones.

    Args:
        text: Texto de entrada a convertir.

    Returns:
        Cadena slug valida para usar en URLs.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:170]


def _resolve_or_create_tags(raw_tags: str) -> list[Tag]:
    """Resuelve la lista de etiquetas desde una cadena separada por comas.

    Para cada nombre de etiqueta, busca en la BD una existente con ese slug;
    si no existe, la crea. Esto evita duplicados silenciosos.

    Args:
        raw_tags: Cadena de etiquetas separadas por comas (ej: "python, flask").

    Returns:
        Lista de instancias de ``Tag`` listas para asociar a una pregunta.
    """
    tags: list[Tag] = []
    for name in raw_tags.split(","):
        name = name.strip()
        if not name:
            continue
        slug = _slugify(name)[:35]
        tag = db.session.scalar(db.select(Tag).filter_by(slug=slug))
        if tag is None:
            tag = Tag(name=name[:30], slug=slug)
            db.session.add(tag)
        tags.append(tag)
    return tags


@questions_bp.get("/")
def list_questions() -> Any:
    """Muestra el listado de preguntas ordenadas por fecha de creacion desc.

    Returns:
        Respuesta HTTP con la plantilla ``questions/list.html`` renderizada.
    """
    questions = (
        db.session.execute(db.select(Question).order_by(Question.created_at.desc()))
        .scalars()
        .all()
    )
    return render_template("questions/list.html", questions=questions)


@questions_bp.get("/<slug>")
def question_detail(slug: str) -> Any:
    """Muestra el detalle completo de una pregunta identificada por su slug.

    Args:
        slug: Slug unico de la pregunta a mostrar.

    Returns:
        Respuesta HTTP con la plantilla ``questions/detail.html`` renderizada,
        o 404 si no existe ninguna pregunta con ese slug.
    """
    question = db.session.scalar(db.select(Question).filter_by(slug=slug))
    if question is None:
        return render_template("404.html"), 404
    return render_template(
        "questions/detail.html",
        question=question,
        answers=get_ordered_answers(question),
        answer_errors={},
        answer_body="",
    )


@questions_bp.route("/new", methods=("GET", "POST"))
@login_required
def create_question() -> Any:
    """Muestra y procesa el formulario de creacion de una nueva pregunta.

    GET: Renderiza el formulario con el desplegable de categorias cargado.
    POST: Valida los campos, crea la pregunta con la categoria y etiquetas
    seleccionadas, y redirige al detalle con un mensaje flash de exito.

    Returns:
        Respuesta HTTP: renderizado del formulario (GET/error) o redireccion
        al detalle de la pregunta creada (POST exitoso).
    """
    categories = (
        db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()
    )

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        raw_tags = request.form.get("tags", "").strip()
        category_id_raw = request.form.get("category_id", "")

        errors: dict[str, str] = {}

        if len(title) < 5:
            errors["title"] = "El titulo debe tener al menos 5 caracteres."
        if len(title) > 150:
            errors["title"] = "El titulo no puede superar los 150 caracteres."
        if not body:
            errors["body"] = "El contenido de la pregunta es obligatorio."
        if not category_id_raw:
            errors["category_id"] = "Debes seleccionar una categoria."

        category_id: int | None = None
        if category_id_raw:
            try:
                category_id = int(category_id_raw)
            except ValueError:
                errors["category_id"] = "Categoria invalida."

        if not errors:
            # Generar slug base desde el titulo y garantizar unicidad.
            base_slug = _slugify(title)
            slug = base_slug
            suffix = 1
            while (
                db.session.scalar(db.select(Question).filter_by(slug=slug)) is not None
            ):
                slug = f"{base_slug}-{suffix}"
                suffix += 1

            tags = _resolve_or_create_tags(raw_tags)
            question = Question(
                title=title,
                slug=slug,
                body=body,
                user_id=g.current_user.id,
                category_id=category_id,
            )
            # Agregar tags via lista directa (no dynamic) para la creacion inicial.
            for tag in tags:
                question.tags.append(tag)

            db.session.add(question)
            db.session.commit()
            flash("Pregunta publicada exitosamente.", "success")
            return redirect(url_for("questions.question_detail", slug=question.slug))

        form_data = {
            "title": title,
            "body": body,
            "tags": raw_tags,
            "category_id": category_id_raw,
        }
        return (
            render_template(
                "questions/create.html",
                categories=categories,
                form_data=form_data,
                errors=errors,
            ),
            400,
        )

    return render_template(
        "questions/create.html",
        categories=categories,
        form_data={},
        errors={},
    )


@questions_bp.route("/<slug>/edit", methods=("GET", "POST"))
@login_required
def edit_question(slug: str) -> Any:
    """Muestra y procesa el formulario de edicion de una pregunta existente.

    Solo el autor original puede editar su pregunta.

    Args:
        slug: Slug unico de la pregunta a editar.

    Returns:
        Respuesta HTTP: renderizado del formulario (GET/error), redireccion
        al detalle (POST exitoso), o 404/403 segun corresponda.
    """
    question = db.session.scalar(db.select(Question).filter_by(slug=slug))
    if question is None:
        return render_template("404.html"), 404

    # Solo el autor puede editar su propia pregunta.
    if question.user_id != g.current_user.id:
        flash("No tenes permiso para editar esta pregunta.", "danger")
        return redirect(url_for("questions.question_detail", slug=slug))

    categories = (
        db.session.execute(db.select(Category).order_by(Category.name)).scalars().all()
    )

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        raw_tags = request.form.get("tags", "").strip()
        category_id_raw = request.form.get("category_id", "")

        errors: dict[str, str] = {}

        if len(title) < 5:
            errors["title"] = "El titulo debe tener al menos 5 caracteres."
        if len(title) > 150:
            errors["title"] = "El titulo no puede superar los 150 caracteres."
        if not body:
            errors["body"] = "El contenido de la pregunta es obligatorio."
        if not category_id_raw:
            errors["category_id"] = "Debes seleccionar una categoria."

        category_id: int | None = None
        if category_id_raw:
            try:
                category_id = int(category_id_raw)
            except ValueError:
                errors["category_id"] = "Categoria invalida."

        if not errors:
            question.title = title
            question.body = body
            question.category_id = category_id

            # Reemplazar coleccion de tags en su totalidad.
            new_tags = _resolve_or_create_tags(raw_tags)
            existing = list(question.tags)
            for t in existing:
                question.tags.remove(t)
            for t in new_tags:
                question.tags.append(t)

            db.session.commit()
            flash("Pregunta actualizada exitosamente.", "success")
            return redirect(url_for("questions.question_detail", slug=question.slug))

        current_tag_names = ", ".join(t.name for t in question.tags)
        form_data = {
            "title": title,
            "body": body,
            "tags": raw_tags,
            "category_id": category_id_raw,
        }
        return (
            render_template(
                "questions/edit.html",
                question=question,
                categories=categories,
                form_data=form_data,
                errors=errors,
            ),
            400,
        )

    current_tag_names = ", ".join(t.name for t in question.tags)
    form_data = {
        "title": question.title,
        "body": question.body,
        "tags": current_tag_names,
        "category_id": question.category_id,
    }
    return render_template(
        "questions/edit.html",
        question=question,
        categories=categories,
        form_data=form_data,
        errors={},
    )


@questions_bp.post("/<slug>/ai-answer")
@login_required
def generate_ai_answer(slug: str) -> Any:
    """Genera y guarda una respuesta automática del Agente IA para una pregunta.

    Args:
        slug: Slug único de la pregunta a responder.

    Returns:
        Redirección al detalle de la pregunta tras persistir la respuesta,
        o HTTP 404 si la pregunta no existe.
    """
    question = db.session.scalar(db.select(Question).filter_by(slug=slug))
    if question is None:
        return render_template("404.html"), 404

    AIService.generate_answer_for_question(question)
    flash("¡Respuesta de IA generada con éxito!", "success")
    return redirect(url_for("questions.question_detail", slug=question.slug))
