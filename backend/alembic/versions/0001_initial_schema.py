"""Initial CheckFlow MVP schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-29
"""

from alembic import op

from app.core.database import schema_sql_for_backend


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    backend = "postgresql" if op.get_bind().dialect.name == "postgresql" else "sqlite"
    for statement in schema_sql_for_backend(backend).split(";"):
        statement = statement.strip()
        if statement:
            op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("MVP migration downgrade is intentionally not implemented.")
