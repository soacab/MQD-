import os
import sqlite3
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
os.environ["CHECKFLOW_DATABASE_URL"] = "sqlite:///:memory:"


class DatabaseConstraintTest(unittest.TestCase):
    def setUp(self):
        from app.core.database import reset_database
        from app.seed import seed_database

        reset_database()
        seed_database()

    def tearDown(self):
        from app.core.database import close_database

        close_database()

    def test_project_and_qg_schema_excludes_removed_business_fields(self):
        from app.core.database import query_all

        project_columns = {row["name"] for row in query_all("PRAGMA table_info(projects)")}
        qg_columns = {row["name"] for row in query_all("PRAGMA table_info(qg_nodes)")}

        self.assertNotIn("project_code", project_columns)
        self.assertNotIn("node_name", qg_columns)
        self.assertNotIn("is_active", qg_columns)

    def test_user_permission_and_qg_unique_constraints(self):
        from app.core.database import execute

        with self.assertRaises(sqlite3.IntegrityError):
            execute(
                "INSERT INTO users(uid, name, email, status) VALUES (?, ?, ?, ?)",
                ("admin", "Duplicate Admin", "duplicate@example.com", "active"),
            )

        with self.assertRaises(sqlite3.IntegrityError):
            execute("INSERT INTO user_permissions(user_id, permission_code) VALUES (?, ?)", (1, "super_admin"))

        with self.assertRaises(sqlite3.IntegrityError):
            execute("INSERT INTO qg_nodes(node_code, sort_order) VALUES (?, ?)", ("QG4", 99))

    def test_rule_unique_constraints(self):
        from app.core.database import execute

        execute(
            "INSERT INTO business_rule_versions(qg_node_id, version_no, change_summary, created_by) VALUES (?, ?, ?, ?)",
            (1, "V-UNIQUE", "Unique constraint test", 1),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            execute(
                "INSERT INTO business_rule_versions(qg_node_id, version_no, change_summary, created_by) VALUES (?, ?, ?, ?)",
                (1, "V-UNIQUE", "Duplicate version", 1),
            )

        execute(
            """
            INSERT INTO business_check_rules(
                business_rule_version_id, qg_node_id, rule_code, item_name, item_type, check_type
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1, 1, "RULE_UNIQUE", "Rule unique", "manual", "manual"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            execute(
                """
                INSERT INTO business_check_rules(
                    business_rule_version_id, qg_node_id, rule_code, item_name, item_type, check_type
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (1, 1, "RULE_UNIQUE", "Duplicate rule", "manual", "manual"),
            )

        execute(
            """
            INSERT INTO auto_check_execution_rules(
                business_check_rule_id, execution_code, execution_mode, adapter_type, config_json, config_version, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "EXEC_UNIQUE", "file_existence", "vdrive", "{}", "V1", 1),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            execute(
                """
                INSERT INTO auto_check_execution_rules(
                    business_check_rule_id, execution_code, execution_mode, adapter_type, config_json, config_version, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (1, "EXEC_UNIQUE", "file_existence", "vdrive", "{}", "V1", 1),
            )

    def test_inspection_task_snapshot_round_and_report_unique_constraints(self):
        from app.core.database import execute

        project_id = self._create_project()
        version_id = self._create_rule_version()
        task_id = self._create_task(project_id, task_no="TASK-UNIQUE-1")

        with self.assertRaises(sqlite3.IntegrityError):
            self._create_task(project_id, task_no="TASK-UNIQUE-2")

        self._complete_task(task_id)
        second_task_id = self._create_task(project_id, task_no="TASK-UNIQUE-2")

        execute(
            """
            INSERT INTO rule_snapshots(
                inspection_task_id, business_rule_version_id, business_rule_snapshot_json, auto_check_execution_rule_snapshot_json
            ) VALUES (?, ?, ?, ?)
            """,
            (task_id, version_id, "[]", "[]"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            execute(
                """
                INSERT INTO rule_snapshots(
                    inspection_task_id, business_rule_version_id, business_rule_snapshot_json, auto_check_execution_rule_snapshot_json
                ) VALUES (?, ?, ?, ?)
                """,
                (task_id, version_id, "[]", "[]"),
            )

        execute("INSERT INTO inspection_rounds(inspection_task_id, round_no, status) VALUES (?, ?, ?)", (task_id, 1, "running"))
        with self.assertRaises(sqlite3.IntegrityError):
            execute("INSERT INTO inspection_rounds(inspection_task_id, round_no, status) VALUES (?, ?, ?)", (task_id, 1, "running"))

        execute(
            """
            INSERT INTO inspection_reports(
                inspection_task_id, project_id, qg_node_id, report_no, business_rule_version_no, generated_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, project_id, 1, "REPORT-UNIQUE-1", "V1", 1),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            execute(
                """
                INSERT INTO inspection_reports(
                    inspection_task_id, project_id, qg_node_id, report_no, business_rule_version_no, generated_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, project_id, 1, "REPORT-UNIQUE-2", "V1", 1),
            )

        with self.assertRaises(sqlite3.IntegrityError):
            execute(
                """
                INSERT INTO inspection_reports(
                    inspection_task_id, project_id, qg_node_id, report_no, business_rule_version_no, generated_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (second_task_id, project_id, 1, "REPORT-UNIQUE-1", "V1", 1),
            )

    def test_rectification_followup_and_report_item_unique_constraints(self):
        from app.core.database import execute

        project_id = self._create_project()
        task_id = self._create_task(project_id, task_no="TASK-UNIQUE-3")
        round_id = self._create_round(task_id)
        item_id = self._create_item(task_id, round_id, "RULE-1")
        report_id = self._create_report(task_id, project_id)

        self._create_rectification(task_id, round_id, item_id, project_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self._create_rectification(task_id, round_id, item_id, project_id)

        followup_item_id = self._create_item(task_id, round_id, "RULE-2")
        self._create_followup(task_id, round_id, followup_item_id, project_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self._create_followup(task_id, round_id, followup_item_id, project_id)

        execute(
            """
            INSERT INTO report_items(
                report_id, source_rule_code, item_name_snapshot, item_type_snapshot, check_type_snapshot,
                latest_inspection_item_id, process_records_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (report_id, "RULE-1", "Rule 1", "manual", "manual", item_id, "[]"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            execute(
                """
                INSERT INTO report_items(
                    report_id, source_rule_code, item_name_snapshot, item_type_snapshot, check_type_snapshot,
                    latest_inspection_item_id, process_records_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (report_id, "RULE-1", "Rule 1 duplicate", "manual", "manual", item_id, "[]"),
            )

    def _create_project(self) -> int:
        from app.core.database import execute

        result = execute(
            "INSERT INTO projects(project_name, customer, status, created_by) VALUES (?, ?, ?, ?)",
            ("Constraint Project", "Customer", "normal", 1),
        )
        return int(result.lastrowid)

    def _create_task(self, project_id: int, task_no: str) -> int:
        from app.core.database import execute

        result = execute(
            "INSERT INTO inspection_tasks(project_id, qg_node_id, task_no, status, created_by) VALUES (?, ?, ?, ?, ?)",
            (project_id, 1, task_no, "running", 1),
        )
        return int(result.lastrowid)

    def _complete_task(self, task_id: int) -> None:
        from app.core.database import execute

        execute("UPDATE inspection_tasks SET status = ? WHERE id = ?", ("completed", task_id))

    def _create_rule_version(self) -> int:
        from app.core.database import execute

        result = execute(
            "INSERT INTO business_rule_versions(qg_node_id, version_no, change_summary, created_by) VALUES (?, ?, ?, ?)",
            (1, "V-SNAPSHOT", "Snapshot constraint test", 1),
        )
        return int(result.lastrowid)

    def _create_round(self, task_id: int) -> int:
        from app.core.database import execute

        result = execute("INSERT INTO inspection_rounds(inspection_task_id, round_no, status) VALUES (?, ?, ?)", (task_id, 1, "running"))
        return int(result.lastrowid)

    def _create_item(self, task_id: int, round_id: int, rule_code: str) -> int:
        from app.core.database import execute

        result = execute(
            """
            INSERT INTO inspection_items(
                inspection_task_id, inspection_round_id, source_rule_code, item_name_snapshot,
                item_type_snapshot, check_type_snapshot, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, round_id, rule_code, f"{rule_code} item", "manual", "manual", "confirmed"),
        )
        return int(result.lastrowid)

    def _create_rectification(self, task_id: int, round_id: int, item_id: int, project_id: int) -> None:
        from app.core.database import execute

        execute(
            """
            INSERT INTO rectification_items(
                inspection_task_id, source_round_id, source_item_id, project_id,
                item_name_snapshot, problem_desc, responsible_owner, planned_finish_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, round_id, item_id, project_id, "Rule item", "Problem", "Owner", "2026-07-15"),
        )

    def _create_followup(self, task_id: int, round_id: int, item_id: int, project_id: int) -> None:
        from app.core.database import execute

        execute(
            """
            INSERT INTO followup_items(
                inspection_task_id, source_round_id, source_item_id, project_id,
                item_name_snapshot, countermeasure, responsible_owner, planned_finish_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, round_id, item_id, project_id, "Rule item", "Countermeasure", "Owner", "2026-07-15"),
        )

    def _create_report(self, task_id: int, project_id: int) -> int:
        from app.core.database import execute

        result = execute(
            """
            INSERT INTO inspection_reports(
                inspection_task_id, project_id, qg_node_id, report_no, business_rule_version_no, generated_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, project_id, 1, f"REPORT-{task_id}", "V1", 1),
        )
        return int(result.lastrowid)


if __name__ == "__main__":
    unittest.main()
