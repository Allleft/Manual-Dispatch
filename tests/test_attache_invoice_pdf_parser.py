from datetime import date
import unittest

from backend.services.manual_dispatch.attache_invoice_pdf_parser import (
    _find_postcode,
    _is_stop_marker,
    parse_attache_invoice_text,
)


class AttacheInvoicePdfParserTest(unittest.TestCase):
    def assert_product(
        self,
        line,
        code,
        name,
        quantity,
        unit,
        package_quantity=None,
        package_unit=None,
    ):
        self.assertEqual(
            {
                "product_name": name,
                "quantity": quantity,
                "unit": unit,
                "product_code": code,
                "package_quantity": package_quantity,
                "package_unit": package_unit,
            },
            line,
        )

    def assert_charge_data_excluded(self, parsed):
        searchable = " ".join(
            [
                str(parsed.product_lines),
                str(parsed.warnings),
                parsed.note or "",
            ]
        ).upper()
        self.assertNotIn("DELIVERY /FUEL LEVY CHARGE", searchable)
        self.assertNotIn("TOTAL INVOICE:AUD", searchable)

    def assert_order_number_not_in_note(self, parsed):
        note = parsed.note or ""
        self.assertNotIn("Order No", note)
        self.assertNotIn("Order #", note)
        if parsed.order_no:
            self.assertNotIn(parsed.order_no, note)

    def test_king_pin_products_delivery_address_does_not_include_invoice_metadata(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
             181486
            Customer
            Code
            KINCHE89
            Date
            04/02/26
            Invoice to:
            Order No
            002848
            KING PIN PRODUCTS
            9 PARK RD
            CHELTENHAM 3192
            DiscPricePerTotal
            Deliver to:
            KING PIN PRODUCTS
            9 PARK RD
            CHELTENHAM
            9583 5333
            3192
            B.S.L. WIPERS (VIC) PTY LTD
            email: admin@teamsaustralia.com.au
            98-102 HUME HIGHWAY, SOMERTON VIC 3062
            Amt+GST
            Phone: (03) 9930 7740
            RSING 200COLOR TSHIRT RAGS 385.0035.000.001.750KG
            BAG10 20PLASTIC BAG 10 kg 0.000.000.000.000
            PAL 1PALLET 27.502.500.0025.000PLT
            DEL 1DELIVERY /FUEL LEVY CHARGE 9.350.850.008.500DEL
            """,
            source_filename="181486.pdf",
            import_date=date(2026, 2, 4),
        )

        self.assertEqual("181486", parsed.invoice_number)
        self.assertEqual("KINCHE89", parsed.customer_code)
        self.assertEqual("002848", parsed.order_no)
        self.assertEqual("KING PIN PRODUCTS", parsed.company_name)
        self.assertEqual("9 PARK RD", parsed.delivery_address)
        self.assertEqual("CHELTENHAM", parsed.suburb)
        self.assertEqual("9583 5333", parsed.phone)
        self.assertEqual("3192", parsed.postcode)
        self.assertEqual("2026-02-05", parsed.delivery_date)
        self.assertEqual((1, 0, 0), (
            parsed.pallet_quantity,
            parsed.loose_bags_quantity,
            parsed.carton_quantity,
        ))
        self.assertEqual(1, len(parsed.product_lines))
        self.assert_product(
            parsed.product_lines[0],
            "RSING",
            "COLOR TSHIRT RAGS",
            200,
            "KG",
            20,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)
        self.assert_order_number_not_in_note(parsed)
        self.assertNotEqual("(03) 9930 7740", parsed.phone)

        excluded_fragments = [
            "KING PIN PRODUCTS",
            "CHELTENHAM",
            "3192",
            "Invoice No",
            "Customer Code",
            "Date",
            "Order No",
            "B.S.L.",
            "WIPERS",
            "98-102",
            "SOMERTON",
            "98-102 HUME HIGHWAY",
        ]
        for fragment in excluded_fragments:
            self.assertNotIn(fragment, parsed.delivery_address)

    def test_interleaved_delivery_address_keeps_customer_phone_and_postcode(self):
        parsed = parse_attache_invoice_text(
            """
            Customer
            Code
            Code Description Tax
            email: admin@teamsaustralia.com.au
            MELBOURNE CLEANING CLOTHS
            Invoice No
              184066
            Order No Date
            04/06/26 BOLDAN 524783
            Invoice to:
            Bolts & Industrial Supplies
            Unit 1 / 433 Hammond Road
            Dandenong,  3175
            Total
            Deliver to:
            Bolts & Industrial Supplies
            Unit 1 / 433 Hammond Road
            Dandenong,
            web: www.melbournecleaningcloths.com.au
            ABN: 23 114 428 563
            Tax Invoice
            (03) 9768 3537
            3175
            Price Per Net
            98-102 HUME HIGHWAY SOMERTON VIC 3062
            Amt+GST
            Phone: (03) 9930 7700
            RWIND 121.50 KG 450 WINDCHEATER #15 2.700 1,336.50 1,215.00
            BAG10 0.00 45 PLASTIC BAG 10 kg 0.000 0.00 0.00
            PAL 0.00 PLT 1 PALLET 0.000 0.00 0.00
            DEL 1.00 DEL 1 DELIVERY /FUEL LEVY CHARGE 10.000 11.00 10.00
            """,
            source_filename="184066.pdf",
        )

        self.assertEqual("184066", parsed.invoice_number)
        self.assertEqual("BOLDAN", parsed.customer_code)
        self.assertEqual("524783", parsed.order_no)
        self.assertEqual("Bolts & Industrial Supplies", parsed.company_name)
        self.assertEqual("Unit 1 / 433 Hammond Road", parsed.delivery_address)
        self.assertEqual("Dandenong", parsed.suburb)
        self.assertEqual("3175", parsed.postcode)
        self.assertEqual("(03) 9768 3537", parsed.phone)
        self.assertNotIn("MELBOURNE CLEANING CLOTHS", parsed.delivery_address)
        self.assertNotIn("98-102 HUME HIGHWAY", parsed.delivery_address)
        self.assertNotIn("SOMERTON", parsed.delivery_address)
        self.assertNotEqual("(03) 9930 7700", parsed.phone)
        self.assertFalse(
            any(
                warning.startswith("Unclassified invoice item:")
                for warning in parsed.warnings
            )
        )
        self.assertEqual((1, 0, 0), (
            parsed.pallet_quantity,
            parsed.loose_bags_quantity,
            parsed.carton_quantity,
        ))
        self.assert_product(
            parsed.product_lines[0],
            "RWIND",
            "WINDCHEATER #15",
            450,
            "KG",
            45,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)

    def test_postcode_detection_does_not_use_phone_exchange(self):
        self.assertEqual("3175", _find_postcode(["(03) 9768 3537", "3175"]))
        self.assertEqual("3175", _find_postcode(["Dandenong, 3175"]))
        self.assertIsNone(
            _find_postcode(["(03) 9768 3537", "03 9768 3537", "0402 848 618"])
        )

    def test_paid_and_attention_operational_note_block(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
              184040
            Order No Date
            03/06/26 LINCLA 3088
            Invoice to:
            LINEAR METAL POLISHING PTY LTD
            55 SARTON RD
            CLAYTON 3168
            Deliver to:
            LINEAR METAL POLISHING PTY LTD
            55 SARTON RD
            CLAYTON
            Tax Invoice
            9548 7214
            3168
            RFLAN 12.80 KG 40 FLANNELETTE #9 3.199 140.76 127.96
            BAG10 0.00 4 PLASTIC BAG 10 kg 0.000 0.00 0.00
            DEL 1.36 DEL 1 DELIVERY /FUEL LEVY CHARGE 13.640 15.00 13.64
            PAID EWAY
            ATTN: DANIELLE FOWLER
            Payment by Visa, Mastercard can be made by phoning: 03 9930 7700
            Terms: C.O.D.
            Total Invoice:AUD 155.76
            """,
            source_filename="184040.pdf",
        )

        self.assertEqual("184040", parsed.invoice_number)
        self.assertEqual("LINCLA", parsed.customer_code)
        self.assertEqual("3088", parsed.order_no)
        self.assertIn("PAID EWAY\nATTN: DANIELLE FOWLER", parsed.note)
        self.assertNotIn("DELIVERY /FUEL LEVY", parsed.note)
        self.assertNotIn("Total Invoice", parsed.note)
        self.assertEqual((0, 4, 0), (
            parsed.pallet_quantity,
            parsed.loose_bags_quantity,
            parsed.carton_quantity,
        ))
        self.assert_product(
            parsed.product_lines[0],
            "RFLAN",
            "FLANNELETTE #9",
            40,
            "KG",
            4,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)
        self.assert_order_number_not_in_note(parsed)

    def test_prepayment_operational_note_keeps_customer_email(self):
        parsed = parse_attache_invoice_text(
            """
            email: admin@teamsaustralia.com.au
            MELBOURNE CLEANING CLOTHS
            Invoice No
              184061
            Order No Date
            04/06/26 EDEMIC PO-0458
            Invoice to:
            EDENS EXCAVATIONS
            21 CONSTANCE CRT
            EPPING 3076
            Deliver to:
            EDENS EXCAVATIONS OPENS 8AM
            21 CONSTANCE CRT
            EPPING
            Tax Invoice
            0448999253
            3076
            RSING 5.25 KG 30 COLOR TSHIRT RAGS 1.750 57.75 52.50
            BAG10 0.00 3 PLASTIC BAG 10 kg 0.000 0.00 0.00
            RBATH 3.50 KG 20 COLOURED TOWEL MIX #10 1.750 38.50 35.00
            BAG10 0.00 2 PLASTIC BAG 10 kg 0.000 0.00 0.00
            DEL 1.00 DEL 1 DELIVERY /FUEL LEVY CHARGE 10.000 11.00 10.00
            EMAIL INVOICE FOR PRE PAYMENT
            accounts@edensexcavations.com.au
            admin@teamsaustralia.com.au
            Payment by Visa, Mastercard can be made by phoning: 03 9930 7700
            """,
            source_filename="184061.pdf",
        )

        self.assertEqual("184061", parsed.invoice_number)
        self.assertEqual("EDEMIC", parsed.customer_code)
        self.assertEqual("PO-0458", parsed.order_no)
        self.assertEqual("08:00", parsed.start_time)
        self.assertIn("EMAIL INVOICE FOR PRE PAYMENT", parsed.note)
        self.assertIn(
            "[accounts@edensexcavations.com.au](mailto:accounts@edensexcavations.com.au)",
            parsed.note,
        )
        self.assertNotIn("admin@teamsaustralia.com.au", parsed.note)
        self.assertEqual((0, 5, 0), (
            parsed.pallet_quantity,
            parsed.loose_bags_quantity,
            parsed.carton_quantity,
        ))
        self.assert_product(
            parsed.product_lines[0],
            "RSING",
            "COLOR TSHIRT RAGS",
            30,
            "KG",
            3,
            "BAG10",
        )
        self.assert_product(
            parsed.product_lines[1],
            "RBATH",
            "COLOURED TOWEL MIX #10",
            20,
            "KG",
            2,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)
        self.assert_order_number_not_in_note(parsed)

    def test_delivery_docket_operational_note_keeps_multiline_instructions(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
              184062
            Order No Date
            04/06/26 MICTHO PO61432
            Invoice to:
            MICRO FASTENERS
            6 MERCEDES DV
            THOMASTOWN 3074
            Deliver to:
            MICRO FASTENERS
            6 MERCEDES DV
            THOMASTOWN
            Tax Invoice
            94640330
            OPENS 7AM
            3074
            RPWSING 121.50 KG 450 PURE WHITE SINGLET 2.700 1,336.50 1215.00
            BAG10 0.00 45 PLASTIC BAG 10 kg 0.000 0.00 0.00
            PAL 0.00 PLT 1 PALLET 0.000 0.00 0.00
            DEL 1.00 DEL 1 DELIVERY /FUEL LEVY CHARGE 10.000 11.00 10.00
            ON DELIVERY DOCKET NO INVOICE
            REGENT RV PTY LTD
            20-50 FILLO DRIVE
            SOMERTON, VIC, 3062
            SITE CONTACT: Atra - 0477511802
            DELIVERY ONLY ACCEPTED BETWEEN 7.30 am until 2.30pm
            Payment by Visa, Mastercard can be made by phoning: 03 9930 7700
            Terms: 30 DAYS
            BSB: 013-226 ACCOUNT: 654484155
            PLEASE NOTE NEW BANK ACC DETAILS:
            """,
            source_filename="184062.pdf",
        )

        self.assertEqual("184062", parsed.invoice_number)
        self.assertEqual("MICTHO", parsed.customer_code)
        self.assertEqual("PO61432", parsed.order_no)
        self.assertEqual("07:00", parsed.start_time)
        expected_lines = [
            "ON DELIVERY DOCKET NO INVOICE",
            "REGENT RV PTY LTD",
            "20-50 FILLO DRIVE",
            "SOMERTON, VIC, 3062",
            "SITE CONTACT: Atra - 0477511802",
            "DELIVERY ONLY ACCEPTED BETWEEN 7.30 am until 2.30pm",
        ]
        note_lines = parsed.note.splitlines()
        positions = [note_lines.index(line) for line in expected_lines]
        self.assertEqual(sorted(positions), positions)
        self.assertNotIn("PLEASE NOTE NEW BANK ACC DETAILS", parsed.note)
        self.assertNotIn("BSB:", parsed.note)
        self.assertNotIn("654484155", parsed.note)
        self.assertEqual((1, 0, 0), (
            parsed.pallet_quantity,
            parsed.loose_bags_quantity,
            parsed.carton_quantity,
        ))
        self.assert_product(
            parsed.product_lines[0],
            "RPWSING",
            "PURE WHITE SINGLET",
            450,
            "KG",
            45,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)
        self.assert_order_number_not_in_note(parsed)

    def test_pallet_load_does_not_replace_product_bag_quantity(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
              184063
            Order No Date
            04/06/26 BTLDAN 6300379
            Invoice to:
            TOYOTA MATERIAL HANDLING
            253-281 DISCOVERY ROAD
            DANDENONG SOUTH 3175
            Deliver to:
            TOYOTA MATERIAL HANDLING (VIC) P/L
            253-281 DISCOVERY ROAD
            DANDENONG SOUTH VIC
            Tax Invoice
            8795 2500
            RSING10KG 130.50 BAG 90 COLOUR RAGS 10KG NET 14.500 1,435.50 1305.00
            BAG10 0.00 90 PLASTIC BAG 10 kg 0.000 0.00 0.00
            PAL 0.00 PLT 2 PALLET 0.000 0.00 0.00
            DEL 1.00 DEL 1 DELIVERY /FUEL LEVY CHARGE 10.000 11.00 10.00
            """,
            source_filename="184063.pdf",
        )

        self.assertEqual("184063", parsed.invoice_number)
        self.assertEqual("6300379", parsed.order_no)
        self.assertEqual(2, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertEqual(0, parsed.carton_quantity)
        self.assert_product(
            parsed.product_lines[0],
            "RSING10KG",
            "COLOUR RAGS 10KG NET",
            90,
            "BAG",
            90,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)

    def test_pallet_and_carton_load_remain_order_level(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
              184068
            Order No Date
            04/06/26 JBCBAL 7147703
            Invoice to:
            JB CAMERON
            132 Armstrong Street
            BALLARAT 3350
            Deliver to:
            JB CAMERON
            126 ARMSTRONG ST SOUTH
            BALLARAT CENTRAL
            Tax Invoice
            (03) 5337 4400
            3350
            RSING10KG 65.25 BAG 45 COLOUR RAGS 10KG NET 14.500 717.75 652.50
            BAG10 0.00 45 PLASTIC BAG 10 kg 0.000 0.00 0.00
            RSING1.5KG 9.80 BAG 28 COLOR RAGS 1.5KG BAG 3.500 107.80 98.00
            BAG1.5 0.00 28 PLASTIC BAG 1.5 kg 0.000 0.00 0.00
            CTN 0.00 CTN 2 CARTONS 0.000 0.00 0.00
            PAL 0.00 PLT 1 PALLET 0.000 0.00 0.00
            DEL 10.50 DEL 1 DELIVERY /FUEL LEVY CHARGE 105.000 115.50 105.00
            """,
            source_filename="184068.pdf",
        )

        self.assertEqual("184068", parsed.invoice_number)
        self.assertEqual("7147703", parsed.order_no)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertEqual(2, parsed.carton_quantity)
        self.assert_product(
            parsed.product_lines[0],
            "RSING10KG",
            "COLOUR RAGS 10KG NET",
            45,
            "BAG",
            45,
            "BAG10",
        )
        self.assert_product(
            parsed.product_lines[1],
            "RSING1.5KG",
            "COLOR RAGS 1.5KG BAG",
            28,
            "BAG",
            28,
            "BAG1.5",
        )
        self.assert_charge_data_excluded(parsed)

    def test_snap_pack_bag_invoice(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
              182438
            Order NoDate
            20/03/26 SNASPR 20032026
            Invoice to:
            SNAP PACK
            B8/2A WESTALL ROAD
            SPRINGVALE 3171
            Deliver to:
            SNAP PACK
            DELIVERY BETWEEN 7:00 AM - 12:00PM
            B8/2A WESTALL ROAD SPRINGVALE
            Tax Invoice
            0422275484
            HALLMARK BUSINESS CENTRE
            3171
            DELIVERY BETWEEN 7:00 AM - 12:00PM
            RPWSING 24.50 KG 100 PURE WHITE SINGLET 2.450 269.50 245.00
            BAG10 0.00 10 PLASTIC BAG 10 kg 0.000 0.00 0.00
            RSING 4.13 KG 25 COLOR TSHIRT RAGS 1.650 45.38 41.25
            BAG5 0.00 5 PLASTIC BAG 5 kg 0.000 0.00 0.00
            GST 12.00
            """,
            source_filename="182438.pdf",
            import_date=date(2026, 3, 20),
        )

        self.assertEqual("182438", parsed.invoice_number)
        self.assertEqual("SNASPR", parsed.customer_code)
        self.assertEqual("20032026", parsed.order_no)
        self.assert_order_number_not_in_note(parsed)
        self.assertEqual("SNAP PACK", parsed.company_name)
        self.assertEqual("2026-03-21", parsed.delivery_date)
        self.assertEqual(0, parsed.pallet_quantity)
        self.assertEqual(15, parsed.loose_bags_quantity)
        self.assertEqual(0, parsed.carton_quantity)
        self.assertEqual("07:00", parsed.start_time)
        self.assertEqual("12:00", parsed.end_time)
        self.assert_product(
            parsed.product_lines[0],
            "RPWSING",
            "PURE WHITE SINGLET",
            100,
            "KG",
            10,
            "BAG10",
        )
        self.assert_product(
            parsed.product_lines[1],
            "RSING",
            "COLOR TSHIRT RAGS",
            25,
            "KG",
            5,
            "BAG5",
        )
        self.assert_charge_data_excluded(parsed)

    def test_coringle_furniture_mixed_pallet_and_bag_invoice(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
              183075
            Order No Date
            21/04/26 CORRIN 40
            Invoice to:
            Coringle Furniture
            13-16 Summer Ln
            Ringwood 3134
            Deliver to:
            Coringle Furniture
            13-16 Summer Ln
            Ringwood
            Tax Invoice
            9870 3900
            3134
            RPWSING 81.00 KG 300 PURE WHITE SINGLET 2.700 891.00 810.00
            BAG10 0.00 30 PLASTIC BAG 10 kg 0.000 0.00 0.00
            FIN-3PLY 12.00 BAG 3 FINESSE-3PLY T/PAPER 180 SHTSx72ROLLS 40.000 132.00 120.00
            PAL 2.50 PLT 1 PALLET 25.000 27.50 25.00
            FUEL LEVY CHARGE 1 DELIVERY
            """,
            source_filename="183075.pdf",
            import_date=date(2026, 4, 21),
        )

        self.assertEqual("183075", parsed.invoice_number)
        self.assertEqual("CORRIN", parsed.customer_code)
        self.assertEqual("40", parsed.order_no)
        self.assert_order_number_not_in_note(parsed)
        self.assertEqual("Coringle Furniture", parsed.company_name)
        self.assertEqual("2026-04-22", parsed.delivery_date)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertEqual(0, parsed.carton_quantity)
        self.assert_product(
            parsed.product_lines[0],
            "RPWSING",
            "PURE WHITE SINGLET",
            300,
            "KG",
            30,
            "BAG10",
        )
        self.assert_product(
            parsed.product_lines[1],
            "FIN-3PLY",
            "FINESSE-3PLY T/PAPER 180 SHTS x 72 ROLLS",
            3,
            "BAG",
        )
        self.assert_charge_data_excluded(parsed)

    def test_tutt_bryant_palletized_bag10_is_not_loose_bag(self):
        parsed = parse_attache_invoice_text(
            """
            Date
            21/04/26
            Invoice No
              183077 BTEDANR
            Invoice to:
            BT EQUIPMENT trading as Tutt Bryant
            80-86 FRANKSTON DANDENONG ROAD
            DANDENONG 3175
            Order No
            PO000008304
            Deliver to:
            BT EQUIPMENT trading as Tutt Bryant
            80-86 FRANKSTON-DANDENONG ROAD
            DANDENONG
            NO VAN, MUST BE TRUCK DELIVERY
            3175
            9554 0300
            Tax Invoice
            RSING 385.00 35.00 0.00 KG 1.750 COLOR TSHIRT RAGS 200
            BAG10 0.00 0.00 0.00 0.000 PLASTIC BAG 10 kg 20
            PAL 27.50 2.50 0.00 PLT 25.000 PALLET 1
            DEL 9.35 0.85 0.00 DELIVERY 8.500 DELIVERY /FUEL LEVY CHARGE 1
            Total Amount 123.45
            """,
            source_filename="183077.pdf",
        )

        self.assertEqual("183077", parsed.invoice_number)
        self.assertEqual("PO000008304", parsed.order_no)
        self.assert_order_number_not_in_note(parsed)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertIn("NO VAN, MUST BE TRUCK DELIVERY", parsed.note)
        self.assert_product(
            parsed.product_lines[0],
            "RSING",
            "COLOR TSHIRT RAGS",
            200,
            "KG",
            20,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)

    def test_desi_dhaba_opens_instruction(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
              183080
            Order No. Date
            21/04/26 DESCRA 21042026
            Invoice to:
            DESI DHABA CRAIGIEBURN
            340 CRAIGIEBURN ROAD
            CRAIGIEBURN 3064
            Deliver to:
            DESI DHABA CRAIGIEBURN
            340 CRAIGIEBURN ROAD
            CRAIGIEBURN
            Tax Invoice
            0402 848 618
            OPENS 11AM
            3064
            RWSHEET 12.75 KG 50 WHITE SHEETING #11S 2.550 140.25 127.50
            BAG10 0.00 5 PLASTIC BAG 10 kg 0.000 0.00 0.00
            DEL 1.00 DEL 1 DELIVERY /FUEL LEVY CHARGE 10.000 11.00 10.00
            """,
            source_filename="183080.pdf",
        )

        self.assertEqual("183080", parsed.invoice_number)
        self.assertEqual("DESCRA", parsed.customer_code)
        self.assertEqual("21042026", parsed.order_no)
        self.assert_order_number_not_in_note(parsed)
        self.assertEqual("11:00", parsed.start_time)
        self.assertIsNone(parsed.end_time)
        self.assertEqual(0, parsed.pallet_quantity)
        self.assertEqual(5, parsed.loose_bags_quantity)
        self.assert_product(
            parsed.product_lines[0],
            "RWSHEET",
            "WHITE SHEETING #11S",
            50,
            "KG",
            5,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)

    def test_pakenham_accident_repair_opens_instruction(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
              183081
            ORDER NODATE
            21/04/26 PAKPAK21 21042026
            Invoice to:
            PAKENHAM ACCIDENT REPAIR
            21 BALD HILL ROAD
            PAKENHAM 3810
            Deliver to:
            PAKENHAM ACCIDENT REPAIR
            21 BALD HILL ROAD
            PAKENHAM
            Tax Invoice
            59412772
            OPENS 8AM
            3810
            RSING 10.50 KG 60 COLOR TSHIRT RAGS 1.750 115.50 105.00
            BAG10 0.00 6 PLASTIC BAG 10 kg 0.000 0.00 0.00
            DEL 1.00 DEL 1 DELIVERY /FUEL LEVY CHARGE 10.000 11.00 10.00
            """,
            source_filename="183081.pdf",
        )

        self.assertEqual("183081", parsed.invoice_number)
        self.assertEqual("PAKPAK21", parsed.customer_code)
        self.assertEqual("21042026", parsed.order_no)
        self.assert_order_number_not_in_note(parsed)
        self.assertEqual("08:00", parsed.start_time)
        self.assertIsNone(parsed.end_time)
        self.assertEqual(6, parsed.loose_bags_quantity)
        self.assert_product(
            parsed.product_lines[0],
            "RSING",
            "COLOR TSHIRT RAGS",
            60,
            "KG",
            6,
            "BAG10",
        )
        self.assert_charge_data_excluded(parsed)

    def test_footer_advertising_is_excluded_and_unknown_rows_warn_safely(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No 199001
            Date 04/06/26
            Invoice to:
            SAFE CUSTOMER
            1 TEST ROAD
            RICHMOND 3121
            Deliver to:
            SAFE CUSTOMER
            1 TEST ROAD
            RICHMOND
            3121
            Tax Invoice
            RSING 5.25 KG 30 COLOR TSHIRT RAGS 1.750 57.75 52.50
            MYST 12 UNRECOGNISED WIDGET 99.95
            Total Invoice:AUD 120.00
            *NEW PRODUCT*
            FIN-3PLY 12.00 BAG 3 FINESSE-3PLY T/PAPER 40.000 132.00 120.00
            """,
            source_filename="unknown-row.txt",
        )

        self.assertEqual(["RSING"], [line["product_code"] for line in parsed.product_lines])
        warning = next(
            item for item in parsed.warnings if item.startswith("Unclassified invoice item:")
        )
        self.assertIn("MYST UNRECOGNISED WIDGET", warning)
        self.assertNotIn("99.95", warning)
        self.assertNotIn("120.00", warning)
        self.assert_charge_data_excluded(parsed)

    def test_packaging_only_associates_with_immediately_preceding_product(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No 199002
            Date 04/06/26
            Invoice to:
            SAFE CUSTOMER
            1 TEST ROAD
            RICHMOND 3121
            Deliver to:
            SAFE CUSTOMER
            1 TEST ROAD
            RICHMOND
            3121
            Code Description
            RPWSING 24.50 KG 100 PURE WHITE SINGLET 2.450 269.50 245.00
            MYST 1 AMBIGUOUS ROW 9.95
            BAG10 0.00 10 PLASTIC BAG 10 kg 0.000 0.00 0.00
            RSING 4.13 KG 25 COLOR TSHIRT RAGS 1.650 45.38 41.25
            BAG5 0.00 5 PLASTIC BAG 5 kg 0.000 0.00 0.00
            Total Invoice:AUD 300.00
            """,
            source_filename="packaging-association.txt",
        )

        self.assertIsNone(parsed.product_lines[0]["package_quantity"])
        self.assertIsNone(parsed.product_lines[0]["package_unit"])
        self.assertEqual(5, parsed.product_lines[1]["package_quantity"])
        self.assertEqual("BAG5", parsed.product_lines[1]["package_unit"])
        self.assertEqual(15, parsed.loose_bags_quantity)
        self.assertTrue(
            any(
                warning.startswith("Unclassified invoice item:")
                for warning in parsed.warnings
            )
        )

    def test_real_column_order_185517_equivalent_uses_import_date_and_bag_count(self):
        parsed = parse_attache_invoice_text(
            """
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
            """,
            source_filename="sanitized-185517.txt",
            import_date=date(2026, 8, 12),
        )

        self.assertEqual("185517", parsed.invoice_number)
        self.assertEqual("2026-08-11", parsed.invoice_date)
        self.assertEqual("2026-08-13", parsed.delivery_date)
        self.assertEqual("CUSTOM PERFORMANCE GARAGE", parsed.company_name)
        self.assertEqual("HALLAM", parsed.suburb)
        self.assertGreaterEqual(len(parsed.product_lines), 1)
        self.assert_product(
            parsed.product_lines[0],
            "RSING",
            "COLOR TSHIRT RAGS",
            50,
            "KG",
            5,
            "BAG10",
        )
        self.assertEqual(
            (0, 5, 0),
            (
                parsed.pallet_quantity,
                parsed.loose_bags_quantity,
                parsed.carton_quantity,
            ),
        )

    def test_real_column_order_185497_equivalent_uses_import_date_and_bag_count(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No 185497
            Date 11/08/26
            Order No Date
            11/08/26 SEVTRA 030482
            Invoice to:
            SEVILLE TRACTORS
            2 SANITIZED ROAD
            SEVILLE 3139
            Deliver to:
            SEVILLE TRACTORS
            2 SANITIZED ROAD
            SEVILLE
            3139
            Tax Invoice
            RSING 305.25 KG 27.75 0.00 1.850 150 COLOR TSHIRT RAGS
            BAG10 0.00 0.00 0.00 0.000 15 PLASTIC BAG 10 kg
            Total Invoice:AUD 335.78
            """,
            source_filename="sanitized-185497.txt",
            import_date=date(2026, 8, 12),
        )

        self.assertEqual("185497", parsed.invoice_number)
        self.assertEqual("2026-08-11", parsed.invoice_date)
        self.assertEqual("2026-08-13", parsed.delivery_date)
        self.assertEqual("SEVILLE TRACTORS", parsed.company_name)
        self.assertEqual("SEVILLE", parsed.suburb)
        self.assertGreaterEqual(len(parsed.product_lines), 1)
        self.assert_product(
            parsed.product_lines[0],
            "RSING",
            "COLOR TSHIRT RAGS",
            150,
            "KG",
            15,
            "BAG10",
        )
        self.assertEqual(
            (0, 15, 0),
            (
                parsed.pallet_quantity,
                parsed.loose_bags_quantity,
                parsed.carton_quantity,
            ),
        )

    def test_total_tools_dandenong_address_profile_is_not_treated_as_total_footer(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
            185505
            Order NoDate
            11/08/26 TOTDAN4 129534
            Invoice to:
            TOTAL TOOLS - DANDENONG
            221-232 GREENS ROAD
            DANDENONG 3175
            Total
            Deliver to:
            TOTAL TOOLS - DANDENONG
            221-232 GREENS ROAD
            DANDENONG
            web: www.melbournecleaningcloths.com.au
            ABN: 23 114 428 563
            Tax Invoice
            9798 4533
            3175
            RSING 96.25 KG 8.75 0.00 1.750 50 COLOR TSHIRT RAGS
            BAG10 0.00 0.00 0.00 0.000 5 PLASTIC BAG 10 kg
            PAL 27.50 2.50 0.00 PLT 25.000 PALLET 1
            BARCODES & LABELS
            Total Invoice:AUD 133.38
            """,
            source_filename="sanitized-total-tools-dandenong.txt",
            import_date=date(2026, 8, 13),
        )

        self.assertEqual("185505", parsed.invoice_number)
        self.assertEqual("2026-08-11", parsed.invoice_date)
        self.assertEqual("TOTDAN4", parsed.customer_code)
        self.assertEqual("129534", parsed.order_no)
        self.assertEqual("TOTAL TOOLS - DANDENONG", parsed.company_name)
        self.assertEqual("221-232 GREENS ROAD", parsed.delivery_address)
        self.assertEqual("DANDENONG", parsed.suburb)
        self.assertEqual("3175", parsed.postcode)
        self.assertEqual("9798 4533", parsed.phone)
        self.assertEqual("2026-08-14", parsed.delivery_date)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertEqual(
            ["Unclassified invoice item: BARCODES & LABELS"],
            parsed.warnings,
        )
        self.assertNotIn("Customer name was not found.", parsed.warnings)
        self.assertNotIn("Suburb was not found.", parsed.warnings)

    def test_total_tools_kilsyth_address_profile_is_not_treated_as_total_footer(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
            185506
            Order NoDate
            11/08/26 TOTKIL 132367
            Invoice to:
            TOTAL TOOLS KILSYTH
            CNR CANTERBURY RD & LIVERPOOL RD
            KILSYTH 3137
            Total
            Deliver to:
            TOTAL TOOLS KILSYTH
            CNR CANTERBURY RD & LIVERPOOL RD
            KILSYTH
            web: www.melbournecleaningcloths.com.au
            ABN: 23 114 428 563
            Tax Invoice
            8739 5110
            3137
            RSING 96.25 KG 8.75 0.00 1.750 50 COLOR TSHIRT RAGS
            BAG10 0.00 0.00 0.00 0.000 5 PLASTIC BAG 10 kg
            PAL 27.50 2.50 0.00 PLT 25.000 PALLET 1
            BARCODES & LABELS
            Total Invoice:AUD 133.38
            """,
            source_filename="sanitized-total-tools-kilsyth.txt",
            import_date=date(2026, 8, 13),
        )

        self.assertEqual("185506", parsed.invoice_number)
        self.assertEqual("2026-08-11", parsed.invoice_date)
        self.assertEqual("TOTKIL", parsed.customer_code)
        self.assertEqual("132367", parsed.order_no)
        self.assertEqual("TOTAL TOOLS KILSYTH", parsed.company_name)
        self.assertEqual(
            "CNR CANTERBURY RD & LIVERPOOL RD",
            parsed.delivery_address,
        )
        self.assertEqual("KILSYTH", parsed.suburb)
        self.assertEqual("3137", parsed.postcode)
        self.assertEqual("8739 5110", parsed.phone)
        self.assertEqual("2026-08-14", parsed.delivery_date)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertEqual(
            ["Unclassified invoice item: BARCODES & LABELS"],
            parsed.warnings,
        )
        self.assertNotIn("Customer name was not found.", parsed.warnings)
        self.assertNotIn("Suburb was not found.", parsed.warnings)

    def test_total_customer_names_are_not_stop_markers_but_total_footers_are(self):
        self.assertFalse(_is_stop_marker("TOTAL TOOLS - DANDENONG"))
        self.assertFalse(_is_stop_marker("TOTAL TOOLS KILSYTH"))
        for footer in (
            "Total",
            "TOTAL:",
            "Total Invoice:AUD 352.00",
            "Total Net Amount 320.00",
            "Total GST 32.00",
            "Total Amount 352.00",
        ):
            with self.subTest(footer=footer):
                self.assertTrue(_is_stop_marker(footer))

    def test_real_packet_layout_185526_maps_packet_metadata_to_one_product(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No
            185526
            Order NoDate
            12/08/26 LOTHEI PO-1677
            Invoice to:
            LOTUS COMMERCIAL PTY LTD - MEL
            2/58 DOUGHARTY RD
            HEIDELBERG 3084
            Deliver to:
            LOTUS COMMERCIAL PTY LTD - MEL
            2/58 DOUGHARTY RD
            HEIDELBERG
            Tax Invoice
            1300 653 536
            3084
            Code Description Price Per Net Amt+GST
            RBATH KG450COLOURED TOWEL MIX #10 2.300 1,138.50 1035.00 103.50
            BAG10 45PLASTIC BAG 10 kg 0.000 0.00 0.00 0.00
            MIC-MICROF 250MICRO FIBRE CLOTH 40 X 40 EACH 1.090 299.75 272.50 27.25
            PKT PKT1025 PIECES IN A PACKET 0.000 0.00 0.00 0.00
            10 PACKETS
            PAL PLT1PALLET 0.000 0.00 0.00 0.00
            DEL DEL1DELIVERY /FUEL LEVY CHARGE 10.000 11.00 10.00 1.00
            """,
            source_filename="sanitized-185526.txt",
            import_date=date(2026, 8, 13),
        )

        self.assertEqual("185526", parsed.invoice_number)
        self.assertEqual("2026-08-12", parsed.invoice_date)
        self.assertEqual("PO-1677", parsed.order_no)
        self.assertEqual("LOTUS COMMERCIAL PTY LTD - MEL", parsed.company_name)
        self.assertEqual("1300 653 536", parsed.phone)
        self.assertEqual("2/58 DOUGHARTY RD", parsed.delivery_address)
        self.assertEqual("HEIDELBERG", parsed.suburb)
        self.assertEqual("3084", parsed.postcode)
        self.assertEqual("2026-08-14", parsed.delivery_date)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertEqual(0, parsed.carton_quantity)
        self.assertEqual(2, len(parsed.product_lines))
        self.assert_product(
            parsed.product_lines[0],
            "RBATH",
            "COLOURED TOWEL MIX #10",
            450,
            "KG",
            45,
            "BAG10",
        )
        self.assert_product(
            parsed.product_lines[1],
            "MIC-MICROF",
            "MICRO FIBRE CLOTH 40 X 40",
            250,
            "EACH",
            10,
            "PKT25",
        )
        packet_warning_text = " ".join(parsed.warnings).upper()
        self.assertNotIn("PKT", packet_warning_text)
        self.assertNotIn("PACKET", packet_warning_text)

    def test_packet_summary_variants_confirm_structural_packet_packaging(self):
        for summary in ("10 PACKETS", "10 PACKET", "10 PKT"):
            with self.subTest(summary=summary):
                parsed = parse_attache_invoice_text(
                    f"""
                    Invoice No 199101
                    Invoice Date 12/08/26
                    Invoice to:
                    PACKET TEST CUSTOMER
                    1 TEST ROAD
                    RICHMOND 3121
                    Deliver to:
                    PACKET TEST CUSTOMER
                    1 TEST ROAD
                    RICHMOND
                    3121
                    Code Description Price Per Net Amt+GST
                    MICRO 250MICRO FIBRE CLOTH EACH 1.000 1.00 1.00 0.00
                    PKT 25 PIECES PER PACKET 0.000 0.00 0.00 0.00
                    {summary}
                    """,
                    source_filename="packet-summary.txt",
                    import_date=date(2026, 8, 13),
                )

                self.assertEqual(1, len(parsed.product_lines))
                self.assert_product(
                    parsed.product_lines[0],
                    "MICRO",
                    "MICRO FIBRE CLOTH",
                    250,
                    "EACH",
                    10,
                    "PKT25",
                )
                self.assertEqual(0, parsed.loose_bags_quantity)
                self.assertFalse(any("Unclassified" in warning for warning in parsed.warnings))

    def test_packet_descriptor_and_summary_mismatch_requires_review_warning(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No 199102
            Invoice Date 12/08/26
            Invoice to:
            PACKET TEST CUSTOMER
            1 TEST ROAD
            RICHMOND 3121
            Deliver to:
            PACKET TEST CUSTOMER
            1 TEST ROAD
            RICHMOND
            3121
            Code Description Price Per Net Amt+GST
            MICRO 250MICRO FIBRE CLOTH EAC 1.000 1.00 1.00 0.00
            PKT 25 PIECES IN A PACKET 8 PKT 0.000 0.00 0.00 0.00
            10 PACKETS
            """,
            source_filename="packet-mismatch.txt",
            import_date=date(2026, 8, 13),
        )

        self.assert_product(
            parsed.product_lines[0],
            "MICRO",
            "MICRO FIBRE CLOTH",
            250,
            "EACH",
            8,
            "PKT25",
        )
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertTrue(
            any("packet quantity mismatch" in warning.lower() for warning in parsed.warnings),
            parsed.warnings,
        )

    def test_explicit_delivery_date_overrides_import_date_default(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No 199003
            Invoice Date 09/08/26
            Delivery Date 20/08/26
            Invoice to:
            EXPLICIT DATE CUSTOMER
            3 SANITIZED ROAD
            RICHMOND 3121
            Deliver to:
            EXPLICIT DATE CUSTOMER
            3 SANITIZED ROAD
            RICHMOND
            3121
            Tax Invoice
            RSING 4.13 KG 25 COLOR TSHIRT RAGS 1.650 45.38 41.25
            BAG5 0.00 5 PLASTIC BAG 5 kg 0.000 0.00 0.00
            """,
            source_filename="explicit-delivery-date.txt",
            import_date=date(2026, 8, 12),
        )

        self.assertEqual("2026-08-09", parsed.invoice_date)
        self.assertEqual("2026-08-20", parsed.delivery_date)


if __name__ == "__main__":
    unittest.main()
