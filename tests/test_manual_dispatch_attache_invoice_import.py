from datetime import date
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    CommitAttacheInvoicePdfImportRequest,
    CommitAttacheInvoicePdfImportRow,
    RegisterOperatorAccountRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tests.manual_dispatch_api_test_helpers import authenticate_test_client


_api_import_temp_dir = tempfile.TemporaryDirectory(
    prefix="manual-dispatch-attache-api-import-",
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


def tearDownModule():
    _api_import_temp_dir.cleanup()


class ManualDispatchAttacheInvoiceImportTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"attache-import-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.previous_logbook_dir = os.environ.get("MANUAL_DISPATCH_LOGBOOK_DIR")
        os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = str(self.temp_dir / "logbook")
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)
        self.identity = self.service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name="Attaché Import Tester",
                password="secret123",
                confirm_password="secret123",
            )
        )
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        if self.previous_logbook_dir is None:
            os.environ.pop("MANUAL_DISPATCH_LOGBOOK_DIR", None)
        else:
            os.environ["MANUAL_DISPATCH_LOGBOOK_DIR"] = self.previous_logbook_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_commit_import_persists_product_packaging_and_load_to_board(self):
        request = CommitAttacheInvoicePdfImportRequest(
            rows=[
                CommitAttacheInvoicePdfImportRow(
                    row_id="ATTACHE-184068",
                    source_filename="Customer Invoice 184068N.pdf",
                    invoice_number="184068",
                    invoice_date="2026-06-04",
                    order_no="7147703",
                    company_name="JB CAMERON",
                    phone="(03) 5337 4400",
                    delivery_address="126 ARMSTRONG ST SOUTH",
                    suburb="BALLARAT CENTRAL",
                    postcode="3350",
                    delivery_date="2026-06-05",
                    pallet_quantity=1,
                    loose_bags_quantity=0,
                    carton_quantity=2,
                    product_lines=[
                        {
                            "product_code": "RBAG15",
                            "product_name": "COLOR RAGS 1.5KG BAG",
                            "quantity": 300,
                            "unit": "KG",
                            "package_quantity": 200,
                            "package_unit": "BAG1.5",
                        },
                    ],
                )
            ]
        )

        with patch.object(manual_dispatch_api, "service", self.service):
            response = manual_dispatch_api.commit_attache_invoice_pdf_import(
                request,
                SimpleNamespace(
                    state=SimpleNamespace(operator_identity=self.identity),
                ),
            )

        self.assertEqual(1, response["imported_count"])
        self.assertEqual(0, response["skipped_count"])
        created_order_id = response["created_orders"][0]["order_id"]

        reloaded_repository = SQLiteManualDispatchRepository(self.db_path)
        reloaded_service = ManualDispatchService(reloaded_repository)
        board = reloaded_service.get_board("2026-06-05")
        imported = next(
            order for order in board.orders if order.invoice_number == "184068"
        )

        self.assertEqual(created_order_id, imported.order_id)
        self.assertEqual("2026-06-04", imported.invoice_date)
        self.assertEqual("7147703", imported.order_no)
        self.assertEqual("ACTIVE", imported.status)
        self.assertEqual(1, imported.pallet_quantity)
        self.assertEqual(0, imported.loose_bags_quantity)
        self.assertEqual(2, imported.carton_quantity)
        self.assertEqual(1, len(imported.product_lines))
        product = imported.product_lines[0]
        self.assertEqual("RBAG15", product.product_code)
        self.assertEqual("COLOR RAGS 1.5KG BAG", product.product_name)
        self.assertEqual(300, product.quantity)
        self.assertEqual("KG", product.unit)
        self.assertEqual(200, product.package_quantity)
        self.assertEqual("BAG1.5", product.package_unit)
        self.assertNotIn(
            imported.order_id,
            [assignment.task_id for assignment in board.assignments],
        )

    def test_preview_commit_and_reopen_persist_true_invoice_and_import_delivery_dates(self):
        sanitized_text = """
        Invoice No 185517
        Date 11/08/26
        Order No Date
        11/08/26 CUSPER 32074
        Invoice to:
        CUSTOM PERFORMANCE GARAGE
        1 SANITIZED ROAD
        HALLAM 3803
        Deliver to:
        CUSTOM PERFORMANCE GARAGE
        1 SANITIZED ROAD
        HALLAM
        3803
        Tax Invoice
        RSING 96.25 KG 8.75 0.00 1.750 50 COLOR TSHIRT RAGS
        BAG10 0.00 0.00 0.00 0.000 5 PLASTIC BAG 10 kg
        Total Invoice:AUD 105.88
        """

        with (
            patch.object(manual_dispatch_api, "service", self.service),
            patch(
                "backend.api.manual_dispatch_routes.attache_routes.current_melbourne_business_date",
                return_value=date(2026, 8, 12),
            ),
            patch(
                "backend.services.manual_dispatch.attache_invoice_pdf_parser.extract_pdf_text",
                return_value=sanitized_text,
            ),
        ):
            authenticate_test_client(self.client, self.service, self.identity)
            preview_response = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-pdf-preview",
                files=[
                    (
                        "files",
                        (
                            "sanitized-185517.pdf",
                            b"%PDF-1.4 sanitized regression fixture",
                            "application/pdf",
                        ),
                    )
                ],
            )
            self.assertEqual(200, preview_response.status_code, preview_response.text)
            preview_row = preview_response.json()["rows"][0]
            self.assertEqual("2026-08-11", preview_row["invoice_date"])
            self.assertEqual("2026-08-13", preview_row["delivery_date"])
            self.assertEqual(5, preview_row["loose_bags_quantity"])

            commit_response = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit",
                json={"rows": [preview_row]},
            )
            self.assertEqual(200, commit_response.status_code, commit_response.text)
            self.assertEqual(1, commit_response.json()["imported_count"])

            board_response = self.client.get(
                "/api/manual-dispatch/delivery/board",
                params={"dispatch_date": "2026-08-13"},
            )
            self.assertEqual(200, board_response.status_code, board_response.text)
            api_order = next(
                order
                for order in board_response.json()["orders"]
                if order["invoice_number"] == "185517"
            )
            self.assertEqual("2026-08-11", api_order["invoice_date"])
            self.assertEqual("2026-08-13", api_order["delivery_date"])

        reloaded_repository = SQLiteManualDispatchRepository(self.db_path)
        reloaded_board = ManualDispatchService(
            reloaded_repository
        ).get_delivery_workspace_board("2026-08-13")
        persisted = next(
            order
            for order in reloaded_board.orders
            if order.invoice_number == "185517"
        )
        self.assertEqual("2026-08-11", persisted.invoice_date)
        self.assertEqual("2026-08-13", persisted.delivery_date)
        self.assertEqual(5, persisted.loose_bags_quantity)

    def test_batch_limits_accept_30_and_reject_31_for_preview_and_commit(self):
        sanitized_text = """
        Invoice No 199900
        Date 12/08/26
        Order No Date
        12/08/26 BATCH30 ORDER-30
        Invoice to:
        BATCH LIMIT CUSTOMER
        30 TEST ROAD
        RICHMOND 3121
        Deliver to:
        BATCH LIMIT CUSTOMER
        30 TEST ROAD
        RICHMOND
        3121
        Tax Invoice
        TEST 1 KG SAMPLE PRODUCT 1.000 1.00 1.00 0.00
        """
        files = [
            (
                "files",
                (
                    f"batch-{index:02d}.pdf",
                    b"%PDF-1.4 sanitized batch fixture",
                    "application/pdf",
                ),
            )
            for index in range(31)
        ]

        with (
            patch.object(manual_dispatch_api, "service", self.service),
            patch(
                "backend.services.manual_dispatch.attache_invoice_pdf_parser.extract_pdf_text",
                return_value=sanitized_text,
            ),
        ):
            authenticate_test_client(self.client, self.service, self.identity)
            rows = None
            for file_count in (1, 20, 21, 30):
                preview_response = self.client.post(
                    "/api/manual-dispatch/delivery/orders/import-attache-pdf-preview",
                    files=files[:file_count],
                )
                self.assertEqual(200, preview_response.status_code, preview_response.text)
                preview_rows = preview_response.json()["rows"]
                self.assertEqual(file_count, len(preview_rows))
                if file_count == 30:
                    rows = preview_rows
            self.assertIsNotNone(rows)

            overflow_preview = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-pdf-preview",
                files=files,
            )
            self.assertEqual(413, overflow_preview.status_code, overflow_preview.text)

            for index, row in enumerate(rows):
                row["row_id"] = f"ATTACHE-BATCH-{index:02d}"
                row["source_filename"] = f"batch-{index:02d}.pdf"
                row["invoice_number"] = f"920{index:03d}"
                row["order_no"] = f"BATCH-{index:02d}"
                row["is_duplicate"] = False
                row["importable"] = True
                row["selected"] = True
            commit_response = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit",
                json={"rows": rows},
            )
            self.assertEqual(200, commit_response.status_code, commit_response.text)
            self.assertEqual(30, commit_response.json()["imported_count"])

            overflow_row = {**rows[-1]}
            overflow_row["row_id"] = "ATTACHE-BATCH-OVERFLOW"
            overflow_row["invoice_number"] = "920999"
            overflow_commit = self.client.post(
                "/api/manual-dispatch/delivery/orders/import-attache-pdf-commit",
                json={"rows": [*rows, overflow_row]},
            )
            self.assertEqual(413, overflow_commit.status_code, overflow_commit.text)


if __name__ == "__main__":
    unittest.main()
