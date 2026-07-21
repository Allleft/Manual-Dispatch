import importlib
import os
import shutil
import sqlite3
import time
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    LoginOperatorAccountRequest,
    RegisterOperatorAccountRequest,
    ResetOperatorPasswordRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from backend.api.manual_dispatch_routes import common as auth_common

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
        self.previous_reset_code = os.environ.get("MANUAL_DISPATCH_ADMIN_RESET_CODE")

    def tearDown(self):
        if self.previous_reset_code is None:
            os.environ.pop("MANUAL_DISPATCH_ADMIN_RESET_CODE", None)
        else:
            os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = self.previous_reset_code
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

    def test_missing_cookie_secret_has_no_known_deterministic_fallback(self):
        previous_secret = os.environ.pop("MANUAL_DISPATCH_AUTH_COOKIE_SECRET", None)
        try:
            fallback = auth_common.operator_cookie_secret()
        finally:
            if previous_secret is not None:
                os.environ["MANUAL_DISPATCH_AUTH_COOKIE_SECRET"] = previous_secret

        self.assertEqual(32, len(fallback))
        self.assertNotEqual(
            b"manual-dispatch-local-operator-cookie",
            fallback,
        )

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

    def test_successful_password_reset_allows_new_password_only(self):
        self._register("Mandy")
        os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = "test-reset-code"

        identity = self.service.reset_operator_password(
            ResetOperatorPasswordRequest(
                account_name="Mandy",
                admin_reset_code="test-reset-code",
                new_password="newsecret123",
                confirm_password="newsecret123",
            )
        )

        self.assertEqual("Mandy", identity.account_name)
        self.assertFalse(hasattr(identity, "password_hash"))
        self.assertFalse(hasattr(identity, "password_salt"))

        with self.assertRaisesRegex(ValueError, "Invalid account name or password"):
            self.service.login_operator_account(
                LoginOperatorAccountRequest(
                    account_name="Mandy",
                    password="secret123",
                )
            )

        login_identity = self.service.login_operator_account(
            LoginOperatorAccountRequest(
                account_name="Mandy",
                password="newsecret123",
            )
        )
        self.assertEqual("Mandy", login_identity.account_name)

    def test_reset_password_rejects_missing_admin_reset_code_environment(self):
        self._register("Mandy")
        os.environ.pop("MANUAL_DISPATCH_ADMIN_RESET_CODE", None)

        with self.assertRaisesRegex(ValueError, "Password reset is not configured"):
            self.service.reset_operator_password(self._reset_request())

    def test_reset_password_rejects_wrong_admin_reset_code(self):
        self._register("Mandy")
        os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = "test-reset-code"

        with self.assertRaisesRegex(
            ValueError,
            "Unable to reset password. Please check your details or contact an administrator.",
        ):
            self.service.reset_operator_password(
                self._reset_request(admin_reset_code="wrong-code")
            )

    def test_reset_password_rejects_invalid_new_password(self):
        self._register("Mandy")
        os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = "test-reset-code"

        with self.assertRaisesRegex(ValueError, "password must be at least"):
            self.service.reset_operator_password(
                self._reset_request(new_password="123", confirm_password="123")
            )

    def test_reset_password_rejects_mismatched_confirm_password(self):
        self._register("Mandy")
        os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = "test-reset-code"

        with self.assertRaisesRegex(ValueError, "Passwords do not match"):
            self.service.reset_operator_password(
                self._reset_request(confirm_password="different")
            )

    def test_reset_password_keeps_new_password_hashed_and_salted(self):
        self._register("Mandy")
        os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = "test-reset-code"

        with sqlite3.connect(self.db_path) as connection:
            before = connection.execute(
                """
                SELECT password_hash, password_salt
                FROM operator_accounts
                WHERE account_name = ?
                """,
                ("Mandy",),
            ).fetchone()

        self.service.reset_operator_password(self._reset_request())

        with sqlite3.connect(self.db_path) as connection:
            after = connection.execute(
                """
                SELECT password_hash, password_salt
                FROM operator_accounts
                WHERE account_name = ?
                """,
                ("Mandy",),
            ).fetchone()

        self.assertNotEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])
        self.assertNotEqual("newsecret123", after[0])
        self.assertNotEqual("newsecret123", after[1])

    def _register(self, account_name):
        return self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name=account_name,
                password="secret123",
                confirm_password="secret123",
            )
        )

    def _reset_request(
        self,
        admin_reset_code="test-reset-code",
        new_password="newsecret123",
        confirm_password="newsecret123",
    ):
        return ResetOperatorPasswordRequest(
            account_name="Mandy",
            admin_reset_code=admin_reset_code,
            new_password=new_password,
            confirm_password=confirm_password,
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
        self.previous_reset_code = os.environ.get("MANUAL_DISPATCH_ADMIN_RESET_CODE")
        self.previous_allow_registration = os.environ.get(
            "MANUAL_DISPATCH_ALLOW_REGISTRATION"
        )
        self.previous_cookie_secret = os.environ.get(
            "MANUAL_DISPATCH_AUTH_COOKIE_SECRET"
        )
        self.previous_cookie_secure = os.environ.get(
            "MANUAL_DISPATCH_AUTH_COOKIE_SECURE"
        )
        os.environ["MANUAL_DISPATCH_ALLOW_REGISTRATION"] = "true"
        os.environ["MANUAL_DISPATCH_AUTH_COOKIE_SECRET"] = (
            "manual-dispatch-auth-route-test-secret-20260721"
        )
        os.environ["MANUAL_DISPATCH_AUTH_COOKIE_SECURE"] = "false"
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
        if self.previous_reset_code is None:
            os.environ.pop("MANUAL_DISPATCH_ADMIN_RESET_CODE", None)
        else:
            os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = self.previous_reset_code
        if self.previous_allow_registration is None:
            os.environ.pop("MANUAL_DISPATCH_ALLOW_REGISTRATION", None)
        else:
            os.environ[
                "MANUAL_DISPATCH_ALLOW_REGISTRATION"
            ] = self.previous_allow_registration
        if self.previous_cookie_secret is None:
            os.environ.pop("MANUAL_DISPATCH_AUTH_COOKIE_SECRET", None)
        else:
            os.environ[
                "MANUAL_DISPATCH_AUTH_COOKIE_SECRET"
            ] = self.previous_cookie_secret
        if self.previous_cookie_secure is None:
            os.environ.pop("MANUAL_DISPATCH_AUTH_COOKIE_SECURE", None)
        else:
            os.environ[
                "MANUAL_DISPATCH_AUTH_COOKIE_SECURE"
            ] = self.previous_cookie_secure
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

    def test_logout_route_returns_success_and_deletes_operator_cookie(self):
        self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        cookie_name = self.api_module.OPERATOR_COOKIE_NAME
        self.assertIn(cookie_name, self.client.cookies)

        response = self.client.post("/api/manual-dispatch/auth/logout")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"logged_out": True}, response.json())
        self.assertNotIn(cookie_name, self.client.cookies)
        set_cookie = response.headers.get("set-cookie", "")
        self.assertIn(f"{cookie_name}=", set_cookie)
        self.assertIn("Max-Age=0", set_cookie)
        self.assertIn("Path=/", set_cookie)

    def test_logout_route_requires_valid_cookie(self):
        cookie_name = self.api_module.OPERATOR_COOKIE_NAME
        self.assertNotIn(cookie_name, self.client.cookies)

        first_response = self.client.post("/api/manual-dispatch/auth/logout")
        second_response = self.client.post("/api/manual-dispatch/auth/logout")

        self.assertEqual(401, first_response.status_code)
        self.assertEqual(401, second_response.status_code)
        self.assertEqual("Authentication required", first_response.json()["detail"])
        self.assertNotIn(cookie_name, self.client.cookies)

    def test_register_route_can_be_disabled_by_environment(self):
        os.environ["MANUAL_DISPATCH_ALLOW_REGISTRATION"] = "false"

        response = self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "Registration is disabled. Please contact an administrator.",
            response.json()["detail"],
        )

    def test_register_route_is_disabled_when_environment_is_absent(self):
        os.environ.pop("MANUAL_DISPATCH_ALLOW_REGISTRATION", None)

        response = self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )

        self.assertEqual(403, response.status_code)

    def test_session_route_restores_valid_identity_and_rejects_missing_cookie(self):
        self._register_and_login_route()

        valid = self.client.get("/api/manual-dispatch/auth/session")
        self.client.cookies.clear()
        missing = self.client.get("/api/manual-dispatch/auth/session")

        self.assertEqual(200, valid.status_code)
        self.assertEqual("Mandy", valid.json()["account_name"])
        self.assertEqual(401, missing.status_code)

    def test_protected_read_write_patch_and_export_reject_missing_cookie(self):
        requests = (
            self.client.get("/api/manual-dispatch/shared/specifications"),
            self.client.post("/api/manual-dispatch/delivery/orders", json={}),
            self.client.patch("/api/manual-dispatch/delivery/orders/ORD-1", json={}),
            self.client.get("/api/manual-dispatch/export-excel"),
            self.client.get("/api/manual-dispatch/board", params={"dispatch_date": "2026-07-21"}),
        )

        self.assertTrue(all(response.status_code == 401 for response in requests))

    def test_forged_and_expired_cookies_are_rejected(self):
        self._register_and_login_route()
        cookie_name = self.api_module.OPERATOR_COOKIE_NAME
        valid_cookie = self.client.cookies.get(cookie_name)
        self.client.cookies.set(cookie_name, f"{valid_cookie}forged")
        forged = self.client.get("/api/manual-dispatch/auth/session")

        account = self.repository.get_operator_account_by_name("Mandy")
        issued_at = int(time.time()) - auth_common.OPERATOR_COOKIE_MAX_AGE_SECONDS - 1
        payload = auth_common._encode_operator_cookie_payload(account, issued_at)
        expired_cookie = f"{payload}.{auth_common.operator_cookie_signature(account, payload)}"
        self.client.cookies.set(cookie_name, expired_cookie)
        expired = self.client.get("/api/manual-dispatch/auth/session")

        self.assertEqual(401, forged.status_code)
        self.assertEqual(401, expired.status_code)

    def test_password_reset_invalidates_existing_cookie(self):
        os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = "test-reset-code"
        self._register_and_login_route()
        cookie_name = self.api_module.OPERATOR_COOKIE_NAME
        old_cookie = self.client.cookies.get(cookie_name)

        reset = self.client.post(
            "/api/manual-dispatch/auth/reset-password",
            json={
                "account_name": "Mandy",
                "admin_reset_code": "test-reset-code",
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )
        self.client.cookies.set(cookie_name, old_cookie)

        self.assertEqual(200, reset.status_code)
        self.assertEqual(401, self.client.get("/api/manual-dispatch/auth/session").status_code)

    def test_secure_cookie_attribute_is_environment_controlled(self):
        os.environ["MANUAL_DISPATCH_AUTH_COOKIE_SECURE"] = "true"

        response = self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )

        set_cookie = response.headers.get("set-cookie", "")
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=lax", set_cookie)
        self.assertIn("Secure", set_cookie)
        self.assertIn("Max-Age=43200", set_cookie)

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

    def test_reset_password_route_returns_identity_only(self):
        os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = "test-reset-code"
        self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )

        response = self.client.post(
            "/api/manual-dispatch/auth/reset-password",
            json={
                "account_name": "Mandy",
                "admin_reset_code": "test-reset-code",
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("Mandy", payload["account_name"])
        self.assertNotIn("password_hash", payload)
        self.assertNotIn("password_salt", payload)
        self.assertNotIn("admin_reset_code", payload)

    def test_reset_password_route_rejects_wrong_code_safely(self):
        os.environ["MANUAL_DISPATCH_ADMIN_RESET_CODE"] = "test-reset-code"
        self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )

        response = self.client.post(
            "/api/manual-dispatch/auth/reset-password",
            json={
                "account_name": "Mandy",
                "admin_reset_code": "wrong-code",
                "new_password": "newsecret123",
                "confirm_password": "newsecret123",
            },
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "Unable to reset password. Please check your details or contact an administrator.",
            response.json()["detail"],
        )

    def _register_and_login_route(self):
        register = self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Mandy",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        self.assertEqual(200, register.status_code)
        login = self.client.post(
            "/api/manual-dispatch/auth/login",
            json={"account_name": "Mandy", "password": "secret123"},
        )
        self.assertEqual(200, login.status_code)


if __name__ == "__main__":
    unittest.main()
