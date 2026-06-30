import os
import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*")

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
os.environ["CHECKFLOW_DATABASE_URL"] = "sqlite:///:memory:"


class P0MainFlowTest(unittest.TestCase):
    def setUp(self):
        from app.core.database import reset_database
        from app.seed import seed_database
        from app.main import app

        reset_database()
        seed_database()
        self.client = TestClient(app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/login",
            json={"uid": "admin", "password": "admin"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["data"]["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        from app.core.database import close_database

        close_database()

    def test_health_and_current_user(self):
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        me = self.client.get("/api/v1/auth/me", headers=self.headers)
        self.assertEqual(me.status_code, 200, me.text)
        self.assertIn("super_admin", me.json()["data"]["permissions"])

    def test_vdrive_mock_adapter_is_replaceable_boundary(self):
        from app.vdrive import MockVDriveAdapter, validate_vdrive_folder_link

        result = validate_vdrive_folder_link("https://vdrive.example.com/?folderGuid=BOUNDARY", MockVDriveAdapter())

        self.assertTrue(result["valid"])
        self.assertEqual(result["folder_guid"], "BOUNDARY")
        self.assertIn("folder_path", result)

    def test_app_startup_creates_schema_before_seed(self):
        from app.core.database import close_database
        from app.main import app

        close_database()
        with TestClient(app, raise_server_exceptions=False) as client:
            health = client.get("/health")

        self.assertEqual(health.status_code, 200, health.text)

    def test_project_rule_task_archive_report_rectification_recheck_flow(self):
        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_code": "P0_FILE_EXISTS",
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "config_version": "V1",
                "is_enabled": True,
                "config_json": {"mock": True},
            },
        )
        self.assertEqual(execution_rule.status_code, 200, execution_rule.text)

        published = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/publish",
            headers=self.headers,
        )
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(published.json()["data"]["status"], "published")

        task = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(task.status_code, 200, task.text)
        task_data = task.json()["data"]
        self.assertEqual(task_data["status"], "running")
        self.assertEqual(task_data["current_round_no"], 1)

        duplicate = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["error"]["code"], "ACTIVE_TASK_EXISTS")

        items = self.client.get(
            f"/api/v1/inspection-tasks/{task_data['inspection_task_id']}/current-round/items",
            headers=self.headers,
        )
        self.assertEqual(items.status_code, 200, items.text)
        item_rows = items.json()["data"]["items"]
        self.assertEqual([item["source_rule_code"] for item in item_rows], ["P0_MANUAL", "P0_AUTO"])
        self.assertEqual(item_rows[0]["status"], "manual_required")
        self.assertEqual(item_rows[1]["status"], "auto_completed")

        auto_results = self.client.get(
            f"/api/v1/inspection-items/{item_rows[1]['id']}/auto-check-results",
            headers=self.headers,
        )
        self.assertEqual(auto_results.status_code, 200, auto_results.text)
        self.assertEqual(auto_results.json()["data"]["items"][0]["auto_status"], "success")

        fail_item = item_rows[0]
        pass_item = item_rows[1]
        fail_confirm = self.client.post(
            f"/api/v1/inspection-items/{fail_item['id']}/confirm",
            headers=self.headers,
            json={
                "decision_result": "fail",
                "decision_text": "Missing signed evidence.",
                "responsible_owner": "MQD",
                "planned_finish_date": "2026-07-15",
            },
        )
        self.assertEqual(fail_confirm.status_code, 200, fail_confirm.text)

        manual = self.client.post(
            f"/api/v1/inspection-items/{pass_item['id']}/convert-to-manual",
            headers=self.headers,
            json={"reason": "Mock auto check requires engineer final decision."},
        )
        self.assertEqual(manual.status_code, 200, manual.text)
        pass_confirm = self.client.post(
            f"/api/v1/inspection-items/{pass_item['id']}/confirm",
            headers=self.headers,
            json={"decision_result": "pass", "decision_text": "Evidence accepted."},
        )
        self.assertEqual(pass_confirm.status_code, 200, pass_confirm.text)

        archived = self.client.post(
            f"/api/v1/inspection-tasks/{task_data['inspection_task_id']}/archive-current-round",
            headers=self.headers,
        )
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()["data"]["overall_result"], "NO_GO")
        self.assertEqual(archived.json()["data"]["task_status"], "rectifying")
        self.assertEqual(archived.json()["data"]["generated_rectification_count"], 1)

        reports = self.client.get("/api/v1/reports?overall_result=NO_GO&qg_node_id=1", headers=self.headers)
        self.assertEqual(reports.status_code, 200, reports.text)
        report_id = reports.json()["data"]["items"][0]["id"]
        report = self.client.get(f"/api/v1/reports/{report_id}", headers=self.headers)
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(report.json()["data"]["overall_result"], "NO_GO")
        self.assertEqual(report.json()["data"]["project"]["id"], project_id)
        self.assertEqual(len(report.json()["data"]["items"]), 2)

        rectifications = self.client.get(
            f"/api/v1/rectification-items?task_id={task_data['inspection_task_id']}",
            headers=self.headers,
        )
        self.assertEqual(rectifications.status_code, 200, rectifications.text)
        rectification_id = rectifications.json()["data"]["items"][0]["id"]
        done = self.client.post(
            f"/api/v1/rectification-items/{rectification_id}/mark-done",
            headers=self.headers,
        )
        self.assertEqual(done.status_code, 200, done.text)

        recheck = self.client.post(
            f"/api/v1/inspection-tasks/{task_data['inspection_task_id']}/trigger-recheck",
            headers=self.headers,
        )
        self.assertEqual(recheck.status_code, 200, recheck.text)
        self.assertEqual(recheck.json()["data"]["task_status"], "running")
        self.assertEqual(recheck.json()["data"]["new_round_no"], 2)
        self.assertEqual(recheck.json()["data"]["generated_items_count"], 1)

    def test_dashboard_overview_and_todos_follow_current_scope(self):
        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_code": "DASHBOARD_FILE_EXISTS",
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "config_version": "V1",
                "is_enabled": True,
                "config_json": {"mock": True},
            },
        )
        self.assertEqual(execution_rule.status_code, 200, execution_rule.text)
        published = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/publish",
            headers=self.headers,
        )
        self.assertEqual(published.status_code, 200, published.text)
        task = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(task.status_code, 200, task.text)
        task_id = task.json()["data"]["inspection_task_id"]

        overview = self.client.get("/api/v1/dashboard/overview", headers=self.headers)
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(overview.json()["data"]["running_count"], 1)
        self.assertEqual(overview.json()["data"]["archive_ready_count"], 0)

        todos = self.client.get("/api/v1/dashboard/my-todos", headers=self.headers)
        self.assertEqual(todos.status_code, 200, todos.text)
        todo_rows = todos.json()["data"]["items"]
        self.assertTrue(any(row["type"] == "running_task" and row["target_id"] == task_id for row in todo_rows))

    def test_project_listing_filters_deleted_models_qg_and_updates_project(self):
        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        other_project = self.client.post(
            "/api/v1/projects",
            headers=self.headers,
            json={
                "project_name": "MQD Other Project",
                "customer": "Customer B",
                "vdrive_url": "https://vdrive.example/indrive#/index?id=enterprise_folder-002",
                "receive_date": "2026-07-01",
                "models": ["OTHER-MODEL"],
            },
        )
        self.assertEqual(other_project.status_code, 200, other_project.text)
        other_project_id = other_project.json()["data"]["id"]

        edited = self.client.patch(
            f"/api/v1/projects/{project_id}",
            headers=self.headers,
            json={
                "customer": "Customer Edited",
                "project_category": "new_platform",
                "bu": "BU2",
                "project_level": "B",
                "mp_owner": "MP Owner",
                "group_name": "Group B",
                "planned_mp_date": "2026-12-01",
                "production_line": "Line 9",
            },
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        edited_data = edited.json()["data"]
        self.assertEqual(edited_data["customer"], "Customer Edited")
        self.assertEqual(edited_data["bu"], "BU2")
        self.assertEqual(edited_data["production_line"], "Line 9")

        vdrive = self.client.post(
            f"/api/v1/projects/{project_id}/vdrive-link",
            headers=self.headers,
            json={"vdrive_url": "https://vdrive.example/indrive#/index?folderGuid=updated-folder"},
        )
        self.assertEqual(vdrive.status_code, 200, vdrive.text)
        self.assertEqual(vdrive.json()["data"]["vdrive"]["folder_guid"], "updated-folder")
        self.assertEqual(vdrive.json()["data"]["vdrive"]["folder_path"], "/mock/updated-folder")

        by_model = self.client.get("/api/v1/projects?keyword=M2", headers=self.headers)
        self.assertEqual(by_model.status_code, 200, by_model.text)
        self.assertEqual([row["id"] for row in by_model.json()["data"]["items"]], [project_id])

        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_code": "PROJECT_FILTER_FILE_EXISTS",
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "config_version": "V1",
                "is_enabled": True,
                "config_json": {"mock": True},
            },
        )
        self.assertEqual(execution_rule.status_code, 200, execution_rule.text)
        published = self.client.post(f"/api/v1/business-rule-versions/{version_id}/publish", headers=self.headers)
        self.assertEqual(published.status_code, 200, published.text)
        task = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(task.status_code, 200, task.text)

        by_qg = self.client.get("/api/v1/projects?qg_node_id=1", headers=self.headers)
        self.assertEqual(by_qg.status_code, 200, by_qg.text)
        self.assertEqual([row["id"] for row in by_qg.json()["data"]["items"]], [project_id])

        deleted = self.client.request(
            "DELETE",
            f"/api/v1/projects/{other_project_id}",
            headers=self.headers,
            json={"confirm_project_name": "MQD Other Project", "delete_reason": "test deleted filter"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        deleted_list = self.client.get("/api/v1/projects?status=deleted", headers=self.headers)
        self.assertEqual(deleted_list.status_code, 200, deleted_list.text)
        self.assertEqual([row["id"] for row in deleted_list.json()["data"]["items"]], [other_project_id])

    def test_add_order_is_blocked_when_project_has_active_task(self):
        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_code": "ORDER_BLOCK_FILE_EXISTS",
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "config_version": "V1",
                "is_enabled": True,
                "config_json": {"mock": True},
            },
        )
        self.assertEqual(execution_rule.status_code, 200, execution_rule.text)
        published = self.client.post(f"/api/v1/business-rule-versions/{version_id}/publish", headers=self.headers)
        self.assertEqual(published.status_code, 200, published.text)
        task = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(task.status_code, 200, task.text)

        order = self.client.post(
            f"/api/v1/projects/{project_id}/orders",
            headers=self.headers,
            json={"receive_date": "2026-08-01", "models": ["M3"]},
        )
        self.assertEqual(order.status_code, 400)
        self.assertEqual(order.json()["error"]["code"], "PROJECT_HAS_ACTIVE_TASK")

    def test_rule_version_history_includes_current_marker_publisher_and_change_details(self):
        version = self.client.post(
            "/api/v1/business-rule-versions",
            headers=self.headers,
            json={"qg_node_id": 1, "version_no": "V-HISTORY", "change_summary": "history fields"},
        )
        self.assertEqual(version.status_code, 200, version.text)
        version_id = version.json()["data"]["id"]
        manual_rule = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "rule_code": "HISTORY_MANUAL",
                "item_name": "History manual item",
                "item_type": "manual",
                "check_type": "manual",
                "checklist_requirement": "Initial requirement",
                "owner_dept": "MQD",
                "is_apqp": False,
                "is_active": True,
                "sort_order": 1,
            },
        )
        self.assertEqual(manual_rule.status_code, 200, manual_rule.text)
        rule_id = manual_rule.json()["data"]["id"]
        edited_rule = self.client.patch(
            f"/api/v1/business-check-rules/{rule_id}",
            headers=self.headers,
            json={
                "item_name": "History manual item edited",
                "checklist_requirement": "Edited requirement",
                "is_apqp": True,
                "is_active": False,
                "sort_order": 3,
            },
        )
        self.assertEqual(edited_rule.status_code, 200, edited_rule.text)

        published = self.client.post(f"/api/v1/business-rule-versions/{version_id}/publish", headers=self.headers)
        self.assertEqual(published.status_code, 200, published.text)
        published_data = published.json()["data"]
        self.assertEqual(published_data["published_by_name"], "系统管理员")
        self.assertTrue(published_data["is_current"])
        self.assertEqual(published_data["change_details"][0]["rule_code"], "HISTORY_MANUAL")
        self.assertEqual(published_data["change_details"][0]["change_type"], "disabled")

        versions = self.client.get("/api/v1/business-rule-versions?qg_node_id=1", headers=self.headers)
        self.assertEqual(versions.status_code, 200, versions.text)
        history_version = next(row for row in versions.json()["data"]["items"] if row["id"] == version_id)
        self.assertEqual(history_version["published_by_name"], "系统管理员")
        self.assertTrue(history_version["is_current"])
        self.assertEqual(history_version["change_details"][0]["item_name"], "History manual item edited")

    def test_task_creation_rolls_back_when_later_step_fails(self):
        from app.core.database import query_all

        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_code": "P0_FILE_EXISTS",
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "config_version": "V1",
                "is_enabled": True,
                "config_json": {"mock": True},
            },
        )
        self.assertEqual(execution_rule.status_code, 200, execution_rule.text)
        published = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/publish",
            headers=self.headers,
        )
        self.assertEqual(published.status_code, 200, published.text)

        with patch("app.main.generate_items_for_round", side_effect=RuntimeError("forced failure")):
            failed = self.client.post(
                "/api/v1/inspection-tasks",
                headers=self.headers,
                json={"project_id": project_id, "qg_node_id": 1},
            )

        self.assertEqual(failed.status_code, 500)
        self.assertEqual(query_all("SELECT * FROM inspection_tasks"), [])
        self.assertEqual(query_all("SELECT * FROM rule_snapshots"), [])
        self.assertEqual(query_all("SELECT * FROM inspection_rounds"), [])

    def test_published_rule_version_is_frozen(self):
        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_code": "P0_FILE_EXISTS",
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "config_version": "V1",
                "is_enabled": True,
                "config_json": {"mock": True},
            },
        )
        self.assertEqual(execution_rule.status_code, 200, execution_rule.text)
        execution_rule_id = execution_rule.json()["data"]["id"]
        published = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/publish",
            headers=self.headers,
        )
        self.assertEqual(published.status_code, 200, published.text)

        edited_rule = self.client.patch(
            f"/api/v1/business-check-rules/{auto_rule_id}",
            headers=self.headers,
            json={"item_name": "Changed after publish"},
        )
        self.assertEqual(edited_rule.status_code, 400)
        self.assertEqual(edited_rule.json()["error"]["code"], "RULE_VERSION_NOT_DRAFT")

        edited_execution = self.client.patch(
            f"/api/v1/auto-check-execution-rules/{execution_rule_id}",
            headers=self.headers,
            json={"config_json": {"changed": True}},
        )
        self.assertEqual(edited_execution.status_code, 400)
        self.assertEqual(edited_execution.json()["error"]["code"], "RULE_VERSION_NOT_DRAFT")

        extra_execution = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_code": "AFTER_PUBLISH",
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "config_version": "V2",
                "is_enabled": True,
                "config_json": {},
            },
        )
        self.assertEqual(extra_execution.status_code, 400)
        self.assertEqual(extra_execution.json()["error"]["code"], "RULE_VERSION_NOT_DRAFT")

    def _create_project_and_rules(self):
        project = self.client.post(
            "/api/v1/projects",
            headers=self.headers,
            json={
                "project_name": "MQD P0 Project",
                "customer": "Customer A",
                "project_category": "new_project",
                "bu": "BU1",
                "project_level": "A",
                "mq_user_id": 1,
                "mp_owner": "PM",
                "group_name": "MQD",
                "planned_mp_date": "2026-10-01",
                "production_line": "Line 1",
                "vdrive_url": "https://vdrive.example/indrive#/index?id=enterprise_folder-001",
                "receive_date": "2026-06-30",
                "models": ["M1", "M2"],
            },
        )
        self.assertEqual(project.status_code, 200, project.text)
        project_id = project.json()["data"]["id"]

        version = self.client.post(
            "/api/v1/business-rule-versions",
            headers=self.headers,
            json={
                "qg_node_id": 1,
                "version_no": "V-P0",
                "change_summary": "P0 acceptance rules",
            },
        )
        self.assertEqual(version.status_code, 200, version.text)
        version_id = version.json()["data"]["id"]

        manual_rule = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "rule_code": "P0_MANUAL",
                "item_name": "Manual checklist",
                "item_type": "manual",
                "check_type": "manual",
                "checklist_requirement": "Engineer confirms the manual item.",
                "owner_dept": "MQD",
                "is_apqp": False,
                "sort_order": 1,
            },
        )
        self.assertEqual(manual_rule.status_code, 200, manual_rule.text)

        auto_rule = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "rule_code": "P0_AUTO",
                "item_name": "Auto file checklist",
                "item_type": "auto",
                "check_type": "file_existence",
                "checklist_requirement": "Required file exists in VDrive.",
                "owner_dept": "PT",
                "is_apqp": True,
                "sort_order": 2,
            },
        )
        self.assertEqual(auto_rule.status_code, 200, auto_rule.text)
        auto_rule_id = auto_rule.json()["data"]["id"]
        return project_id, version_id, auto_rule_id


if __name__ == "__main__":
    unittest.main()
