"""Simplify project and QG node fields.

Revision ID: 0002_simplify_project_qg_fields
Revises: 0001_initial_schema
Create Date: 2026-07-01
"""

from alembic import op


revision = "0002_simplify_project_qg_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN project_code")
    op.execute("ALTER TABLE qg_nodes DROP COLUMN node_name")
    op.execute("ALTER TABLE qg_nodes DROP COLUMN is_active")


def downgrade() -> None:
    raise NotImplementedError("MVP migration downgrade is intentionally not implemented.")
