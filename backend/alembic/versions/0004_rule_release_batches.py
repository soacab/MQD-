"""Add business rule release batches.

Revision ID: 0004_rule_release_batches
Revises: 0003_simplify_execution_and_vdrive_schema
Create Date: 2026-07-01
"""

from alembic import op


revision = "0004_rule_release_batches"
down_revision = "0003_simplify_execution_and_vdrive_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    backend = op.get_bind().dialect.name
    id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if backend == "sqlite" else "BIGSERIAL PRIMARY KEY"
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS business_rule_release_batches (
            id {id_type},
            batch_no TEXT NOT NULL UNIQUE,
            change_summary TEXT,
            published_by INTEGER REFERENCES users(id),
            published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS business_rule_release_batch_items (
            id {id_type},
            release_batch_id INTEGER NOT NULL REFERENCES business_rule_release_batches(id),
            qg_node_id INTEGER NOT NULL REFERENCES qg_nodes(id),
            old_version_id INTEGER REFERENCES business_rule_versions(id),
            new_version_id INTEGER NOT NULL REFERENCES business_rule_versions(id),
            old_version_no TEXT,
            new_version_no TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(release_batch_id, qg_node_id),
            UNIQUE(new_version_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS business_rule_change_logs (
            id {id_type},
            release_batch_id INTEGER NOT NULL REFERENCES business_rule_release_batches(id),
            qg_node_id INTEGER NOT NULL REFERENCES qg_nodes(id),
            business_rule_version_id INTEGER NOT NULL REFERENCES business_rule_versions(id),
            rule_code TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT,
            change_type TEXT NOT NULL,
            change_summary TEXT,
            change_detail_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("MVP migration downgrade is intentionally not implemented.")
