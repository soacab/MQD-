import os
import sys
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
os.environ["CHECKFLOW_DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient


class AuthPermissionTest(unittest.TestCase):
    def setUp(self):
        from app.core.database import reset_database
        from app.seed import seed_database
        from app.main import app

        reset_database()
        seed_database()
        self.client = TestClient(app, raise_server_exceptions=False)
        self.admin_headers = self._login_headers("admin", "admin")

    def tearDown(self):
        from app.core.database import close_database

        close_database()

    def _login_headers(self, uid: str, password: str | None = None) -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/login",
            json={"uid": uid, "password": password or uid},
        )
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def _create_user(self, uid: str, permissions: list[str], status: str = "active") -> dict:
        response = self.client.post(
            "/api/v1/users",
            headers=self.admin_headers,
            json={
                "uid": uid,
                "name": uid.upper(),
                "email": f"{uid}@example.com",
                "permissions": permissions,
                "status": status,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def _audit_actions_for_entity(self, entity_type: str, entity_id: int | None) -> list[str]:
        response = self.client.get("/api/v1/audit-logs", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()["data"]["items"]
        return [row["action"] for row in rows if row["entity_type"] == entity_type and row["entity_id"] == entity_id]

    def _create_project(self, name: str, folder_guid: str) -> int:
        response = self.client.post(
            "/api/v1/projects",
            headers=self.admin_headers,
            json={
                "project_name": name,
                "customer": "ACME",
                "receive_date": "2026-06-30",
                "vdrive_url": f"https://vdrive.example.com/?folderGuid={folder_guid}",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]["id"]

    def _publish_manual_rule(self, version_no: str = "AUTH-SCOPE") -> int:
        version = self.client.post(
            "/api/v1/business-rule-versions",
            headers=self.admin_headers,
            json={"qg_node_id": 1, "version_no": version_no, "change_summary": "scope test"},
        )
        self.assertEqual(version.status_code, 200, version.text)
        version_id = version.json()["data"]["id"]
        rule = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.admin_headers,
            json={
                "rule_code": f"{version_no}-MANUAL",
                "item_name": "Manual scope item",
                "item_type": "manual",
                "check_type": "manual",
                "checklist_requirement": "Engineer confirms scope item.",
                "owner_dept": "MQD",
                "sort_order": 1,
            },
        )
        self.assertEqual(rule.status_code, 200, rule.text)
        published = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/publish",
            headers=self.admin_headers,
        )
        self.assertEqual(published.status_code, 200, published.text)
        return version_id

    def _create_task(self, headers: dict[str, str], project_id: int) -> int:
        response = self.client.post(
            "/api/v1/inspection-tasks",
            headers=headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]["inspection_task_id"]

    def _current_item_id(self, headers: dict[str, str], task_id: int) -> int:
        response = self.client.get(
            f"/api/v1/inspection-tasks/{task_id}/current-round/items",
            headers=headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]["items"][0]["id"]

    def _archive_single_item_task(self, headers: dict[str, str], task_id: int, result: str) -> None:
        item_id = self._current_item_id(headers, task_id)
        payload = {"decision_result": result, "decision_text": f"{result} decision"}
        if result == "fail":
            payload.update({"responsible_owner": "MQD", "planned_finish_date": "2026-07-15"})
        if result == "conditional":
            payload.update(
                {
                    "countermeasure": "Follow up countermeasure.",
                    "responsible_owner": "MQD",
                    "planned_finish_date": "2026-07-15",
                }
            )
        confirm = self.client.post(f"/api/v1/inspection-items/{item_id}/confirm", headers=headers, json=payload)
        self.assertEqual(confirm.status_code, 200, confirm.text)
        archive = self.client.post(f"/api/v1/inspection-tasks/{task_id}/archive-current-round", headers=headers)
        self.assertEqual(archive.status_code, 200, archive.text)

    def test_permission_management_does_not_grant_business_permissions(self):
        self._create_user("perm_mgr", ["super_admin"])
        headers = self._login_headers("perm_mgr")

        project = self.client.post(
            "/api/v1/projects",
            headers=headers,
            json={
                "project_name": "P-permission-manager",
                "customer": "ACME",
                "receive_date": "2026-06-30",
                "vdrive_url": "https://vdrive.example.com/?folderGuid=PERM",
            },
        )

        self.assertEqual(project.status_code, 403, project.text)

    def test_permission_management_has_no_business_data_scope(self):
        self._create_user("perm_scope_only", ["super_admin"])
        headers = self._login_headers("perm_scope_only")
        project_id = self._create_project("P-permission-scope", "PERMISSION-SCOPE")

        for path in (
            "/api/v1/projects",
            f"/api/v1/projects/{project_id}",
            "/api/v1/inspection-tasks",
            "/api/v1/rectification-items",
            "/api/v1/followup-items",
            "/api/v1/reports",
        ):
            response = self.client.get(path, headers=headers)
            self.assertEqual(response.status_code, 403, f"{path}: {response.text}")

    def test_inspection_engineer_scope_is_created_tasks(self):
        self._publish_manual_rule("AUTH-SCOPE-OWN")
        own_project_id = self._create_project("P-own-task", "OWN-TASK")
        other_project_id = self._create_project("P-other-task", "OTHER-TASK")
        engineer = self._create_user("scope_engineer", ["inspection_engineer"])
        other_engineer = self._create_user("other_scope_engineer", ["inspection_engineer"])
        engineer_headers = self._login_headers("scope_engineer")
        other_headers = self._login_headers("other_scope_engineer")

        own_task_id = self._create_task(engineer_headers, own_project_id)
        other_task_id = self._create_task(other_headers, other_project_id)

        own_task = self.client.get(f"/api/v1/inspection-tasks/{own_task_id}", headers=engineer_headers)
        self.assertEqual(own_task.status_code, 200, own_task.text)
        self.assertEqual(own_task.json()["data"]["created_by"], engineer["id"])

        task_list = self.client.get("/api/v1/inspection-tasks", headers=engineer_headers)
        self.assertEqual(task_list.status_code, 200, task_list.text)
        self.assertEqual([item["id"] for item in task_list.json()["data"]["items"]], [own_task_id])

        project_list = self.client.get("/api/v1/projects", headers=engineer_headers)
        self.assertEqual(project_list.status_code, 200, project_list.text)
        self.assertEqual([item["id"] for item in project_list.json()["data"]["items"]], [own_project_id])

        own_project = self.client.get(f"/api/v1/projects/{own_project_id}", headers=engineer_headers)
        self.assertEqual(own_project.status_code, 200, own_project.text)

        other_project = self.client.get(f"/api/v1/projects/{other_project_id}", headers=engineer_headers)
        self.assertEqual(other_project.status_code, 403, other_project.text)

        other_task = self.client.get(f"/api/v1/inspection-tasks/{other_task_id}", headers=engineer_headers)
        self.assertEqual(other_task.status_code, 403, other_task.text)

        other_item_id = self._current_item_id(other_headers, other_task_id)
        other_item = self.client.get(f"/api/v1/inspection-items/{other_item_id}", headers=engineer_headers)
        self.assertEqual(other_item.status_code, 403, other_item.text)

        reports = self.client.get("/api/v1/reports", headers=engineer_headers)
        self.assertEqual(reports.status_code, 200, reports.text)
        self.assertEqual([item["inspection_task_id"] for item in reports.json()["data"]["items"]], [own_task_id])

    def test_inspection_engineer_cannot_mutate_other_users_task(self):
        self._publish_manual_rule("AUTH-SCOPE-MUTATE")
        project_id = self._create_project("P-other-mutate", "OTHER-MUTATE")
        self._create_user("mutating_engineer", ["inspection_engineer"])
        self._create_user("owning_engineer", ["inspection_engineer"])
        mutating_headers = self._login_headers("mutating_engineer")
        owning_headers = self._login_headers("owning_engineer")

        task_id = self._create_task(owning_headers, project_id)
        item_id = self._current_item_id(owning_headers, task_id)

        confirm = self.client.post(
            f"/api/v1/inspection-items/{item_id}/confirm",
            headers=mutating_headers,
            json={"decision_result": "pass", "decision_text": "Not my task."},
        )
        self.assertEqual(confirm.status_code, 403, confirm.text)

        archive = self.client.post(f"/api/v1/inspection-tasks/{task_id}/archive-current-round", headers=mutating_headers)
        self.assertEqual(archive.status_code, 403, archive.text)

        voided = self.client.post(
            f"/api/v1/inspection-tasks/{task_id}/void",
            headers=mutating_headers,
            json={"void_reason": "Not my task."},
        )
        self.assertEqual(voided.status_code, 403, voided.text)

    def test_project_admin_has_full_business_scope_and_combined_permissions_can_operate(self):
        self._publish_manual_rule("AUTH-SCOPE-ADMIN")
        project_id = self._create_project("P-admin-scope", "ADMIN-SCOPE")
        self._create_user("task_owner", ["inspection_engineer"])
        self._create_user("scope_project_admin", ["project_admin"])
        self._create_user("scope_combo", ["inspection_engineer", "project_admin"])
        owner_headers = self._login_headers("task_owner")
        project_admin_headers = self._login_headers("scope_project_admin")
        combo_headers = self._login_headers("scope_combo")

        task_id = self._create_task(owner_headers, project_id)
        item_id = self._current_item_id(project_admin_headers, task_id)

        task_list = self.client.get("/api/v1/inspection-tasks", headers=project_admin_headers)
        self.assertEqual(task_list.status_code, 200, task_list.text)
        self.assertIn(task_id, [item["id"] for item in task_list.json()["data"]["items"]])

        project_list = self.client.get("/api/v1/projects", headers=project_admin_headers)
        self.assertEqual(project_list.status_code, 200, project_list.text)
        self.assertIn(project_id, [item["id"] for item in project_list.json()["data"]["items"]])

        project_detail = self.client.get(f"/api/v1/projects/{project_id}", headers=project_admin_headers)
        self.assertEqual(project_detail.status_code, 200, project_detail.text)

        project_admin_confirm = self.client.post(
            f"/api/v1/inspection-items/{item_id}/confirm",
            headers=project_admin_headers,
            json={"decision_result": "pass", "decision_text": "Project admin can read but not inspect."},
        )
        self.assertEqual(project_admin_confirm.status_code, 403, project_admin_confirm.text)

        combo_confirm = self.client.post(
            f"/api/v1/inspection-items/{item_id}/confirm",
            headers=combo_headers,
            json={"decision_result": "pass", "decision_text": "Combined permission can inspect all tasks."},
        )
        self.assertEqual(combo_confirm.status_code, 200, combo_confirm.text)

    def test_work_item_lists_follow_task_creator_scope(self):
        self._publish_manual_rule("AUTH-SCOPE-WORK")
        fail_project_id = self._create_project("P-fail-work", "FAIL-WORK")
        followup_project_id = self._create_project("P-followup-work", "FOLLOWUP-WORK")
        self._create_user("fail_owner", ["inspection_engineer"])
        self._create_user("followup_owner", ["inspection_engineer"])
        self._create_user("work_project_admin", ["project_admin"])
        fail_headers = self._login_headers("fail_owner")
        followup_headers = self._login_headers("followup_owner")
        project_admin_headers = self._login_headers("work_project_admin")

        fail_task_id = self._create_task(fail_headers, fail_project_id)
        followup_task_id = self._create_task(followup_headers, followup_project_id)
        self._archive_single_item_task(fail_headers, fail_task_id, "fail")
        self._archive_single_item_task(followup_headers, followup_task_id, "conditional")

        fail_owner_rectifications = self.client.get("/api/v1/rectification-items", headers=fail_headers)
        self.assertEqual(fail_owner_rectifications.status_code, 200, fail_owner_rectifications.text)
        self.assertEqual(
            [item["inspection_task_id"] for item in fail_owner_rectifications.json()["data"]["items"]],
            [fail_task_id],
        )

        fail_owner_followups = self.client.get("/api/v1/followup-items", headers=fail_headers)
        self.assertEqual(fail_owner_followups.status_code, 200, fail_owner_followups.text)
        self.assertEqual(fail_owner_followups.json()["data"]["items"], [])

        project_admin_rectifications = self.client.get("/api/v1/rectification-items", headers=project_admin_headers)
        self.assertEqual(project_admin_rectifications.status_code, 200, project_admin_rectifications.text)
        self.assertEqual(
            [item["inspection_task_id"] for item in project_admin_rectifications.json()["data"]["items"]],
            [fail_task_id],
        )

        project_admin_followups = self.client.get("/api/v1/followup-items", headers=project_admin_headers)
        self.assertEqual(project_admin_followups.status_code, 200, project_admin_followups.text)
        self.assertEqual(
            [item["inspection_task_id"] for item in project_admin_followups.json()["data"]["items"]],
            [followup_task_id],
        )

    def test_deleted_project_business_entries_are_blocked(self):
        self._publish_manual_rule("AUTH-DELETED-PROJECT")
        project_id = self._create_project("P-deleted-business", "DELETED-BUSINESS")
        self._create_user("deleted_project_owner", ["inspection_engineer"])
        self._create_user("deleted_project_admin", ["project_admin"])
        owner_headers = self._login_headers("deleted_project_owner")
        project_admin_headers = self._login_headers("deleted_project_admin")

        task_id = self._create_task(owner_headers, project_id)
        item_id = self._current_item_id(owner_headers, task_id)
        confirm = self.client.post(
            f"/api/v1/inspection-items/{item_id}/confirm",
            headers=owner_headers,
            json={
                "decision_result": "fail",
                "decision_text": "Deleted project should hide business entries.",
                "responsible_owner": "MQD",
                "planned_finish_date": "2026-07-15",
            },
        )
        self.assertEqual(confirm.status_code, 200, confirm.text)
        archive = self.client.post(f"/api/v1/inspection-tasks/{task_id}/archive-current-round", headers=owner_headers)
        self.assertEqual(archive.status_code, 200, archive.text)
        report_id = self.client.get("/api/v1/reports", headers=owner_headers).json()["data"]["items"][0]["id"]
        rectification_id = self.client.get("/api/v1/rectification-items", headers=owner_headers).json()["data"]["items"][0]["id"]

        deleted = self.client.request(
            "DELETE",
            f"/api/v1/projects/{project_id}",
            headers=project_admin_headers,
            json={"confirm_project_name": "P-deleted-business", "delete_reason": "scope test"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)

        for path in (
            f"/api/v1/projects/{project_id}",
            f"/api/v1/inspection-tasks/{task_id}",
            f"/api/v1/inspection-tasks/{task_id}/current-round/items",
            f"/api/v1/inspection-items/{item_id}",
            f"/api/v1/reports/{report_id}",
        ):
            response = self.client.get(path, headers=project_admin_headers)
            self.assertEqual(response.status_code, 400, f"{path}: {response.text}")
            self.assertEqual(response.json()["error"]["code"], "PROJECT_DELETED")

        mark_done = self.client.post(
            f"/api/v1/rectification-items/{rectification_id}/mark-done",
            headers=owner_headers,
        )
        self.assertEqual(mark_done.status_code, 400, mark_done.text)
        self.assertEqual(mark_done.json()["error"]["code"], "PROJECT_DELETED")

        for path in (
            "/api/v1/projects",
            "/api/v1/inspection-tasks",
            "/api/v1/rectification-items",
            "/api/v1/reports",
        ):
            response = self.client.get(path, headers=project_admin_headers)
            self.assertEqual(response.status_code, 200, f"{path}: {response.text}")
            self.assertEqual(response.json()["data"]["items"], [])

    def test_business_permissions_are_independent(self):
        project_user = self._create_user("project_admin_only", ["project_admin"])
        project_headers = self._login_headers("project_admin_only")

        project = self.client.post(
            "/api/v1/projects",
            headers=project_headers,
            json={
                "project_name": "P-project-admin",
                "customer": "ACME",
                "receive_date": "2026-06-30",
                "mq_user_id": project_user["id"],
                "vdrive_url": "https://vdrive.example.com/?folderGuid=PROJ",
            },
        )
        self.assertEqual(project.status_code, 200, project.text)

        rule = self.client.post(
            "/api/v1/business-rule-versions",
            headers=project_headers,
            json={"qg_node_id": 1, "version_no": "P1", "change_summary": "project user cannot edit rules"},
        )
        self.assertEqual(rule.status_code, 403, rule.text)

    def test_list_users_supports_permission_filter_and_hides_deleted_by_default(self):
        user = self._create_user("delete_me", ["inspection_engineer"])

        filtered = self.client.get(
            "/api/v1/users?permission=inspection_engineer",
            headers=self.admin_headers,
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertIn("delete_me", [item["uid"] for item in filtered.json()["data"]["items"]])

        deleted = self.client.delete(f"/api/v1/users/{user['id']}", headers=self.admin_headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)

        listed = self.client.get("/api/v1/users", headers=self.admin_headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertNotIn("delete_me", [item["uid"] for item in listed.json()["data"]["items"]])

        deleted_status = self.client.get("/api/v1/users?status=deleted", headers=self.admin_headers)
        self.assertEqual(deleted_status.status_code, 200, deleted_status.text)
        self.assertEqual(deleted_status.json()["data"]["items"], [])

        deleted_status_with_permission = self.client.get(
            "/api/v1/users?status=deleted&permission=inspection_engineer",
            headers=self.admin_headers,
        )
        self.assertEqual(deleted_status_with_permission.status_code, 200, deleted_status_with_permission.text)
        self.assertEqual(deleted_status_with_permission.json()["data"]["items"], [])

        login = self.client.post("/api/v1/auth/login", json={"uid": "delete_me", "password": "delete_me"})
        self.assertEqual(login.status_code, 401, login.text)

    def test_rule_read_requires_rule_or_business_permission(self):
        version_id = self._publish_manual_rule("AUTH-RULE-READ")
        self._create_user("rule_reader_denied", ["super_admin"])
        self._create_user("rule_reader_rules", ["rules_admin"])
        self._create_user("rule_reader_inspection", ["inspection_engineer"])
        self._create_user("rule_reader_project", ["project_admin"])

        denied_headers = self._login_headers("rule_reader_denied")
        for path in (
            "/api/v1/qg-nodes",
            "/api/v1/business-rule-versions",
            f"/api/v1/business-rule-versions/{version_id}",
        ):
            response = self.client.get(path, headers=denied_headers)
            self.assertEqual(response.status_code, 403, f"{path}: {response.text}")

        for uid in ("rule_reader_rules", "rule_reader_inspection", "rule_reader_project"):
            headers = self._login_headers(uid)
            for path in (
                "/api/v1/qg-nodes",
                "/api/v1/business-rule-versions",
                f"/api/v1/business-rule-versions/{version_id}",
            ):
                response = self.client.get(path, headers=headers)
                self.assertEqual(response.status_code, 200, f"{uid} {path}: {response.text}")

    def test_deleted_user_history_snapshots_remain_readable(self):
        user = self._create_user("snapshot_user", ["inspection_engineer"])
        project = self.client.post(
            "/api/v1/projects",
            headers=self.admin_headers,
            json={
                "project_name": "P-history",
                "customer": "ACME",
                "receive_date": "2026-06-30",
                "mq_user_id": user["id"],
                "vdrive_url": "https://vdrive.example.com/?folderGuid=HISTORY",
            },
        )
        self.assertEqual(project.status_code, 200, project.text)
        project_id = project.json()["data"]["id"]

        deleted = self.client.delete(f"/api/v1/users/{user['id']}", headers=self.admin_headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)

        fetched = self.client.get(f"/api/v1/projects/{project_id}", headers=self.admin_headers)
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json()["data"]["mq_user_name_snapshot"], "SNAPSHOT_USER")

    def test_disabled_user_cannot_login_and_existing_token_is_rejected(self):
        user = self._create_user("disable_lifecycle", ["inspection_engineer"])
        headers = self._login_headers("disable_lifecycle")

        disabled = self.client.post(f"/api/v1/users/{user['id']}/disable", headers=self.admin_headers)
        self.assertEqual(disabled.status_code, 200, disabled.text)

        relogin = self.client.post(
            "/api/v1/auth/login",
            json={"uid": "disable_lifecycle", "password": "disable_lifecycle"},
        )
        self.assertEqual(relogin.status_code, 401, relogin.text)

        me = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me.status_code, 401, me.text)
        self.assertEqual(me.json()["error"]["code"], "UNAUTHORIZED")

        enabled = self.client.post(f"/api/v1/users/{user['id']}/enable", headers=self.admin_headers)
        self.assertEqual(enabled.status_code, 200, enabled.text)

        relogin_after_enable = self.client.post(
            "/api/v1/auth/login",
            json={"uid": "disable_lifecycle", "password": "disable_lifecycle"},
        )
        self.assertEqual(relogin_after_enable.status_code, 200, relogin_after_enable.text)

    def test_deleted_user_cannot_login_and_history_snapshot_remains_readable(self):
        user = self._create_user("delete_lifecycle", ["inspection_engineer"])
        project = self.client.post(
            "/api/v1/projects",
            headers=self.admin_headers,
            json={
                "project_name": "P-delete-lifecycle",
                "customer": "ACME",
                "receive_date": "2026-06-30",
                "mq_user_id": user["id"],
                "vdrive_url": "https://vdrive.example.com/?folderGuid=DELETE-LIFECYCLE",
            },
        )
        self.assertEqual(project.status_code, 200, project.text)
        project_id = project.json()["data"]["id"]

        deleted = self.client.delete(f"/api/v1/users/{user['id']}", headers=self.admin_headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)

        login = self.client.post(
            "/api/v1/auth/login",
            json={"uid": "delete_lifecycle", "password": "delete_lifecycle"},
        )
        self.assertEqual(login.status_code, 401, login.text)

        fetched = self.client.get(f"/api/v1/projects/{project_id}", headers=self.admin_headers)
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json()["data"]["mq_user_name_snapshot"], "DELETE_LIFECYCLE")

    def test_account_lifecycle_and_settings_write_audit_logs(self):
        user = self._create_user("audit_lifecycle", ["inspection_engineer"])

        updated = self.client.put(
            f"/api/v1/users/{user['id']}",
            headers=self.admin_headers,
            json={
                "name": "Audit Lifecycle Updated",
                "email": "audit-updated@example.com",
                "status": "active",
                "permissions": ["inspection_engineer", "rules_admin"],
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)

        permission_update = self.client.put(
            f"/api/v1/users/{user['id']}/permissions",
            headers=self.admin_headers,
            json={"permissions": ["inspection_engineer"]},
        )
        self.assertEqual(permission_update.status_code, 200, permission_update.text)

        disabled = self.client.post(f"/api/v1/users/{user['id']}/disable", headers=self.admin_headers)
        self.assertEqual(disabled.status_code, 200, disabled.text)

        enabled = self.client.post(f"/api/v1/users/{user['id']}/enable", headers=self.admin_headers)
        self.assertEqual(enabled.status_code, 200, enabled.text)

        deleted = self.client.delete(f"/api/v1/users/{user['id']}", headers=self.admin_headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)

        settings = self.client.put(
            "/api/v1/system-settings/auto_check_enabled",
            headers=self.admin_headers,
            json={"value": False},
        )
        self.assertEqual(settings.status_code, 200, settings.text)

        self.assertEqual(
            self._audit_actions_for_entity("user", user["id"]),
            [
                "delete_user",
                "enable_user",
                "disable_user",
                "update_user_permissions",
                "update_user",
                "create_user",
            ],
        )
        self.assertIn("save_system_setting", self._audit_actions_for_entity("system_setting", None))

    def test_account_protection_rules(self):
        other_manager = self._create_user("other_manager", ["super_admin"])
        other_headers = self._login_headers("other_manager")

        self_delete = self.client.delete(f"/api/v1/users/{other_manager['id']}", headers=other_headers)
        self.assertEqual(self_delete.status_code, 400, self_delete.text)

        self_disable = self.client.post(f"/api/v1/users/{other_manager['id']}/disable", headers=other_headers)
        self.assertEqual(self_disable.status_code, 400, self_disable.text)

        remove_own_permission = self.client.put(
            f"/api/v1/users/{other_manager['id']}",
            headers=other_headers,
            json={
                "name": "Other Manager",
                "email": "other_manager@example.com",
                "status": "active",
                "permissions": ["inspection_engineer"],
            },
        )
        self.assertEqual(remove_own_permission.status_code, 400, remove_own_permission.text)

    def test_system_keeps_at_least_one_active_permission_manager(self):
        admin_user = self.client.get("/api/v1/auth/me", headers=self.admin_headers).json()["data"]

        update = self.client.put(
            f"/api/v1/users/{admin_user['id']}/permissions",
            headers=self.admin_headers,
            json={"permissions": ["inspection_engineer"]},
        )
        self.assertEqual(update.status_code, 400, update.text)

        disabled = self.client.post(f"/api/v1/users/{admin_user['id']}/disable", headers=self.admin_headers)
        self.assertEqual(disabled.status_code, 400, disabled.text)

        deleted = self.client.delete(f"/api/v1/users/{admin_user['id']}", headers=self.admin_headers)
        self.assertEqual(deleted.status_code, 400, deleted.text)


if __name__ == "__main__":
    unittest.main()
