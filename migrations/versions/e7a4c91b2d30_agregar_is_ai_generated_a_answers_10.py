"""Agregar columna is_ai_generated a answers (#10)

Revision ID: e7a4c91b2d30
Revises: 167524f336a2
Create Date: 2026-11-25 15:05:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e7a4c91b2d30"
down_revision = "167524f336a2"
branch_labels = None
depends_on = None


def upgrade():
    """Agrega la columna booleana is_ai_generated a la tabla answers."""
    with op.batch_alter_table("answers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_ai_generated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade():
    """Elimina la columna is_ai_generated de la tabla answers."""
    with op.batch_alter_table("answers", schema=None) as batch_op:
        batch_op.drop_column("is_ai_generated")
