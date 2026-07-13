from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.manual_dispatch.logbook_file_service import (  # noqa: E402
    resolve_logbook_dir,
)


LOGBOOK_PATTERN = "manual_dispatch_logbook_*.txt"
SEARCH_FIELDS = (
    "summary",
    "actor",
    "action",
    "workspace",
    "entity_id",
    "driver",
    "vehicle",
    "run_sheet_id",
    "collection_id",
)


def parse_date_argument(value: str) -> date:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"{value!r} is invalid; expected YYYY-MM-DD"
        ) from error
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError(
            f"{value!r} is invalid; expected YYYY-MM-DD"
        )
    return parsed


def parse_limit_argument(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "limit must be a non-negative integer"
        ) from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("limit must be a non-negative integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read and filter Manual Dispatch monthly JSON Lines logbook files."
    )
    parser.add_argument("--logbook-dir")
    parser.add_argument("--date-from", type=parse_date_argument)
    parser.add_argument("--date-to", type=parse_date_argument)
    parser.add_argument("--workspace")
    parser.add_argument("--actor")
    parser.add_argument("--action")
    parser.add_argument("--result")
    parser.add_argument("--driver")
    parser.add_argument("--entity-id")
    parser.add_argument("--search")
    parser.add_argument("--limit", type=parse_limit_argument)
    parser.add_argument("--format", choices=("text", "jsonl"), default="text")
    return parser


def discover_logbook_files(
    logbook_dir: str | Path,
    *,
    stderr: TextIO | None = None,
) -> list[Path]:
    warning_stream = sys.stderr if stderr is None else stderr
    directory = Path(logbook_dir)
    try:
        return sorted(directory.glob(LOGBOOK_PATTERN), key=lambda path: path.name)
    except OSError as error:
        print(
            f"Warning: {directory}: unable to list logbook files "
            f"({type(error).__name__}).",
            file=warning_stream,
        )
        return []


def read_logbook_records(
    logbook_dir: str | Path,
    *,
    stderr: TextIO | None = None,
) -> list[dict[str, Any]]:
    warning_stream = sys.stderr if stderr is None else stderr
    sortable_records = []

    for file_index, path in enumerate(
        discover_logbook_files(logbook_dir, stderr=warning_stream)
    ):
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        _warn_malformed(path, line_number, warning_stream)
                        continue
                    if not isinstance(record, dict):
                        _warn_malformed(
                            path,
                            line_number,
                            warning_stream,
                            reason="expected a JSON object",
                        )
                        continue
                    sortable_records.append(
                        (
                            _record_sort_key(record, file_index, line_number),
                            record,
                        )
                    )
        except (OSError, UnicodeError) as error:
            print(
                f"Warning: {path.name}: unable to read file "
                f"({type(error).__name__}).",
                file=warning_stream,
            )

    sortable_records.sort(key=lambda item: item[0])
    return [record for _, record in sortable_records]


def filter_records(
    records: Iterable[dict[str, Any]],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    workspace: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    result: str | None = None,
    driver: str | None = None,
    entity_id: str | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if limit == 0:
        return []

    matches = []
    for record in records:
        if not _matches_record(
            record,
            date_from=date_from,
            date_to=date_to,
            workspace=workspace,
            actor=actor,
            action=action,
            result=result,
            driver=driver,
            entity_id=entity_id,
            search=search,
        ):
            continue
        matches.append(record)
        if limit is not None and len(matches) >= limit:
            break
    return matches


def format_text_record(record: dict[str, Any]) -> str:
    fields = ("time", "result", "workspace", "actor", "action", "summary")
    return " | ".join(_display_value(record.get(field)) for field in fields)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_utf8(sys.stdout)
    logbook_dir = resolve_logbook_dir(args.logbook_dir)
    records = read_logbook_records(logbook_dir)
    matches = filter_records(
        records,
        date_from=args.date_from,
        date_to=args.date_to,
        workspace=args.workspace,
        actor=args.actor,
        action=args.action,
        result=args.result,
        driver=args.driver,
        entity_id=args.entity_id,
        search=args.search,
        limit=args.limit,
    )

    for record in matches:
        if args.format == "jsonl":
            print(json.dumps(record, ensure_ascii=False))
        else:
            print(format_text_record(record))
    return 0


def _matches_record(
    record: dict[str, Any],
    *,
    date_from: date | None,
    date_to: date | None,
    workspace: str | None,
    actor: str | None,
    action: str | None,
    result: str | None,
    driver: str | None,
    entity_id: str | None,
    search: str | None,
) -> bool:
    if date_from is not None or date_to is not None:
        record_date = _record_date(record)
        if record_date is None:
            return False
        if date_from is not None and record_date < date_from:
            return False
        if date_to is not None and record_date > date_to:
            return False

    exact_filters = {
        "workspace": workspace,
        "action": action,
        "result": result,
        "entity_id": entity_id,
    }
    for field, expected in exact_filters.items():
        if expected is not None and _casefold(record.get(field)) != expected.casefold():
            return False

    substring_filters = {"actor": actor, "driver": driver}
    for field, expected in substring_filters.items():
        if expected is not None and expected.casefold() not in _casefold(record.get(field)):
            return False

    if search is not None:
        needle = search.casefold()
        if not any(needle in _casefold(record.get(field)) for field in SEARCH_FIELDS):
            return False

    return True


def _record_date(record: dict[str, Any]) -> date | None:
    value = str(record.get("time") or "")
    if len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _record_sort_key(
    record: dict[str, Any],
    file_index: int,
    line_number: int,
):
    value = str(record.get("time") or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return (0, parsed, file_index, line_number)
    except ValueError:
        return (1, datetime.max, file_index, line_number)


def _warn_malformed(
    path: Path,
    line_number: int,
    stderr: TextIO,
    *,
    reason: str = "invalid JSON",
) -> None:
    print(f"Warning: {path.name}:{line_number}: {reason}; skipped.", file=stderr)


def _casefold(value: Any) -> str:
    if value is None:
        return ""
    return str(value).casefold()


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _configure_utf8(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
