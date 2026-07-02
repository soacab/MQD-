import os
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
os.environ["CHECKFLOW_DATABASE_URL"] = "sqlite:///:memory:"


class SeedDataTest(unittest.TestCase):
    def setUp(self):
        from app.core.database import reset_database

        reset_database()

    def tearDown(self):
        from app.core.database import close_database

        close_database()

    def test_seed_database_creates_prototype_rule_versions_once(self):
        from app.core.database import query_all, query_one
        from app.seed import seed_database

        seed_database()

        version_rows = query_all(
            """
            SELECT q.node_code, v.version_no, v.status
            FROM business_rule_versions v
            JOIN qg_nodes q ON q.id = v.qg_node_id
            ORDER BY q.sort_order
            """
        )
        self.assertEqual([row["node_code"] for row in version_rows], ["QG2", "QG3.1", "QG3.2", "QG3.3", "QG3", "QG4"])
        self.assertEqual({row["status"] for row in version_rows}, {"published"})
        self.assertEqual(next(row for row in version_rows if row["node_code"] == "QG3.3")["version_no"], "V14")

        rule_counts = {
            row["node_code"]: row["rule_count"]
            for row in query_all(
                """
                SELECT q.node_code, COUNT(r.id) AS rule_count
                FROM qg_nodes q
                JOIN business_rule_versions v ON v.qg_node_id = q.id
                JOIN business_check_rules r ON r.business_rule_version_id = v.id
                GROUP BY q.node_code
                """
            )
        }
        self.assertEqual(rule_counts["QG2"], 6)
        self.assertEqual(rule_counts["QG3.1"], 8)
        self.assertEqual(rule_counts["QG3.2"], 11)
        self.assertEqual(rule_counts["QG3"], 17)
        self.assertEqual(rule_counts["QG3.3"], 16)
        self.assertEqual(rule_counts["QG4"], 22)

        before = {
            "versions": query_one("SELECT COUNT(*) AS total FROM business_rule_versions")["total"],
            "rules": query_one("SELECT COUNT(*) AS total FROM business_check_rules")["total"],
        }

        seed_database()

        after = {
            "versions": query_one("SELECT COUNT(*) AS total FROM business_rule_versions")["total"],
            "rules": query_one("SELECT COUNT(*) AS total FROM business_check_rules")["total"],
        }
        self.assertEqual(after, before)

    def test_seed_database_fills_existing_empty_rule_version(self):
        from app.core.database import execute, query_one
        from app.seed import seed_database

        execute("INSERT INTO qg_nodes(node_code, sort_order) VALUES (?, ?)", ("QG2", 1))
        execute(
            "INSERT INTO business_rule_versions(qg_node_id, version_no, status) VALUES (?, ?, ?)",
            (1, "V01", "published"),
        )

        seed_database()

        rule_count = query_one(
            """
            SELECT COUNT(*) AS total
            FROM business_check_rules r
            JOIN business_rule_versions v ON v.id = r.business_rule_version_id
            JOIN qg_nodes q ON q.id = v.qg_node_id
            WHERE q.node_code = ?
            """,
            ("QG2",),
        )["total"]
        self.assertEqual(rule_count, 6)

    def test_seed_database_preserves_existing_business_rule_fields(self):
        from app.core.database import execute, query_one
        from app.seed import seed_database

        execute("INSERT INTO qg_nodes(node_code, sort_order) VALUES (?, ?)", ("QG2", 1))
        version = execute(
            "INSERT INTO business_rule_versions(qg_node_id, version_no, status) VALUES (?, ?, ?)",
            (1, "V01", "published"),
        )
        execute(
            """
            INSERT INTO business_check_rules(
                business_rule_version_id, rule_code, item_name, item_type, check_type,
                checklist_requirement, owner_dept, is_apqp, is_active, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version.lastrowid,
                "QG2:PROCESS_PLAN",
                "用户已编辑过程开发计划",
                "manual",
                "manual",
                "用户已编辑要求",
                "USER",
                0,
                0,
                99,
            ),
        )

        seed_database()

        existing_rule = query_one(
            "SELECT * FROM business_check_rules WHERE rule_code = ?",
            ("QG2:PROCESS_PLAN",),
        )
        self.assertEqual(existing_rule["item_name"], "用户已编辑过程开发计划")
        self.assertEqual(existing_rule["item_type"], "manual")
        self.assertEqual(existing_rule["check_type"], "manual")
        self.assertEqual(existing_rule["checklist_requirement"], "用户已编辑要求")
        self.assertEqual(existing_rule["owner_dept"], "USER")
        self.assertEqual(existing_rule["is_apqp"], 0)
        self.assertEqual(existing_rule["is_active"], 0)
        self.assertEqual(existing_rule["sort_order"], 99)
        execution_count = query_one(
            """
            SELECT COUNT(*) AS total
            FROM auto_check_execution_rules
            WHERE business_check_rule_id = ?
            """,
            (existing_rule["id"],),
        )["total"]
        self.assertEqual(execution_count, 0)

        qg2_count = query_one(
            """
            SELECT COUNT(*) AS total
            FROM business_check_rules r
            JOIN business_rule_versions v ON v.id = r.business_rule_version_id
            JOIN qg_nodes q ON q.id = v.qg_node_id
            WHERE q.node_code = ?
            """,
            ("QG2",),
        )["total"]
        self.assertEqual(qg2_count, 6)

    def test_seed_database_creates_auto_execution_rules_for_auto_and_system_rules(self):
        from app.core.database import query_all, query_one
        from app.seed import seed_database

        seed_database()

        executable_rule_count = query_one(
            "SELECT COUNT(*) AS total FROM business_check_rules WHERE item_type IN ('auto', 'system')"
        )["total"]
        execution_count = query_one("SELECT COUNT(*) AS total FROM auto_check_execution_rules")["total"]
        self.assertEqual(execution_count, executable_rule_count)

        qg4_inherit_rows = query_all(
            """
            SELECT r.rule_code, r.item_type, r.check_type
            FROM business_check_rules r
            JOIN business_rule_versions v ON v.id = r.business_rule_version_id
            JOIN qg_nodes q ON q.id = v.qg_node_id
            WHERE q.node_code = 'QG4' AND r.rule_code LIKE 'QG4:INHERIT_%'
            """
        )
        self.assertTrue(qg4_inherit_rows)
        self.assertEqual({row["item_type"] for row in qg4_inherit_rows}, {"inherit"})
        self.assertEqual({row["check_type"] for row in qg4_inherit_rows}, {"inherit"})

        plm_rule = query_one("SELECT item_type, check_type FROM business_check_rules WHERE rule_code = ?", ("QG4:PLM_THREE_DOCS_RELEASE",))
        self.assertEqual(plm_rule["item_type"], "manual")
        self.assertEqual(plm_rule["check_type"], "manual")

        execution = query_one(
            """
            SELECT e.execution_mode, e.adapter_type, e.config_json
            FROM auto_check_execution_rules e
            JOIN business_check_rules r ON r.id = e.business_check_rule_id
            WHERE r.rule_code = ?
            """,
            ("QG3.2:PFMEA_FRESHNESS",),
        )
        self.assertEqual(execution["execution_mode"], "file_existence")
        self.assertEqual(execution["adapter_type"], "vdrive")
        self.assertIn("freshness_days", execution["config_json"])

        seed_database()
        repeated_execution_count = query_one("SELECT COUNT(*) AS total FROM auto_check_execution_rules")["total"]
        self.assertEqual(repeated_execution_count, execution_count)


if __name__ == "__main__":
    unittest.main()
