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
        self.assertEqual(rule_counts["QG3.3"], 15)
        self.assertEqual(rule_counts["QG4"], 22)

        auto_rule_count = query_one(
            """
            SELECT COUNT(*) AS total
            FROM business_check_rules
            WHERE item_type IN ('auto', 'system')
            """
        )["total"]
        execution_count = query_one(
            """
            SELECT COUNT(*) AS total
            FROM auto_check_execution_rules
            WHERE is_enabled = 1
            """
        )["total"]
        self.assertEqual(execution_count, auto_rule_count)

        before = {
            "versions": query_one("SELECT COUNT(*) AS total FROM business_rule_versions")["total"],
            "rules": query_one("SELECT COUNT(*) AS total FROM business_check_rules")["total"],
            "executions": query_one("SELECT COUNT(*) AS total FROM auto_check_execution_rules")["total"],
        }

        seed_database()

        after = {
            "versions": query_one("SELECT COUNT(*) AS total FROM business_rule_versions")["total"],
            "rules": query_one("SELECT COUNT(*) AS total FROM business_check_rules")["total"],
            "executions": query_one("SELECT COUNT(*) AS total FROM auto_check_execution_rules")["total"],
        }
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
