import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


class AlembicMigrationTest(unittest.TestCase):
    def test_empty_sqlite_database_upgrades_to_head(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = Path(tmpdir) / "checkflow-alembic-test.db"
            previous_database_url = os.environ.get("CHECKFLOW_DATABASE_URL")
            os.environ["CHECKFLOW_DATABASE_URL"] = f"sqlite:///{database_path}"
            try:
                config = Config(str(REPO_ROOT / "alembic.ini"))
                config.set_main_option("script_location", str(REPO_ROOT / "backend/alembic"))
                expected_head = ScriptDirectory.from_config(config).get_current_head()

                command.upgrade(config, "head")

                conn = sqlite3.connect(database_path)
                conn.row_factory = sqlite3.Row
                try:
                    version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                    project_columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
                    qg_columns = {row["name"] for row in conn.execute("PRAGMA table_info(qg_nodes)")}
                    rule_columns = {row["name"] for row in conn.execute("PRAGMA table_info(business_check_rules)")}
                    execution_columns = {
                        row["name"] for row in conn.execute("PRAGMA table_info(auto_check_execution_rules)")
                    }
                    table_names = {
                        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                    }
                finally:
                    conn.close()
            finally:
                if previous_database_url is None:
                    os.environ.pop("CHECKFLOW_DATABASE_URL", None)
                else:
                    os.environ["CHECKFLOW_DATABASE_URL"] = previous_database_url

        self.assertEqual(expected_head, version["version_num"])
        self.assertNotIn("project_code", project_columns)
        self.assertNotIn("node_name", qg_columns)
        self.assertNotIn("is_active", qg_columns)
        self.assertNotIn("created_at", qg_columns)
        self.assertNotIn("updated_at", qg_columns)
        self.assertNotIn("qg_node_id", rule_columns)
        self.assertNotIn("execution_code", execution_columns)
        self.assertNotIn("config_version", execution_columns)
        self.assertIn("business_rule_release_batches", table_names)
        self.assertIn("business_rule_release_batch_items", table_names)
        self.assertIn("business_rule_change_logs", table_names)


if __name__ == "__main__":
    unittest.main()
