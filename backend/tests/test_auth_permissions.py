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

        login = self.client.post("/api/v1/auth/login", json={"uid": "delete_me", "password": "delete_me"})
        self.assertEqual(login.status_code, 401, login.text)

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
