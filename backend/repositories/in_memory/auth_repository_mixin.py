from backend.schemas import OperatorAccountRecord

class InMemoryAuthRepositoryMixin:
    """Auth in-memory responsibilities."""

    def get_operator_account_by_name(self, account_name):
        normalized_name = str(account_name or "").strip().lower()
        return next(
            (
                account
                for account in self.operator_accounts
                if account.account_name.lower() == normalized_name
            ),
            None,
        )

    def get_operator_account_by_id(self, account_id):
        return next(
            (
                account
                for account in self.operator_accounts
                if account.account_id == account_id
            ),
            None,
        )

    def create_operator_account(self, account_name, password_hash, password_salt):
        if self.get_operator_account_by_name(account_name):
            raise ValueError("Account name already exists")
        account = OperatorAccountRecord(
            account_id=self._next_operator_account_id,
            account_name=account_name,
            password_hash=password_hash,
            password_salt=password_salt,
            created_at="in-memory",
            updated_at="in-memory",
        )
        self._next_operator_account_id += 1
        self.operator_accounts.append(account)
        return account

    def update_operator_account_password(self, account_id, password_hash, password_salt):
        account = self.get_operator_account_by_id(account_id)
        if not account:
            raise ValueError("Operator account does not exist")
        account.password_hash = password_hash
        account.password_salt = password_salt
        account.updated_at = "in-memory"
        return account
