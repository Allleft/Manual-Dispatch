import os
import tempfile
import unittest
from pathlib import Path

from manual_dispatch_test_bootstrap import configure_test_environment


_TEST_ENVIRONMENT = configure_test_environment()


class FullSuitePersistenceIsolationTest(unittest.TestCase):
    def test_default_full_suite_persistence_is_isolated_under_os_temp(self):
        temp_root = _TEST_ENVIRONMENT["temp_root"]
        configured_db = Path(os.environ["MANUAL_DISPATCH_DB_PATH"]).resolve()
        configured_logbook = Path(os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"]).resolve()

        self.assertEqual("1", os.environ["MANUAL_DISPATCH_TEST_MODE"])
        self.assertEqual(
            "2000-01-03",
            os.environ["MANUAL_DISPATCH_TEST_BUSINESS_DATE"],
        )
        self.assertEqual(Path(tempfile.gettempdir()).resolve(), temp_root.parent)
        self.assertEqual(temp_root, configured_db.parent)
        self.assertEqual(temp_root, configured_logbook.parent)
        self.assertNotEqual(
            (Path.cwd() / "data" / "manual_dispatch.sqlite3").resolve(),
            configured_db,
        )
        self.assertNotEqual(
            (Path.cwd() / "data" / "logbook").resolve(),
            configured_logbook,
        )
