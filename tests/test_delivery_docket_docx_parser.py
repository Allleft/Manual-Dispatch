from datetime import date
from io import BytesIO
import unittest

from docx import Document

from backend.services.manual_dispatch.delivery_docket_docx_parser import (
    extract_delivery_docket_docx_text,
    parse_delivery_docket_docx_bytes,
    parse_delivery_docket_text,
)


IMPORT_DATE = date(2026, 8, 13)


def _docx_bytes(lines, table_rows=()):
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    if table_rows:
        table = document.add_table(rows=0, cols=len(table_rows[0]))
        for values in table_rows:
            cells = table.add_row().cells
            for cell, value in zip(cells, values):
                cell.text = value
    payload = BytesIO()
    document.save(payload)
    return payload.getvalue()


def _parse(lines, filename):
    return parse_delivery_docket_docx_bytes(
        _docx_bytes(lines),
        source_filename=filename,
        import_date=IMPORT_DATE,
    )


class DeliveryDocketDocxParserTest(unittest.TestCase):
    def test_extracts_paragraphs_and_table_cells_in_document_order(self):
        payload = _docx_bytes(
            ["DELIVERY DOCKET: 4370/185467", "DATED: 10/08/2026"],
            table_rows=[("DELIVER TO:", "PATONS TRANSPORT"), ("143 FOUNDATION ROAD", "TRUGANINA")],
        )

        text = extract_delivery_docket_docx_text(payload)

        self.assertLess(text.index("DATED: 10/08/2026"), text.index("DELIVER TO:"))
        self.assertLess(text.index("DELIVER TO:"), text.index("PATONS TRANSPORT"))
        self.assertLess(text.index("143 FOUNDATION ROAD"), text.index("TRUGANINA"))

    def test_case_4370_prefers_substantive_header_and_on_forward_customer(self):
        parsed = _parse(
            [
                "DELIVERY DOCKET: 073",
                "DELIVERY DOCKET: 4370/185467",
                "DATED: 10/08/2026",
                "EMAIL PATONS TRANSPORT TO ADVISE DROP OFF OF STOCK",
                "admin@patonstransport.com.au",
                "DELIVER to",
                "PATONS TRANSPORT",
                "c/o Victorian freight specialists",
                "143 foundation road",
                "truganina",
                "ON FWD TO:",
                "CHEMBLAST INDUSTRIAL COATINGS",
                "14 DEANE STREET",
                "BUNBURY WA 6230",
                "52 x 10kg COLOUR SINGLET RAGS",
                "1 PALLET",
                "INVOICE TO FOLLOW FROM MELBOURNE CLEANING CLOTHS",
                "PH: 03 9930 7700",
            ],
            "docket-4370.docx",
        )

        self.assertEqual("4370", parsed.docket_number)
        self.assertEqual("185467", parsed.docket_reference)
        self.assertEqual("185467", parsed.invoice_number)
        self.assertEqual("2026-08-10", parsed.invoice_date)
        self.assertIsNone(parsed.order_no)
        self.assertEqual("CHEMBLAST INDUSTRIAL COATINGS", parsed.company_name)
        self.assertIsNone(parsed.phone)
        self.assertEqual("143 FOUNDATION ROAD", parsed.delivery_address)
        self.assertEqual("TRUGANINA", parsed.suburb)
        self.assertIsNone(parsed.postcode)
        self.assertEqual("2026-08-14", parsed.delivery_date)
        self.assertEqual((1, 0, 0), (parsed.pallet_quantity, parsed.loose_bags_quantity, parsed.carton_quantity))
        self.assertEqual(
            {
                "product_code": None,
                "product_name": "COLOUR SINGLET RAGS",
                "quantity": 520,
                "unit": "KG",
                "package_quantity": 52,
                "package_unit": "BAG10",
            },
            parsed.product_lines[0],
        )
        self.assertIn("Delivery Docket: 4370", parsed.note)
        self.assertIn("Deliver To: PATONS TRANSPORT", parsed.note)
        self.assertIn("C/O VICTORIAN FREIGHT SPECIALISTS", parsed.note)
        self.assertIn("On Forward To: CHEMBLAST INDUSTRIAL COATINGS", parsed.note)
        self.assertIn("Booking Email: admin@patonstransport.com.au", parsed.note)
        self.assertNotIn("03 9930 7700", parsed.note)
        self.assertNotIn("Delivery Docket: 073", parsed.note)

    def test_case_4371_keeps_newway_reference_without_guessing_invoice(self):
        parsed = _parse(
            [
                "DELIVERY DOCKET: 4371/NEWWAY 182-2",
                "Princes SS",
                "DATED: 10/08/2026",
                "EMAIL SCT LOGISTICS TO ADVISE DROP OFF OF STOCK TO THEIR ALTONA DEPOT",
                "melbourne.pickups2@sctlogistics.com.au",
                "DELIVER to",
                "SCT ALTONA",
                "7 WESTLINK COURT",
                "ALTONA VIC 3018",
                "SCT REFERENCE# 103010642",
                "ON FWD TO CUSTOMER:",
                "PRINCES FABRICARE MAROOCHYDORE",
                "BAUHINA CENTRE, 3/526 MAROOCHYDORE ROAD",
                "KUNDA PARK",
                "QLD 4556",
                "PHONE: 07 5445 5133",
                "TOTAL: 2 PALLETS",
            ],
            "docket-4371.docx",
        )

        self.assertEqual("4371", parsed.docket_number)
        self.assertEqual("NEWWAY 182-2 Princes SS", parsed.docket_reference)
        self.assertIsNone(parsed.invoice_number)
        self.assertEqual("2026-08-10", parsed.invoice_date)
        self.assertEqual("PRINCES FABRICARE MAROOCHYDORE", parsed.company_name)
        self.assertEqual("07 5445 5133", parsed.phone)
        self.assertEqual("7 WESTLINK COURT", parsed.delivery_address)
        self.assertEqual("ALTONA", parsed.suburb)
        self.assertEqual("3018", parsed.postcode)
        self.assertEqual(2, parsed.pallet_quantity)
        self.assertEqual([], parsed.product_lines)
        self.assertTrue(any("No product lines" in warning for warning in parsed.warnings))
        self.assertTrue(parsed.importable)
        self.assertIn("Docket Reference: NEWWAY 182-2 Princes SS", parsed.note)
        self.assertIn("SCT Reference: 103010642", parsed.note)
        self.assertIn("Booking Email: melbourne.pickups2@sctlogistics.com.au", parsed.note)

    def test_case_4372_ignores_template_header_and_keeps_attention_context(self):
        parsed = _parse(
            [
                "DELIVERY DOCKET: 073",
                "DELIVERY DOCKET: 4372/NEWWAY 181-3, 185, 186 Princes AD",
                "DATED: 10/08/2026",
                "DELIVER to",
                "SCT ALTONA",
                "7 WESTLINK COURT",
                "ALTONA VIC 3018",
                "SCT REFERENCE# 103010643",
                "ON FWD TO CUSTOMER:",
                "PRINCES LINEN ADELAIDE",
                "ATTN: MELANIE FISHER",
                "15 WALDAREE STREET",
                "GEPPS CROSS SA 5094",
                "PHONE: 08 8121 5488",
                "TOTAL: 10 PALLETS",
            ],
            "docket-4372.docx",
        )

        self.assertEqual("4372", parsed.docket_number)
        self.assertIsNone(parsed.invoice_number)
        self.assertEqual("PRINCES LINEN ADELAIDE", parsed.company_name)
        self.assertEqual("08 8121 5488", parsed.phone)
        self.assertEqual("7 WESTLINK COURT", parsed.delivery_address)
        self.assertEqual("ALTONA", parsed.suburb)
        self.assertEqual("3018", parsed.postcode)
        self.assertEqual(10, parsed.pallet_quantity)
        self.assertIn("Contact: MELANIE FISHER", parsed.note)
        self.assertIn("GEPPS CROSS SA 5094", parsed.note)

    def test_case_4373_splits_final_customer_from_physical_depot(self):
        parsed = _parse(
            [
                "DELIVERY DOCKET: 073",
                "DELIVERY DOCKET: 4373/185504",
                "DATED: 11/08/2026",
                "DELIVER to",
                "C/-LUBRIMAXX SUNSHINE",
                "30 SPENCER STREET",
                "SUNSHINE WEST",
                "ON FWD TO:",
                "NOEL'S AUTO PARTS",
                "366 EDWARD STREET",
                "WAGGA WAGGA NSW 2650",
                "ATT: DAVID",
                "PH: 02 6925 3777",
                "ORDER NUMBER: 40592",
                "36x10kgs COLOUR T-SHIRT RAGS",
                "1 X PALLET",
            ],
            "docket-4373.docx",
        )

        self.assertEqual("185504", parsed.invoice_number)
        self.assertEqual("40592", parsed.order_no)
        self.assertEqual("NOEL'S AUTO PARTS", parsed.company_name)
        self.assertEqual("02 6925 3777", parsed.phone)
        self.assertEqual("30 SPENCER STREET", parsed.delivery_address)
        self.assertEqual("SUNSHINE WEST", parsed.suburb)
        self.assertEqual(360, parsed.product_lines[0]["quantity"])
        self.assertIn("Deliver To: C/-LUBRIMAXX SUNSHINE", parsed.note)
        self.assertIn("On Forward Address: 366 EDWARD STREET / WAGGA WAGGA NSW 2650", parsed.note)
        self.assertIn("Contact: DAVID", parsed.note)

    def test_case_4374_parses_open_window_and_two_products_without_loose_double_count(self):
        parsed = _parse(
            [
                "DELIVERY DOCKET: 073",
                "DELIVERY DOCKET: 4374/185503",
                "Email to book:",
                "office@keatingfreightlines.com.au",
                "DATED: 11/08/2026",
                "DELIVER to",
                "keatings transport OPEN 7AM-3pm",
                "36-38 glenbarry road",
                "campbellfield",
                "ON FWD TO:",
                "FASTENER SPECIALISTS",
                "274 TOWNSEND ST",
                "SOUTH ALBURY 2640",
                "STOCK:",
                "63 X 10KG WORKSHOP rags",
                "63 X 10KG WINDCHEATER RAGS",
                "2 X PALLETS",
            ],
            "docket-4374.docx",
        )

        self.assertEqual("FASTENER SPECIALISTS", parsed.company_name)
        self.assertIsNone(parsed.phone)
        self.assertEqual("36-38 GLENBARRY ROAD", parsed.delivery_address)
        self.assertEqual("CAMPBELLFIELD", parsed.suburb)
        self.assertEqual(("07:00", "15:00"), (parsed.start_time, parsed.end_time))
        self.assertEqual(2, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertEqual([630, 630], [line["quantity"] for line in parsed.product_lines])
        self.assertEqual(["BAG10", "BAG10"], [line["package_unit"] for line in parsed.product_lines])
        self.assertIn("Delivery Window: OPEN 7AM-3PM", parsed.note)
        self.assertIn("Booking Email: office@keatingfreightlines.com.au", parsed.note)

    def test_case_4375_preserves_order_slash_and_entry_as_note_only(self):
        parsed = _parse(
            [
                "DELIVERY DOCKET: 4375/185512",
                "DATED: 11/08/2026",
                "DELIVER TO:",
                "JJS WASTE & RECYLING",
                "46-52 ELLIOTT ROAD",
                "ENTRY VIA 427 HAMMOND RD",
                "DANDENONG SOUTH 3175",
                "ORDER NUMBER: 77058/VIC",
                "45X10KG COLOURED SINGLET",
                "1pallet",
                "INVOICE TO FOLLOW FROM SMITHS RAGS",
            ],
            "docket-4375.docx",
        )

        self.assertEqual("DIRECT", parsed.delivery_mode)
        self.assertEqual("77058/VIC", parsed.order_no)
        self.assertEqual("JJS WASTE & RECYLING", parsed.company_name)
        self.assertEqual("46-52 ELLIOTT ROAD", parsed.delivery_address)
        self.assertEqual("DANDENONG SOUTH", parsed.suburb)
        self.assertEqual("3175", parsed.postcode)
        self.assertEqual(450, parsed.product_lines[0]["quantity"])
        self.assertIn("Entry: VIA 427 HAMMOND RD", parsed.note)
        self.assertNotIn("Deliver To Address: ENTRY", parsed.note)

    def test_case_4376_explicit_time_slot_wins_and_supplier_phone_is_excluded(self):
        parsed = _parse(
            [
                "DELIVERY DOCKET: 4376/185531",
                "DATED: 21/08/2026",
                "DELIVER TO:",
                "SRGS PTY LTD",
                "MELBOURNE DISTRIBUTION CENTRE",
                "STORE DC31",
                "413 MT ATKINSON ROAD",
                "TRUGANINA",
                "Time slot: FRIDAY 21/08/26 @ 9am",
                "BOOKING # 2232671",
                "ORDER NUMBER: 4522009179",
                "1120 X 1.5KG COLOUR RAGS",
                "45 X 10KG COLOR T SHIRT RAGS",
                "6 PALLETS",
                "INVOICE TO FOLLOW FROM MCC RAGMAN PTY LTD",
                "TRADING AS MELBOURNE CLEANING CLOTHS",
                "PH: 03 9930 7700",
            ],
            "docket-4376.docx",
        )

        self.assertEqual("DIRECT", parsed.delivery_mode)
        self.assertEqual("2026-08-21", parsed.invoice_date)
        self.assertEqual("2026-08-21", parsed.delivery_date)
        self.assertEqual("09:00", parsed.start_time)
        self.assertIsNone(parsed.end_time)
        self.assertEqual("SRGS PTY LTD", parsed.company_name)
        self.assertIsNone(parsed.phone)
        self.assertEqual("413 MT ATKINSON ROAD", parsed.delivery_address)
        self.assertEqual("TRUGANINA", parsed.suburb)
        self.assertEqual(6, parsed.pallet_quantity)
        self.assertEqual([1680, 450], [line["quantity"] for line in parsed.product_lines])
        self.assertEqual(["BAG1.5", "BAG10"], [line["package_unit"] for line in parsed.product_lines])
        self.assertIn("Site: MELBOURNE DISTRIBUTION CENTRE", parsed.note)
        self.assertIn("Store: DC31", parsed.note)
        self.assertIn("Booking #: 2232671", parsed.note)
        self.assertIn("Time Slot: FRIDAY 21/08/26 @ 9AM", parsed.note)
        self.assertNotIn("03 9930 7700", parsed.note)

    def test_fractional_actual_kg_is_warned_and_not_importable(self):
        parsed = parse_delivery_docket_text(
            """
            DELIVERY DOCKET: 4999/199999
            DATED: 12/08/2026
            DELIVER TO:
            EXAMPLE CUSTOMER
            1 EXAMPLE ROAD
            RICHMOND 3121
            3 X 1.5KG SAMPLE RAGS
            """,
            source_filename="fractional.docx",
            import_date=IMPORT_DATE,
        )

        self.assertFalse(parsed.importable)
        self.assertTrue(any("fractional" in warning.lower() for warning in parsed.warnings))


if __name__ == "__main__":
    unittest.main()
