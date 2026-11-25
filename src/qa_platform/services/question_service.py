"""Servicio y utilidades de dominio compartidas para preguntas, slugs y etiquetas."""

import re
from typing import Any

from qa_platform.extensions import db
from qa_platform.models.category import Category
from qa_platform.models.question import Question
from qa_platform.models.tag import Tag


def slugify(text: str) -> str:
    """Convierte un texto en un slug URL-friendly.

    Args:
        text: Texto de entrada a convertir.

    Returns:
        Cadena slug válida para usar en URLs (máximo 170 caracteres).
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:170]


def generate_unique_slug(title: str) -> str:
    """Genera un slug único a partir del título consultando la base de datos.

    Args:
        title: Título de la pregunta.

    Returns:
        Slug único no utilizado por ninguna otra pregunta existente.
    """
    base_slug = slugify(title) or "pregunta"
    slug = base_slug
    suffix = 1
    while db.session.scalar(db.select(Question).filter_by(slug=slug)) is not None:
        suffix_str = f"-{suffix}"
        slug = f"{base_slug[: 170 - len(suffix_str)]}{suffix_str}"
        suffix += 1
    return slug


def resolve_or_create_tags(raw_tags: str | list[str]) -> list[Tag]:
    """Resuelve o crea etiquetas a partir de una cadena o lista de nombres.

    Evita duplicados tanto dentro del mismo payload como contra la base de datos.

    Args:
        raw_tags: Cadena separada por comas o lista de nombres de etiquetas.

    Returns:
        Lista de instancias ``Tag`` listas para asociar a una pregunta.
    """
    if isinstance(raw_tags, str):
        candidates = raw_tags.split(",")
    else:
        candidates = [str(item) for item in raw_tags]

    tags: list[Tag] = []
    seen_slugs: set[str] = set()
    for raw_name in candidates:
        name = raw_name.strip()
        if not name:
            continue
        slug = slugify(name)[:35]
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        tag = db.session.scalar(db.select(Tag).filter_by(slug=slug))
        if tag is None:
            tag = Tag(name=name[:30], slug=slug)
            db.session.add(tag)
        tags.append(tag)
    return tags


def validate_question_fields(
    *,
    title: str | None = None,
    body: str | None = None,
    category_id_raw: Any = None,
    check_title: bool = True,
    check_body: bool = True,
    check_category: bool = True,
) -> tuple[dict[str, str], int | None]:
    """Valida los campos de una pregunta para formularios web y API JSON.

    Args:
        title: Título limpio de la pregunta.
        body: Cuerpo limpio de la pregunta.
        category_id_raw: Valor crudo de ``category_id``.
        check_title: Si se debe validar ``title``.
        check_body: Si se debe validar ``body``.
        check_category: Si se debe validar ``category_id_raw``.

    Returns:
        Tupla ``(errors, category_id)`` con los mensajes de error por campo y
        el identificador entero de categoría validado cuando corresponde.
    """
    errors: dict[str, str] = {}

    if check_title:
        clean_title = (title or "").strip()
        if len(clean_title) < 5:
            errors["title"] = "El titulo debe tener al menos 5 caracteres."
        elif len(clean_title) > 150:
            errors["title"] = "El titulo no puede superar los 150 caracteres."

    if check_body:
        clean_body = (body or "").strip()
        if not clean_body:
            errors["body"] = "El contenido de la pregunta es obligatorio."

    category_id: int | None = None
    if check_category:
        if category_id_raw is None or str(category_id_raw).strip() == "":
            errors["category_id"] = "Debes seleccionar una categoria."
        else:
            try:
                category_id = int(category_id_raw)
            except (TypeError, ValueError):
                errors["category_id"] = "Categoria invalida."
            else:
                if db.session.get(Category, category_id) is None:
                    errors["category_id"] = "La categoria indicada no existe."

    return errors, category_id
