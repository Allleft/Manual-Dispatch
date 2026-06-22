import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.api import manual_dispatch as manual_dispatch_api
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    CommitAttacheInvoicePdfImportRequest,
    CommitAttacheInvoicePdfImportRow,
)
from backend.services.manual_dispatch_service import ManualDispatchService


class ManualDispatchAttacheInvoiceImportTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"attache-import-test-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self.service = ManualDispatchService(self.repository)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_commit_import_persists_cartons_and_returns_order_to_board(self):
        request = CommitAttacheInvoicePdfImportRequest(
            rows=[
                CommitAttacheInvoicePdfImportRow(
                    row_id="ATTACHE-184068",
                    source_filename="Customer Invoice 184068N.pdf",
                    invoice_number="184068",
                    order_no="7147703",
                    company_name="JB CAMERON",
                    phone="(03) 5337 4400",
                    delivery_address="126 ARMSTRONG ST SOUTH",
                    suburb="BALLARAT CENTRAL",
                    postcode="3350",
                    delivery_date="2026-06-05",
                    pallet_quantity=1,
                    loose_bags_quantity=0,
                    product_lines=[
                        {
                            "product_name": "COLOUR RAGS 10KG NET",
                            "quantity": 1,
                            "unit": "PALLETS",
                        },
                        {
                            "product_name": "COLOR RAGS 1.5KG BAG",
                            "quantity": 2,
                            "unit": "CARTONS",
                        },
                    ],
                )
            ]
        )

        with patch.object(manual_dispatch_api, "service", self.service):
            response = manual_dispatch_api.commit_attache_invoice_pdf_import(request)

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
        self.assertEqual("7147703", imported.order_no)
        self.assertEqual("ACTIVE", imported.status)
        self.assertEqual(1, imported.pallet_quantity)
        self.assertEqual(0, imported.loose_bags_quantity)
        self.assertEqual(
            ["PALLETS", "CARTONS"],
            [line.unit for line in imported.product_lines],
        )
        self.assertNotIn(
            imported.order_id,
            [assignment.task_id for assignment in board.assignments],
        )


if __name__ == "__main__":
    unittest.main()
