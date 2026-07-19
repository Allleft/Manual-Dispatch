from backend.db.connection import connect

class SQLiteAuthRepositoryMixin:
    """Auth persistence responsibilities."""

    def get_operator_account_by_name(self, account_name):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM operator_accounts
                WHERE account_name = ? COLLATE NOCASE
                """,
                (account_name,),
            ).fetchone()
        return self._row_to_operator_account(row) if row else None

    def get_operator_account_by_id(self, account_id):
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM operator_accounts
                WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
        return self._row_to_operator_account(row) if row else None

    def create_operator_account(self, account_name, password_hash, password_salt):
        timestamp = self._timestamp()
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO operator_accounts (
                    account_name,
                    password_hash,
                    password_salt,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (account_name, password_hash, password_salt, timestamp, timestamp),
            )
            account_id = cursor.lastrowid
            connection.commit()
        return self.get_operator_account_by_id(account_id)

    def update_operator_account_password(self, account_id, password_hash, password_salt):
        timestamp = self._timestamp()
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE operator_accounts
                SET password_hash = ?, password_salt = ?, updated_at = ?
                WHERE id = ?
                """,
                (password_hash, password_salt, timestamp, account_id),
            )
            connection.commit()

        if cursor.rowcount == 0:
            raise ValueError("Operator account does not exist")
        return self.get_operator_account_by_id(account_id)
