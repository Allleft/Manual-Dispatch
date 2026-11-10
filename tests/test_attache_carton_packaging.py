from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import Mock, patch
import unittest

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.repositories.sqlite_manual_dispatch_repository import SQLiteManualDispatchRepository
from backend.schemas import (CreateDriverRequest, DeliveryWorkspaceAssignOrderRequest,
                             GenerateDeliveryRunSheetRequest, ProductDetailLine,
                             SaveGeneratedWorkspaceSnapshotRequest)
from backend.services.manual_dispatch.attache_direct_invoice_normalizer import normalize_direct_attache_invoice
from backend.services.manual_dispatch.attache_invoice_pdf_parser import (
    normalize_attache_structured_product_rows, parse_attache_invoice_text,
)
from backend.services.manual_dispatch.attache_carton_packaging import cartonized_product_weight_kg
from backend.services.manual_dispatch_service import ManualDispatchService
from backend.services.delivery_run_sheet_excel_export_service import (
    build_delivery_run_sheet_excel, build_delivery_run_sheets_excel,
    delivery_run_sheet_product_display,
)
from tests.manual_dispatch_api_test_helpers import authenticate_test_client
from tests.test_attache_import_urgency_frontend import NODE_HARNESS
from tests.test_delivery_run_sheet_excel_pagination import synthetic_order, synthetic_sheet, finish_row


ROOT = Path(__file__).resolve().parents[1]


def carton_payload(bags=14, cartons=2):
    return {
        "invoice_number": "187321", "invoice_date": "2026-11-05", "customer_code": "SYNTHETIC-BOWENS",
        "customer_name": "BOWENS THE BUILDERS CHOICE", "order_reference": "SYNTHETIC-PO-187321",
        "delivery_address_lines": ["1 SYNTHETIC ROAD"], "suburb": "HALLAM", "postcode": "3803",
        "lines": [
            {"code": "RSING1.5KG", "description": "COLOR RAGS 1.5KG BAG", "quantity_invoiced": bags, "unit": "BAG"},
            {"code": "BAG1.5", "description": "PLASTIC BAG 1.5 kg", "quantity_invoiced": bags, "unit": "EACH"},
            {"code": "RWTSHIRT1.", "description": "WHITE T-SHIRT RAGS 1.5KG BAG", "quantity_invoiced": bags, "unit": "BAG"},
            {"code": "BAG1.5", "description": "PLASTIC BAG 1.5 kg", "quantity_invoiced": bags, "unit": "EACH"},
            {"code": "CTN", "description": "CARTONS", "quantity_invoiced": cartons, "unit": "CTN"},
            {"code": "DEL", "description": "DELIVERY / FUEL LEVY CHARGE", "quantity_invoiced": 1, "unit": "EACH"},
        ],
    }


CARTON_PDF_TEXT = """
Invoice No 187321
Order No Date
05/11/26 SYNBOW SYNTHETIC-PO-187321
Invoice to:
BOWENS THE BUILDERS CHOICE
1 SYNTHETIC ROAD
HALLAM 3803
Deliver to:
BOWENS THE BUILDERS CHOICE
1 SYNTHETIC ROAD
HALLAM 3803
Tax Invoice
RSING1.5KG 9.80 BAG 14 COLOR RAGS 1.5KG BAG 3.500 107.80 98.00
BAG1.5 0.00 14 PLASTIC BAG 1.5 kg 0.000 0.00 0.00
RWTSHIRT1. 9.80 BAG 14 WHITE T-SHIRT RAGS 1.5KG BAG 3.500 107.80 98.00
BAG1.5 0.00 14 PLASTIC BAG 1.5 kg 0.000 0.00 0.00
CTN 0.00 CTN 2 CARTONS 0.000 0.00 0.00
DEL 10.50 DEL 1 DELIVERY /FUEL LEVY CHARGE 105.000 115.50 105.00
"""


def carton_pdf_bytes():
    # Minimal real text PDF keeps extraction in the end-to-end import path.
    lines = [line for line in CARTON_PDF_TEXT.strip().splitlines() if line]
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    stream = ("BT /F1 9 Tf 12 TL 40 800 Td\n" + "\n".join(f"({line}) Tj T*" for line in escaped) + "\nET\n").encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream"]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{number} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    start = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{value:010d} 00000 n \n".encode("ascii") for value in offsets[1:])
    return result + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode("ascii")


def normalize(payload):
    return normalize_attache_structured_product_rows(payload["lines"])


