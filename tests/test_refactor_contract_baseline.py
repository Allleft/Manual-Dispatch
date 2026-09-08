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

        self.assertEqual(103, len(routes))
        self.assertIn(
            (
                "/api/manual-dispatch/opshop/pickups/countryside-order",
                ("POST",),
            ),
            routes,
        )
        self.assertIn(
            (
                "/api/manual-dispatch/delivery/orders/import-attache-direct-preview",
                ("POST",),
            ),
            routes,
        )
        self.assertIn(
            (
                "/api/manual-dispatch/delivery/orders/import-attache-current-future-preview",
                ("POST",),
            ),
            routes,
        )
        self.assertIn(
            (
                "/api/manual-dispatch/delivery/orders/import-attache-current-future-commit",
                ("POST",),
            ),
            routes,
        )
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
            "159e9852377a51178aedfe583951f866ee9154d4f0cc6a86c0cdb96ee00fe903",
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
        self.assertEqual(98, len(public_methods))
        self.assertTrue(
            {
                "classify_delivery_area",
                "reorder_countryside_pickup_order",
                "update_delivery_order_area",
            }.issubset(
                {method["name"] for method in public_methods}
            )
        )
        self.assertEqual(
            "adb8cd90b4285ef425ba96e9100583b44fafce201357e56a0fe865ec7d4d2f76",
            self._contract_digest(public_methods),
        )

    def test_repository_facades_keep_identical_public_contracts(self):
        sqlite_methods = self._public_methods(SQLiteManualDispatchRepository)
        in_memory_methods = self._public_methods(
            InMemoryManualDispatchRepository,
        )

        self.assertEqual(sqlite_methods, in_memory_methods)
        self.assertEqual(118, len(sqlite_methods))
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
                "roll_forward_unassigned_delivery_order_dates",
                "update_countryside_pickup_trip_sequences",
            }.issubset({method["name"] for method in sqlite_methods})
        )
        self.assertEqual(
            "02116dee69e13de9f443c87d486778df994ee8edea7f8352d5cf5a24256f4ab0",
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
        self.assertEqual(106, len(contract["apiExportNames"]))
        self.assertIn("apiPreviewDirectAttacheInvoice", contract["apiExportNames"])
        self.assertIn("apiPreviewDeliveryDockets", contract["apiExportNames"])
        self.assertIn("apiCommitDeliveryDockets", contract["apiExportNames"])
        self.assertIn("apiClassifyDeliveryArea", contract["apiExportNames"])
        self.assertIn("apiUpdateDeliveryOrderArea", contract["apiExportNames"])
        self.assertIn(
            "apiReorderOpShopCountrysidePickups",
            contract["apiExportNames"],
        )
        self.assertEqual(
            "d936c3da8cb913d815d52e08e4516d55793449e8ba045d74c7eb361f683a1235",
            self._contract_digest(contract["apiExportNames"]),
        )
        self.assertEqual(115, len(contract["actionNames"]))
        self.assertIn("lookupDeliveryDirectAttacheInvoice", contract["actionNames"])
        self.assertIn("updateDeliveryDirectAttacheInvoiceNumber", contract["actionNames"])
        self.assertIn("previewDeliveryDocketImport", contract["actionNames"])
        self.assertIn("commitDeliveryDocketImport", contract["actionNames"])
        self.assertIn("reorderCountrysidePickups", contract["actionNames"])
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
            "eab798ec78a413cff1772e3484c07fd44a6500a10e5f761cf2513f0dbb02ea6c",
            self._contract_digest(contract["actionNames"]),
        )
        self.assertEqual(192, len(contract["stateFields"]))
        self.assertIn("deliveryDocumentImportState", contract["stateFields"])
        self.assertIn("deliveryDocketImportState", contract["stateFields"])
        self.assertEqual(
            "39433ee4978eae37ae07080250888a409b74a06753e407f8718bfb518f19682e",
            self._contract_digest(contract["stateFields"]),
        )


if __name__ == "__main__":
    unittest.main()
