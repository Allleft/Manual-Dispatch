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

        self.assertEqual(99, len(routes))
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
        self.assertIn(
            (
                "/api/manual-dispatch/delivery/area-classification",
                ("POST",),
            ),
            routes,
        )
        self.assertIn(
            (
                "/api/manual-dispatch/delivery/orders/{order_id}/delivery-area",
                ("PATCH",),
            ),
            routes,
        )
        self.assertEqual(
            "8eb2e2c47a164bc014d69575874f8b1d4795b583a932b0f3123c0069874b8103",
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
        self.assertEqual(97, len(public_methods))
        self.assertTrue(
            {"classify_delivery_area", "update_delivery_order_area"}.issubset(
                {method["name"] for method in public_methods}
            )
        )
        self.assertEqual(
            "e6f559b2d64e3a525ad82ef77dc589c90c65742e99663e05dd9449332b2b9220",
            self._contract_digest(public_methods),
        )

    def test_repository_facades_keep_identical_public_contracts(self):
        sqlite_methods = self._public_methods(SQLiteManualDispatchRepository)
        in_memory_methods = self._public_methods(
            InMemoryManualDispatchRepository,
        )

        self.assertEqual(sqlite_methods, in_memory_methods)
        self.assertEqual(116, len(sqlite_methods))
        self.assertIn(
            "list_saved_opshop_pickup_dates_by_opshop_ids",
            {method["name"] for method in sqlite_methods},
        )
        self.assertIn(
            "list_opshop_pickup_collection_reservations_for_task_ids",
            {method["name"] for method in sqlite_methods},
        )
        self.assertTrue(
            {
                "get_delivery_order_area_override",
                "set_delivery_order_area_override",
                "clear_delivery_order_area_override",
            }.issubset({method["name"] for method in sqlite_methods})
        )
        self.assertEqual(
            "048d01513b170d3cbc3cc5c8e4769794f3030baf257119b50c0b08907d51907a",
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
        self.assertEqual(104, len(contract["apiExportNames"]))
        self.assertIn("apiPreviewDeliveryDockets", contract["apiExportNames"])
        self.assertIn("apiCommitDeliveryDockets", contract["apiExportNames"])
        self.assertIn("apiClassifyDeliveryArea", contract["apiExportNames"])
        self.assertIn("apiUpdateDeliveryOrderArea", contract["apiExportNames"])
        self.assertEqual(
            "97faabe7cc7175b70087357d811ffeea1f12987bdbd6284e5163b4576390ff5c",
            self._contract_digest(contract["apiExportNames"]),
        )
        self.assertEqual(110, len(contract["actionNames"]))
        self.assertIn("previewDeliveryDocketImport", contract["actionNames"])
        self.assertIn("commitDeliveryDocketImport", contract["actionNames"])
        self.assertTrue(
            {
                "classifyDeliveryOrderForm",
                "classifyDeliveryAttacheImportRow",
                "classifyDeliveryDocketImportRow",
                "moveDeliveryOrderToArea",
                "resetDeliveryOrderArea",
            }.issubset(contract["actionNames"])
        )
        self.assertEqual(
            "4dca4472a8573ec52e67dfe748ee2ce03c9000c029f8be664656b4e06c394afc",
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
