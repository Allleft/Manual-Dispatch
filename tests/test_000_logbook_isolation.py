import atexit
import os
import shutil
import unittest
from pathlib import Path


_WORKSPACE_TMP = (Path.cwd() / "tmp").resolve()
_PREVIOUS_LOGBOOK_DIR = os.environ.get("MANUAL_DISPATCH_LOGBOOK_DIR")
_FULL_SUITE_LOGBOOK_DIR = (
    _WORKSPACE_TMP / f"unittest-logbook-{os.getpid()}"
).resolve()
_CONFIGURED_BY_THIS_MODULE = _PREVIOUS_LOGBOOK_DIR is None

if _FULL_SUITE_LOGBOOK_DIR.parent != _WORKSPACE_TMP:
    raise RuntimeError("Full-suite Logbook isolation escaped the workspace tmp directory.")

if _CONFIGURED_BY_THIS_MODULE:
    os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = str(_FULL_SUITE_LOGBOOK_DIR)


def _cleanup_full_suite_logbook():
    if not _CONFIGURED_BY_THIS_MODULE or not _FULL_SUITE_LOGBOOK_DIR.exists():
        return
    resolved = _FULL_SUITE_LOGBOOK_DIR.resolve()
    if resolved.parent != _WORKSPACE_TMP:
        raise RuntimeError("Refusing to clean a Logbook directory outside workspace tmp.")
    shutil.rmtree(resolved)


atexit.register(_cleanup_full_suite_logbook)


class FullSuiteLogbookIsolationTest(unittest.TestCase):
    def test_default_full_suite_logbook_is_isolated_under_tmp(self):
        configured = Path(os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"]).resolve()
        if _CONFIGURED_BY_THIS_MODULE:
            self.assertEqual(_FULL_SUITE_LOGBOOK_DIR, configured)
            self.assertEqual(_WORKSPACE_TMP, configured.parent)
            self.assertNotEqual((Path.cwd() / "data" / "logbook").resolve(), configured)
        else:
            self.assertEqual(Path(_PREVIOUS_LOGBOOK_DIR).resolve(), configured)
