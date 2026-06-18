import unittest

from backend.services.manual_dispatch.attache_invoice_pdf_parser import (
    parse_attache_invoice_text,
)


class AttacheInvoicePdfParserTest(unittest.TestCase):
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
        )

        self.assertEqual("182438", parsed.invoice_number)
        self.assertEqual("SNASPR", parsed.customer_code)
        self.assertEqual("20032026", parsed.order_no)
        self.assert_order_number_not_in_note(parsed)
        self.assertEqual("SNAP PACK", parsed.company_name)
        self.assertEqual("2026-03-21", parsed.delivery_date)
        self.assertEqual(0, parsed.pallet_quantity)
        self.assertEqual(15, parsed.loose_bags_quantity)
        self.assertEqual("07:00", parsed.start_time)
        self.assertEqual("12:00", parsed.end_time)
        self.assertEqual(
            [
                {
                    "product_name": "PURE WHITE SINGLET",
                    "quantity": 10,
                    "unit": "BAGS",
                },
                {
                    "product_name": "COLOR TSHIRT RAGS",
                    "quantity": 5,
                    "unit": "BAGS",
                },
            ],
            parsed.product_lines,
        )

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
        )

        self.assertEqual("183075", parsed.invoice_number)
        self.assertEqual("CORRIN", parsed.customer_code)
        self.assertEqual("40", parsed.order_no)
        self.assert_order_number_not_in_note(parsed)
        self.assertEqual("Coringle Furniture", parsed.company_name)
        self.assertEqual("2026-04-22", parsed.delivery_date)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(3, parsed.loose_bags_quantity)
        self.assertEqual(
            [
                {
                    "product_name": "PURE WHITE SINGLET",
                    "quantity": 1,
                    "unit": "PALLETS",
                },
                {
                    "product_name": "FINESSE-3PLY T/PAPER 180 SHTSx72ROLLS",
                    "quantity": 3,
                    "unit": "BAGS",
                },
            ],
            parsed.product_lines,
        )

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
        self.assertEqual(
            [
                {
                    "product_name": "COLOR TSHIRT RAGS",
                    "quantity": 1,
                    "unit": "PALLETS",
                }
            ],
            parsed.product_lines,
        )

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
        self.assertEqual(
            [
                {
                    "product_name": "WHITE SHEETING #11S",
                    "quantity": 5,
                    "unit": "BAGS",
                }
            ],
            parsed.product_lines,
        )

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
        self.assertEqual(
            [
                {
                    "product_name": "COLOR TSHIRT RAGS",
                    "quantity": 6,
                    "unit": "BAGS",
                }
            ],
            parsed.product_lines,
        )


if __name__ == "__main__":
    unittest.main()
