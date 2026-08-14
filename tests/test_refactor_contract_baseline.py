import hashlib
import inspect
import json
import subprocess
import textwrap
import unittest
from pathlib import Path

from backend.api import manual_dispatch as api_module
from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.manual_dispatch_service import ManualDispatchService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RefactorContractBaselineTest(unittest.TestCase):
    @staticmethod
    def _contract_digest(value):
        canonical = json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _public_methods(subject):
        return [
            {
                "name": name,
                "signature": str(inspect.signature(member)),
            }
            for name, member in inspect.getmembers(
                subject,
                predicate=inspect.isfunction,
            )
            if not name.startswith("_")
        ]

    def test_api_module_keeps_stable_router_and_service_exports(self):
        self.assertIsNotNone(api_module.router)
        self.assertIsInstance(api_module._get_service(), ManualDispatchService)

    def test_api_path_and_method_contract_fingerprint(self):
        routes = sorted(
            (
                route.path,
                tuple(sorted(route.methods or [])),
            )
            for route in api_module.router.routes
            if getattr(route, "path", None)
        )

        self.assertEqual(97, len(routes))
        self.assertIn(
            (
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
                ("POST",),
            ),
            routes,
        )
        self.assertIn(
            (
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-commit",
                ("POST",),
            ),
            routes,
        )
        self.assertEqual(
            "ab82894eec8875bdd702113aace6068d3b7aea7520d9e6dc0b1f382f05867501",
            self._contract_digest(routes),
        )

    def test_manual_dispatch_service_facade_contract(self):
        repository = InMemoryManualDispatchRepository()
        service = ManualDispatchService(repository=repository)

        self.assertEqual(
            "(repository=None, logbook=None)",
            str(inspect.signature(ManualDispatchService)),
        )
        self.assertIs(repository, service.repository)
        self.assertTrue(
            {
                "repository",
                "logbook",
                "opshop_pickup_service",
                "board_service",
                "validator",
                "opshop_template_service",
                "id_generator",
                "auth_service",
                "assignment_service",
                "order_service",
                "specification_service",
                "final_summary_service",
                "delivery_run_sheet_service",
                "opshop_pickup_collection_service",
                "delivery_workspace_board_service",
                "opshop_workspace_board_service",
                "delivery_workspace_mutation_service",
                "opshop_workspace_mutation_service",
                "workspace_migration_readiness_service",
            }.issubset(vars(service)),
        )

        public_methods = self._public_methods(ManualDispatchService)
        self.assertEqual(95, len(public_methods))
        self.assertEqual(
            "415b277e405ced2f55bddf5f14cef0f686bc4de5277a47428098e8353f1ce2ec",
            self._contract_digest(public_methods),
        )

    def test_repository_facades_keep_identical_public_contracts(self):
        sqlite_methods = self._public_methods(SQLiteManualDispatchRepository)
        in_memory_methods = self._public_methods(
            InMemoryManualDispatchRepository,
        )

        self.assertEqual(sqlite_methods, in_memory_methods)
        self.assertEqual(112, len(sqlite_methods))
        self.assertIn(
            "list_saved_opshop_pickup_dates_by_opshop_ids",
            {method["name"] for method in sqlite_methods},
        )
        self.assertEqual(
            "5c8e2689c2527ae492d0c737efa2b6a01dce7eda4ee39103d2108817808ba1cf",
            self._contract_digest(sqlite_methods),
        )

    def test_frontend_facade_and_state_contracts(self):
        action_uri = (
            PROJECT_ROOT / "frontend" / "js" / "actions" / "workspace-actions.js"
        ).as_uri()
        api_uri = (
            PROJECT_ROOT / "frontend" / "js" / "api" / "manual-dispatch-api.js"
        ).as_uri()
        state_uri = (
            PROJECT_ROOT / "frontend" / "js" / "state" / "app-state.js"
        ).as_uri()
        delivery_renderer_uri = (
            PROJECT_ROOT
            / "frontend"
            / "js"
            / "render"
            / "delivery-workspace-renderer.js"
        ).as_uri()
        opshop_renderer_uri = (
            PROJECT_ROOT
            / "frontend"
            / "js"
            / "render"
            / "opshop-workspace-renderer.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            globalThis.window = {{
              MANUAL_DISPATCH_API_BASE_URL: "",
              location: {{ protocol: "http:", origin: "http://127.0.0.1", hash: "" }},
              history: {{
                pushState: (_state, _title, url) => {{
                  window.location.hash = String(url || "");
                }},
              }},
            }};
            const api = await import({api_uri!r});
            const {{ createWorkspaceActions }} = await import({action_uri!r});
            const {{ state }} = await import({state_uri!r});
            const {{ renderDeliveryWorkspace }} = await import({delivery_renderer_uri!r});
            const {{ renderOpShopWorkspace }} = await import({opshop_renderer_uri!r});

            const actions = createWorkspaceActions({{
              state,
              renderWorkspace() {{}},
              api: {{}},
              confirmAction() {{ return true; }},
              navigateWorkspaceRoute: null,
            }});

            console.log(JSON.stringify({{
              apiExportNames: Object.keys(api),
              actionNames: Object.keys(actions),
              stateFields: Object.keys(state),
              rendererTypes: [
                typeof renderDeliveryWorkspace,
                typeof renderOpShopWorkspace,
              ],
            }}));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        contract = json.loads(completed.stdout)

        self.assertEqual(["function", "function"], contract["rendererTypes"])
        self.assertEqual(102, len(contract["apiExportNames"]))
        self.assertIn("apiPreviewDeliveryDockets", contract["apiExportNames"])
        self.assertIn("apiCommitDeliveryDockets", contract["apiExportNames"])
        self.assertEqual(
            "c970821f02bcbb4a6109ebdf9ba2d00f7ffa63844d33911f7627192211294acf",
            self._contract_digest(contract["apiExportNames"]),
        )
        self.assertEqual(105, len(contract["actionNames"]))
        self.assertIn("previewDeliveryDocketImport", contract["actionNames"])
        self.assertIn("commitDeliveryDocketImport", contract["actionNames"])
        self.assertEqual(
            "8e4fe91668be2101b9c8ff46a97cb46da9f2c0f3a02e23ebdf87c647278aefb0",
            self._contract_digest(contract["actionNames"]),
        )
        self.assertEqual(190, len(contract["stateFields"]))
        self.assertIn("deliveryDocumentImportState", contract["stateFields"])
        self.assertIn("deliveryDocketImportState", contract["stateFields"])
        self.assertEqual(
            "eb1a9f7fe296ff6e34a3226bb735708f4aad110f6d2a3238e1a44b0b9e55ff2f",
            self._contract_digest(contract["stateFields"]),
        )


if __name__ == "__main__":
    unittest.main()
