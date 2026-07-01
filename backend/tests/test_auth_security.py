import importlib
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

from fastapi import FastAPI
from fastapi.testclient import TestClient


class AuthSecurityTest(unittest.TestCase):
    def setUp(self):
        os.environ["CHECKFLOW_ENV"] = "development"
        os.environ["CHECKFLOW_AUTH_MODE"] = "local"
        from app.core.database import reset_database
        from app.seed import seed_database
        from app.main import app

        reset_database()
        seed_database()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        for key in (
            "CHECKFLOW_ENV",
            "CHECKFLOW_AUTH_MODE",
            "CHECKFLOW_JWT_SECRET",
            "CHECKFLOW_CORS_ORIGINS",
            "CHECKFLOW_IAM_AUTHORIZE_URL",
            "CHECKFLOW_IAM_TOKEN_URL",
            "CHECKFLOW_IAM_PROFILE_URL",
            "CHECKFLOW_IAM_CLIENT_ID",
            "CHECKFLOW_IAM_CLIENT_SECRET",
            "CHECKFLOW_IAM_REDIRECT_URI",
        ):
            os.environ.pop(key, None)
        from app.core.database import close_database

        close_database()

    def test_development_local_login_keeps_seed_accounts_available(self):
        response = self.client.post("/api/v1/auth/login", json={"uid": "admin", "password": "admin"})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["user"]["uid"], "admin")

    def test_production_rejects_development_password_bypass(self):
        from app.core.database import execute

        execute(
            "INSERT INTO users(uid, name, email, status) VALUES (?, ?, ?, ?)",
            ("prod_user", "Production User", "prod_user@example.com", "active"),
        )
        os.environ["CHECKFLOW_ENV"] = "production"
        os.environ["CHECKFLOW_JWT_SECRET"] = "production-secret-at-least-32-bytes-long"

        for uid, password in (("admin", "admin"), ("prod_user", "prod_user")):
            response = self.client.post("/api/v1/auth/login", json={"uid": uid, "password": password})
            self.assertEqual(response.status_code, 401, response.text)
            self.assertEqual(response.json()["error"]["code"], "LOCAL_AUTH_DISABLED")

    def test_production_requires_explicit_jwt_secret(self):
        os.environ["CHECKFLOW_ENV"] = "production"
        os.environ.pop("CHECKFLOW_JWT_SECRET", None)
        import app.core.config as config

        with self.assertRaisesRegex(RuntimeError, "CHECKFLOW_JWT_SECRET"):
            importlib.reload(config).Settings()

    def test_production_cors_rejects_wildcard_origin_with_credentials(self):
        os.environ["CHECKFLOW_ENV"] = "production"
        os.environ["CHECKFLOW_JWT_SECRET"] = "production-secret-at-least-32-bytes-long"
        os.environ["CHECKFLOW_CORS_ORIGINS"] = "*"

        from app.core.cors import configure_cors

        with self.assertRaisesRegex(RuntimeError, "CHECKFLOW_CORS_ORIGINS"):
            configure_cors(FastAPI())

    def test_iam_callback_requires_code(self):
        os.environ["CHECKFLOW_AUTH_MODE"] = "iam"

        response = self.client.get("/api/v1/auth/iam/callback")

        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(response.json()["error"]["code"], "IAM_CODE_REQUIRED")

    def test_iam_callback_rejects_token_exchange_failure(self):
        os.environ["CHECKFLOW_AUTH_MODE"] = "iam"

        with patch("app.services.auth_service.exchange_iam_code_for_token", side_effect=RuntimeError("iam down")):
            response = self.client.get("/api/v1/auth/iam/callback?code=bad-code")

        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()["error"]["code"], "IAM_TOKEN_EXCHANGE_FAILED")

    def test_iam_callback_rejects_profile_without_uid_mapping(self):
        os.environ["CHECKFLOW_AUTH_MODE"] = "iam"

        with (
            patch("app.services.auth_service.exchange_iam_code_for_token", return_value={"access_token": "iam-token"}),
            patch("app.services.auth_service.fetch_iam_profile", return_value={"attributes": {}}),
        ):
            response = self.client.get("/api/v1/auth/iam/callback?code=ok-code")

        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()["error"]["code"], "IAM_PROFILE_UID_MISSING")

    def test_iam_callback_rejects_unknown_or_disabled_local_user(self):
        os.environ["CHECKFLOW_AUTH_MODE"] = "iam"

        with (
            patch("app.services.auth_service.exchange_iam_code_for_token", return_value={"access_token": "iam-token"}),
            patch("app.services.auth_service.fetch_iam_profile", return_value={"attributes": {"account_no": "missing_uid"}}),
        ):
            missing = self.client.get("/api/v1/auth/iam/callback?code=ok-code")

        self.assertEqual(missing.status_code, 401, missing.text)
        self.assertEqual(missing.json()["error"]["code"], "INVALID_UID")

    def test_iam_callback_maps_active_local_user_to_checkflow_token(self):
        os.environ["CHECKFLOW_AUTH_MODE"] = "iam"

        with (
            patch("app.services.auth_service.exchange_iam_code_for_token", return_value={"access_token": "iam-token"}),
            patch("app.services.auth_service.fetch_iam_profile", return_value={"attributes": {"account_no": "admin"}}),
        ):
            response = self.client.get("/api/v1/auth/iam/callback?code=ok-code")

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(data["user"]["uid"], "admin")
        self.assertNotEqual(data["access_token"], "iam-token")


if __name__ == "__main__":
    unittest.main()
