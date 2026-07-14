from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import backfill_opshop_source_driver_assignments as backfill
from tools import import_countryside_opshop_pickups_to_db as countryside
from tools import import_oncall_opshop_pickups_to_db as oncall
from tools import import_regular_opshop_pickups_to_db as regular
from tools import migrate_legacy_final_summaries_to_workspaces as migration
from tools.maintenance_logbook import (
    MAINTENANCE_ACTOR_ENV,
    record_maintenance_event,
    resolve_maintenance_actor,
    safe_basename,
    sanitized_failure_metadata,
)


class Stage2C1MaintenanceLogbookTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.logbook_dir = self.root / "logbook"
        self.db_path = self.root / "private" / "manual_dispatch_test.sqlite3"
        self.db_path.parent.mkdir(parents=True)
        self.db_path.write_bytes(b"database-before")
        self.env = patch.dict(
            os.environ,
            {
                "MANUAL_DISPATCH_LOGBOOK_DIR": str(self.root / "env-logbook"),
                MAINTENANCE_ACTOR_ENV: "Environment Operator",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def _events(self, logbook_dir=None):
        directory = Path(logbook_dir or self.logbook_dir)
        events = []
        for path in sorted(directory.glob("manual_dispatch_logbook_*.txt")):
            events.extend(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        return events

    def _import_summary(self, *, unresolved=None, backup=True, countryside_mode=False):
        values = {
            "rows_read": 7,
            "rows_imported": 5,
            "rows_skipped_inactive": 2,
            "locations_inserted": 1,
            "locations_updated": 4,
            "schedules_inserted": 2,
            "schedules_updated": 3,
            "schedules_deactivated": 1,
            "unresolved_assigned_to": unresolved or {},
            "default_driver_mapping_counts": {"Sensitive Driver": 5},
            "backup_path": (
                str(self.root / "private" / "manual_dispatch_before_import.sqlite3")
                if backup
                else None
            ),
            "source_rows": [
                {
                    "address": "99 Private Street",
                    "phone": "0400000000",
                }
            ],
        }
        if countryside_mode:
            values.update(
                {
                    "sheets_read": 2,
                    "route_groups_inserted": 1,
                    "route_groups_updated": 1,
                    "route_groups_deactivated": 0,
                    "duplicate_locations_reused": 2,
                }
            )
        return SimpleNamespace(**values)

    def _import_args(self, workbook, *, actor="Explicit Operator"):
        args = [
            "--file",
            str(workbook),
            "--db-path",
            str(self.db_path),
            "--logbook-dir",
            str(self.logbook_dir),
        ]
        if actor is not None:
            args.extend(["--actor", actor])
        return args

    def _backfill_summary(self, *, blockers=0):
        return {
            "regular_source_rows": 2,
            "oncall_source_rows": 3,
            "matched_templates": 5,
            "templates_to_update": 2,
            "tasks_to_assign": 1,
            "already_correct": 2,
            "existing_assignments_preserved": 1,
            "unmatched": 0,
            "ambiguous": blockers,
            "generated_lock_skipped": 0,
            "saved_lock_skipped": 0,
            "conflicts": 0,
            "unknown_driver_aliases": 0,
            "blocking_findings": blockers,
        }

    def _backfill_analysis(self, *, blockers=0):
        return {
            "summary": self._backfill_summary(blockers=blockers),
            "records": [
                {
                    "company": "Private Company",
                    "address": "99 Private Street",
                    "source_driver_alias": "Secret Alias",
                }
            ],
        }

    def _backfill_args(self, mode):
        return [
            "--regular-workbook",
            str(self.root / "private" / "regular-opshop.xlsx"),
            "--oncall-workbook",
            str(self.root / "private" / "oncall-opshop.xlsx"),
            "--db-path",
            str(self.db_path),
            "--from-date",
            "2026-07-14",
            f"--{mode}",
            "--report-path",
            str(self.root / "private" / f"backfill-{mode}.json"),
            "--logbook-dir",
            str(self.logbook_dir),
        ]

    def _migration_report(self, *, blockers=False, apply=False):
        backup_path = (
            str(self.root / "private" / "manual_dispatch_before_migration.sqlite3")
            if apply
            else None
        )
        return {
            "db_path": str(self.db_path),
            "mode": "apply" if apply else "dry-run",
            "backup_path": backup_path,
            "summary": {
                "saved_legacy_summaries": 2,
                "generated_legacy_summaries": 1 if blockers else 0,
                "delivery_to_create": 1,
                "opshop_to_create": 1,
                "already_migrated": 0,
                "conflicts": 0,
                "skipped": 0,
            },
            "generated_summaries": (
                [{"summary_id": "PRIVATE-ID", "driver_name": "Private Driver"}]
                if blockers
                else []
            ),
            "candidates": [{"summary_id": "PRIVATE-CANDIDATE"}],
            "conflicts": [],
            "skipped": [],
            "applied": (
                {
                    "delivery_run_sheets": 1,
                    "delivery_rows": 3,
                    "opshop_collections": 1,
                    "opshop_rows": 2,
                }
                if apply
                else None
            ),
        }

    def _migration_args(self, *, apply=False, yes=False):
        args = [
            "--db-path",
            str(self.db_path),
            "--logbook-dir",
            str(self.logbook_dir),
        ]
        if apply:
            args.append("--apply")
        if yes:
            args.append("--yes")
        return args

    def test_actor_resolution_order_and_blank_fallbacks(self):
        environment = {MAINTENANCE_ACTOR_ENV: "  Environment Actor  "}
        self.assertEqual(
            "Explicit Actor",
            resolve_maintenance_actor("  Explicit Actor  ", environment),
        )
        self.assertEqual(
            "Environment Actor",
            resolve_maintenance_actor("   ", environment),
        )
        self.assertEqual(
            "Unknown",
            resolve_maintenance_actor("", {MAINTENANCE_ACTOR_ENV: "   "}),
        )

    def test_safe_basename_and_failure_metadata_do_not_leak_paths(self):
        self.assertEqual(
            "regular-opshop.xlsx",
            safe_basename(r"C:\Users\Private\regular-opshop.xlsx"),
        )
        self.assertEqual(
            "oncall-opshop.xlsx",
            safe_basename("/volume/private/oncall-opshop.xlsx"),
        )
        error = FileNotFoundError(r"C:\Users\Private\secret.xlsx")
        metadata = sanitized_failure_metadata(error, "workbook_read")
        serialized = json.dumps(metadata)
        self.assertEqual("FileNotFoundError", metadata["error_type"])
        self.assertNotIn("Private", serialized)
        self.assertNotIn("secret.xlsx", serialized)

    def test_logbook_directory_override_and_best_effort_writer(self):
        explicit_dir = self.root / "explicit-logbook"
        self.assertTrue(
            record_maintenance_event(
                action="TEST_MAINTENANCE_EVENT",
                result="SUCCESS",
                workspace="SYSTEM",
                actor="  Explicit Actor  ",
                entity_type="TEST",
                entity_id="test",
                summary="Test maintenance event.",
                metadata={"count": 1},
                logbook_dir=explicit_dir,
            )
        )
        self.assertEqual("Explicit Actor", self._events(explicit_dir)[0]["actor"])
        self.assertEqual([], self._events(self.root / "env-logbook"))
        with patch(
            "tools.maintenance_logbook.LogbookFileService.record",
            side_effect=RuntimeError("writer failed"),
        ):
            self.assertFalse(
                record_maintenance_event(
                    action="TEST_MAINTENANCE_EVENT",
                    result="FAILED",
                    workspace="SYSTEM",
                    actor="Operator",
                    entity_type="TEST",
                    entity_id="test",
                    summary="Writer failure.",
                    metadata={},
                    logbook_dir=explicit_dir,
                )
            )

    def test_importer_success_events_are_single_aggregate_and_private(self):
        cases = (
            (
                regular,
                "import_regular_opshop_pickups_to_db",
                "REGULAR_WORKBOOK_IMPORT_COMPLETED",
                "regular",
                False,
            ),
            (
                oncall,
                "import_oncall_opshop_pickups_to_db",
                "ONCALL_WORKBOOK_IMPORT_COMPLETED",
                "oncall",
                False,
            ),
            (
                countryside,
                "import_countryside_opshop_pickups_to_db",
                "COUNTRYSIDE_WORKBOOK_IMPORT_COMPLETED",
                "countryside",
                True,
            ),
        )
        for module, function_name, action, prefix, countryside_mode in cases:
            with self.subTest(action=action):
                logbook = self.root / f"logbook-{prefix}"
                workbook = self.root / "private" / f"{prefix}-opshop.xlsx"
                summary = self._import_summary(countryside_mode=countryside_mode)
                args = self._import_args(workbook)
                args[args.index(str(self.logbook_dir))] = str(logbook)
                with patch.object(module, function_name, return_value=summary), patch.object(
                    module, "print_summary"
                ):
                    self.assertIsNone(module.main(args))
                events = self._events(logbook)
                self.assertEqual(1, len(events))
                event = events[0]
                self.assertEqual(action, event["action"])
                self.assertEqual("SUCCESS", event["result"])
                self.assertEqual("OPSHOP", event["workspace"])
                self.assertEqual("Explicit Operator", event["actor"])
                self.assertEqual(
                    f"{prefix}:{prefix}-opshop.xlsx",
                    event["entity_id"],
                )
                self.assertEqual(5, event["metadata"]["rows_imported"])
                self.assertEqual(
                    "manual_dispatch_before_import.sqlite3",
                    event["metadata"]["backup_filename"],
                )
                serialized = json.dumps(event)
                self.assertNotIn(str(self.root), serialized)
                self.assertNotIn("99 Private Street", serialized)
                self.assertNotIn("0400000000", serialized)
                self.assertNotIn("Sensitive Driver", serialized)

    def test_importer_unresolved_aliases_are_partial_but_inactive_rows_are_not(self):
        for module, function_name, action, prefix in (
            (
                regular,
                "import_regular_opshop_pickups_to_db",
                "REGULAR_WORKBOOK_IMPORT_COMPLETED",
                "regular",
            ),
            (
                oncall,
                "import_oncall_opshop_pickups_to_db",
                "ONCALL_WORKBOOK_IMPORT_COMPLETED",
                "oncall",
            ),
            (
                countryside,
                "import_countryside_opshop_pickups_to_db",
                "COUNTRYSIDE_WORKBOOK_IMPORT_COMPLETED",
                "countryside",
            ),
        ):
            with self.subTest(action=action):
                logbook = self.root / f"partial-{prefix}"
                workbook = self.root / "private" / f"{prefix}.xlsx"
                summary = self._import_summary(
                    unresolved={"Private Alias": 2},
                    countryside_mode=module is countryside,
                )
                args = self._import_args(workbook)
                args[args.index(str(self.logbook_dir))] = str(logbook)
                with patch.object(module, function_name, return_value=summary), patch.object(
                    module, "print_summary"
                ):
                    module.main(args)
                event = self._events(logbook)[0]
                self.assertEqual("PARTIAL", event["result"])
                self.assertEqual(1, event["metadata"]["unresolved_alias_count"])
                self.assertEqual(
                    2,
                    event["metadata"]["unresolved_alias_occurrence_count"],
                )
                self.assertNotIn("Private Alias", json.dumps(event))

        success_log = self.root / "inactive-success"
        summary = self._import_summary(unresolved={})
        args = self._import_args(self.root / "private" / "regular.xlsx")
        args[args.index(str(self.logbook_dir))] = str(success_log)
        with patch.object(
            regular,
            "import_regular_opshop_pickups_to_db",
            return_value=summary,
        ), patch.object(regular, "print_summary"):
            regular.main(args)
        self.assertEqual("SUCCESS", self._events(success_log)[0]["result"])

    def test_missing_workbook_records_one_failed_event_and_preserves_exception(self):
        missing = self.root / "private" / "missing-regular.xlsx"
        with self.assertRaises(FileNotFoundError):
            regular.main(self._import_args(missing))
        events = self._events()
        self.assertEqual(1, len(events))
        self.assertEqual("FAILED", events[0]["result"])
        self.assertEqual("workbook_read", events[0]["metadata"]["failure_phase"])
        self.assertEqual("FileNotFoundError", events[0]["metadata"]["error_type"])
        self.assertNotIn(str(self.root), json.dumps(events[0]))

    def test_direct_importer_call_does_not_append_event(self):
        direct_logbook = self.root / "direct-logbook"
        with patch.dict(
            os.environ,
            {"MANUAL_DISPATCH_LOGBOOK_DIR": str(direct_logbook)},
            clear=False,
        ):
            with self.assertRaises(FileNotFoundError):
                regular.import_regular_opshop_pickups_to_db(
                    self.root / "missing-direct.xlsx",
                    self.db_path,
                )
        self.assertEqual([], self._events(direct_logbook))

    def test_logbook_failure_preserves_importer_success_and_failure(self):
        summary = self._import_summary()
        with patch.object(
            regular,
            "import_regular_opshop_pickups_to_db",
            return_value=summary,
        ), patch.object(regular, "print_summary"), patch(
            "tools.maintenance_logbook.LogbookFileService.record",
            side_effect=RuntimeError("writer failed"),
        ):
            self.assertIsNone(
                regular.main(
                    self._import_args(self.root / "private" / "regular.xlsx")
                )
            )

        original = FileNotFoundError("original importer failure")
        with patch.object(
            regular,
            "import_regular_opshop_pickups_to_db",
            side_effect=original,
        ), patch(
            "tools.maintenance_logbook.LogbookFileService.record",
            side_effect=RuntimeError("writer failed"),
        ):
            with self.assertRaises(FileNotFoundError) as raised:
                regular.main(
                    self._import_args(self.root / "private" / "missing.xlsx")
                )
        self.assertIs(original, raised.exception)

    def test_backfill_dry_run_success_is_read_only_and_private(self):
        before = self.db_path.read_bytes()
        analysis = self._backfill_analysis()
        args = self._backfill_args("dry-run")
        with patch.object(backfill, "analyze_backfill", return_value=analysis):
            self.assertEqual(0, backfill.main(args))
        self.assertEqual(before, self.db_path.read_bytes())
        self.assertTrue((self.root / "private" / "backfill-dry-run.json").is_file())
        events = self._events()
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual("SOURCE_DRIVER_BACKFILL_DRY_RUN", event["action"])
        self.assertEqual("SUCCESS", event["result"])
        self.assertEqual("Environment Operator", event["actor"])
        self.assertTrue(event["metadata"]["report_created"])
        serialized = json.dumps(event)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("records", serialized)
        self.assertNotIn("Private Company", serialized)
        self.assertNotIn("99 Private Street", serialized)

    def test_backfill_dry_run_blockers_are_partial(self):
        analysis = self._backfill_analysis(blockers=2)
        with patch.object(backfill, "analyze_backfill", return_value=analysis):
            self.assertEqual(0, backfill.main(self._backfill_args("dry-run")))
        event = self._events()[0]
        self.assertEqual("PARTIAL", event["result"])
        self.assertEqual(2, event["metadata"]["blocking_findings"])

    def test_backfill_apply_records_one_applied_event_after_changes(self):
        analysis = self._backfill_analysis()
        backup = self.root / "private" / "db-before-backfill.sqlite3"

        def apply_side_effect(_analysis, db_path):
            backup.write_bytes(Path(db_path).read_bytes())
            Path(db_path).write_bytes(b"database-after")
            return backup

        with patch.object(backfill, "analyze_backfill", return_value=analysis), patch.object(
            backfill,
            "apply_backfill",
            side_effect=apply_side_effect,
        ):
            self.assertEqual(0, backfill.main(self._backfill_args("apply")))
        self.assertEqual(b"database-after", self.db_path.read_bytes())
        events = self._events()
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual("SOURCE_DRIVER_BACKFILL_APPLIED", event["action"])
        self.assertEqual("SUCCESS", event["result"])
        self.assertEqual("db-before-backfill.sqlite3", event["metadata"]["backup_filename"])
        self.assertEqual(2, event["metadata"]["templates_updated"])
        self.assertEqual(1, event["metadata"]["tasks_assigned"])

    def test_backfill_blocked_apply_records_one_failure_and_preserves_refusal(self):
        analysis = self._backfill_analysis(blockers=1)
        with patch.object(backfill, "analyze_backfill", return_value=analysis):
            with self.assertRaises(SystemExit) as raised:
                backfill.main(self._backfill_args("apply"))
        self.assertEqual(
            "Apply refused because blocking findings remain",
            str(raised.exception),
        )
        events = self._events()
        self.assertEqual(1, len(events))
        self.assertEqual("SOURCE_DRIVER_BACKFILL_APPLIED", events[0]["action"])
        self.assertEqual("FAILED", events[0]["result"])
        self.assertEqual("BackfillBlocked", events[0]["metadata"]["error_type"])
        self.assertFalse(events[0]["metadata"]["backup_created"])
        self.assertTrue(events[0]["metadata"]["report_created"])

    def test_backfill_report_failure_records_one_failure_without_success(self):
        analysis = self._backfill_analysis()
        original = OSError("private report path")
        with patch.object(backfill, "analyze_backfill", return_value=analysis), patch.object(
            backfill,
            "write_report",
            side_effect=original,
        ):
            with self.assertRaises(OSError) as raised:
                backfill.main(self._backfill_args("dry-run"))
        self.assertIs(original, raised.exception)
        events = self._events()
        self.assertEqual(1, len(events))
        self.assertEqual("FAILED", events[0]["result"])
        self.assertEqual("report_write", events[0]["metadata"]["failure_phase"])
        self.assertNotIn("private report path", json.dumps(events[0]))

    def test_migration_dry_run_success_is_read_only_and_aggregate_only(self):
        before = self.db_path.read_bytes()
        report = self._migration_report()
        with patch.object(
            migration,
            "migrate_legacy_final_summaries",
            return_value=report,
        ), patch.object(migration, "format_console_report", return_value="report"):
            self.assertEqual(0, migration.main(self._migration_args()))
        self.assertEqual(before, self.db_path.read_bytes())
        event = self._events()[0]
        self.assertEqual("LEGACY_WORKSPACE_MIGRATION_DRY_RUN", event["action"])
        self.assertEqual("SUCCESS", event["result"])
        self.assertFalse(event["metadata"]["backup_created"])
        serialized = json.dumps(event)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("PRIVATE-CANDIDATE", serialized)
        self.assertNotIn("PRIVATE-ID", serialized)
        self.assertNotIn("Private Driver", serialized)

    def test_migration_dry_run_blockers_are_partial(self):
        report = self._migration_report(blockers=True)
        with patch.object(
            migration,
            "migrate_legacy_final_summaries",
            return_value=report,
        ), patch.object(migration, "format_console_report", return_value="report"):
            self.assertEqual(0, migration.main(self._migration_args()))
        event = self._events()[0]
        self.assertEqual("PARTIAL", event["result"])
        self.assertEqual(1, event["metadata"]["generated_legacy_summaries"])

    def test_migration_apply_records_one_applied_event(self):
        report = self._migration_report(apply=True)
        with patch.object(
            migration,
            "migrate_legacy_final_summaries",
            return_value=report,
        ), patch.object(migration, "format_console_report", return_value="report"):
            self.assertEqual(
                0,
                migration.main(self._migration_args(apply=True, yes=True)),
            )
        events = self._events()
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual("LEGACY_WORKSPACE_MIGRATION_APPLIED", event["action"])
        self.assertEqual("SUCCESS", event["result"])
        self.assertEqual(
            "manual_dispatch_before_migration.sqlite3",
            event["metadata"]["backup_filename"],
        )
        self.assertEqual(1, event["metadata"]["delivery_run_sheets_created"])
        self.assertEqual(1, event["metadata"]["opshop_collections_created"])

    def test_migration_apply_without_yes_records_failed_and_retains_exit_two(self):
        report = self._migration_report()
        error = migration.MigrationBlockedError(
            "Apply requires both --apply and --yes.",
            report,
        )
        with patch.object(
            migration,
            "migrate_legacy_final_summaries",
            side_effect=error,
        ), patch.object(migration, "format_console_report", return_value="report"):
            self.assertEqual(2, migration.main(self._migration_args(apply=True)))
        events = self._events()
        self.assertEqual(1, len(events))
        self.assertEqual("LEGACY_WORKSPACE_MIGRATION_APPLIED", events[0]["action"])
        self.assertEqual("FAILED", events[0]["result"])
        self.assertEqual("preflight", events[0]["metadata"]["failure_phase"])
        self.assertEqual(
            "MigrationBlockedError",
            events[0]["metadata"]["error_type"],
        )

    def test_migration_transaction_failure_never_records_success(self):
        error = sqlite3.OperationalError("private SQL details")
        with patch.object(
            migration,
            "migrate_legacy_final_summaries",
            side_effect=error,
        ):
            self.assertEqual(
                2,
                migration.main(self._migration_args(apply=True, yes=True)),
            )
        events = self._events()
        self.assertEqual(1, len(events))
        self.assertEqual("FAILED", events[0]["result"])
        self.assertEqual("database_apply", events[0]["metadata"]["failure_phase"])
        self.assertNotIn("private SQL details", json.dumps(events[0]))


if __name__ == "__main__":
    unittest.main()
