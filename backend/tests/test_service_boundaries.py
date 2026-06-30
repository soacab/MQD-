import importlib
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


class ServiceBoundaryTest(unittest.TestCase):
    def test_backend_service_boundary_modules_are_importable(self):
        module_names = [
            "app.api.deps",
            "app.api.responses",
            "app.api.routers.auth",
            "app.api.routers.projects",
            "app.api.routers.rules",
            "app.api.routers.inspection",
            "app.api.routers.reports",
            "app.repositories.common",
            "app.services.ai_execution_service",
            "app.services.inspection_service",
            "app.services.permission_service",
            "app.services.report_service",
            "app.services.rule_service",
        ]

        for module_name in module_names:
            importlib.import_module(module_name)


    def test_main_only_wires_application_and_routers(self):
        main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
        main_text = main_path.read_text(encoding="utf-8")

        self.assertNotIn('@app.post("/api/v1/', main_text)
        self.assertNotIn('@app.get("/api/v1/', main_text)
        self.assertNotIn("def archive_current_round(", main_text)
        self.assertNotIn("def require_task_scope(", main_text)
        self.assertLessEqual(len(main_text.splitlines()), 90)
