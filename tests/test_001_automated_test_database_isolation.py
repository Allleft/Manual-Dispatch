import hashlib
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "manual_dispatch.sqlite3"
DEFAULT_LOGBOOK_DIR = PROJECT_ROOT / "data" / "logbook"
TEST_MODE_ENV = "MANUAL_DISPATCH_TEST_MODE"
DB_PATH_ENV = "MANUAL_DISPATCH_DB_PATH"
LOGBOOK_DIR_ENV = "MANUAL_DISPATCH_LOGBOOK_DIR"
DEFAULT_DB_TEST_ERROR = (
    "Automated tests may not open the default Manual Dispatch database"
)
DEFAULT_LOGBOOK_TEST_ERROR = (
    "Automated tests may not use the default Manual Dispatch Logbook"
)


def _file_evidence(path):
    if not path.exists():
        return None
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def _stat_evidence(path):
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def _directory_evidence(path):
    if not path.exists():
        return None
    return tuple(
        (
            str(file.relative_to(path)),
            _file_evidence(file),
        )
        for file in sorted(item for item in path.rglob("*") if item.is_file())
    )


class AutomatedTestDatabaseIsolationTest(unittest.TestCase):
    def setUp(self):
        self.default_db_before = _stat_evidence(DEFAULT_DB_PATH)
        self.default_logbook_before = _directory_evidence(DEFAULT_LOGBOOK_DIR)

    def tearDown(self):
        self.assertEqual(self.default_db_before, _stat_evidence(DEFAULT_DB_PATH))
        self.assertEqual(
            self.default_logbook_before,
            _directory_evidence(DEFAULT_LOGBOOK_DIR),
        )

    def _run_isolated(self, source, *, db_path=None, test_mode=True):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        if test_mode:
            environment[TEST_MODE_ENV] = "1"
        else:
            environment.pop(TEST_MODE_ENV, None)
        if db_path is None:
            environment.pop(DB_PATH_ENV, None)
        else:
            environment[DB_PATH_ENV] = str(db_path)

        with tempfile.TemporaryDirectory(prefix="manual-dispatch-logbook-test-") as root:
            environment[LOGBOOK_DIR_ENV] = str(Path(root) / "logbook")
            completed = subprocess.run(
                [sys.executable, "-c", textwrap.dedent(source)],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(
            0,
            completed.returncode,
            msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return completed

    def test_test_mode_rejects_default_database_before_open(self):
        self._run_isolated(
            f"""
            from backend.db.connection import connect, get_database_path, initialize_database

            for operation in (get_database_path, connect, initialize_database):
                try:
                    operation()
                except RuntimeError as error:
                    assert str(error) == {DEFAULT_DB_TEST_ERROR!r}
                else:
                    raise AssertionError(f"{{operation.__name__}} did not fail closed")
            """,
        )

    def test_test_mode_rejects_default_logbook(self):
        self._run_isolated(
            f"""
            import os
            os.environ.pop("{LOGBOOK_DIR_ENV}", None)
            from backend.services.manual_dispatch.logbook_file_service import resolve_logbook_dir

            try:
                resolve_logbook_dir()
            except RuntimeError as error:
                assert str(error) == {DEFAULT_LOGBOOK_TEST_ERROR!r}
            else:
                raise AssertionError("default Logbook did not fail closed")
            """,
        )

    def test_focused_delivery_area_module_isolates_logbook_without_environment(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment.pop(TEST_MODE_ENV, None)
        environment.pop(LOGBOOK_DIR_ENV, None)
        environment.pop(DB_PATH_ENV, None)
        before = _directory_evidence(DEFAULT_LOGBOOK_DIR)

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_delivery_area_classification.py",
                "-v",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            0,
            completed.returncode,
            msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        self.assertEqual(before, _directory_evidence(DEFAULT_LOGBOOK_DIR))

    def test_api_import_with_explicit_test_database_is_lazy(self):
        with tempfile.TemporaryDirectory(prefix="manual-dispatch-api-import-") as root:
            database_path = Path(root) / "manual_dispatch.sqlite3"
            self._run_isolated(
                """
                import os
                from pathlib import Path
                from backend.api import manual_dispatch

                assert manual_dispatch.service is None
                assert not Path(os.environ["MANUAL_DISPATCH_DB_PATH"]).exists()
                """,
                db_path=database_path,
            )
            self.assertFalse(database_path.exists())

    def test_main_import_under_test_isolation_is_lazy(self):
        with tempfile.TemporaryDirectory(prefix="manual-dispatch-main-import-") as root:
            database_path = Path(root) / "manual_dispatch.sqlite3"
            self._run_isolated(
                """
                import os
                from pathlib import Path
                import backend.main

                assert backend.main.app is not None
                assert not Path(os.environ["MANUAL_DISPATCH_DB_PATH"]).exists()
                """,
                db_path=database_path,
            )
            self.assertFalse(database_path.exists())

    def test_pre_setup_api_test_module_import_cannot_touch_default_database(self):
        self._run_isolated(
            """
            import sys
            from pathlib import Path

            sys.path.insert(0, str(Path.cwd() / "tests"))
            import test_frontend_static_cache_headers
            assert test_frontend_static_cache_headers.app is not None
            """,
        )

    def test_non_test_explicit_startup_initializes_configured_database(self):
        with tempfile.TemporaryDirectory(prefix="manual-dispatch-production-start-") as root:
            database_path = Path(root) / "manual_dispatch.sqlite3"
            self._run_isolated(
                """
                import os
                import sqlite3
                from pathlib import Path
                from backend.api import manual_dispatch

                database_path = Path(os.environ["MANUAL_DISPATCH_DB_PATH"])
                assert manual_dispatch.service is None
                assert not database_path.exists()
                assert manual_dispatch._get_service() is manual_dispatch.service
                assert database_path.exists()
                with sqlite3.connect(database_path) as connection:
                    assert connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='manual_orders'"
                    ).fetchone() == (1,)
                """,
                db_path=database_path,
                test_mode=False,
            )
            self.assertTrue(database_path.exists())


if __name__ == "__main__":
    unittest.main()
