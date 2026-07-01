"""Simplify project and QG node fields.

Revision ID: 0002_simplify_project_qg_fields
Revises: 0001_initial_schema
Create Date: 2026-07-01
"""

from alembic import op
from sqlalchemy import inspect


revision = "0002_simplify_project_qg_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _drop_column_if_exists("projects", "project_code")
    _drop_column_if_exists("qg_nodes", "node_name")
    _drop_column_if_exists("qg_nodes", "is_active")


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def downgrade() -> None:
    raise NotImplementedError("MVP migration downgrade is intentionally not implemented.")
