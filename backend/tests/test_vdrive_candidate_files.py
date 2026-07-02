import os
import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient` is deprecated.*")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
os.environ["CHECKFLOW_DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient


class VDriveCandidateFileTest(unittest.TestCase):
    def setUp(self):
        from app.core.database import reset_database
        from app.main import app
        from app.seed import seed_database

        reset_database()
        seed_database()
        self.client = TestClient(app, raise_server_exceptions=False)
        self.headers = self._login_headers("admin", "admin")
        self.task_counter = 0

    def tearDown(self):
        from app.core.database import close_database

        close_database()

    def _login_headers(self, uid: str, password: str | None = None) -> dict[str, str]:
        response = self.client.post("/api/v1/auth/login", json={"uid": uid, "password": password or uid})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}

    def _create_auto_task(
        self,
        config_json: dict | None = None,
        *,
        check_type: str = "file_existence",
        execution_mode: str = "file_existence",
        adapter_type: str = "vdrive",
    ) -> int:
        self.task_counter += 1
        project = self.client.post(
            "/api/v1/projects",
            headers=self.headers,
            json={
                "project_name": f"VDrive Candidate Project {self.task_counter}",
                "customer": "ACME",
                "receive_date": "2026-06-30",
                "vdrive_url": f"https://docs.desaysv.com/indrive#/index?id=enterprise_candidate-root-{self.task_counter}",
            },
        )
        self.assertEqual(project.status_code, 200, project.text)
        project_id = project.json()["data"]["id"]
        version = self.client.post(
            "/api/v1/business-rule-versions",
            headers=self.headers,
            json={"qg_node_id": 1, "version_no": f"V-CANDIDATE-{self.task_counter}", "change_summary": "candidate test"},
        )
        self.assertEqual(version.status_code, 200, version.text)
        version_id = version.json()["data"]["id"]
        rule = self.client.post(
            f"/api/v1/business-rule-versions/{version_id}/business-check-rules",
            headers=self.headers,
            json={
                "rule_code": "PFMEA_FILE",
                "item_name": "PFMEA file checklist",
                "item_type": "system" if execution_mode == "system_direct" else "auto",
                "check_type": check_type,
                "checklist_requirement": "PFMEA evidence file exists.",
                "owner_dept": "MQD",
                "sort_order": 1,
            },
        )
        self.assertEqual(rule.status_code, 200, rule.text)
        execution = self.client.post(
            f"/api/v1/business-check-rules/{rule.json()['data']['id']}/auto-check-execution-rules",
            headers=self.headers,
            json={
                "execution_mode": execution_mode,
                "adapter_type": adapter_type,
                "is_enabled": True,
                "config_json": config_json or {"candidate_keywords": ["PFMEA"]},
            },
        )
        self.assertEqual(execution.status_code, 200, execution.text)
        published = self.client.post(f"/api/v1/business-rule-versions/{version_id}/publish", headers=self.headers)
        self.assertEqual(published.status_code, 200, published.text)
        task = self.client.post(
            "/api/v1/inspection-tasks",
            headers=self.headers,
            json={"project_id": project_id, "qg_node_id": 1},
        )
        self.assertEqual(task.status_code, 200, task.text)
        items = self.client.get(
            f"/api/v1/inspection-tasks/{task.json()['data']['inspection_task_id']}/current-round/items",
            headers=self.headers,
        )
        self.assertEqual(items.status_code, 200, items.text)
        return items.json()["data"]["items"][0]["id"]

    def test_task_creation_runs_file_existence_scan_without_mock_auto_result(self):
        item_id = self._create_auto_task({"candidate_keywords": ["PFMEA_V3"]})

        item = self.client.get(f"/api/v1/inspection-items/{item_id}", headers=self.headers)
        self.assertEqual(item.status_code, 200, item.text)
        self.assertEqual(item.json()["data"]["status"], "auto_completed")
        results = self.client.get(f"/api/v1/inspection-items/{item_id}/auto-check-results", headers=self.headers)
        self.assertEqual(results.status_code, 200, results.text)
        latest = results.json()["data"]["items"][-1]
        self.assertEqual(latest["auto_status"], "success")
        self.assertEqual(latest["auto_result"], "pass")
        self.assertNotIn("Mock adapter", latest["evidence_text"])
        self.assertEqual(latest["candidate_files"][0]["file_name"], "PFMEA_V3.xlsx")

    def test_task_creation_marks_stale_freshness_file_failed_but_waits_for_engineer_confirmation(self):
        item_id = self._create_auto_task({"candidate_keywords": ["PFMEA_V2"], "freshness_days": 1})

        item = self.client.get(f"/api/v1/inspection-items/{item_id}", headers=self.headers)
        self.assertEqual(item.status_code, 200, item.text)
        self.assertEqual(item.json()["data"]["status"], "auto_completed")
        self.assertIsNone(item.json()["data"]["final_result"])
        results = self.client.get(f"/api/v1/inspection-items/{item_id}/auto-check-results", headers=self.headers)
        self.assertEqual(results.status_code, 200, results.text)
        latest = results.json()["data"]["items"][-1]
        self.assertEqual(latest["auto_status"], "success")
        self.assertEqual(latest["auto_result"], "fail")
        self.assertIn("超过 1 天", latest["evidence_text"])

    def test_task_creation_degrades_content_and_system_direct_checks_to_manual_required(self):
        content_item_id = self._create_auto_task(
            {"candidate_keywords": ["PFMEA"], "manual_reason": "文件内容解析暂未接入"},
            check_type="content_check",
            execution_mode="file_content",
        )
        system_item_id = self._create_auto_task(
            {"target_system": "QMS", "manual_reason": "QMS 直连暂未接入"},
            check_type="system_direct",
            execution_mode="system_direct",
            adapter_type="qms",
        )

        for item_id, expected_text in (
            (content_item_id, "文件内容解析暂未接入"),
            (system_item_id, "QMS 直连暂未接入"),
        ):
            item = self.client.get(f"/api/v1/inspection-items/{item_id}", headers=self.headers)
            self.assertEqual(item.status_code, 200, item.text)
            self.assertEqual(item.json()["data"]["status"], "manual_required")
            results = self.client.get(f"/api/v1/inspection-items/{item_id}/auto-check-results", headers=self.headers)
            self.assertEqual(results.status_code, 200, results.text)
            latest = results.json()["data"]["items"][-1]
            self.assertEqual(latest["auto_status"], "manual_required")
            self.assertEqual(latest["auto_result"], "manual_required")
            self.assertIn(expected_text, latest["evidence_text"])

    def test_task_creation_degrades_auto_checks_when_auto_check_setting_is_disabled(self):
        from app.core.database import execute, to_json
        from app.core.enums import SystemSettingKey

        execute(
            "UPDATE system_settings SET value_json = ? WHERE key = ?",
            (to_json(False), SystemSettingKey.AUTO_CHECK_ENABLED),
        )
        item_id = self._create_auto_task({"candidate_keywords": ["PFMEA_V3"]})

        item = self.client.get(f"/api/v1/inspection-items/{item_id}", headers=self.headers)
        self.assertEqual(item.status_code, 200, item.text)
        self.assertEqual(item.json()["data"]["status"], "manual_required")
        results = self.client.get(f"/api/v1/inspection-items/{item_id}/auto-check-results", headers=self.headers)
        self.assertEqual(results.status_code, 200, results.text)
        latest = results.json()["data"]["items"][-1]
        self.assertEqual(latest["auto_status"], "manual_required")
        self.assertIn("自动检查开关已关闭", latest["evidence_text"])

    def test_mock_vdrive_lists_files_recursively_with_vdrive_field_mapping(self):
        from app.vdrive import MockVDriveAdapter

        adapter = MockVDriveAdapter()
        root = adapter.validate_folder_link("https://docs.desaysv.com/indrive#/index?id=enterprise_candidate-root")
        files = adapter.list_files(root["folder_id"])

        self.assertTrue(files)
        pfmea = next(file for file in files if file["file_name"] == "PFMEA_V3.xlsx")
        self.assertEqual(pfmea["vdrive_file_id"], 9001)
        self.assertEqual(pfmea["file_guid"], "file-guid-pfmea-v3")
        self.assertEqual(pfmea["file_ext"], ".xlsx")
        self.assertEqual(pfmea["file_version"], "3.0")
        self.assertEqual(pfmea["created_time"], "2026-06-25 18:00:00")
        self.assertIsNone(pfmea["modified_time"])
        self.assertEqual(pfmea["file_path"], "/mock/candidate-root/QG3/PFMEA/PFMEA_V3.xlsx")

    def test_real_vdrive_adapter_maps_folder_guid_response_fields(self):
        from app.vdrive import RealVDriveAdapter

        class FakeRealVDriveAdapter(RealVDriveAdapter):
            def _request(self, path, params):
                self.seen = {"path": path, "params": params}
                return {
                    "result": 0,
                    "data": {
                        "FolderId": 123,
                        "ParentFolderId": 1,
                        "FolderName": "A项目资料",
                        "FolderPath": "1\\806\\123",
                        "CreateTime": "2026-06-30 10:00:00",
                        "CreatorName": "MQD",
                        "IsDeleted": False,
                    },
                }

        adapter = FakeRealVDriveAdapter(base_url="https://docs.desaysv.com", token="token")
        folder = adapter.validate_folder_link("https://docs.desaysv.com/indrive#/index?id=enterprise_real-guid")

        self.assertEqual(adapter.seen["path"], "/api/services/Folder/GetFolderInfoByGuid")
        self.assertEqual(adapter.seen["params"], {"folderGuid": "real-guid"})
        self.assertEqual(folder["folder_guid"], "real-guid")
        self.assertEqual(folder["folder_id"], 123)
        self.assertEqual(folder["folder_name"], "A项目资料")
        self.assertEqual(folder["folder_path"], "1\\806\\123")
        self.assertFalse(folder["is_deleted"])

    def test_real_vdrive_adapter_paginates_and_recurses_folder_children(self):
        from app.vdrive import RealVDriveAdapter

        class FakeRealVDriveAdapter(RealVDriveAdapter):
            def list_folder_children(self, folder_id, page_num, page_size=100):
                responses = {
                    (10, 1): {
                        "Settings": {"PageNum": 1, "PageSize": 1, "TotalCount": 2},
                        "FilesInfo": [
                            {
                                "FileId": 1,
                                "FileGuid": "root-file",
                                "FileLastVerNumStr": "1.0",
                                "FileName": "root.xlsx",
                                "FileExtName": ".xlsx",
                                "FileLastSize": 100,
                                "FileCreateTime": "2026-06-01 09:00:00",
                                "IsDeleted": False,
                            },
                            {
                                "FileId": 999,
                                "FileGuid": "deleted-root-file",
                                "FileLastVerNumStr": "1.0",
                                "FileName": "deleted.xlsx",
                                "FileExtName": ".xlsx",
                                "FileLastSize": 100,
                                "FileCreateTime": "2026-06-01 09:00:00",
                                "IsDeleted": True,
                            }
                        ],
                        "FoldersInfo": [],
                    },
                    (10, 2): {
                        "Settings": {"PageNum": 2, "PageSize": 1, "TotalCount": 2},
                        "FilesInfo": [],
                        "FoldersInfo": [
                            {"FolderId": 20, "FolderName": "child", "IsDeleted": False},
                            {"FolderId": 99, "FolderName": "deleted-child", "IsDeleted": True},
                        ],
                    },
                    (20, 1): {
                        "Settings": {"PageNum": 1, "PageSize": 100, "TotalCount": 1},
                        "FilesInfo": [
                            {
                                "FileId": 2,
                                "FileGuid": "child-file",
                                "FileLastVerNumStr": "2.0",
                                "FileName": "child.xlsx",
                                "FileExtName": ".xlsx",
                                "FileLastSize": 200,
                                "FileCreateTime": "2026-06-02 09:00:00",
                                "IsDeleted": False,
                            }
                        ],
                        "FoldersInfo": [],
                    },
                }
                return responses[(folder_id, page_num)]

        files = FakeRealVDriveAdapter(base_url="https://docs.desaysv.com", token="token").list_files(10, "/root")

        self.assertEqual([file["file_name"] for file in files], ["root.xlsx", "child.xlsx"])
        self.assertEqual(files[0]["file_path"], "/root/root.xlsx")
        self.assertEqual(files[1]["file_path"], "/root/child/child.xlsx")
        self.assertEqual(files[1]["vdrive_file_id"], 2)
        self.assertEqual(files[1]["file_guid"], "child-file")
        self.assertIsNone(files[1]["modified_time"])

    def test_scan_candidate_files_single_match_marks_auto_completed_and_embeds_candidates(self):
        item_id = self._create_auto_task({"candidate_keywords": ["PFMEA_V3"]})

        scan = self.client.post(f"/api/v1/inspection-items/{item_id}/candidate-files/scan", headers=self.headers)
        self.assertEqual(scan.status_code, 200, scan.text)
        self.assertEqual(scan.json()["data"]["auto_status"], "success")
        self.assertEqual(scan.json()["data"]["auto_result"], "pass")
        self.assertEqual(len(scan.json()["data"]["candidate_files"]), 1)
        self.assertTrue(scan.json()["data"]["candidate_files"][0]["is_selected"])

        item = self.client.get(f"/api/v1/inspection-items/{item_id}", headers=self.headers)
        self.assertEqual(item.status_code, 200, item.text)
        self.assertEqual(item.json()["data"]["status"], "auto_completed")
        results = self.client.get(f"/api/v1/inspection-items/{item_id}/auto-check-results", headers=self.headers)
        self.assertEqual(results.status_code, 200, results.text)
        latest = results.json()["data"]["items"][-1]
        self.assertEqual(latest["auto_status"], "success")
        self.assertEqual(latest["candidate_files"][0]["file_name"], "PFMEA_V3.xlsx")

    def test_scan_candidate_files_multiple_matches_waits_for_selection_then_select_completes(self):
        item_id = self._create_auto_task({"candidate_keywords": ["PFMEA"]})

        scan = self.client.post(f"/api/v1/inspection-items/{item_id}/candidate-files/scan", headers=self.headers)
        self.assertEqual(scan.status_code, 200, scan.text)
        self.assertEqual(scan.json()["data"]["auto_status"], "candidate_waiting")
        self.assertEqual(len(scan.json()["data"]["candidate_files"]), 2)
        item = self.client.get(f"/api/v1/inspection-items/{item_id}", headers=self.headers)
        self.assertEqual(item.json()["data"]["status"], "candidate_waiting")
        overview = self.client.get("/api/v1/dashboard/overview", headers=self.headers)
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(overview.json()["data"]["candidate_waiting_count"], 1)
        self.assertEqual(overview.json()["data"]["manual_required_count"], 0)

        candidates = self.client.get(f"/api/v1/inspection-items/{item_id}/candidate-files", headers=self.headers)
        self.assertEqual(candidates.status_code, 200, candidates.text)
        selected_id = candidates.json()["data"]["items"][0]["id"]
        select = self.client.post(
            f"/api/v1/inspection-items/{item_id}/candidate-files/select",
            headers=self.headers,
            json={"candidate_file_id": selected_id},
        )
        self.assertEqual(select.status_code, 200, select.text)
        self.assertEqual(select.json()["data"]["auto_status"], "success")
        selected = [file for file in select.json()["data"]["candidate_files"] if file["is_selected"]]
        self.assertEqual([file["id"] for file in selected], [selected_id])
        item = self.client.get(f"/api/v1/inspection-items/{item_id}", headers=self.headers)
        self.assertEqual(item.json()["data"]["status"], "auto_completed")

    def test_retry_marks_previous_result_not_latest_and_increments_attempt(self):
        item_id = self._create_auto_task({"candidate_keywords": ["PFMEA_V3"]})
        first = self.client.post(f"/api/v1/inspection-items/{item_id}/candidate-files/scan", headers=self.headers)
        self.assertEqual(first.status_code, 200, first.text)

        retry = self.client.post(f"/api/v1/inspection-items/{item_id}/auto-check/retry", headers=self.headers)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(retry.json()["data"]["attempt_no"], first.json()["data"]["attempt_no"] + 1)

        results = self.client.get(f"/api/v1/inspection-items/{item_id}/auto-check-results", headers=self.headers)
        self.assertEqual(results.status_code, 200, results.text)
        latest_rows = [row for row in results.json()["data"]["items"] if row["is_latest"]]
        self.assertEqual(len(latest_rows), 1)
        self.assertEqual(latest_rows[0]["attempt_no"], retry.json()["data"]["attempt_no"])

    def test_scan_without_candidates_or_vdrive_error_degrades_to_manual_required(self):
        item_id = self._create_auto_task({"candidate_keywords": ["NO_SUCH_FILE"]})
        no_candidate = self.client.post(f"/api/v1/inspection-items/{item_id}/candidate-files/scan", headers=self.headers)
        self.assertEqual(no_candidate.status_code, 200, no_candidate.text)
        self.assertEqual(no_candidate.json()["data"]["auto_status"], "manual_required")
        self.assertEqual(no_candidate.json()["data"]["auto_result"], "not_found")
        overview = self.client.get("/api/v1/dashboard/overview", headers=self.headers)
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(overview.json()["data"]["manual_required_count"], 1)

        error_item_id = self._create_auto_task({"candidate_keywords": ["PFMEA_V3"]})
        with patch("app.services.ai_execution_service.list_vdrive_files_for_item", side_effect=RuntimeError("VDrive timeout")):
            error = self.client.post(f"/api/v1/inspection-items/{error_item_id}/candidate-files/scan", headers=self.headers)
        self.assertEqual(error.status_code, 200, error.text)
        self.assertEqual(error.json()["data"]["auto_status"], "error")
        self.assertEqual(error.json()["data"]["auto_result"], "error")
        item = self.client.get(f"/api/v1/inspection-items/{error_item_id}", headers=self.headers)
        self.assertEqual(item.json()["data"]["status"], "manual_required")

    def test_scan_and_retry_reject_confirmed_item_without_changing_final_result(self):
        item_id = self._create_auto_task({"candidate_keywords": ["PFMEA_V3"]})
        confirm = self.client.post(
            f"/api/v1/inspection-items/{item_id}/confirm",
            headers=self.headers,
            json={"decision_result": "pass", "decision_text": "Already confirmed."},
        )
        self.assertEqual(confirm.status_code, 200, confirm.text)

        scan = self.client.post(f"/api/v1/inspection-items/{item_id}/candidate-files/scan", headers=self.headers)
        self.assertEqual(scan.status_code, 400, scan.text)
        self.assertEqual(scan.json()["error"]["code"], "ITEM_NOT_AUTO_CHECKABLE")
        retry = self.client.post(f"/api/v1/inspection-items/{item_id}/auto-check/retry", headers=self.headers)
        self.assertEqual(retry.status_code, 400, retry.text)
        self.assertEqual(retry.json()["error"]["code"], "ITEM_NOT_AUTO_CHECKABLE")

        item = self.client.get(f"/api/v1/inspection-items/{item_id}", headers=self.headers)
        self.assertEqual(item.status_code, 200, item.text)
        self.assertEqual(item.json()["data"]["status"], "confirmed")
        self.assertEqual(item.json()["data"]["final_result"], "pass")

    def test_candidate_file_actions_follow_business_scope(self):
        item_id = self._create_auto_task({"candidate_keywords": ["PFMEA_V3"]})
        self.client.post(
            "/api/v1/users",
            headers=self.headers,
            json={
                "uid": "candidate_viewer",
                "name": "Candidate Viewer",
                "email": "candidate@example.com",
                "permissions": ["super_admin"],
                "status": "active",
            },
        )
        viewer_headers = self._login_headers("candidate_viewer")

        scan = self.client.post(f"/api/v1/inspection-items/{item_id}/candidate-files/scan", headers=viewer_headers)
        self.assertEqual(scan.status_code, 403, scan.text)
        candidates = self.client.get(f"/api/v1/inspection-items/{item_id}/candidate-files", headers=viewer_headers)
        self.assertEqual(candidates.status_code, 403, candidates.text)


if __name__ == "__main__":
    unittest.main()
