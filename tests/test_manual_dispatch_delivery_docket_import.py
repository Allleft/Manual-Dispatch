from datetime import date
from io import BytesIO
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient


_api_import_temp_dir = tempfile.TemporaryDirectory(
    prefix="manual-dispatch-docket-api-import-",
)
_api_import_previous_db_path = os.environ.get("MANUAL_DISPATCH_DB_PATH")
_api_import_previous_logbook_dir = os.environ.get("MANUAL_DISPATCH_LOGBOOK_DIR")
os.environ["MANUAL_DISPATCH_DB_PATH"] = str(
    Path(_api_import_temp_dir.name) / "manual_dispatch.sqlite3"
)
os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = str(
    Path(_api_import_temp_dir.name) / "logbook"
)
try:
    from backend.api import manual_dispatch as manual_dispatch_api
    from backend.main import app
finally:
    if _api_import_previous_db_path is None:
        os.environ.pop("MANUAL_DISPATCH_DB_PATH", None)
    else:
        os.environ["MANUAL_DISPATCH_DB_PATH"] = _api_import_previous_db_path
    if _api_import_previous_logbook_dir is None:
        os.environ.pop("MANUAL_DISPATCH_LOGBOOK_DIR", None)
    else:
        os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = _api_import_previous_logbook_dir

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    DeliveryWorkspaceAssignOrderRequest,
    Driver,
    GenerateDeliveryRunSheetRequest,
    RegisterOperatorAccountRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client


DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def tearDownModule():
    _api_import_temp_dir.cleanup()


def _docx_bytes(lines):
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    payload = BytesIO()
    document.save(payload)
    return payload.getvalue()


class ManualDispatchDeliveryDocketImportTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="manual-dispatch-docket-api-"))
        self.previous_logbook_dir = os.environ.get("MANUAL_DISPATCH_LOGBOOK_DIR")
        os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = str(self.temp_dir / "logbook")
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.identity = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Delivery Docket Tester",
                password="secret123",
                confirm_password="secret123",
            )
        )
        self.service_patcher = patch.object(
            manual_dispatch_api,
            "service",
            self.service,
        )
        self.service_patcher.start()
        self.client = TestClient(app)
        authenticate_test_client(self.client, self.service, self.identity)

    def tearDown(self):
        self.client.close()
        self.service_patcher.stop()
        if self.previous_logbook_dir is None:
            os.environ.pop("MANUAL_DISPATCH_LOGBOOK_DIR", None)
        else:
            os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = self.previous_logbook_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_multi_docx_preview_edit_commit_reload_board_and_run_sheet(self):
        cases = [
            (
                "docket-4373.docx",
                [
                    "DELIVERY DOCKET: 4373/185504",
                    "DATED: 11/08/2026",
                    "DELIVER TO:",
                    "C/-LUBRIMAXX SUNSHINE",
                    "30 SPENCER STREET",
                    "SUNSHINE WEST",
                    "ON FWD TO:",
                    "NOEL'S AUTO PARTS",
                    "366 EDWARD STREET",
                    "WAGGA WAGGA NSW 2650",
                    "PH: 02 6925 3777",
                    "ORDER NUMBER: 40592",
                    "36 X 10KG COLOUR T-SHIRT RAGS",
                    "1 PALLET",
                ],
            ),
            (
                "docket-4375.docx",
                [
                    "DELIVERY DOCKET: 4375/185512",
                    "DATED: 11/08/2026",
                    "DELIVER TO:",
                    "JJS WASTE & RECYLING",
                    "46-52 ELLIOTT ROAD",
                    "ENTRY VIA 427 HAMMOND RD",
                    "DANDENONG SOUTH 3175",
                    "ORDER NUMBER: 77058/VIC",
                    "45 X 10KG COLOURED SINGLET",
                    "1 PALLET",
                ],
            ),
        ]
        files = [
            ("files", (filename, _docx_bytes(lines), DOCX_CONTENT_TYPE))
            for filename, lines in cases
        ]

        with (
            patch.object(manual_dispatch_api, "service", self.service),
            patch(
                "backend.api.manual_dispatch_routes.delivery_docket_routes.current_melbourne_business_date",
                return_value=date(2026, 8, 13),
            ),
        ):
            preview_response = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
                files=files,
            )
            self.assertEqual(200, preview_response.status_code, preview_response.text)
            rows = preview_response.json()["rows"]
            self.assertEqual(2, len(rows))
            self.assertEqual(["2026-08-14", "2026-08-14"], [row["delivery_date"] for row in rows])
            self.assertEqual(["4373", "4375"], [row["docket_number"] for row in rows])

            rows[0]["company_name"] = "EDITED FINAL CUSTOMER"
            rows[0]["note"] += "\nOperator Review: dock access confirmed"
            commit_response = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-commit",
                json={"rows": rows},
            )
            self.assertEqual(200, commit_response.status_code, commit_response.text)
            self.assertEqual(2, commit_response.json()["imported_count"])
            created = commit_response.json()["created_orders"]

            board_response = self.client.get(
                "/api/manual-dispatch/delivery/board",
                params={"dispatch_date": "2026-08-14"},
            )
            self.assertEqual(200, board_response.status_code, board_response.text)
            board_orders = board_response.json()["orders"]
            imported = next(order for order in board_orders if order["invoice_number"] == "185504")
            self.assertEqual("EDITED FINAL CUSTOMER", imported["company_name"])
            self.assertEqual("30 SPENCER STREET", imported["delivery_address"])
            self.assertIn("Delivery Docket: 4373", imported["note"])
            self.assertIn("dock access confirmed", imported["note"])

        reloaded_service = ManualDispatchService(
            SQLiteManualDispatchRepository(self.db_path)
        )
        reloaded = reloaded_service.get_delivery_workspace_board("2026-08-14")
        persisted = next(order for order in reloaded.orders if order.invoice_number == "185504")
        self.assertEqual("EDITED FINAL CUSTOMER", persisted.company_name)
        self.assertEqual(360, persisted.product_lines[0].quantity)
        self.assertEqual("BAG10", persisted.product_lines[0].package_unit)

        self.repository.create_driver(
            Driver(
                driver_id="DOCKET-DRIVER",
                name="Docket Driver",
                start_time=None,
                end_time=None,
                is_available=True,
                preferred_zone=None,
                pallet_only=False,
            )
        )
        reloaded_service.assign_delivery_workspace_order(
            DeliveryWorkspaceAssignOrderRequest(
                dispatch_date="2026-08-14",
                order_id=created[0]["order_id"],
                driver_id="DOCKET-DRIVER",
                trip_no="trip1",
            )
        )
        run_sheet = reloaded_service.create_generated_delivery_run_sheet(
            GenerateDeliveryRunSheetRequest(
                dispatch_date="2026-08-14",
                delivery_date="2026-08-14",
                driver_id="DOCKET-DRIVER",
            )
        )
        snapshot = run_sheet.trips[0].orders[0]
        self.assertEqual("EDITED FINAL CUSTOMER", snapshot.company_name_snapshot)
        self.assertEqual("30 SPENCER STREET", snapshot.delivery_address_snapshot)
        self.assertIn("Delivery Docket: 4373", snapshot.note_snapshot)

    def test_docx_type_enforcement_and_existing_invoice_duplicate_semantics(self):
        lines = [
            "DELIVERY DOCKET: 4376/185531",
            "DATED: 21/08/2026",
            "DELIVER TO:",
            "SRGS PTY LTD",
            "413 MT ATKINSON ROAD",
            "TRUGANINA",
            "45 X 10KG COLOR T SHIRT RAGS",
            "6 PALLETS",
        ]
        with patch.object(manual_dispatch_api, "service", self.service):
            invalid_response = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
                files=[("files", ("wrong.pdf", b"%PDF-1.4", "application/pdf"))],
            )
            self.assertEqual(400, invalid_response.status_code)

            preview = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
                files=[("files", ("docket-4376.docx", _docx_bytes(lines), DOCX_CONTENT_TYPE))],
            )
            self.assertEqual(200, preview.status_code, preview.text)
            row = preview.json()["rows"][0]
            first_commit = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-commit",
                json={"rows": [row]},
            )
            self.assertEqual(1, first_commit.json()["imported_count"])

            duplicate_preview = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
                files=[("files", ("docket-4376.docx", _docx_bytes(lines), DOCX_CONTENT_TYPE))],
            )
            duplicate = duplicate_preview.json()["rows"][0]
            self.assertTrue(duplicate["is_duplicate"])
            self.assertFalse(duplicate["importable"])
            self.assertFalse(duplicate["selected"])

    def test_batch_limits_accept_30_and_reject_31_for_preview_and_commit(self):
        payload = _docx_bytes(
            [
                "DELIVERY DOCKET: 9000/199900",
                "DATED: 12/08/2026",
                "DELIVER TO:",
                "BATCH LIMIT CUSTOMER",
                "30 TEST ROAD",
                "RICHMOND 3121",
                "1 X 10KG COLOURED RAGS",
                "1 PALLET",
            ]
        )
        files = [
            (
                "files",
                (f"batch-{index:02d}.docx", payload, DOCX_CONTENT_TYPE),
            )
            for index in range(31)
        ]

        rows = None
        for file_count in (1, 20, 21, 30):
            preview_response = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
                files=files[:file_count],
            )
            self.assertEqual(200, preview_response.status_code, preview_response.text)
            preview_rows = preview_response.json()["rows"]
            self.assertEqual(file_count, len(preview_rows))
            if file_count == 30:
                rows = preview_rows
        self.assertIsNotNone(rows)

        overflow_preview = self.client.post(
            "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-preview",
            files=files,
        )
        self.assertEqual(413, overflow_preview.status_code, overflow_preview.text)

        for index, row in enumerate(rows):
            row["row_id"] = f"DOCKET-BATCH-{index:02d}"
            row["source_filename"] = f"batch-{index:02d}.docx"
            row["docket_number"] = f"93{index:03d}"
            row["invoice_number"] = f"930{index:03d}"
            row["is_duplicate"] = False
            row["importable"] = True
            row["selected"] = True
        commit_response = self.client.post(
            "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-commit",
            json={"rows": rows},
        )
        self.assertEqual(200, commit_response.status_code, commit_response.text)
        self.assertEqual(30, commit_response.json()["imported_count"])

        overflow_row = {**rows[-1]}
        overflow_row["row_id"] = "DOCKET-BATCH-OVERFLOW"
        overflow_row["docket_number"] = "93998"
        overflow_row["invoice_number"] = "930999"
        overflow_commit = self.client.post(
            "/api/manual-dispatch/delivery/orders/import-delivery-docket-docx-commit",
            json={"rows": [*rows, overflow_row]},
        )
        self.assertEqual(413, overflow_commit.status_code, overflow_commit.text)


if __name__ == "__main__":
    unittest.main()
