"""Read-only integrity checker for Manual Dispatch System Logbook files."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.manual_dispatch.logbook_file_service import (  # noqa: E402
    resolve_logbook_dir,
)
from tools.logbook_contract import (  # noqa: E402
    ALLOWED_RESULTS,
    ALLOWED_WORKSPACES,
    DATE_FIELDS,
    INCIDENT_ANNOTATION_ACTION,
    KNOWN_ACTIONS,
    LOGBOOK_FILENAME_PATTERN,
    LOGBOOK_FILENAME_REGEX,
    NON_EMPTY_STRING_FIELDS,
    NULLABLE_STRING_FIELDS,
    REQUIRED_FIELDS,
)


@dataclass(frozen=True)
class IntegrityIssue:
    severity: str
    code: str
    filename: str
    line_number: int | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "filename": self.filename,
            "line_number": self.line_number,
            "message": self.message,
        }


@dataclass
class IntegrityCheckResult:
    files_checked: int = 0
    records_checked: int = 0
    issues: list[IntegrityIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "ERROR" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "WARNING" for issue in self.issues)

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "files_checked": self.files_checked,
            "records_checked": self.records_checked,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class IntegrityCheckFatalError(Exception):
    """A safe fatal error that prevented a valid integrity result."""


def check_logbook_integrity(logbook_dir: str | Path) -> IntegrityCheckResult:
    """Inspect every candidate Logbook file without modifying the directory."""
    directory = Path(logbook_dir)
    try:
        if not directory.exists():
            raise IntegrityCheckFatalError("Logbook directory does not exist.")
        if not directory.is_dir():
            raise IntegrityCheckFatalError("Logbook path is not a directory.")
        candidates = sorted(
            directory.glob(LOGBOOK_FILENAME_PATTERN),
            key=lambda path: path.name,
        )
    except IntegrityCheckFatalError:
        raise
    except OSError as error:
        raise IntegrityCheckFatalError(
            "Logbook directory could not be listed."
        ) from error

    if not candidates:
        return IntegrityCheckResult(
            issues=[
                IntegrityIssue(
                    "ERROR",
                    "NO_LOGBOOK_FILES",
                    "",
                    None,
                    "No Logbook files were found.",
                )
            ]
        )

    issues: list[IntegrityIssue] = []
    records_checked = 0
    incident_annotations: dict[tuple[str, str], tuple[str, int]] = {}

    for path in candidates:
        filename_match = LOGBOOK_FILENAME_REGEX.fullmatch(path.name)
        if filename_match is None:
            issues.append(
                IntegrityIssue(
                    "ERROR",
                    "INVALID_FILENAME",
                    path.name,
                    None,
                    "Filename does not use the required monthly format.",
                )
            )

        try:
            content = path.read_bytes()
        except OSError:
            issues.append(
                IntegrityIssue(
                    "ERROR",
                    "UNREADABLE_FILE",
                    path.name,
                    None,
                    "File could not be read.",
                )
            )
            continue

        if not content:
            issues.append(
                IntegrityIssue(
                    "WARNING",
                    "EMPTY_LOGBOOK_FILE",
                    path.name,
                    None,
                    "File is empty.",
                )
            )
            continue

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(
                IntegrityIssue(
                    "ERROR",
                    "INVALID_UTF8",
                    path.name,
                    None,
                    "File is not valid UTF-8.",
                )
            )
            continue

        lines = text.split("\n")
        nonblank_lines = [
            (line_number, line)
            for line_number, line in enumerate(lines, start=1)
            if line.strip()
        ]
        last_nonblank_line = nonblank_lines[-1][0] if nonblank_lines else None
        ends_with_newline = content.endswith(b"\n")
        final_json_value_is_valid = False

        for line_number, line in nonblank_lines:
            records_checked += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                is_unterminated_final = (
                    line_number == last_nonblank_line and not ends_with_newline
                )
                issues.append(
                    IntegrityIssue(
                        "ERROR",
                        (
                            "TRUNCATED_FINAL_LINE"
                            if is_unterminated_final
                            else "MALFORMED_JSON"
                        ),
                        path.name,
                        line_number,
                        (
                            "Final line appears to be truncated."
                            if is_unterminated_final
                            else "Line is not valid JSON."
                        ),
                    )
                )
                continue

            if line_number == last_nonblank_line:
                final_json_value_is_valid = True
            if not isinstance(record, dict):
                issues.append(
                    IntegrityIssue(
                        "ERROR",
                        "NON_OBJECT_RECORD",
                        path.name,
                        line_number,
                        "JSON value is not an object.",
                    )
                )
                continue

            _validate_record(
                record,
                path.name,
                line_number,
                filename_match,
                incident_annotations,
                issues,
            )

        if not ends_with_newline and final_json_value_is_valid:
            issues.append(
                IntegrityIssue(
                    "WARNING",
                    "MISSING_FINAL_NEWLINE",
                    path.name,
                    None,
                    "File does not end with a newline.",
                )
            )

    issues.sort(key=_issue_sort_key)
    return IntegrityCheckResult(
        files_checked=len(candidates),
        records_checked=records_checked,
        issues=issues,
    )


def _validate_record(
    record: dict[str, Any],
    filename: str,
    line_number: int,
    filename_match,
    incident_annotations: dict[tuple[str, str], tuple[str, int]],
    issues: list[IntegrityIssue],
) -> None:
    def add(code: str, message: str) -> None:
        issues.append(IntegrityIssue("ERROR", code, filename, line_number, message))

    for name in REQUIRED_FIELDS:
        if name not in record:
            add("MISSING_REQUIRED_FIELD", f"Required field '{name}' is missing.")

    for name in NON_EMPTY_STRING_FIELDS:
        if name not in record:
            continue
        value = record[name]
        if not isinstance(value, str):
            add("INVALID_FIELD_TYPE", f"Field '{name}' must be a string.")
        elif not value.strip():
            add("EMPTY_REQUIRED_VALUE", f"Field '{name}' must not be empty.")

    for name in NULLABLE_STRING_FIELDS:
        if name not in record:
            continue
        value = record[name]
        if value is not None and not isinstance(value, str):
            add(
                "INVALID_FIELD_TYPE",
                f"Field '{name}' must be a string or null.",
            )

    if "metadata" in record and not isinstance(record["metadata"], dict):
        add("INVALID_FIELD_TYPE", "Field 'metadata' must be a JSON object.")

    parsed_time = _validate_timestamp(record.get("time"), add)
    if parsed_time is not None and filename_match is not None:
        file_year = int(filename_match.group(1))
        file_month = int(filename_match.group(2))
        if (parsed_time.year, parsed_time.month) != (file_year, file_month):
            add(
                "EVENT_MONTH_MISMATCH",
                "Event timestamp does not match the monthly filename.",
            )

    _validate_allowed_value(record, "result", ALLOWED_RESULTS, "INVALID_RESULT", add)
    _validate_allowed_value(
        record,
        "workspace",
        ALLOWED_WORKSPACES,
        "INVALID_WORKSPACE",
        add,
    )
    _validate_allowed_value(record, "action", KNOWN_ACTIONS, "UNKNOWN_ACTION", add)

    for name in DATE_FIELDS:
        value = record.get(name)
        if isinstance(value, str) and not _is_valid_date(value):
            add(
                "INVALID_DATE_FIELD",
                f"Field '{name}' must use a valid YYYY-MM-DD date.",
            )

    if record.get("action") == INCIDENT_ANNOTATION_ACTION:
        entity_id = record.get("entity_id")
        if entity_id is None:
            add(
                "INVALID_FIELD_TYPE",
                "Incident annotation entity_id must be a non-empty string.",
            )
        elif isinstance(entity_id, str) and not entity_id.strip():
            add(
                "EMPTY_REQUIRED_VALUE",
                "Incident annotation entity_id must not be empty.",
            )
        elif isinstance(entity_id, str):
            key = (INCIDENT_ANNOTATION_ACTION, entity_id)
            first = incident_annotations.get(key)
            if first is None:
                incident_annotations[key] = (filename, line_number)
            else:
                first_filename, first_line = first
                add(
                    "DUPLICATE_INCIDENT_ANNOTATION",
                    "Incident annotation duplicates the occurrence at "
                    f"{first_filename}:{first_line}.",
                )


def _validate_timestamp(value: Any, add) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        add("INVALID_TIMESTAMP", "Timestamp is not valid ISO 8601.")
        return None
    try:
        aware = parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        aware = False
    if not aware:
        add("NAIVE_TIMESTAMP", "Timestamp must include a timezone offset.")
        return None
    return parsed


def _validate_allowed_value(record, field_name, allowed, code, add) -> None:
    value = record.get(field_name)
    if isinstance(value, str) and value.strip() and value not in allowed:
        label = field_name.replace("_", " ").capitalize()
        add(code, f"{label} is not registered.")


def _is_valid_date(value: str) -> bool:
    if len(value) != 10 or value[4:5] != "-" or value[7:8] != "-":
        return False
    if not (value[:4] + value[5:7] + value[8:]).isdigit():
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _issue_sort_key(issue: IntegrityIssue):
    return (
        issue.filename,
        issue.line_number or 0,
        issue.severity,
        issue.code,
    )


def format_text_result(result: IntegrityCheckResult) -> str:
    lines = [
        "Manual Dispatch Logbook Integrity Check",
        f"Files checked: {result.files_checked}",
        f"Records checked: {result.records_checked}",
        f"Errors: {result.error_count}",
        f"Warnings: {result.warning_count}",
        f"Result: {'OK' if result.ok else 'FAILED'}",
    ]
    if result.issues:
        lines.extend(("", "Issues:"))
        for issue in result.issues:
            location = issue.filename
            if issue.line_number:
                location += f":{issue.line_number}"
            lines.append(
                f"{issue.severity} | {location} | {issue.code} | {issue.message}"
            )
    return "\n".join(lines)


def format_json_result(result: IntegrityCheckResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check Manual Dispatch Logbook files without modifying them."
    )
    parser.add_argument("--logbook-dir")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_utf8(sys.stdout)
    _configure_utf8(sys.stderr)
    try:
        result = check_logbook_integrity(resolve_logbook_dir(args.logbook_dir))
    except IntegrityCheckFatalError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except Exception:
        print("Error: Logbook integrity check could not be completed.", file=sys.stderr)
        return 2

    output = (
        format_json_result(result)
        if args.format == "json"
        else format_text_result(result)
    )
    print(output)
    if result.error_count or (args.strict and result.warning_count):
        return 1
    return 0


def _configure_utf8(stream: TextIO) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
