"""Print parsed Attache invoice PDF previews as JSON for local verification.

This script is intentionally local-only: pass real PDF paths from the office
machine when checking pypdf extraction behavior without committing the PDFs or
their extracted text into the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.schemas import to_dict  # noqa: E402
from backend.services.manual_dispatch.attache_invoice_pdf_parser import (  # noqa: E402
    parse_attache_invoice_pdf_bytes,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Parse Attache invoice PDFs and print preview JSON.",
    )
    parser.add_argument(
        "pdf_paths",
        nargs="+",
        help="Path(s) to real Attache invoice PDFs.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    rows = []

    for pdf_path in args.pdf_paths:
        path = Path(pdf_path)
        try:
            parsed = parse_attache_invoice_pdf_bytes(
                path.read_bytes(),
                source_filename=path.name,
            )
            rows.append(to_dict(parsed))
        except Exception as error:  # pragma: no cover - CLI diagnostics only.
            rows.append(
                {
                    "source_filename": path.name,
                    "source_path": str(path),
                    "error": str(error),
                }
            )

    print(json.dumps({"rows": rows}, indent=2, ensure_ascii=False))
    return 1 if any("error" in row for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
