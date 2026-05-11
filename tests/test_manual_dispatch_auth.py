import importlib
import os
import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    LoginOperatorAccountRequest,
    RegisterOperatorAccountRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


class ManualDispatchAuthTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"auth-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_registering_new_account_returns_identity_only(self):
        identity = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name=" Mandy ",
                password="secret123",
                confirm_password="secret123",
            )
        )

        self.assertEqual("Mandy", identity.account_name)
        self.assertGreater(identity.account_id, 0)
        self.assertFalse(hasattr(identity, "password_hash"))
        self.assertFalse(hasattr(identity, "password_salt"))

    def test_rejects_duplicate_account_name(self):
        self._register("Mandy")

        with self.assertRaisesRegex(ValueError, "Account name already exists"):
            self._register("mandy")

    def test_rejects_invalid_account_name(self):
        with self.assertRaisesRegex(
            ValueError,
            "account_name must be between 2 and 50 characters",
        ):
            self._register("M")

    def test_rejects_invalid_password(self):
        with self.assertRaisesRegex(ValueError, "password must be at least"):
            self.service.register_operator_account(
                RegisterOperatorAccountRequest(
                    account_name="Mandy",
                    password="123",
                    confirm_password="123",
                )
            )

    def test_rejects_mismatched_confirm_password(self):
        with self.assertRaisesRegex(ValueError, "Passwords do not match"):
            self.service.register_operator_account(
                RegisterOperatorAccountRequest(
                    account_name="Mandy",
                    password="secret123",
                    confirm_password="different",
                )
            )

    def test_rejects_missing_confirm_password(self):
        with self.assertRaisesRegex(ValueError, "confirm_password is required"):
            self.service.register_operator_account(
                RegisterOperatorAccountRequest(
                    account_name="Mandy",
                    password="secret123",
                )
            )

    def test_login_success_with_correct_password(self):
        self._register("Mandy")

        identity = self.service.login_operator_account(
            LoginOperatorAccountRequest(account_name="Mandy", password="secret123")
        )

        self.assertEqual("Mandy", identity.account_name)

    def test_login_failure_with_wrong_password_uses_safe_message(self):
        self._register("Mandy")

        with self.assertRaisesRegex(ValueError, "Invalid account name or password"):
            self.service.login_operator_account(
                LoginOperatorAccountRequest(account_name="Mandy", password="wrongpass")
            )

    def test_password_is_stored_as_hash_and_salt_not_plain_text(self):
        self._register("Mandy")

        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT password_hash, password_salt
                FROM operator_accounts
                WHERE account_name = ?
                """,
                ("Mandy",),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertNotEqual("secret123", row[0])
        self.assertNotEqual("secret123", row[1])
        self.assertGreater(len(row[0]), 32)
        self.assertGreater(len(row[1]), 16)

    def _register(self, account_name):
        return self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name=account_name,
                password="secret123",
                confirm_password="secret123",
            )
        )


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient is not installed")
class ManualDispatchAuthRouteTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"auth-route-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service

        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.api_module.service = self.original_service
        if self.previous_db_path is None:
            os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
        else:
            os.environ["MANUAL_DISPATCH_DB_PATH"] = self.previous_db_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_and_login_routes_return_identity_only(self):
        register_response = self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        login_response = self.client.post(
            "/api/manual-dispatch/auth/login",
            json={"account_name": "Mandy", "password": "secret123"},
        )

        self.assertEqual(200, register_response.status_code)
        self.assertEqual(200, login_response.status_code)
        self.assertEqual("Mandy", login_response.json()["account_name"])
        self.assertNotIn("password_hash", login_response.json())
        self.assertNotIn("password_salt", login_response.json())

    def test_login_route_rejects_wrong_password(self):
        self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )

        response = self.client.post(
            "/api/manual-dispatch/auth/login",
            json={"account_name": "Mandy", "password": "wrongpass"},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("Invalid account name or password", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
