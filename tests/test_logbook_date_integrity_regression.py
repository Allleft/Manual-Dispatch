import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from backend.schemas import (
    CreateOrderRequest,
    GenerateDeliveryRunSheetRequest,
    GenerateOpShopPickupCollectionRequest,
)
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService
from backend.services.manual_dispatch_service import ManualDispatchService
from tools import check_logbook_integrity, read_logbook


class CapturingLogbook:
    def __init__(self):
        self.entries = []

    def record(self, **entry):
        self.entries.append(entry)


class FailingLogbook:
    def record(self, **entry):
        raise OSError("synthetic writer failure")


class LogbookDateIntegrityRegressionTest(unittest.TestCase):
    def test_failed_dates_normalize_empty_values_and_preserve_valid_dates(self):
        logbook = CapturingLogbook()
        service = ManualDispatchService(logbook=logbook)

        self._record_failure(
            service,
            dispatch_date=None,
            delivery_date="",
            pickup_date="   ",
        )
        empty_entry = logbook.entries[-1]
        self.assertIsNone(empty_entry["dispatch_date"])
        self.assertIsNone(empty_entry["delivery_date"])
        self.assertIsNone(empty_entry["pickup_date"])
        self.assertNotIn(
            "rejected_logbook_date_fields",
            empty_entry["metadata"],
        )

        self._record_failure(
            service,
            dispatch_date="2026-07-14",
            delivery_date="2026-07-15",
            pickup_date="2026-07-16",
        )
        valid_entry = logbook.entries[-1]
        self.assertEqual("2026-07-14", valid_entry["dispatch_date"])
        self.assertEqual("2026-07-15", valid_entry["delivery_date"])
        self.assertEqual("2026-07-16", valid_entry["pickup_date"])
        self.assertNotIn(
            "rejected_logbook_date_fields",
            valid_entry["metadata"],
        )

    def test_failed_dates_reject_malformed_nonempty_values_without_guessing(self):
        values = (
            "2026-07-14T08:30:00+10:00",
            "2026-7-14",
            "2026-02-30",
            "14/07/2026",
        )
        for value in values:
            with self.subTest(value=value):
                logbook = CapturingLogbook()
                service = ManualDispatchService(logbook=logbook)
                self._record_failure(service, dispatch_date=value)

                entry = logbook.entries[-1]
                self.assertIsNone(entry["dispatch_date"])
                self.assertEqual(
                    ["dispatch_date"],
                    entry["metadata"]["rejected_logbook_date_fields"],
                )
                self.assertNotIn(value, json.dumps(entry))

    def test_failed_dates_reject_wrong_types_without_raising(self):
        logbook = CapturingLogbook()
        service = ManualDispatchService(logbook=logbook)
        self._record_failure(service, dispatch_date=object())

        entry = logbook.entries[-1]
        self.assertIsNone(entry["dispatch_date"])
        self.assertEqual(
            ["dispatch_date"],
            entry["metadata"]["rejected_logbook_date_fields"],
        )

    def test_rejected_generate_requests_write_contract_valid_failed_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logbook_dir = Path(temp_dir)
            service = ManualDispatchService(
                logbook=LogbookFileService(logbook_dir),
            )
            fixed_now = datetime.fromisoformat("2026-07-14T10:00:00+10:00")

            with patch(
                "backend.services.manual_dispatch.logbook_file_service._melbourne_now",
                return_value=fixed_now,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "dispatch_date must use YYYY-MM-DD",
                ):
                    service.create_generated_delivery_run_sheet(
                        GenerateDeliveryRunSheetRequest(
                            dispatch_date="24-06-2026",
                            delivery_date="2026-06-24",
                            driver_id="DRIVER-1",
                        )
                    )
                with self.assertRaisesRegex(
                    ValueError,
                    "pickup_date must be a valid YYYY-MM-DD date",
                ):
                    service.create_generated_opshop_pickup_collection(
                        GenerateOpShopPickupCollectionRequest(
                            dispatch_date="2026-06-24",
                            pickup_date="2026-99-24",
                            driver_id="DRIVER-1",
                        )
                    )

            path = logbook_dir / "manual_dispatch_logbook_2026-07.txt"
            text = path.read_text(encoding="utf-8")
            records = [json.loads(line) for line in text.splitlines()]
            self.assertEqual(2, len(records))
            self.assertEqual(["FAILED", "FAILED"], [row["result"] for row in records])
            self.assertIsNone(records[0]["dispatch_date"])
            self.assertEqual("2026-06-24", records[0]["delivery_date"])
            self.assertEqual(
                ["dispatch_date"],
                records[0]["metadata"]["rejected_logbook_date_fields"],
            )
            self.assertEqual("2026-06-24", records[1]["dispatch_date"])
            self.assertIsNone(records[1]["pickup_date"])
            self.assertEqual(
                ["pickup_date"],
                records[1]["metadata"]["rejected_logbook_date_fields"],
            )
            self.assertNotIn("24-06-2026", text)
            self.assertNotIn("2026-99-24", text)

            integrity = check_logbook_integrity.check_logbook_integrity(logbook_dir)
            self.assertTrue(integrity.ok)
            self.assertEqual(0, integrity.error_count)
            self.assertEqual(2, integrity.records_checked)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = read_logbook.main(
                    [
                        "--logbook-dir",
                        str(logbook_dir),
                        "--format",
                        "jsonl",
                    ]
                )
            reader_records = [
                json.loads(line)
                for line in stdout.getvalue().splitlines()
                if line.strip()
            ]
            self.assertEqual(0, exit_code)
            self.assertEqual(2, len(reader_records))
            self.assertEqual(
                {
                    "DELIVERY_RUN_SHEET_GENERATED",
                    "PICKUP_COLLECTION_GENERATED",
                },
                {row["action"] for row in reader_records},
            )

    def test_physical_writer_failure_does_not_block_successful_business_operation(self):
        service = ManualDispatchService(logbook=FailingLogbook())
        request = CreateOrderRequest(
            invoice_number="DATE-INTEGRITY-001",
            order_no="DATE-INTEGRITY-001",
            company_name="Synthetic Customer",
            phone="",
            delivery_address="1 Test Street",
            suburb="Coburg",
            postcode="3058",
            delivery_date="2026-07-14",
            zone="North",
            urgency="Normal",
            pallet_quantity=1,
            loose_bags_quantity=0,
            product_lines=[
                {
                    "product_name": "Synthetic Product",
                    "quantity": 1,
                    "unit": "PALLETS",
                }
            ],
        )

        with self.assertLogs(
            "backend.services.manual_dispatch_service",
            level="ERROR",
        ):
            order = service.create_delivery_order(request)

        self.assertEqual("Synthetic Customer", order.company_name)

    def test_physical_writer_failure_does_not_replace_business_error(self):
        service = ManualDispatchService(logbook=FailingLogbook())

        with self.assertLogs(
            "backend.services.manual_dispatch_service",
            level="ERROR",
        ):
            with self.assertRaisesRegex(
                ValueError,
                "dispatch_date must use YYYY-MM-DD",
            ):
                service.create_generated_delivery_run_sheet(
                    GenerateDeliveryRunSheetRequest(
                        dispatch_date="24-06-2026",
                        delivery_date="2026-06-24",
                        driver_id="DRIVER-1",
                    )
                )

    @staticmethod
    def _record_failure(service, **dates):
        service._record_failed_logbook(
            workspace="DELIVERY",
            action="DELIVERY_RUN_SHEET_GENERATED",
            entity_type="DELIVERY_RUN_SHEET",
            summary="Synthetic failure.",
            **dates,
        )
