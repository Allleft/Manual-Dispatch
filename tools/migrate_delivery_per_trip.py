"""Dry-run by default; Stage 1 supports explicitly isolated SQLite fixtures."""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.delivery_per_trip import DeliveryPerTripMigrationError, migrate_delivery_per_trip


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = migrate_delivery_per_trip(args.db_path, apply=args.apply, yes=args.yes)
    except DeliveryPerTripMigrationError as error:
        print(json.dumps({"error": str(error), "report": error.report}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
