import importlib
import json
import os
import shutil
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.manual_dispatch_service import ManualDispatchService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except (ImportError, ModuleNotFoundError, RuntimeError):
    FastAPI = None
    TestClient = None


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI TestClient unavailable")
class LogbookStage2BEventsTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"logbook-stage2b-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.logbook_dir = self.temp_dir / "logbook"
        self.previous_environment = {
            name: os.environ.get(name)
            for name in (
                "MANUAL_DISPATCH_DB_PATH",
                "MANUAL_DISPATCH_LOGBOOK_DIR",
                "MANUAL_DISPATCH_SEED_DEMO_DATA",
                "MANUAL_DISPATCH_ALLOW_REGISTRATION",
            )
        }
        os.environ["MANUAL_DISPATCH_DB_PATH"] = str(self.db_path)
        os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = str(self.logbook_dir)
        os.environ["MANUAL_DISPATCH_SEED_DEMO_DATA"] = "0"
        os.environ.pop("MANUAL_DISPATCH_ALLOW_REGISTRATION", None)

        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.api_module = importlib.import_module("backend.api.manual_dispatch")
        self.original_service = self.api_module.service
        self.api_module.service = self.service
        app = FastAPI()
        app.include_router(self.api_module.router)
        self.client = TestClient(app)
        response = self.client.post(
            "/api/manual-dispatch/auth/register",
            json={
                "account_name": "Stage 2B Operator",
                "password": "secret123",
                "confirm_password": "secret123",
            },
        )
        self.assertEqual(200, response.status_code)

    def tearDown(self):
        self.api_module.service = self.original_service
        for name, value in self.previous_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_delivery_single_and_daily_exports_record_one_event_each(self):
        run_sheet = self._run_sheet()
        with (
            patch.object(
                self.service,
                "get_saved_delivery_run_sheet_for_export",
                return_value=run_sheet,
            ),
            patch.object(
                self.service,
                "list_delivery_run_sheets_for_date_export",
                return_value=[run_sheet, self._run_sheet("RUN-2", "GENERATED")],
            ),
            patch.object(
                self.api_module,
                "build_delivery_run_sheet_excel",
                return_value=b"single-xlsx",
            ),
            patch.object(
                self.api_module,
                "build_delivery_run_sheets_excel",
                return_value=b"daily-xlsx",
            ),
        ):
            single = self.client.get(
                "/api/manual-dispatch/delivery/run-sheets/RUN-1/export-excel"
            )
            daily = self.client.get(
                "/api/manual-dispatch/delivery/run-sheets/export-excel",
                params={"delivery_date": "2026-07-10"},
            )

        self.assertEqual(200, single.status_code)
        self.assertEqual(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            single.headers["content-type"],
        )
        self.assertEqual(
            'attachment; filename="Delivery_Run_Sheet_2026-07-10_Gavin_Fynn.xlsx"',
            single.headers["content-disposition"],
        )
        self.assertEqual(200, daily.status_code)
        single_entry = self._only_entry("DELIVERY_RUN_SHEET_EXPORTED")
        self.assertEqual("Stage 2B Operator", single_entry["actor"])
        self.assertEqual("RUN-1", single_entry["run_sheet_id"])
        self.assertEqual("2026-07-10", single_entry["delivery_date"])
        self.assertEqual("Gavin Fynn", single_entry["driver"])
        self.assertEqual("single", single_entry["metadata"]["export_scope"])
        self.assertEqual(3, single_entry["metadata"]["order_count"])
        self.assertEqual(
            "Delivery_Run_Sheet_2026-07-10_Gavin_Fynn.xlsx",
            single_entry["metadata"]["filename"],
        )
        daily_entry = self._only_entry("DELIVERY_RUN_SHEETS_DAILY_EXPORTED")
        self.assertEqual(2, daily_entry["metadata"]["run_sheet_count"])
        self.assertEqual(1, daily_entry["metadata"]["saved_count"])
        self.assertEqual(1, daily_entry["metadata"]["generated_count"])

        before = len(self._entries_for("DELIVERY_RUN_SHEET_EXPORTED"))
        with (
            patch.object(
                self.service,
                "get_saved_delivery_run_sheet_for_export",
                return_value=run_sheet,
            ),
            patch.object(
                self.api_module,
                "build_delivery_run_sheet_excel",
                side_effect=RuntimeError("workbook failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.client.get(
                "/api/manual-dispatch/delivery/run-sheets/RUN-1/export-excel"
            )
        self.assertEqual(
            before,
            len(self._entries_for("DELIVERY_RUN_SHEET_EXPORTED")),
        )

    def test_opshop_single_and_daily_exports_record_filters_and_counts(self):
        collection = self._collection()
        with (
            patch.object(
                self.service,
                "get_opshop_pickup_collection_for_export",
                return_value=collection,
            ),
            patch.object(
                self.service,
                "list_opshop_pickup_collections_for_date_export",
                return_value=[collection],
            ),
            patch.object(
                self.api_module,
                "build_opshop_pickup_collection_excel",
                return_value=b"single-xlsx",
            ),
            patch.object(
                self.api_module,
                "build_opshop_pickup_collections_excel",
                return_value=b"daily-xlsx",
            ),
        ):
            single = self.client.get(
                "/api/manual-dispatch/opshop/pickup-collections/COL-1/export-excel"
            )
            daily = self.client.get(
                "/api/manual-dispatch/opshop/pickup-collections/export-excel",
                params={
                    "pickup_date": "2026-07-10",
                    "dispatch_date": "2026-07-09",
                    "status": "SAVED",
                },
            )

        self.assertEqual(200, single.status_code)
        self.assertEqual(
            'attachment; filename="OPSHOP_Pickup_Collection_2026-07-10_Guanlin_Li.xlsx"',
            single.headers["content-disposition"],
        )
        self.assertEqual(200, daily.status_code)
        single_entry = self._only_entry("PICKUP_COLLECTION_EXPORTED")
        self.assertEqual("Stage 2B Operator", single_entry["actor"])
        self.assertEqual("COL-1", single_entry["collection_id"])
        self.assertEqual(3, single_entry["metadata"]["pickup_count"])
        self.assertEqual(1, single_entry["metadata"]["regular_count"])
        self.assertEqual(1, single_entry["metadata"]["oncall_count"])
        self.assertEqual(1, single_entry["metadata"]["countryside_count"])
        daily_entry = self._only_entry("PICKUP_COLLECTIONS_DAILY_EXPORTED")
        self.assertEqual("SUCCESS", daily_entry["result"])
        self.assertEqual("Stage 2B Operator", daily_entry["actor"])
        self.assertEqual("2026-07-10", daily_entry["pickup_date"])
        self.assertEqual(1, daily_entry["metadata"]["collection_count"])
        self.assertEqual("SAVED", daily_entry["metadata"]["status_filter"])
        self.assertNotIn(
            "dispatch_date_filter",
            daily_entry["metadata"],
        )


    def test_collection_weight_sheet_update_event_excludes_operational_values(self):
        collection = self._collection()
        self.service.opshop_event_recorder.record_collection_weight_sheet_updated(
            collection,
            changed_row_count=2,
            changed_field_count=5,
        )

        entry = self._only_entry("PICKUP_COLLECTION_WEIGHT_SHEET_UPDATED")
        self.assertEqual("SUCCESS", entry["result"])
        self.assertEqual("OPSHOP", entry["workspace"])
        self.assertEqual("COL-1", entry["collection_id"])
        self.assertEqual(
            {
                "collection_id": "COL-1",
                "changed_row_count": 2,
                "changed_field_count": 5,
            },
            entry["metadata"],
        )
        serialized = json.dumps(entry["metadata"])
        for forbidden in ("12.25", "09:05", "black_bags", "clothing_kg"):
            self.assertNotIn(forbidden, serialized)

        with patch.object(
            self.service.logbook,
            "record",
            side_effect=RuntimeError("logbook unavailable"),
        ):
            self.service.opshop_event_recorder.record_collection_weight_sheet_updated(
                collection,
                changed_row_count=1,
                changed_field_count=1,
            )

    def test_attache_commit_records_batch_results_and_keeps_order_events(self):
        success_row = self._attache_row(
            "ROW-1",
            r"C:\private\invoice-184068.pdf",
            "184068",
        )
        skipped_row = self._attache_row(
            "ROW-2",
            r"D:\secret\invoice-184069.pdf",
            "184069",
            selected=False,
        )
        partial = self.client.post(
            "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit",
            json={"rows": [success_row, skipped_row]},
        )
        self.assertEqual(200, partial.status_code)
        self.assertEqual(1, partial.json()["imported_count"])
        self.assertEqual(1, len(self._entries_for("ORDER_CREATED")))
        entry = self._only_entry("ATTACHE_IMPORT_CONFIRMED")
        self.assertEqual("PARTIAL", entry["result"])
        self.assertEqual("Stage 2B Operator", entry["actor"])
        self.assertEqual(
            ["invoice-184068.pdf", "invoice-184069.pdf"],
            entry["metadata"]["source_filenames"],
        )
        serialized = json.dumps(entry)
        self.assertNotIn("C:\\private", serialized)
        self.assertNotIn("D:\\secret", serialized)
        self.assertNotIn("secret123", serialized)

        many_rows = [
            SimpleNamespace(
                row_id=f"TRUNCATE-{index}",
                source_filename=rf"C:\private\invoice-{index:02d}.pdf",
                selected=True,
                is_duplicate=False,
            )
            for index in range(21)
        ]
        with self.service.logbook_actor("Stage 2B Operator"):
            self.service.record_attache_import_confirmation(
                many_rows,
                {
                    "imported_count": 21,
                    "skipped_count": 0,
                    "skipped_rows": [],
                },
            )
        truncated_entry = self._entries_for("ATTACHE_IMPORT_CONFIRMED")[-1]
        self.assertEqual(21, truncated_entry["metadata"]["source_file_count"])
        self.assertEqual(20, len(truncated_entry["metadata"]["source_filenames"]))
        self.assertTrue(truncated_entry["metadata"]["source_filenames_truncated"])

        failed = self.client.post(
            "/api/manual-dispatch/orders/import-attache-pdf-commit",
            json={
                "rows": [
                    self._attache_row(
                        "ROW-3",
                        "/private/invoice-184070.pdf",
                        "184070",
                        importable=False,
                    )
                ]
            },
        )
        self.assertEqual(200, failed.status_code)
        failed_entry = self._entries_for("ATTACHE_IMPORT_CONFIRMED")[-1]
        self.assertEqual("FAILED", failed_entry["result"])
        self.assertEqual("Stage 2B Operator", failed_entry["actor"])
        self.assertEqual(
            "No orders were imported",
            failed_entry["metadata"]["failure_reason"],
        )

        before = len(self._entries_for("ATTACHE_IMPORT_CONFIRMED"))
        self.client.post(
            "/api/manual-dispatch/orders/import-attache-pdf-preview",
            files={"files": ("preview.pdf", b"not-a-real-pdf", "application/pdf")},
        )
        self.assertEqual(
            before,
            len(self._entries_for("ATTACHE_IMPORT_CONFIRMED")),
        )

    def test_regular_and_oncall_template_mutations_log_changes_and_noops(self):
        regular = self._create_template("REGULAR", "Vinnies Coburg", "MONDAY")
        regular_id = regular["schedule_id"]
        updated = self.client.patch(
            f"/api/manual-dispatch/opshop-templates/{regular_id}",
            json={"run_day": "TUESDAY"},
        )
        self.assertEqual(200, updated.status_code)
        updated_id = updated.json()["schedule_id"]
        update_entry = self._only_entry("REGULAR_TEMPLATE_UPDATED")
        self.assertEqual(
            {"run_day": "MONDAY"},
            update_entry["metadata"]["before"],
        )
        self.assertEqual(
            {"run_day": "TUESDAY"},
            update_entry["metadata"]["after"],
        )
        before_noop = len(self._entries_for("REGULAR_TEMPLATE_UPDATED"))
        noop = self.client.patch(
            f"/api/manual-dispatch/opshop-templates/{updated_id}",
            json={"run_day": "TUESDAY"},
        )
        self.assertEqual(200, noop.status_code)
        self.assertEqual(
            before_noop,
            len(self._entries_for("REGULAR_TEMPLATE_UPDATED")),
        )
        self.assertEqual(
            200,
            self.client.post(
                f"/api/manual-dispatch/opshop-templates/{updated_id}/disable"
            ).status_code,
        )

        oncall = self._create_template("ON_CALL", "Salvos Preston")
        oncall_id = oncall["schedule_id"]
        changed = self.client.patch(
            f"/api/manual-dispatch/opshop-templates/{oncall_id}",
            json={"status_notes": "Call loading dock"},
        )
        self.assertEqual(200, changed.status_code)
        changed_id = changed.json()["schedule_id"]
        self.assertEqual(
            200,
            self.client.post(
                f"/api/manual-dispatch/opshop-templates/{changed_id}/disable"
            ).status_code,
        )
        before_list = len(self._template_entries())
        self.assertEqual(
            200,
            self.client.get("/api/manual-dispatch/opshop-templates").status_code,
        )
        self.assertEqual(before_list, len(self._template_entries()))
        for action in (
            "REGULAR_TEMPLATE_CREATED",
            "REGULAR_TEMPLATE_UPDATED",
            "REGULAR_TEMPLATE_DISABLED",
            "ONCALL_TEMPLATE_CREATED",
            "ONCALL_TEMPLATE_UPDATED",
            "ONCALL_TEMPLATE_DISABLED",
        ):
            entry = self._only_entry(action)
            self.assertEqual("Stage 2B Operator", entry["actor"])

    def test_countryside_route_group_create_rename_disable_and_noop(self):
        created = self.client.post(
            "/api/manual-dispatch/opshop-countryside-route-groups",
            json={"route_group_name": "Cobram"},
        )
        self.assertEqual(200, created.status_code)
        group_id = created.json()["route_group_id"]
        noop = self.client.patch(
            f"/api/manual-dispatch/opshop-countryside-route-groups/{group_id}",
            json={"route_group_name": "Cobram"},
        )
        self.assertEqual(200, noop.status_code)
        self.assertEqual(
            [],
            self._entries_for("COUNTRYSIDE_ROUTE_GROUP_RENAMED"),
        )
        renamed = self.client.patch(
            f"/api/manual-dispatch/opshop-countryside-route-groups/{group_id}",
            json={"route_group_name": "Cobram and Echuca"},
        )
        self.assertEqual(200, renamed.status_code)
        disabled = self.client.post(
            f"/api/manual-dispatch/opshop-countryside-route-groups/{group_id}/disable"
        )
        self.assertEqual(200, disabled.status_code)
        rename_entry = self._only_entry("COUNTRYSIDE_ROUTE_GROUP_RENAMED")
        self.assertEqual(
            "Cobram",
            rename_entry["metadata"]["before"]["route_group_name"],
        )
        self.assertEqual(
            "Cobram and Echuca",
            rename_entry["metadata"]["after"]["route_group_name"],
        )
        for action in (
            "COUNTRYSIDE_ROUTE_GROUP_CREATED",
            "COUNTRYSIDE_ROUTE_GROUP_RENAMED",
            "COUNTRYSIDE_ROUTE_GROUP_DISABLED",
        ):
            self.assertEqual("Stage 2B Operator", self._only_entry(action)["actor"])

    def test_countryside_membership_add_move_remove_and_noop(self):
        source = self._create_route_group("Shepparton")
        target = self._create_route_group("Echuca")
        added = self.client.post(
            f"/api/manual-dispatch/opshop-countryside-route-groups/{source}/memberships",
            json={
                "name": "Vinnies Shepparton",
                "suburb": "Shepparton",
                "street_address": "1 Test Road",
            },
        )
        self.assertEqual(200, added.status_code)
        schedule_id = added.json()["schedule_id"]
        moved = self.client.post(
            f"/api/manual-dispatch/opshop-countryside-memberships/{schedule_id}/move",
            json={"target_route_group_id": target},
        )
        self.assertEqual(200, moved.status_code)
        moved_id = moved.json()["schedule_id"]
        before_noop = len(self._entries_for("COUNTRYSIDE_MEMBERSHIP_MOVED"))
        noop = self.client.post(
            f"/api/manual-dispatch/opshop-countryside-memberships/{moved_id}/move",
            json={"target_route_group_id": target},
        )
        self.assertEqual(400, noop.status_code)
        self.assertEqual(
            before_noop,
            len(self._entries_for("COUNTRYSIDE_MEMBERSHIP_MOVED")),
        )
        removed = self.client.post(
            f"/api/manual-dispatch/opshop-countryside-memberships/{moved_id}/remove"
        )
        self.assertEqual(200, removed.status_code)
        moved_entry = self._only_entry("COUNTRYSIDE_MEMBERSHIP_MOVED")
        self.assertEqual(
            "Shepparton",
            moved_entry["metadata"]["before"]["route_group_name"],
        )
        self.assertEqual(
            "Echuca",
            moved_entry["metadata"]["after"]["route_group_name"],
        )
        removed_entry = self._only_entry("COUNTRYSIDE_MEMBERSHIP_REMOVED")
        self.assertEqual("Vinnies Shepparton", removed_entry["metadata"]["company_name"])
        self.assertEqual("Echuca", removed_entry["metadata"]["route_group_name"])
        for action in (
            "COUNTRYSIDE_MEMBERSHIP_ADDED",
            "COUNTRYSIDE_MEMBERSHIP_MOVED",
            "COUNTRYSIDE_MEMBERSHIP_REMOVED",
        ):
            self.assertEqual("Stage 2B Operator", self._only_entry(action)["actor"])

    def _create_template(self, run_type, name, run_day=None):
        response = self.client.post(
            "/api/manual-dispatch/opshop-templates",
            json={
                "run_type": run_type,
                "run_day": run_day,
                "name": name,
                "suburb": "Coburg" if run_type == "REGULAR" else "Preston",
                "street_address": "1 Test Road",
                "pickup_frequency": "Weekly" if run_type == "REGULAR" else "On Call",
            },
        )
        self.assertEqual(200, response.status_code)
        return response.json()

    def _create_route_group(self, name):
        response = self.client.post(
            "/api/manual-dispatch/opshop-countryside-route-groups",
            json={"route_group_name": name},
        )
        self.assertEqual(200, response.status_code)
        return response.json()["route_group_id"]

    @staticmethod
    def _run_sheet(run_sheet_id="RUN-1", status="SAVED"):
        return SimpleNamespace(
            run_sheet_id=run_sheet_id,
            dispatch_date="2026-07-09",
            delivery_date="2026-07-10",
            driver_name_snapshot="Gavin Fynn",
            vehicle_rego_snapshot="ABC123",
            status=status,
            trips=[
                SimpleNamespace(trip_no="trip1", orders=[object(), object()]),
                SimpleNamespace(trip_no="trip2", orders=[object()]),
            ],
        )

    @staticmethod
    def _collection():
        return SimpleNamespace(
            collection_id="COL-1",
            dispatch_date="2026-07-09",
            pickup_date="2026-07-10",
            driver_name_snapshot="Guanlin Li",
            status="SAVED",
            pickups=[
                SimpleNamespace(
                    pickup_category_snapshot="NORMAL",
                    run_type_snapshot="REGULAR",
                ),
                SimpleNamespace(
                    pickup_category_snapshot="NORMAL",
                    run_type_snapshot="ON_CALL",
                ),
                SimpleNamespace(
                    pickup_category_snapshot="COUNTRYSIDE",
                    run_type_snapshot="ON_CALL",
                ),
            ],
        )

    @staticmethod
    def _attache_row(
        row_id,
        source_filename,
        invoice_number,
        selected=True,
        importable=True,
    ):
        return {
            "row_id": row_id,
            "source_filename": source_filename,
            "selected": selected,
            "importable": importable,
            "is_duplicate": False,
            "invoice_number": invoice_number,
            "order_no": f"ORDER-{invoice_number}",
            "company_name": "Stage 2B Customer",
            "delivery_address": "1 Test Street",
            "suburb": "Coburg",
            "postcode": "3058",
            "delivery_date": "2026-07-10",
            "zone": "North",
            "urgency": "Normal",
            "pallet_quantity": 1,
            "loose_bags_quantity": 0,
            "product_lines": [
                {
                    "product_name": "COLOUR RAGS",
                    "quantity": 1,
                    "unit": "PALLETS",
                }
            ],
        }

    def _entries(self):
        files = list(self.logbook_dir.glob("manual_dispatch_logbook_*.txt"))
        if not files:
            return []
        self.assertEqual(1, len(files))
        return [
            json.loads(line)
            for line in files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _entries_for(self, action):
        return [entry for entry in self._entries() if entry["action"] == action]

    def _only_entry(self, action):
        entries = self._entries_for(action)
        self.assertEqual(1, len(entries), f"Expected one {action} event")
        return entries[0]

    def _template_entries(self):
        return [
            entry
            for entry in self._entries()
            if "_TEMPLATE_" in entry["action"]
        ]


if __name__ == "__main__":
    unittest.main()
