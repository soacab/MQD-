"""Simplify execution rules and remove VDrive snapshots.

Revision ID: 0003_simplify_execution_and_vdrive_schema
Revises: 0002_simplify_project_qg_fields
Create Date: 2026-07-01
"""

from alembic import op


revision = "0003_simplify_execution_and_vdrive_schema"
down_revision = "0002_simplify_project_qg_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    backend = op.get_bind().dialect.name
    if backend == "sqlite":
        _upgrade_sqlite()
        return
    _upgrade_postgresql()


def _upgrade_sqlite() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    op.execute("DROP TABLE IF EXISTS vdrive_files")
    op.execute("DROP TABLE IF EXISTS vdrive_folders")
    op.execute("DROP TABLE IF EXISTS vdrive_scan_batches")
    op.execute("ALTER TABLE qg_nodes DROP COLUMN created_at")
    op.execute("ALTER TABLE qg_nodes DROP COLUMN updated_at")

    op.execute(
        """
        CREATE TABLE business_check_rules_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_rule_version_id INTEGER NOT NULL REFERENCES business_rule_versions(id),
            rule_code TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            check_type TEXT NOT NULL,
            checklist_requirement TEXT,
            owner_dept TEXT,
            is_apqp INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(business_rule_version_id, rule_code)
        )
        """
    )
    op.execute(
        """
        INSERT INTO business_check_rules_new(
            id, business_rule_version_id, rule_code, item_name, item_type, check_type,
            checklist_requirement, owner_dept, is_apqp, is_active, sort_order, created_at, updated_at
        )
        SELECT
            id, business_rule_version_id, rule_code, item_name, item_type, check_type,
            checklist_requirement, owner_dept, is_apqp, is_active, sort_order, created_at, updated_at
        FROM business_check_rules
        """
    )
    op.execute("DROP TABLE business_check_rules")
    op.execute("ALTER TABLE business_check_rules_new RENAME TO business_check_rules")

    op.execute(
        """
        CREATE TABLE auto_check_execution_rules_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_check_rule_id INTEGER NOT NULL REFERENCES business_check_rules(id),
            execution_mode TEXT NOT NULL,
            adapter_type TEXT NOT NULL,
            config_json TEXT NOT NULL,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(business_check_rule_id)
        )
        """
    )
    op.execute(
        """
        INSERT INTO auto_check_execution_rules_new(
            id, business_check_rule_id, execution_mode, adapter_type, config_json,
            is_enabled, created_by, created_at, updated_at
        )
        SELECT
            MIN(id), business_check_rule_id, execution_mode, adapter_type, config_json,
            is_enabled, created_by, created_at, updated_at
        FROM auto_check_execution_rules
        GROUP BY business_check_rule_id
        """
    )
    op.execute("DROP TABLE auto_check_execution_rules")
    op.execute("ALTER TABLE auto_check_execution_rules_new RENAME TO auto_check_execution_rules")
    op.execute("PRAGMA foreign_keys=ON")


def _upgrade_postgresql() -> None:
    op.execute("DROP TABLE IF EXISTS vdrive_files")
    op.execute("DROP TABLE IF EXISTS vdrive_folders")
    op.execute("DROP TABLE IF EXISTS vdrive_scan_batches")
    op.execute("ALTER TABLE qg_nodes DROP COLUMN created_at")
    op.execute("ALTER TABLE qg_nodes DROP COLUMN updated_at")
    op.execute("ALTER TABLE business_check_rules DROP COLUMN qg_node_id")
    op.execute("ALTER TABLE auto_check_execution_rules DROP CONSTRAINT IF EXISTS auto_check_execution_rules_business_check_rule_id_execution_code_key")
    op.execute("ALTER TABLE auto_check_execution_rules DROP COLUMN execution_code")
    op.execute("ALTER TABLE auto_check_execution_rules DROP COLUMN config_version")
    op.execute("ALTER TABLE auto_check_execution_rules ADD UNIQUE (business_check_rule_id)")


def downgrade() -> None:
    raise NotImplementedError("MVP migration downgrade is intentionally not implemented.")
