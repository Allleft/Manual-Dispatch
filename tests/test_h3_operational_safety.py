import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class H3OperationalSafetyTest(unittest.TestCase):
    def test_ci_covers_integration_branch_and_matches_python_runtime(self):
        workflow = self._read(".github/workflows/ci.yml")

        self.assertEqual(
            2,
            workflow.count("feature/separate-delivery-and-opshop-workspaces"),
        )
        self.assertEqual(2, workflow.count('python-version: "3.12"'))
        self.assertEqual(2, workflow.count("pip install -r requirements-dev.txt"))
        self.assertNotIn("pip install httpx", workflow)
        for variable in (
            "MANUAL_DISPATCH_DB_PATH",
            "MANUAL_DISPATCH_LOGBOOK_DIR",
            "MANUAL_DISPATCH_AUTH_COOKIE_SECRET",
            "MANUAL_DISPATCH_ALLOW_REGISTRATION",
            "MANUAL_DISPATCH_SEED_DEMO_DATA",
        ):
            self.assertEqual(2, workflow.count(variable), variable)

        dockerfile = self._read("Dockerfile")
        self.assertIn("FROM python:3.12-slim", dockerfile)

    def test_direct_dependencies_match_validated_versions(self):
        self.assertEqual(
            [
                "fastapi==0.136.1",
                "uvicorn==0.46.0",
                "openpyxl==3.1.5",
                "pypdf==6.13.2",
                "python-multipart==0.0.28",
                "tzdata==2026.2",
            ],
            self._lines("requirements.txt"),
        )
        self.assertEqual(
            [
                "-r requirements.txt",
                "httpx==0.28.1",
                "playwright==1.59.0",
            ],
            self._lines("requirements-dev.txt"),
        )

    def test_docker_deployment_requires_safe_environment_contract(self):
        dockerfile = self._read("Dockerfile")
        compose = self._read("docker-compose.yml")

        for setting in (
            "MANUAL_DISPATCH_DB_PATH=/app/data/manual_dispatch.sqlite3",
            "MANUAL_DISPATCH_LOGBOOK_DIR=/app/data/logbook",
            "MANUAL_DISPATCH_ALLOW_REGISTRATION=false",
            "MANUAL_DISPATCH_SEED_DEMO_DATA=false",
        ):
            self.assertIn(setting, dockerfile)
        self.assertIn("./data:/app/data", compose)
        self.assertIn("MANUAL_DISPATCH_DB_PATH: /app/data/manual_dispatch.sqlite3", compose)
        self.assertIn("MANUAL_DISPATCH_LOGBOOK_DIR: /app/data/logbook", compose)
        self.assertIn("MANUAL_DISPATCH_AUTH_COOKIE_SECRET: ${MANUAL_DISPATCH_AUTH_COOKIE_SECRET:?", compose)
        self.assertIn("MANUAL_DISPATCH_ALLOW_REGISTRATION: ${MANUAL_DISPATCH_ALLOW_REGISTRATION:-false}", compose)
        self.assertIn("MANUAL_DISPATCH_SEED_DEMO_DATA: ${MANUAL_DISPATCH_SEED_DEMO_DATA:-false}", compose)

    def test_environment_examples_define_production_safe_defaults(self):
        for relative_path, db_path in (
            (".env.example", "data/manual_dispatch.sqlite3"),
            (".env.nas.example", "/app/data/manual_dispatch.sqlite3"),
        ):
            source = self._read(relative_path)
            self.assertIn(f"MANUAL_DISPATCH_DB_PATH={db_path}", source)
            self.assertIn("MANUAL_DISPATCH_LOGBOOK_DIR=", source)
            self.assertIn("MANUAL_DISPATCH_AUTH_COOKIE_SECRET=replace-with-", source)
            self.assertIn("MANUAL_DISPATCH_ALLOW_REGISTRATION=false", source)
            self.assertIn("MANUAL_DISPATCH_SEED_DEMO_DATA=false", source)

        readme = self._read("README.md")
        self.assertIn("Python 3.12 is the supported production runtime", readme)
        self.assertIn("Every production deployment must explicitly configure", readme)

    @staticmethod
    def _read(relative_path):
        return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    @classmethod
    def _lines(cls, relative_path):
        return [line for line in cls._read(relative_path).splitlines() if line]


if __name__ == "__main__":
    unittest.main()
