# Phase 15: Database Login and Final Summary Operator Attribution

## Summary

Phase 15 adds a lightweight database-backed operator login to the Manual Dispatch Board.

The login system is intentionally small and demo-friendly:

- Operators use Account Name / Username + Password.
- Accounts are stored in SQLite.
- Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes.
- Raw passwords are never stored, returned, displayed, exported, or logged.
- This is not production enterprise authentication.

No automatic assignment, route optimization, ETA, maps, geocoding, CP-SAT, blocking rules, external auth provider, role-based access control, or MySQL behavior was added.

## Login/Register Behavior

The frontend now shows a login/register gate before the dispatch board can be used.

Login form:

- Account Name / Username
- Password

Create account form:

- Account Name / Username
- Password
- Confirm Password

Account names are trimmed, required, unique, and must be 2 to 50 characters.

Passwords are required and must be at least 6 characters.

After login:

- The board becomes usable.
- The header shows `Logged in as: <account name>`.
- A Logout button clears the frontend session identity and returns to the login gate.

Forgot Password:

- Forgot Password resets the password; it does not recover or reveal the old password.
- The reset form collects Account Name, Admin Reset Code, New Password, and Confirm New Password.
- Admin Reset Code and password fields use password inputs in the frontend.
- Password fields and reset-code fields are cleared after a reset attempt.
- Success message: `Password reset successfully. Please log in with your new password.`
- Failure message: `Unable to reset password. Please check your details or contact an administrator.`

The frontend may store only safe account identity in `sessionStorage`:

- `manualDispatchAccountName`
- `manualDispatchAccountId`

If `sessionStorage` is unavailable, the current login identity remains in frontend memory only.

## Backend API

Added endpoints:

- `POST /api/manual-dispatch/auth/register`
- `POST /api/manual-dispatch/auth/login`
- `POST /api/manual-dispatch/auth/reset-password`

Register returns account identity only:

- `account_id`
- `account_name`

Login returns account identity only:

- `account_id`
- `account_name`

Login failure uses the safe generic error:

```text
Invalid account name or password
```

The API never returns password hash or salt.

Reset Password reads the administrator reset code from:

```text
MANUAL_DISPATCH_ADMIN_RESET_CODE
```

The reset code is not stored in the repository. If the environment variable is missing or empty, password reset is disabled with a safe error.

Reset Password returns account identity only:

- `account_id`
- `account_name`

## SQLite Schema

Added table:

```text
operator_accounts
```

Fields:

- `id`
- `account_name`
- `password_hash`
- `password_salt`
- `created_at`
- `updated_at`

Added Final Trip Summary attribution columns:

- `saved_by_account_name`
- `saved_by_account_id`

Existing SQLite databases are migrated safely using the existing idempotent schema initialization pattern.

Old saved summaries without attribution display `Unknown`.

## Final Trip Summary Attribution

Save and Export now requires a logged-in operator.

The frontend includes the logged-in operator identity in the Final Trip Summary save payload:

- `saved_by_account_name`
- `saved_by_account_id`

The backend validates that `saved_by_account_name` references a registered operator account before saving.

Saved Final Trip Summary responses include:

- `saved_by_account_name`
- `saved_by_account_id`

Frontend display:

- Unsaved generated summary: `Will be saved by`
- Saved/history summary: `Saved by`
- Save/export success: `Final Trip Summary saved and exported by <account name>.`

## Excel Export

Final Trip Summary Excel export now includes:

- `Saved By`

The export continues to use saved Final Trip Summary snapshot records, not live Order, Driver, or Vehicle data.

The export does not include:

- Password
- Password hash
- Password salt
- Generated At
- Saved At

## Security Notes

This is an MVP/demo login system. It is suitable for local/manual workflow attribution, not production identity management.

Implemented safeguards:

- No plain-text password storage.
- Forgot Password resets passwords only; old passwords are not recoverable.
- Per-account random salt from `os.urandom`.
- PBKDF2-HMAC-SHA256 password hashing using the Python standard library.
- Constant-time hash comparison with `hmac.compare_digest`.
- Constant-time admin reset code comparison with `hmac.compare_digest`.
- Login failure does not reveal whether an account exists.
- No password data is included in Final Trip Summary records or Excel export.
- Admin reset code is never returned by the API.

Not included:

- External auth providers.
- Password recovery.
- Account lockout.
- Role-based permissions.
- Server-side session/token management.

## Validation

Automated coverage includes:

- Registering a new account.
- Rejecting duplicate account names.
- Rejecting invalid account names.
- Rejecting invalid passwords.
- Login success with correct password.
- Login failure with wrong password.
- Successful password reset with valid admin reset code.
- Rejection when reset code is missing from the environment.
- Rejection when reset code is wrong.
- Rejection when reset passwords are invalid or do not match.
- Old password stops working after reset.
- New password works after reset.
- API responses exclude hash and salt.
- Passwords are stored as hash + salt.
- Final Summary save requires valid operator attribution.
- Final Summary history includes saved operator attribution.
- Excel export includes `Saved By`.
- Excel export excludes password data.
- Existing duplicate-save, transactional save, finalized-order, and manual dispatch tests still pass.
