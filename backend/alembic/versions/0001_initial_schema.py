"""Initial CheckFlow MVP schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-29
"""

from alembic import op

from app.core.database import SCHEMA_SQL


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(SCHEMA_SQL)


def downgrade() -> None:
    raise NotImplementedError("MVP migration downgrade is intentionally not implemented.")
