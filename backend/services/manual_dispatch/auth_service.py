import hashlib
import hmac
import os

from backend.schemas import OperatorAccountIdentity


PASSWORD_MIN_LENGTH = 6
PASSWORD_HASH_ITERATIONS = 120_000
ADMIN_RESET_CODE_ENV = "MANUAL_DISPATCH_ADMIN_RESET_CODE"
PASSWORD_RESET_FAILURE_MESSAGE = (
    "Unable to reset password. Please check your details or contact an administrator."
)
PASSWORD_RESET_DISABLED_MESSAGE = (
    "Password reset is not configured. Please contact an administrator."
)


class OperatorAuthService:
    def __init__(self, repository):
        self.repository = repository

    def register_operator_account(self, request):
        account_name = self._clean_account_name(request.account_name)
        password = self._clean_required_password(request.password)
        confirm_password = request.confirm_password

        if confirm_password is None:
            raise ValueError("confirm_password is required")

        if password != confirm_password:
            raise ValueError("Passwords do not match")

        if self.repository.get_operator_account_by_name(account_name):
            raise ValueError("Account name already exists")

        password_salt = os.urandom(16).hex()
        password_hash = self._hash_password(password, password_salt)
        account = self.repository.create_operator_account(
            account_name=account_name,
            password_hash=password_hash,
            password_salt=password_salt,
        )
        return OperatorAccountIdentity(
            account_id=account.account_id,
            account_name=account.account_name,
        )

    def login_operator_account(self, request):
        account_name = self._clean_optional_text(request.account_name)
        password = request.password or ""

        if not account_name or not password:
            raise ValueError("Invalid account name or password")

        account = self.repository.get_operator_account_by_name(account_name)
        if not account:
            raise ValueError("Invalid account name or password")

        expected_hash = self._hash_password(password, account.password_salt)
        if not hmac.compare_digest(expected_hash, account.password_hash):
            raise ValueError("Invalid account name or password")

        return OperatorAccountIdentity(
            account_id=account.account_id,
            account_name=account.account_name,
        )

    def reset_operator_password(self, request):
        account_name = self._clean_account_name(request.account_name)
        new_password = self._clean_required_password(request.new_password)
        confirm_password = request.confirm_password

        if confirm_password is None:
            raise ValueError("confirm_password is required")
        if new_password != confirm_password:
            raise ValueError("Passwords do not match")

        configured_reset_code = os.environ.get(ADMIN_RESET_CODE_ENV)
        if not configured_reset_code:
            raise ValueError(PASSWORD_RESET_DISABLED_MESSAGE)

        submitted_reset_code = request.admin_reset_code or ""
        if not hmac.compare_digest(
            str(submitted_reset_code),
            str(configured_reset_code),
        ):
            raise ValueError(PASSWORD_RESET_FAILURE_MESSAGE)

        account = self.repository.get_operator_account_by_name(account_name)
        if not account:
            raise ValueError(PASSWORD_RESET_FAILURE_MESSAGE)

        password_salt = os.urandom(16).hex()
        password_hash = self._hash_password(new_password, password_salt)
        updated_account = self.repository.update_operator_account_password(
            account.account_id,
            password_hash,
            password_salt,
        )
        return OperatorAccountIdentity(
            account_id=updated_account.account_id,
            account_name=updated_account.account_name,
        )

    def _clean_account_name(self, value):
        account_name = self._clean_optional_text(value)
        if not account_name:
            raise ValueError("account_name is required")
        if len(account_name) < 2 or len(account_name) > 50:
            raise ValueError("account_name must be between 2 and 50 characters")
        return account_name

    def _clean_required_password(self, value):
        if value is None:
            raise ValueError("password is required")
        password = str(value)
        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"password must be at least {PASSWORD_MIN_LENGTH} characters"
            )
        return password

    def _clean_optional_text(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _hash_password(self, password, password_salt):
        return hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            bytes.fromhex(password_salt),
            PASSWORD_HASH_ITERATIONS,
        ).hex()