class AttacheCartonNormalizationTest(unittest.TestCase):
    def assert_unconverted(self, payload, warning=True):
        before = deepcopy(payload)
        result = normalize(payload)
        self.assertEqual(before, payload)
        self.assertTrue(all(line["package_unit"] != "CARTON" for line in result["product_lines"]))
        if warning:
            self.assertTrue(any("Carton allocation requires review" in text for text in result["warnings"]), result)
        return result

    def test_pdf_and_direct_equivalent_invoice_keep_bags_and_ship_two_cartons(self):
        payload = carton_payload()
        before = deepcopy(payload)
        direct = normalize_direct_attache_invoice(payload, import_date=date(2026, 11, 5))
        pdf = parse_attache_invoice_text(CARTON_PDF_TEXT, source_filename="synthetic-187321.pdf",
                                        import_date=date(2026, 11, 5))
        self.assertEqual(before, payload)
        self.assertEqual(pdf.product_lines, direct.product_lines)
        for parsed in (pdf, direct):
            self.assertEqual((0, 0, 2), (parsed.pallet_quantity, parsed.loose_bags_quantity, parsed.carton_quantity))
            self.assertEqual(2, len(parsed.product_lines))
            self.assertEqual([(14, "BAG", 1, "CARTON")] * 2,
                             [(p["quantity"], p["unit"], p["package_quantity"], p["package_unit"]) for p in parsed.product_lines])
            self.assertEqual(42, sum(cartonized_product_weight_kg(p) for p in parsed.product_lines))
            self.assertEqual("187321", parsed.invoice_number)
            self.assertEqual("SYNTHETIC-PO-187321", parsed.order_no)
            self.assertEqual("BOWENS THE BUILDERS CHOICE", parsed.company_name)
            self.assertEqual([], parsed.warnings)

    def test_single_28_bag_product_with_ctn2_ships_two_cartons(self):
        payload = carton_payload(bags=28)
        del payload["lines"][2:4]
        result = normalize(payload)
        self.assertEqual((28, 2, "CARTON"), tuple(result["product_lines"][0][k]
                                                for k in ("quantity", "package_quantity", "package_unit")))
        self.assertEqual(42, cartonized_product_weight_kg(result["product_lines"][0]))

    def test_without_ctn_preserves_inner_bags_as_loose_load(self):
        payload = carton_payload()
        del payload["lines"][4]
        result = self.assert_unconverted(payload)
        self.assertEqual((28, 0), (result["loose_bags_quantity"], result["carton_quantity"]))
        pdf = parse_attache_invoice_text(CARTON_PDF_TEXT.replace("CTN 0.00 CTN 2 CARTONS 0.000 0.00 0.00", ""),
                                        source_filename="synthetic-no-ctn.pdf", import_date=date(2026, 11, 5))
        self.assertEqual(28, pdf.loose_bags_quantity)

    def test_pallet_allocation_is_not_assumed(self):
        payload = carton_payload()
        payload["lines"].append({"code": "PAL", "description": "PALLET", "unit": "PLT", "quantity_invoiced": 1})
        result = self.assert_unconverted(payload)
        self.assertEqual((1, 0, 2), tuple(result[k] for k in ("pallet_quantity", "loose_bags_quantity", "carton_quantity")))

    def test_existing_pallet_only_1_5kg_invoice_is_unchanged_without_carton_warning(self):
        payload = carton_payload()
        del payload["lines"][4]
        payload["lines"].append({"code": "PAL", "description": "PALLET", "quantity_invoiced": 1})
        result = self.assert_unconverted(payload, warning=False)
        self.assertEqual([], result["warnings"])
        self.assertEqual((1, 0, 0), tuple(result[k] for k in ("pallet_quantity", "loose_bags_quantity", "carton_quantity")))

    def test_mixed_pallet_carton_loose_load_is_not_converted(self):
        payload = carton_payload()
        payload["lines"].extend([{"code": "PAL", "description": "PALLET", "quantity_invoiced": 1},
                                 {"code": "LBAG", "description": "LOOSE BAGS", "quantity_invoiced": 3}])
        result = self.assert_unconverted(payload)
        self.assertEqual((1, 3, 2), tuple(result[k] for k in ("pallet_quantity", "loose_bags_quantity", "carton_quantity")))

    def test_two_products_ctn1_and_three_products_ctn2_do_not_reconcile(self):
        for third in (False, True):
            payload = carton_payload(cartons=2 if third else 1)
            if third:
                payload["lines"][4:4] = [dict(payload["lines"][0], code="SYNTHETIC-THIRD"), deepcopy(payload["lines"][1])]
            self.assert_unconverted(payload)

    def test_missing_companion_bag_row_is_not_guessed_from_name(self):
        payload = carton_payload()
        del payload["lines"][1]
        self.assert_unconverted(payload)

    def test_inconsistent_companion_count_is_not_converted(self):
        payload = carton_payload()
        payload["lines"][1]["quantity_invoiced"] = 28
        self.assert_unconverted(payload)

    def test_invalid_or_indivisible_inner_bag_quantities_are_not_converted(self):
        for quantity in (0, -14, 15, 14.5, True, "unknown"):
            with self.subTest(quantity=quantity):
                self.assert_unconverted(carton_payload(bags=quantity))

    def test_unknown_or_conflicting_package_size_is_not_converted(self):
        for change in ("BAG2", "CONFLICT"):
            payload = carton_payload()
            if change == "BAG2":
                payload["lines"][1].update(code="BAG2", description="PLASTIC BAG 2 kg")
            else:
                payload["lines"][0]["code"] = "RSING10KG"
            self.assert_unconverted(payload)

    def test_duplicate_packaging_rows_are_flagged_without_changing_products(self):
        payload = carton_payload()
        payload["lines"].insert(2, deepcopy(payload["lines"][1]))
        result = self.assert_unconverted(payload)
        self.assertEqual([14, 14], [p["package_quantity"] for p in result["product_lines"]])

    def test_duplicate_ctn_records_are_not_accepted_as_independent_proof(self):
        payload = carton_payload(cartons=1)
        payload["lines"].insert(5, deepcopy(payload["lines"][4]))
        self.assert_unconverted(payload)

    def test_ctn_without_identifiable_products_does_not_create_product(self):
        payload = carton_payload()
        payload["lines"] = payload["lines"][4:]
        self.assertEqual([], self.assert_unconverted(payload)["product_lines"])

    def test_other_bag_box_packet_units_are_never_divided_by_14(self):
        for unit, name in (("BAG10", "10KG"), ("BAG5", "5KG"), ("BAG", "generic"), ("BOX", "box"), ("PKT", "packet")):
            with self.subTest(unit=unit):
                payload = carton_payload()
                payload["lines"] = [{"code": "SYNTHETIC", "description": name, "quantity_invoiced": 14, "unit": unit}, payload["lines"][4]]
                result = self.assert_unconverted(payload, warning=False)
                self.assertEqual(14, result["product_lines"][0]["quantity"])

    def test_mixed_unrelated_product_preserves_all_original_packaging(self):
        payload = carton_payload()
        payload["lines"].insert(4, {"code": "GLOVE", "description": "Glove", "quantity_invoiced": 2, "unit": "BOX"})
        result = self.assert_unconverted(payload)
        self.assertEqual(3, len(result["product_lines"]))

    def test_weight_actual_product_does_not_lose_original_package_pair(self):
        payload = carton_payload()
        payload["lines"][0].update(quantity_invoiced=21, unit="KG")
        result = self.assert_unconverted(payload)
        self.assertEqual((21, "KG", 14, "BAG1.5"), tuple(result["product_lines"][0][k]
                                                      for k in ("quantity", "unit", "package_quantity", "package_unit")))

    def test_legacy_saved_closed_raw_snapshots_are_not_reinterpreted_or_modified(self):
        raw = [ProductDetailLine("COLOR RAGS 1.5KG BAG", 14, "BAG", "RSING1.5KG", 14, "BAG1.5")]
        for status in ("SAVED", "CLOSED"):
            sheet = synthetic_sheet([synthetic_order(lines=raw, pallet_quantity_snapshot=0,
                                                     loose_bags_quantity_snapshot=0, carton_quantity_snapshot=1)], trip=None, status=status)
            before = deepcopy(sheet)
            self.assertIn("1.5kg x 14Bag", delivery_run_sheet_product_display(sheet.trips[0].orders[0]))
            build_delivery_run_sheet_excel(sheet)
            self.assertEqual(before, sheet)

    def test_delivery_ui_preview_details_trip_and_run_sheet_use_shipping_cartons(self):
        lines = normalize(carton_payload())["product_lines"]
        order = dict(order_id="SYNTHETIC-187321", invoice_number="187321", company_name="Synthetic Bowens",
                     delivery_date="2026-11-06", product_lines=lines, pallet_quantity=0, loose_bags_quantity=0, carton_quantity=2)
        snapshot = dict(product_lines_snapshot=lines, pallet_quantity_snapshot=0, loose_bags_quantity_snapshot=0, carton_quantity_snapshot=2)
        prelude = NODE_HARNESS.split("const {\n  attacheRowStatus")[0]
        script = prelude + "\nconst order = " + json.dumps(order) + ";\nconst snapshot = " + json.dumps(snapshot) + ";\n" + r"""
const { createDeliveryOrderReadOnly } = await import('./frontend/js/render/delivery/delivery-order-modal-renderer.js');
const { createAssignedOrderRow } = await import('./frontend/js/render/delivery/delivery-trip-summary-renderer.js');
const { dailyRunSheetRowValues, formatRunSheetKgTotal } = await import('./frontend/js/render/delivery/delivery-run-sheet-renderer.js');
const { productLineSummary } = await import('./frontend/js/render/delivery/delivery-attache-modal-renderer.js');
const { formatProductDetailLine, formatDeliveryProductDetailLine } = await import('./frontend/js/utils/format-utils.js');
const before = JSON.stringify({order,snapshot});
const detail = createDeliveryOrderReadOnly(order, {}, {drivers:[], assignments:[]});
const trip = createAssignedOrderRow(order, {trip_no:'trip1'}, {driver_id:'SYN-D'}, false, {deliveryTripSummaryRunSheets:[]}, {});
for (const text of [detail.textContent, trip.textContent, productLineSummary(order), dailyRunSheetRowValues(snapshot,1)[4]]) {
 assert.equal((text.match(/1 Carton/g)||[]).length,2,text);
 assert.ok(!text.includes('14 BAG'),text);
}
assert.ok(detail.textContent.includes('Carton quantity2'));
assert.ok(detail.textContent.includes('Loose bag quantity0'));
assert.ok(detail.textContent.includes('Pallet quantity0'));
assert.equal(formatRunSheetKgTotal(snapshot),'42');
assert.deepEqual(dailyRunSheetRowValues(snapshot,1).slice(6,9),['0','0','2']);
assert.ok(formatProductDetailLine(order.product_lines[0]).includes('14 BAG'));
for (const unit of ['BOX','BAG','PKT','BAG10','BAG5']) {
 const line={product_name:'Other',quantity:14,unit,package_quantity:14,package_unit:unit};
 assert.equal(formatDeliveryProductDetailLine(line),formatProductDetailLine(line));
}
assert.equal(JSON.stringify({order,snapshot}),before);
"""
        result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_shipping_carton_edits_do_not_change_original_bag_weight(self):
        original = ProductDetailLine(**normalize(carton_payload())["product_lines"][0])
        for cartons in (0, 2, 20):
            with self.subTest(cartons=cartons):
                line = replace(original, package_quantity=cartons)
                self.assertEqual(21, cartonized_product_weight_kg(line))
                sheet = synthetic_sheet([synthetic_order(lines=[line])])
                book = load_workbook(BytesIO(build_delivery_run_sheet_excel(sheet)))
                self.assertEqual(21, book.active["F9"].value)
                book.close()
                script = "const {getDeliveryProductWeightKg} = await import('./frontend/js/utils/format-utils.js'); "
                script += "if (getDeliveryProductWeightKg(" + json.dumps(asdict(line)) + ") !== 21) throw Error('Shipping edit changed original bag weight');"
                result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)

    def test_excel_shipping_counts_weight_and_worksheet_independence(self):
        lines = [ProductDetailLine(**p) for p in normalize(carton_payload())["product_lines"]]
        order = synthetic_order(lines=lines, pallet_quantity_snapshot=0, loose_bags_quantity_snapshot=0, carton_quantity_snapshot=2)
        sheets = [synthetic_sheet([order], trip=trip, driver_name_snapshot=driver)
                  for driver, trip in (("Driver A", "trip1"), ("Driver A", "trip2"), ("Driver B", "trip1"))]
        before = deepcopy(sheets)
        book = load_workbook(BytesIO(build_delivery_run_sheets_excel(sheets, sheets[0].delivery_date)), rich_text=True)
        self.addCleanup(book.close)
        for ws in book:
            self.assertEqual(42, ws["F9"].value)
            self.assertEqual(2, str(ws["E9"].value).count("1 Carton"))
            self.assertEqual(8, ws["E9"].font.sz)
            start = finish_row(ws) + 4
            self.assertEqual(["CARTON", "CARTON"], [ws.cell(r, 6).value for r in (start, start + 1)])
            self.assertEqual([1, 1], [ws.cell(r, 10).value for r in (start, start + 1)])
            self.assertEqual(start + 1, ws.max_row)
            for label in ("Known product total", "UNALLOCATED loose bags", "Total loose bags"):
                self.assertNotIn(label, [cell.value for row in ws for cell in row])
        self.assertEqual(before, sheets)


