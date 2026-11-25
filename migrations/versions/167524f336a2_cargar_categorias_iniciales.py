"""cargar categorias iniciales

Revision ID: 167524f336a2
Revises: fab9a1bfc844
Create Date: 2026-11-24 22:47:04.569749

"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "167524f336a2"
down_revision = "fab9a1bfc844"
branch_labels = None
depends_on = None

INITIAL_CATEGORIES = (
    {
        "name": "Python",
        "slug": "python",
        "description": "Dudas sobre el lenguaje Python, sintaxis y librerías estándar.",
    },
    {
        "name": "Flask",
        "slug": "flask",
        "description": "Rutas, Blueprints, Jinja2, sesiones y configuración en Flask.",
    },
    {
        "name": "Base de Datos",
        "slug": "base-de-datos",
        "description": "Modelado relacional, SQLAlchemy y migraciones con Alembic.",
    },
    {
        "name": "Diseño y UML",
        "slug": "diseno-uml",
        "description": "Patrones de diseño, principios SOLID y diagramas UML.",
    },
    {
        "name": "General",
        "slug": "general",
        "description": "Consultas generales sobre la materia y el trabajo práctico.",
    },
)

categories_table = sa.table(
    "categories",
    sa.column("name", sa.String(50)),
    sa.column("slug", sa.String(60)),
    sa.column("description", sa.Text),
    sa.column("created_at", sa.DateTime),
)


def upgrade():
    """Inserta las categorías iniciales si aún no existen en la base."""
    bind = op.get_bind()
    existing_rows = bind.execute(sa.text("SELECT slug, name FROM categories")).all()
    existing_slugs = {row[0] for row in existing_rows}
    existing_names = {row[1] for row in existing_rows}

    now = datetime.now(UTC)
    to_insert = [
        {**category, "created_at": now}
        for category in INITIAL_CATEGORIES
        if category["slug"] not in existing_slugs
        and category["name"] not in existing_names
    ]

    if to_insert:
        op.bulk_insert(categories_table, to_insert)


def downgrade():
    """Elimina las categorías iniciales insertadas por esta migración."""
    bind = op.get_bind()
    slugs = [category["slug"] for category in INITIAL_CATEGORIES]
    bind.execute(categories_table.delete().where(categories_table.c.slug.in_(slugs)))
