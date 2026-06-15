import unittest

from backend.services.manual_dispatch.attache_invoice_pdf_parser import (
    parse_attache_invoice_text,
)


class AttacheInvoicePdfParserTest(unittest.TestCase):
    def test_snap_pack_bag_invoice(self):
        parsed = parse_attache_invoice_text(
            """
            Tax Invoice 182438
            Invoice Date: 20/03/2026
            Company: SNAP PACK
            Phone: 0422275484
            Delivery Address: B8/2A WESTALL ROAD, HALLMARK BUSINESS CENTRE
            Suburb: SPRINGVALE
            Postcode: 3171
            DELIVERY BETWEEN 7:00 AM - 12:00PM
            RSING PURE WHITE SINGLET 100KG 10 BAG10
            CT25 COLOR TSHIRT RAGS 25KG 5 BAG5
            GST 12.00
            """,
            source_filename="182438.pdf",
        )

        self.assertEqual("182438", parsed.invoice_number)
        self.assertEqual("SNAP PACK", parsed.company_name)
        self.assertEqual("2026-03-21", parsed.delivery_date)
        self.assertEqual(0, parsed.pallet_quantity)
        self.assertEqual(15, parsed.loose_bags_quantity)
        self.assertEqual("07:00", parsed.start_time)
        self.assertEqual("12:00", parsed.end_time)
        self.assertEqual(
            [
                {
                    "product_name": "PURE WHITE SINGLET 100KG",
                    "quantity": 10,
                    "unit": "BAGS",
                },
                {
                    "product_name": "COLOR TSHIRT RAGS 25KG",
                    "quantity": 5,
                    "unit": "BAGS",
                },
            ],
            parsed.product_lines,
        )

    def test_coringle_furniture_mixed_pallet_and_bag_invoice(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No: 183075
            Invoice Date: 21/04/2026
            Company: Coringle Furniture
            Phone: 9870 3900
            Delivery Address: 13-16 Summer Ln
            Suburb: Ringwood
            Postcode: 3134
            RPWSING PURE WHITE SINGLET 300KG 30 BAG10
            FIN-3PLY FINESSE-3PLY T/PAPER 180 SHTSx72ROLLS 3 BAG
            PAL PALLET 1
            FUEL LEVY CHARGE 1 DELIVERY
            """,
            source_filename="183075.pdf",
        )

        self.assertEqual("183075", parsed.invoice_number)
        self.assertEqual("Coringle Furniture", parsed.company_name)
        self.assertEqual("2026-04-22", parsed.delivery_date)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(3, parsed.loose_bags_quantity)
        self.assertEqual(
            [
                {
                    "product_name": "PURE WHITE SINGLET 300KG",
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
            Invoice No: 183077
            Invoice Date: 21/04/2026
            Company: BT EQUIPMENT trading as Tutt Bryant
            Phone: 9554 0300
            Delivery Address: 80-86 FRANKSTON-DANDENONG ROAD
            Suburb: DANDENONG
            Postcode: 3175
            Order No: PO000008304
            NO VAN, MUST BE TRUCK DELIVERY
            CTRAG COLOR TSHIRT RAGS 200KG 20 BAG10
            PAL PALLET 1
            Total Amount 123.45
            """,
            source_filename="183077.pdf",
        )

        self.assertEqual("183077", parsed.invoice_number)
        self.assertEqual(1, parsed.pallet_quantity)
        self.assertEqual(0, parsed.loose_bags_quantity)
        self.assertIn("Order No: PO000008304", parsed.note)
        self.assertIn("NO VAN, MUST BE TRUCK DELIVERY", parsed.note)
        self.assertEqual(
            [
                {
                    "product_name": "COLOR TSHIRT RAGS 200KG",
                    "quantity": 1,
                    "unit": "PALLETS",
                }
            ],
            parsed.product_lines,
        )

    def test_desi_dhaba_opens_instruction(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No: 183080
            Invoice Date: 21/04/2026
            Company: DESI DHABA CRAIGIEBURN
            Phone: 0402 848 618
            Delivery Address: 340 CRAIGIEBURN ROAD
            Suburb: CRAIGIEBURN
            Postcode: 3064
            OPENS 11AM
            WS11 WHITE SHEETING #11S 50KG 5 BAG10
            """,
            source_filename="183080.pdf",
        )

        self.assertEqual("183080", parsed.invoice_number)
        self.assertEqual("11:00", parsed.start_time)
        self.assertIsNone(parsed.end_time)
        self.assertEqual(0, parsed.pallet_quantity)
        self.assertEqual(5, parsed.loose_bags_quantity)
        self.assertEqual(
            [
                {
                    "product_name": "WHITE SHEETING #11S 50KG",
                    "quantity": 5,
                    "unit": "BAGS",
                }
            ],
            parsed.product_lines,
        )

    def test_pakenham_accident_repair_opens_instruction(self):
        parsed = parse_attache_invoice_text(
            """
            Invoice No: 183081
            Invoice Date: 21/04/2026
            Company: PAKENHAM ACCIDENT REPAIR
            Phone: 59412772
            Delivery Address: 21 BALD HILL ROAD
            Suburb: PAKENHAM
            Postcode: 3810
            OPENS 8AM
            CTRAG COLOR TSHIRT RAGS 60KG 6 BAG10
            """,
            source_filename="183081.pdf",
        )

        self.assertEqual("183081", parsed.invoice_number)
        self.assertEqual("08:00", parsed.start_time)
        self.assertIsNone(parsed.end_time)
        self.assertEqual(6, parsed.loose_bags_quantity)
        self.assertEqual(
            [
                {
                    "product_name": "COLOR TSHIRT RAGS 60KG",
                    "quantity": 6,
                    "unit": "BAGS",
                }
            ],
            parsed.product_lines,
        )


if __name__ == "__main__":
    unittest.main()