class AttacheCartonImportRoundtripTest(unittest.TestCase):
    def exercise(self, source):
        from backend.api import manual_dispatch as api
        from backend.main import app
        with tempfile.TemporaryDirectory(prefix="synthetic-carton-") as directory:
            path = Path(directory) / "synthetic.sqlite3"
            repository = SQLiteManualDispatchRepository(path)
            service = ManualDispatchService(repository)
            bridge = Mock()
            bridge.lookup_invoice.return_value = carton_payload()
            with (TestClient(app) as client, patch.object(api, "service", service),
                  patch("backend.api.manual_dispatch_routes.attache_routes.create_attache_bridge_client", return_value=bridge),
                  patch("backend.api.manual_dispatch_routes.attache_routes.current_melbourne_business_date", return_value=date(2026, 11, 5))):
                args = ({"json": {"invoice_number": "187321"}} if source == "direct" else
                        {"files": [("files", ("synthetic.pdf", carton_pdf_bytes(), "application/pdf"))]})
                endpoint = f"/api/manual-dispatch/delivery/orders/import-attache-{source}-preview"
                self.assertEqual(401, client.post(endpoint, **args).status_code)
                authenticate_test_client(client, service, account_name="Synthetic carton operator")
                preview = client.post(endpoint, **args)
                self.assertEqual(200, preview.status_code, preview.text)
                row = preview.json()["rows"][0]
                self.assertEqual((0, 0, 2), tuple(row[k] for k in ("pallet_quantity", "loose_bags_quantity", "carton_quantity")))
                self.assertEqual(2, len(row["product_lines"]))
                self.assertEqual([], row["warnings"])
                response = client.post("/api/manual-dispatch/delivery/orders/import-attache-pdf-commit", json={"rows": [row]})
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual(1, response.json()["imported_count"])
                duplicate = client.post("/api/manual-dispatch/delivery/orders/import-attache-pdf-commit", json={"rows": [row]})
                self.assertEqual((0, 1), (duplicate.json()["imported_count"], duplicate.json()["skipped_count"]))
                order_id = response.json()["created_orders"][0]["order_id"]
            reloaded = SQLiteManualDispatchRepository(path)
            order = reloaded.get_order(order_id)
            self.assertEqual((0, 0, 2), (order.pallet_quantity, order.loose_bags_quantity, order.carton_quantity))
            self.assertEqual([(14, "BAG", 1, "CARTON")] * 2,
                             [(p.quantity, p.unit, p.package_quantity, p.package_unit) for p in order.product_lines])
            self.assertEqual("SYNTHETIC-PO-187321", order.order_no)
            reloaded_service = ManualDispatchService(reloaded)
            driver = reloaded_service.create_delivery_driver(CreateDriverRequest(name="Synthetic carton driver"))
            reloaded_service.assign_delivery_workspace_order(DeliveryWorkspaceAssignOrderRequest(order_id=order_id, driver_id=driver.driver_id, trip_no="trip1"))
            sheet = reloaded_service.create_generated_delivery_run_sheet(GenerateDeliveryRunSheetRequest(delivery_date=order.delivery_date, driver_id=driver.driver_id, trip_no="trip1"))
            self.assertEqual((0, 0, 2), (sheet.total_pallets, sheet.total_loose_bags, sheet.total_cartons))
            self.assertEqual(order.product_lines, sheet.trips[0].orders[0].product_lines_snapshot)
            account = reloaded.get_operator_account_by_name("Synthetic carton operator")
            saved = reloaded_service.save_generated_delivery_run_sheet(sheet.run_sheet_id, SaveGeneratedWorkspaceSnapshotRequest(saved_by_account_id=account.account_id, saved_by_account_name=account.account_name))
            before = deepcopy(saved)
            book = load_workbook(BytesIO(build_delivery_run_sheet_excel(reloaded_service.get_saved_delivery_run_sheet_for_export(saved.run_sheet_id))))
            self.assertEqual(42, book.active["F9"].value)
            self.assertEqual(2, book.active["E9"].value.count("1 Carton"))
            book.close()
            self.assertEqual(before, reloaded.get_delivery_run_sheet(saved.run_sheet_id))

    def test_pdf_preview_commit_reload_generate_save_export(self):
        self.exercise("pdf")

    def test_direct_preview_commit_reload_generate_save_export(self):
        self.exercise("direct")
