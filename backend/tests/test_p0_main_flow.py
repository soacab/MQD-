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
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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
        process_record = report.json()["data"]["items"][0]["process_records_json"][0]
        self.assertIn("inspected_at", process_record)
        self.assertTrue(process_record["inspected_at"])

        rectifications = self.client.get(
            f"/api/v1/rectification-items?task_id={task_data['inspection_task_id']}",
            headers=self.headers,
        )
        self.assertEqual(rectifications.status_code, 200, rectifications.text)
        rectification_id = rectifications.json()["data"]["items"][0]["id"]
        dashboard = self.client.get("/api/v1/dashboard/my-todos", headers=self.headers)
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        rectification_todo = next(row for row in dashboard.json()["data"]["items"] if row["type"] == "recheck_task")
        self.assertEqual(rectification_todo["project_name"], "MQD P0 Project")
        self.assertEqual(rectification_todo["qg_node"], "QG2")
        self.assertEqual(rectification_todo["round_label"], "第2轮检查待启动")
        self.assertEqual(rectification_todo["rectification_done_count"], 0)
        self.assertEqual(rectification_todo["rectification_total_count"], 1)
        self.assertEqual(rectification_todo["rectification_progress_percent"], 0)
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
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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
        task_row = next(row for row in todo_rows if row["type"] == "running_task" and row["target_id"] == task_id)
        self.assertEqual(task_row["task_id"], task_id)
        self.assertEqual(task_row["project_id"], project_id)
        self.assertEqual(task_row["qg_node"], "QG2")
        self.assertEqual(task_row["round_label"], "第1轮检查")
        self.assertEqual(task_row["confirmed_count"], 0)
        self.assertEqual(task_row["total_count"], 2)
        self.assertEqual(task_row["progress_percent"], 0)
        self.assertEqual(task_row["mq_user_name"], "系统管理员")
        self.assertEqual(task_row["mq_user_uid"], "admin")
        self.assertIn("last_operated_at", task_row)
        self.assertEqual(task_row["auto_check_status"]["label"], "自动检查处理中")

    def test_confirmed_item_cannot_be_confirmed_again(self):
        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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
        items = self.client.get(f"/api/v1/inspection-tasks/{task_id}/current-round/items", headers=self.headers)
        self.assertEqual(items.status_code, 200, items.text)
        item_id = items.json()["data"]["items"][0]["id"]

        first_confirm = self.client.post(
            f"/api/v1/inspection-items/{item_id}/confirm",
            headers=self.headers,
            json={"decision_result": "pass", "decision_text": "First decision."},
        )
        self.assertEqual(first_confirm.status_code, 200, first_confirm.text)
        second_confirm = self.client.post(
            f"/api/v1/inspection-items/{item_id}/confirm",
            headers=self.headers,
            json={"decision_result": "fail", "decision_text": "Second decision.", "responsible_owner": "MQD", "planned_finish_date": "2026-07-15"},
        )

        self.assertEqual(second_confirm.status_code, 400, second_confirm.text)
        self.assertEqual(second_confirm.json()["error"]["code"], "ITEM_NOT_CONFIRMABLE")

    def test_void_task_requires_reason(self):
        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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

        voided = self.client.post(f"/api/v1/inspection-tasks/{task_id}/void", headers=self.headers, json={})

        self.assertEqual(voided.status_code, 400, voided.text)
        self.assertEqual(voided.json()["error"]["code"], "VOID_REASON_REQUIRED")

    def test_undo_rectification_and_close_followup_write_audit_logs(self):
        from app.core.database import query_all

        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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
        items = self.client.get(f"/api/v1/inspection-tasks/{task_id}/current-round/items", headers=self.headers)
        self.assertEqual(items.status_code, 200, items.text)
        item_rows = items.json()["data"]["items"]
        fail_confirm = self.client.post(
            f"/api/v1/inspection-items/{item_rows[0]['id']}/confirm",
            headers=self.headers,
            json={
                "decision_result": "fail",
                "decision_text": "Needs rectification.",
                "responsible_owner": "MQD",
                "planned_finish_date": "2026-07-15",
            },
        )
        self.assertEqual(fail_confirm.status_code, 200, fail_confirm.text)
        conditional_confirm = self.client.post(
            f"/api/v1/inspection-items/{item_rows[1]['id']}/confirm",
            headers=self.headers,
            json={
                "decision_result": "conditional",
                "decision_text": "Can proceed with follow-up.",
                "countermeasure": "Track action.",
                "responsible_owner": "MQD",
                "planned_finish_date": "2026-07-20",
            },
        )
        self.assertEqual(conditional_confirm.status_code, 200, conditional_confirm.text)
        archived = self.client.post(f"/api/v1/inspection-tasks/{task_id}/archive-current-round", headers=self.headers)
        self.assertEqual(archived.status_code, 200, archived.text)
        rectifications = self.client.get(f"/api/v1/rectification-items?task_id={task_id}", headers=self.headers)
        self.assertEqual(rectifications.status_code, 200, rectifications.text)
        followups = self.client.get(f"/api/v1/followup-items?task_id={task_id}", headers=self.headers)
        self.assertEqual(followups.status_code, 200, followups.text)
        rectification_id = rectifications.json()["data"]["items"][0]["id"]
        followup_id = followups.json()["data"]["items"][0]["id"]

        marked = self.client.post(f"/api/v1/rectification-items/{rectification_id}/mark-done", headers=self.headers)
        self.assertEqual(marked.status_code, 200, marked.text)
        undone = self.client.post(f"/api/v1/rectification-items/{rectification_id}/undo-done", headers=self.headers)
        self.assertEqual(undone.status_code, 200, undone.text)
        closed = self.client.post(f"/api/v1/followup-items/{followup_id}/close", headers=self.headers)
        self.assertEqual(closed.status_code, 200, closed.text)

        audit_rows = query_all(
            "SELECT action FROM audit_logs WHERE action IN (?, ?) ORDER BY action",
            ("close_followup", "undo_rectification_done"),
        )
        self.assertEqual([row["action"] for row in audit_rows], ["close_followup", "undo_rectification_done"])

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
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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

    def test_add_order_requires_at_least_one_model(self):
        project_id, _, _ = self._create_project_and_rules()

        order = self.client.post(
            f"/api/v1/projects/{project_id}/orders",
            headers=self.headers,
            json={"receive_date": "2026-07-20", "models": ["", "   "]},
        )

        self.assertEqual(order.status_code, 400)
        self.assertEqual(order.json()["error"]["code"], "PROJECT_ORDER_MODEL_REQUIRED")

    def test_archive_projects_lists_latest_report_rows_and_filters(self):
        from app.core.database import execute

        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        other_project = self.client.post(
            "/api/v1/projects",
            headers=self.headers,
            json={
                "project_name": "Archive Hidden Draft",
                "customer": "Customer B",
                "vdrive_url": "https://vdrive.example/indrive#/index?folderGuid=archive-hidden",
                "receive_date": "2026-07-01",
                "models": ["HIDDEN-MODEL"],
            },
        )
        self.assertEqual(other_project.status_code, 200, other_project.text)

        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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
        task_id = task.json()["data"]["inspection_task_id"]
        execute(
            """
            UPDATE inspection_reports
            SET overall_result = ?, last_modified_at = ?
            WHERE inspection_task_id = ?
            """,
            ("FULL_GO", "2026-06-04 10:00:00", task_id),
        )

        archive = self.client.get("/api/v1/archive-projects", headers=self.headers)
        self.assertEqual(archive.status_code, 200, archive.text)
        rows = archive.json()["data"]["items"]
        self.assertEqual([row["project_id"] for row in rows], [project_id])
        self.assertEqual(rows[0]["project_name"], "MQD P0 Project")
        self.assertEqual(rows[0]["models"], ["M1", "M2"])
        self.assertEqual(rows[0]["qg_node"]["node_code"], "QG2")
        self.assertEqual(rows[0]["overall_result"], "FULL_GO")
        self.assertEqual(rows[0]["report_last_modified_at"], "2026-06-04 10:00:00")
        self.assertEqual(rows[0]["mq_user_name"], "系统管理员")
        self.assertEqual(rows[0]["latest_report_id"], 1)

        filter_cases = [
            ("keyword=M2", [project_id]),
            ("keyword=Archive+Hidden", []),
            ("qg_node_id=1", [project_id]),
            ("qg_node_id=2", []),
            ("overall_result=FULL_GO", [project_id]),
            ("overall_result=C_GO", []),
            ("mq_user_id=1", [project_id]),
            ("modified_from=2026-06-04", [project_id]),
            ("modified_to=2026-06-03", []),
        ]
        for query, expected_ids in filter_cases:
            response = self.client.get(f"/api/v1/archive-projects?{query}", headers=self.headers)
            self.assertEqual(response.status_code, 200, f"{query}: {response.text}")
            self.assertEqual([row["project_id"] for row in response.json()["data"]["items"]], expected_ids, query)

        deleted = self.client.request(
            "DELETE",
            f"/api/v1/projects/{project_id}",
            headers=self.headers,
            json={"confirm_project_name": "MQD P0 Project", "delete_reason": "hide archive row"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        after_delete = self.client.get("/api/v1/archive-projects", headers=self.headers)
        self.assertEqual(after_delete.status_code, 200, after_delete.text)
        self.assertEqual(after_delete.json()["data"]["items"], [])

    def test_prepare_inspection_task_uses_vdrive_folder_name_without_history(self):
        prepared = self.client.post(
            "/api/v1/inspection-tasks/prepare",
            headers=self.headers,
            json={"vdrive_url": "https://vdrive.example/indrive#/index?folderGuid=NEW-FOLDER"},
        )

        self.assertEqual(prepared.status_code, 200, prepared.text)
        data = prepared.json()["data"]
        self.assertFalse(data["has_history"])
        self.assertIsNone(data["project"])
        self.assertEqual(data["vdrive"]["folder_guid"], "NEW-FOLDER")
        self.assertEqual(data["suggested_project_name"], "VDrive-NEW-FOLDER")
        self.assertEqual(data["recommended_qg_node"]["node_code"], "QG2")

    def test_prepare_inspection_task_prefills_history_and_recommends_next_qg(self):
        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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

        prepared = self.client.post(
            "/api/v1/inspection-tasks/prepare",
            headers=self.headers,
            json={"vdrive_url": "https://vdrive.example/indrive#/index?id=enterprise_folder-001"},
        )

        self.assertEqual(prepared.status_code, 200, prepared.text)
        data = prepared.json()["data"]
        self.assertTrue(data["has_history"])
        self.assertEqual(data["project"]["id"], project_id)
        self.assertEqual(data["project"]["project_name"], "MQD P0 Project")
        self.assertEqual([model["model_name"] for model in data["project"]["models"]], ["M1", "M2"])
        self.assertEqual(data["recommended_qg_node"]["node_code"], "QG3.1")

    def test_create_inspection_task_from_wizard_creates_internal_project(self):
        version = self.client.post(
            "/api/v1/business-rule-versions",
            headers=self.headers,
            json={"qg_node_id": 1, "version_no": "V-WIZARD", "change_summary": "wizard create"},
        )
        self.assertEqual(version.status_code, 200, version.text)
        version_id = version.json()["data"]["id"]
        manual_rule = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "rule_code": "WIZARD_MANUAL",
                "item_name": "Wizard manual item",
                "item_type": "manual",
                "check_type": "manual",
                "checklist_requirement": "Engineer confirms wizard-created task.",
                "owner_dept": "MQD",
                "is_apqp": False,
                "sort_order": 1,
            },
        )
        self.assertEqual(manual_rule.status_code, 200, manual_rule.text)
        published = self.client.post(f"/api/v1/business-rule-versions/{version_id}/publish", headers=self.headers)
        self.assertEqual(published.status_code, 200, published.text)

        task = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={
                "vdrive_url": "https://vdrive.example/indrive#/index?folderGuid=WIZARD-FOLDER",
                "project_name": "VDrive-WIZARD-FOLDER",
                "customer": "Wizard Customer",
                "project_category": "new_project",
                "bu": "BU-W",
                "project_level": "A",
                "mq_user_id": 1,
                "mp_owner": "MP Wizard",
                "group_name": "MQD",
                "planned_mp_date": "2026-11-01",
                "production_line": "Line W",
                "receive_date": "2026-07-10",
                "models": ["W1"],
                "qg_node_id": 1,
            },
        )

        self.assertEqual(task.status_code, 200, task.text)
        task_data = task.json()["data"]
        self.assertEqual(task_data["status"], "running")
        project = self.client.get(f"/api/v1/projects/{task_data['project_id']}", headers=self.headers)
        self.assertEqual(project.status_code, 200, project.text)
        project_data = project.json()["data"]
        self.assertEqual(project_data["project_name"], "VDrive-WIZARD-FOLDER")
        self.assertEqual(project_data["vdrive"]["folder_guid"], "WIZARD-FOLDER")
        self.assertEqual([model["model_name"] for model in project_data["models"]], ["W1"])

    def test_create_inspection_task_from_wizard_rolls_back_project_when_later_step_fails(self):
        from app.core.database import query_all

        version = self.client.post(
            "/api/v1/business-rule-versions",
            headers=self.headers,
            json={"qg_node_id": 1, "version_no": "V-WIZARD-ROLLBACK", "change_summary": "wizard rollback"},
        )
        self.assertEqual(version.status_code, 200, version.text)
        version_id = version.json()["data"]["id"]
        manual_rule = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "rule_code": "WIZARD_ROLLBACK_MANUAL",
                "item_name": "Wizard rollback manual item",
                "item_type": "manual",
                "check_type": "manual",
                "checklist_requirement": "Engineer confirms wizard rollback.",
                "owner_dept": "MQD",
                "is_apqp": False,
                "sort_order": 1,
            },
        )
        self.assertEqual(manual_rule.status_code, 200, manual_rule.text)
        published = self.client.post(f"/api/v1/business-rule-versions/{version_id}/publish", headers=self.headers)
        self.assertEqual(published.status_code, 200, published.text)

        with patch("app.services.inspection_service.generate_items_for_round", side_effect=RuntimeError("forced failure")):
            failed = self.client.post(
                "/api/v1/inspection-tasks",
                headers=self.headers,
                json={
                    "vdrive_url": "https://vdrive.example/indrive#/index?folderGuid=WIZARD-ROLLBACK-FOLDER",
                    "project_name": "VDrive-WIZARD-ROLLBACK-FOLDER",
                    "customer": "Wizard Rollback Customer",
                    "project_category": "new_project",
                    "bu": "BU-WR",
                    "project_level": "A",
                    "mq_user_id": 1,
                    "mp_owner": "MP Wizard Rollback",
                    "group_name": "MQD",
                    "planned_mp_date": "2026-11-02",
                    "production_line": "Line WR",
                    "receive_date": "2026-07-11",
                    "models": ["WR1"],
                    "qg_node_id": 1,
                },
            )

        self.assertEqual(failed.status_code, 500)
        self.assertEqual(query_all("SELECT * FROM projects"), [])
        self.assertEqual(query_all("SELECT * FROM project_orders"), [])
        self.assertEqual(query_all("SELECT * FROM project_models"), [])
        self.assertEqual(query_all("SELECT * FROM inspection_tasks"), [])
        self.assertEqual(query_all("SELECT * FROM rule_snapshots"), [])
        self.assertEqual(query_all("SELECT * FROM inspection_rounds"), [])
        self.assertEqual(query_all("SELECT * FROM inspection_items"), [])
        self.assertEqual(query_all("SELECT * FROM inspection_reports"), [])
        self.assertEqual(
            query_all(
                "SELECT * FROM audit_logs WHERE action IN (?, ?)",
                ("create_project_from_task_wizard", "upsert_project_from_task_wizard"),
            ),
            [],
        )

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

    def test_business_rule_creation_defaults_to_manual_with_internal_code_and_next_sort(self):
        version = self.client.post(
            "/api/v1/business-rule-versions",
            headers=self.headers,
            json={"qg_node_id": 1, "version_no": "V-MANUAL-DEFAULT", "change_summary": "manual defaults"},
        )
        self.assertEqual(version.status_code, 200, version.text)
        version_id = version.json()["data"]["id"]
        existing_rule = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "rule_code": "EXISTING-MANUAL",
                "item_name": "Existing manual",
                "item_type": "manual",
                "check_type": "manual",
                "checklist_requirement": "Existing requirement",
                "owner_dept": "MQD",
                "is_apqp": False,
                "sort_order": 5,
            },
        )
        self.assertEqual(existing_rule.status_code, 200, existing_rule.text)

        created = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "item_name": "Generated manual",
                "checklist_requirement": "Generated requirement",
                "owner_dept": "PT",
                "is_apqp": True,
                "is_active": True,
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        created_data = created.json()["data"]
        self.assertEqual(created_data["rule_code"], f"BR-{version_id}-0001")
        self.assertEqual(created_data["item_type"], "manual")
        self.assertEqual(created_data["check_type"], "manual")
        self.assertEqual(created_data["sort_order"], 6)

        second_created = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "item_name": "Second generated manual",
                "checklist_requirement": "Second generated requirement",
                "owner_dept": "TE",
                "is_apqp": False,
                "is_active": True,
            },
        )
        self.assertEqual(second_created.status_code, 200, second_created.text)
        second_data = second_created.json()["data"]
        self.assertEqual(second_data["rule_code"], f"BR-{version_id}-0002")
        self.assertEqual(second_data["sort_order"], 7)

    def test_qg_nodes_expose_published_rule_count_and_ignore_drafts_until_publish(self):
        nodes = self.client.get("/api/v1/qg-nodes", headers=self.headers)
        self.assertEqual(nodes.status_code, 200, nodes.text)
        qg33 = next(row for row in nodes.json()["data"]["items"] if row["node_code"] == "QG3.3")
        qg3 = next(row for row in nodes.json()["data"]["items"] if row["node_code"] == "QG3")
        self.assertEqual(qg33["published_rule_count"], 15)
        self.assertEqual(qg3["published_rule_count"], 18)

        draft = self.client.post(f"/api/v1/qg-nodes/{qg33['id']}/editable-rule-version", headers=self.headers)
        self.assertEqual(draft.status_code, 200, draft.text)
        draft_id = draft.json()["data"]["id"]
        created = self.client.post(
            f"/api/v1/business-rule-versions/{draft_id}/business-check-rules",
            headers=self.headers,
            json={
                "item_name": "Draft-only manual rule",
                "checklist_requirement": "Draft rule should not affect published count before publish.",
                "owner_dept": "MQD",
                "is_apqp": False,
                "is_active": True,
            },
        )
        self.assertEqual(created.status_code, 200, created.text)

        nodes_before_publish = self.client.get("/api/v1/qg-nodes", headers=self.headers)
        self.assertEqual(nodes_before_publish.status_code, 200, nodes_before_publish.text)
        qg33_before_publish = next(row for row in nodes_before_publish.json()["data"]["items"] if row["node_code"] == "QG3.3")
        self.assertEqual(qg33_before_publish["published_rule_count"], 15)

        published = self.client.post(f"/api/v1/business-rule-versions/{draft_id}/publish", headers=self.headers)
        self.assertEqual(published.status_code, 200, published.text)
        nodes_after_publish = self.client.get("/api/v1/qg-nodes", headers=self.headers)
        self.assertEqual(nodes_after_publish.status_code, 200, nodes_after_publish.text)
        qg33_after_publish = next(row for row in nodes_after_publish.json()["data"]["items"] if row["node_code"] == "QG3.3")
        self.assertEqual(qg33_after_publish["published_rule_count"], 16)

    def test_publish_rule_version_does_not_require_auto_execution_rules(self):
        _, version_id, _auto_rule_id = self._create_project_and_rules()

        published = self.client.post(f"/api/v1/business-rule-versions/{version_id}/publish", headers=self.headers)

        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(published.json()["data"]["status"], "published")

    def test_prepare_editable_rule_version_copies_current_published_rules_once(self):
        _, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "is_enabled": True,
                "config_json": {"mock": True},
            },
        )
        self.assertEqual(execution_rule.status_code, 200, execution_rule.text)
        published = self.client.post(f"/api/v1/business-rule-versions/{version_id}/publish", headers=self.headers)
        self.assertEqual(published.status_code, 200, published.text)

        draft = self.client.post("/api/v1/qg-nodes/1/editable-rule-version", headers=self.headers)
        self.assertEqual(draft.status_code, 200, draft.text)
        draft_data = draft.json()["data"]
        self.assertEqual(draft_data["status"], "draft")
        self.assertEqual(draft_data["version_no"], "V02")
        self.assertEqual(draft_data["change_summary"], "基于 V-P0 编辑")
        self.assertEqual([rule["rule_code"] for rule in draft_data["business_check_rules"]], ["P0_MANUAL", "P0_AUTO"])
        copied_auto = next(rule for rule in draft_data["business_check_rules"] if rule["rule_code"] == "P0_AUTO")
        self.assertEqual(copied_auto["auto_check_execution_rules"][0]["execution_mode"], "file_existence")

        repeat = self.client.post("/api/v1/qg-nodes/1/editable-rule-version", headers=self.headers)
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertEqual(repeat.json()["data"]["id"], draft_data["id"])

    def test_publish_rule_version_accepts_change_summary(self):
        _, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "is_enabled": True,
                "config_json": {"mock": True},
            },
        )
        self.assertEqual(execution_rule.status_code, 200, execution_rule.text)

        published = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/publish",
            headers=self.headers,
            json={"change_summary": "QG2 rules updated from workspace"},
        )

        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(published.json()["data"]["change_summary"], "QG2 rules updated from workspace")

    def test_task_creation_rolls_back_when_later_step_fails(self):
        from app.core.database import query_all

        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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

        with patch("app.services.inspection_service.generate_items_for_round", side_effect=RuntimeError("forced failure")):
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
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
                "is_enabled": True,
                "config_json": {},
            },
        )
        self.assertEqual(extra_execution.status_code, 400)
        self.assertEqual(extra_execution.json()["error"]["code"], "RULE_VERSION_NOT_DRAFT")

    def test_completed_task_can_be_recreated_with_unique_task_no(self):
        from app.core.database import execute

        project_id, version_id, auto_rule_id = self._create_project_and_rules()
        execution_rule = self.client.post(
            f"/api/v1/business-check-rules/{auto_rule_id}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": "file_existence",
                "adapter_type": "vdrive",
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

        first = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(first.status_code, 200, first.text)
        first_id = first.json()["data"]["inspection_task_id"]
        execute("UPDATE inspection_tasks SET status = ? WHERE id = ?", ("completed", first_id))

        second = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertNotEqual(first.json()["data"]["task_no"], second.json()["data"]["task_no"])

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
