import argparse
import unicodedata

from backend.integrations.attache_bridge_client import (
    AttacheBridgeError,
    create_attache_bridge_client,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Perform one explicitly authorized read-only Attaché Bridge lookup."
        )
    )
    parser.add_argument(
        "--invoice-number",
        required=True,
        help="Digits-only Attaché invoice number.",
    )
    args = parser.parse_args()

    try:
        payload = create_attache_bridge_client().lookup_invoice(
            args.invoice_number
        )
        summary_lines = build_smoke_summary_lines(payload)
    except (AttacheBridgeError, ValueError) as error:
        parser.exit(1, f"Attaché Bridge smoke check failed: {error}\n")

    for line in summary_lines:
        print(line)


def build_smoke_summary_lines(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
        raise ValueError("Attaché Bridge returned an invalid smoke-test response.")

    product_lines = payload["lines"]
    summary = [
        "ATTACHE_BRIDGE_SMOKE_LOOKUP_OK",
        f"Invoice Number: {_single_line(payload.get('invoice_number'))}",
        f"Invoice Date: {_single_line(payload.get('invoice_date'))}",
        f"Customer Code: {_single_line(payload.get('customer_code'))}",
        f"Customer Name: {_single_line(payload.get('customer_name'))}",
        f"Reference: {_single_line(payload.get('order_reference'))}",
        f"Product Lines: {len(product_lines)}",
    ]
    for line in product_lines:
        if not isinstance(line, dict):
            raise ValueError("Attaché Bridge returned an invalid product line.")
        summary.append(
            "Line "
            f"{_single_line(line.get('line_number'))}: "
            f"{_single_line(line.get('code'))} | "
            f"{_single_line(line.get('description'))} | "
            f"qtyinv={_single_line(line.get('quantity_invoiced'))}"
        )
    return summary


def _single_line(value):
    if value in (None, ""):
        return "-"
    printable = "".join(
        character if not unicodedata.category(character).startswith("C") else " "
        for character in str(value)
    )
    return " ".join(printable.split())[:200] or "-"


if __name__ == "__main__":
    main()
