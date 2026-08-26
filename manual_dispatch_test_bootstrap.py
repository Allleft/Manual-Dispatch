import atexit
import os
import shutil
import tempfile
from pathlib import Path


TEST_MODE_ENV = "MANUAL_DISPATCH_TEST_MODE"
DB_PATH_ENV = "MANUAL_DISPATCH_DB_PATH"
LOGBOOK_DIR_ENV = "MANUAL_DISPATCH_LOGBOOK_DIR"
TEST_BUSINESS_DATE_ENV = "MANUAL_DISPATCH_TEST_BUSINESS_DATE"
_TEMP_PREFIX = "manual-dispatch-tests-"
_state = None


def configure_test_environment():
    global _state
    if _state is not None:
        return _state

    temp_root = Path(tempfile.mkdtemp(prefix=_TEMP_PREFIX)).resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    if temp_root.parent != system_temp or not temp_root.name.startswith(_TEMP_PREFIX):
        raise RuntimeError("Automated-test isolation escaped the OS temp directory")

    os.environ[TEST_MODE_ENV] = "1"
    os.environ[TEST_BUSINESS_DATE_ENV] = "2000-01-03"
    os.environ[DB_PATH_ENV] = str(temp_root / "manual_dispatch.sqlite3")
    os.environ[LOGBOOK_DIR_ENV] = str(temp_root / "logbook")
    _state = {
        "temp_root": temp_root,
        "db_path": Path(os.environ[DB_PATH_ENV]),
        "logbook_dir": Path(os.environ[LOGBOOK_DIR_ENV]),
    }
    atexit.register(_cleanup_test_environment)
    return _state


def _cleanup_test_environment():
    if _state is None:
        return
    temp_root = _state["temp_root"].resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    if temp_root.parent != system_temp or not temp_root.name.startswith(_TEMP_PREFIX):
        raise RuntimeError("Refusing to clean a test path outside the OS temp directory")
    if temp_root.exists():
        shutil.rmtree(temp_root)
