"""Reported invoice rows in Bridge order and text from the real docket 4440.

Invoice customer details are sanitized; PDF financial columns are synthetic.
"""


def invoice_186598_payload():
    rows = (
        ("34287-SEQ", "WHITE COTTON RAGS 1.5KG", "BAG", 224),
        ("BAG1.5", "PLASTIC BAG 1.5 kg", "EACH", 224),
        ("30576-SEQ", "PURE WHITE RAGS 1.5KG", "BAG", 224),
        ("BAG1.5", "PLASTIC BAG 1.5 kg", "EACH", 224),
        ("35762-SEQ", "COLOURED COTTON RAGS 1.5KG", "BAG", 224),
        ("BAG1.5", "PLASTIC BAG 1.5 kg", "EACH", 224),
        ("PAL", "PALLET", "EACH", 3),
        ("DEL", "DELIVERY/FUEL LEVY CHARGE", "EACH", 1),
    )
    return {
        "invoice_number": "186598",
        "invoice_date": None,
        "customer_code": "SANITIZED",
        "customer_name": "SANITIZED CUSTOMER",
        "delivery_description": "SANITIZED CUSTOMER",
        "delivery_address_lines": ["1 TEST ROAD"],
        "suburb": "TRUGANINA",
        "postcode": None,
        "order_reference": None,
        "invoice_order_number": "204722",
        "lines": [
            {
                "line_number": line_number,
                "code": code,
                "description": description,
                "unit": unit,
                "quantity_invoiced": quantity,
                "quantity_ordered": None,
                "quantity_backordered": None,
                "package_number": None,
            }
            for line_number, (code, description, unit, quantity) in enumerate(rows, 1)
        ],
    }


INVOICE_186598_PDF_TEXT = """
Invoice No
186598
Date
05/10/26
Order No
204722
Deliver to:
SANITIZED CUSTOMER
1 TEST ROAD
TRUGANINA VIC 3029
Code Description
34287-SEQ 32.10 BAG 224 WHITE COTTON RAGS 1.5KG 0.950 212.80 193.45
BAG1.5 0.00 224 PLASTIC BAG 1.5 kg 0.000 0.00 0.00
30576-SEQ 32.10 BAG 224 PURE WHITE RAGS 1.5KG 0.950 212.80 193.45
BAG1.5 0.00 224 PLASTIC BAG 1.5 kg 0.000 0.00 0.00
35762-SEQ 32.10 BAG 224 COLOURED COTTON RAGS 1.5KG 0.950 212.80 193.45
BAG1.5 0.00 224 PLASTIC BAG 1.5 kg 0.000 0.00 0.00
PAL 0.00 PLT 3 PALLETS 0.000 0.00 0.00
DEL 10.50 DEL 1 DELIVERY/FUEL LEVY CHARGE 105.000 115.50 105.00
"""


DOCKET_4440_PARAGRAPHS = (
    "DELIVERY DOCKET: 4440/186656",
    "DATED: 05/10/2026",
    "DELIVER TO: c/o",
    "BUrTCHELLS TSPT c/- sargent tspt",
    "23 foundation rd",
    "Truganina  VIC",
    "ON FWD STOCK TO:",
    "**PLS CHARGE CUSTOMERS ACCT**",
    "AG SpaRES  - DENILIQuin",
    "201-205 BARHAM ROAD",
    "DENILIQUIN  2710",
    "PH: 03 5881 1255",
    "ORDER NUMBER: 14096",
    "45X10KG COLOURED T SHIRT",
    "1 PALLET",
    "*INVOICE TO FOLLOW FROM MCC",
)
