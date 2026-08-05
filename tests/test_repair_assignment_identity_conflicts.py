import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from backend.db.connection import initialize_database
from backend.db.invariants import audit_database_invariants
from tools.check_logbook_integrity import check_logbook_integrity
from tools.migrate_database_invariants import migrate_database_invariants
from tools.repair_assignment_identity_conflicts import (
    AssignmentRepairBlockedError,
    apply_assignment_identity_repair,
    inspect_assignment_identity_conflicts,
    load_repair_plan,
    main,
    write_repair_plan,
)


class AssignmentIdentityRepairTest(unittest.TestCase):
    CREATED_AT = "2026-08-06T10:00:00+10:00"
    REPAIR_TIMESTAMP = "2026-08-06T10:05:00+10:00"

    def setUp(self):
        self.root = Path.cwd() / "tmp" / f"assignment-repair-{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=False)
        self.db_path = self.root / "manual_dispatch.sqlite3"
        self.backup_dir = self.root / "backups"
        self.logbook_dir = self.root / "logbook"
        self.plan_path = self.root / "assignment-repair-plan.json"
        with patch.dict(os.environ, {"MANUAL_DISPATCH_SEED_DEMO_DATA": "false"}):
            initialize_database(self.db_path)
        with self._connection() as connection:
            connection.execute("DROP INDEX idx_manual_dispatch_assignments_task_identity")
            connection.executemany(
                """
                INSERT INTO manual_drivers (driver_id, name)
                VALUES (?, ?)
                """,
                (("DRIVER-1", "Driver One"), ("DRIVER-2", "Driver Two")),
            )
            connection.execute(
                """
                INSERT INTO opshop_locations (
                    opshop_id, name, created_at, updated_at
                ) VALUES ('SHOP-1', 'Repair Test Shop', ?, ?)
                """,
                (self.CREATED_AT, self.CREATED_AT),
            )

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_dry_run_is_read_only_and_emits_hashed_plan(self):
        self._seed_assigned_group("TASK-DRY")
        before_sha = self._file_sha256(self.db_path)
        before_count = self._count_assignments()

        plan = self._inspect()
        _, file_sha = write_repair_plan(plan, self.plan_path)

        self.assertEqual(before_sha, self._file_sha256(self.db_path))
        self.assertEqual(before_count, self._count_assignments())
        self.assertEqual(1, plan["duplicate_group_count"])
        self.assertEqual(2, plan["rows_in_duplicate_groups"])
        self.assertEqual(1, plan["expected_rows_deleted"])
        self.assertEqual(0, plan["blocked_groups"])
        self.assertEqual(64, len(plan["database_sha256"]))
        self.assertEqual(64, len(plan["database_logical_sha256"]))
        self.assertEqual(64, len(plan["assignment_table_logical_sha256"]))
        self.assertEqual(64, len(plan["plan_payload_sha256"]))
        self.assertEqual(64, len(file_sha))
        loaded, loaded_sha = load_repair_plan(self.plan_path)
        self.assertEqual(plan, loaded)
        self.assertEqual(file_sha, loaded_sha)

    def test_exact_state_merge_preserves_canonical_origin_and_merges_times(self):
        self._insert_task("TASK-EXACT", driver_id="DRIVER-1", trip_no="trip1")
        self._insert_assignment(
            "ASSIGN-EARLY",
            "TASK-EXACT",
            "2026-01-01",
            driver_id="DRIVER-1",
            trip_no="trip1",
            assigned_at="2026-01-03T09:00:00+11:00",
            updated_at="2026-01-03T10:00:00+11:00",
        )
        self._insert_assignment(
            "ASSIGN-LATE",
            "TASK-EXACT",
            "2026-01-02",
            driver_id="DRIVER-1",
            trip_no="trip1",
            assigned_at="2026-01-02T08:00:00+11:00",
            updated_at="2026-01-04T10:00:00+11:00",
        )

        plan, report = self._plan_and_apply()
        row = self._assignments_for("TASK-EXACT")[0]

        self.assertEqual("ASSIGN-EARLY", row["assignment_id"])
        self.assertEqual("2026-01-01", row["dispatch_date"])
        self.assertEqual("2026-01-02T08:00:00+11:00", row["assigned_at"])
        self.assertEqual("2026-01-04T10:00:00+11:00", row["updated_at"])
        self.assertEqual(1, report["rows_deleted"])
        self.assertEqual(1, report["rows_updated"])
        self.assertEqual(0, report["rows_inserted"])
        self.assertFalse(plan["groups"][0]["driver_trip_normalization_required"])

    def test_current_task_state_overrides_driver_and_trip_at_repair_time(self):
        self._insert_task("TASK-OVERRIDE", driver_id="DRIVER-1", trip_no="trip1")
        self._insert_assignment(
            "ASSIGN-OVERRIDE-1",
            "TASK-OVERRIDE",
            "2026-01-01",
            driver_id="DRIVER-2",
            trip_no="trip2",
            assigned_at="2026-01-01T08:00:00+11:00",
            updated_at="2026-01-01T09:00:00+11:00",
        )
        self._insert_assignment(
            "ASSIGN-OVERRIDE-2",
            "TASK-OVERRIDE",
            "2026-01-03",
            driver_id="DRIVER-2",
            trip_no="trip2",
            assigned_at="2026-01-03T08:00:00+11:00",
            updated_at="2026-01-03T09:00:00+11:00",
        )

        plan, report = self._plan_and_apply()
        row = self._assignments_for("TASK-OVERRIDE")[0]

        self.assertEqual("ASSIGN-OVERRIDE-1", row["assignment_id"])
        self.assertEqual("2026-01-01", row["dispatch_date"])
        self.assertEqual("DRIVER-1", row["driver_id"])
        self.assertEqual("trip1", row["trip_no"])
        self.assertEqual(self.REPAIR_TIMESTAMP, row["updated_at"])
        self.assertTrue(plan["groups"][0]["driver_trip_normalization_required"])
        self.assertEqual(1, report["rows_updated"])

    def test_active_cancelled_and_completed_tasks_remove_all_assignments_only(self):
        before_tasks = {}
        for index, status in enumerate(("ACTIVE", "CANCELLED", "COMPLETED"), start=1):
            task_id = f"TASK-{status}"
            self._insert_task(
                task_id,
                status=status,
                dispatch_date=f"2026-02-0{index}",
                driver_id=None,
                trip_no=None,
            )
            self._insert_assignment(f"{task_id}-A", task_id, "2026-01-01")
            self._insert_assignment(f"{task_id}-B", task_id, "2026-01-02")
            before_tasks[task_id] = self._task(task_id)

        plan, report = self._plan_and_apply()

        self.assertEqual(3, plan["non_assigned_groups"])
        self.assertEqual(6, report["rows_deleted"])
        self.assertEqual(0, report["rows_updated"])
        for task_id, before in before_tasks.items():
            self.assertEqual([], self._assignments_for(task_id))
            self.assertEqual(before, self._task(task_id))

    def test_missing_task_fails_closed(self):
        self._insert_assignment("MISSING-A", "TASK-MISSING", "2026-01-01")
        self._insert_assignment("MISSING-B", "TASK-MISSING", "2026-01-02")

        plan = self._inspect()

        self.assertEqual(1, plan["blocked_groups"])
        self.assertEqual("MISSING_OR_DUPLICATE_TASK", plan["groups"][0]["blocked_category"])

    def test_incomplete_assigned_tasks_fail_closed(self):
        cases = (
            ("MISSING-DRIVER", None, "trip1", "2026-02-01"),
            ("MISSING-TRIP", "DRIVER-1", None, "2026-02-01"),
            ("INVALID-TRIP", "DRIVER-1", "trip3", "2026-02-01"),
            ("MISSING-DATE", "DRIVER-1", "trip1", None),
            ("INVALID-DATE", "DRIVER-1", "trip1", "not-a-date"),
        )
        for task_id, driver_id, trip_no, dispatch_date in cases:
            self._insert_task(
                task_id,
                driver_id=driver_id,
                trip_no=trip_no,
                dispatch_date=dispatch_date,
                ignore_checks=trip_no == "trip3",
            )
            self._insert_assignment(f"{task_id}-A", task_id, "2026-01-01")
            self._insert_assignment(f"{task_id}-B", task_id, "2026-01-02")

        plan = self._inspect()

        self.assertEqual(5, plan["blocked_groups"])
        self.assertEqual(
            {
                "ASSIGNED_TASK_MISSING_DRIVER",
                "ASSIGNED_TASK_INVALID_TRIP",
                "ASSIGNED_TASK_INVALID_DISPATCH_DATE",
            },
            {group["blocked_category"] for group in plan["groups"]},
        )

    def test_missing_driver_row_fails_closed(self):
        self._insert_task(
            "TASK-UNKNOWN-DRIVER",
            driver_id="DRIVER-NOT-FOUND",
            trip_no="trip1",
            foreign_keys=False,
        )
        self._insert_assignment("UNKNOWN-A", "TASK-UNKNOWN-DRIVER", "2026-01-01")
        self._insert_assignment("UNKNOWN-B", "TASK-UNKNOWN-DRIVER", "2026-01-02")

        plan = self._inspect()

        self.assertEqual(1, plan["foreign_key_violation_count"])
        self.assertEqual(1, plan["global_blocker_count"])
        self.assertEqual(1, plan["blocked_groups"])

    def test_invalid_assignment_date_fails_closed(self):
        self._insert_task("TASK-BAD-DATE")
        self._insert_assignment("BAD-DATE-A", "TASK-BAD-DATE", "not-a-date")
        self._insert_assignment("BAD-DATE-B", "TASK-BAD-DATE", "2026-01-02")

        plan = self._inspect()

        self.assertEqual(1, plan["blocked_groups"])
        self.assertEqual(
            "INVALID_ASSIGNMENT_DISPATCH_DATE",
            plan["groups"][0]["blocked_category"],
        )

    def test_invalid_assigned_and_updated_timestamps_fail_closed(self):
        self._insert_task("TASK-BAD-ASSIGNED")
        self._insert_assignment(
            "BAD-ASSIGNED-A",
            "TASK-BAD-ASSIGNED",
            "2026-01-01",
            assigned_at="not-a-timestamp",
        )
        self._insert_assignment("BAD-ASSIGNED-B", "TASK-BAD-ASSIGNED", "2026-01-02")
        self._insert_task("TASK-BAD-UPDATED")
        self._insert_assignment(
            "BAD-UPDATED-A",
            "TASK-BAD-UPDATED",
            "2026-01-01",
            updated_at="not-a-timestamp",
        )
        self._insert_assignment("BAD-UPDATED-B", "TASK-BAD-UPDATED", "2026-01-02")

        plan = self._inspect()

        self.assertEqual(2, plan["blocked_groups"])
        self.assertEqual(
            {"INVALID_ASSIGNMENT_ASSIGNED_AT", "INVALID_ASSIGNMENT_UPDATED_AT"},
            {group["blocked_category"] for group in plan["groups"]},
        )

    def test_external_assignment_id_reference_fails_closed(self):
        self._seed_assigned_group("TASK-EXTERNAL-REF")
        with self._connection() as connection:
            connection.execute(
                "CREATE TABLE repair_reference (id TEXT PRIMARY KEY, assignment_id TEXT)"
            )

        plan = self._inspect()

        self.assertEqual(1, plan["assignment_external_reference_count"])
        self.assertEqual(1, plan["global_blocker_count"])
        self.assertEqual(1, plan["blocked_groups"])

    def test_stale_plan_refuses_without_partial_write_or_backup(self):
        self._seed_assigned_group("TASK-STALE")
        plan = self._inspect()
        write_repair_plan(plan, self.plan_path)
        with self._connection() as connection:
            connection.execute(
                "UPDATE manual_dispatch_assignments SET updated_at = ? WHERE assignment_id = ?",
                ("2026-01-09T00:00:00+11:00", "TASK-STALE-A"),
            )
        before = self._assignments_for("TASK-STALE")

        with self.assertRaisesRegex(
            AssignmentRepairBlockedError,
            "no longer matches",
        ):
            self._apply()

        self.assertEqual(before, self._assignments_for("TASK-STALE"))
        self.assertFalse(self.backup_dir.exists())

    def test_tampered_plan_hash_is_rejected(self):
        self._seed_assigned_group("TASK-TAMPER")
        plan = self._inspect()
        write_repair_plan(plan, self.plan_path)
        tampered = json.loads(self.plan_path.read_text(encoding="utf-8"))
        tampered["expected_rows_deleted"] = 99
        self.plan_path.write_text(json.dumps(tampered), encoding="utf-8")

        with self.assertRaisesRegex(AssignmentRepairBlockedError, "payload SHA-256"):
            self._apply()

        self.assertEqual(2, self._count_assignments())

    def test_apply_requires_all_confirmation_inputs(self):
        self._seed_assigned_group("TASK-CONFIRM")
        write_repair_plan(self._inspect(), self.plan_path)
        commands = (
            ["--db-path", str(self.db_path), "--apply", "--yes"],
            ["--db-path", str(self.db_path), "--apply", "--decision-file", str(self.plan_path)],
            ["--db-path", str(self.db_path), "--yes", "--decision-file", str(self.plan_path)],
        )
        for command in commands:
            with self.subTest(command=command), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(2, main(command))
        self.assertEqual(2, self._count_assignments())
        self.assertFalse(self.backup_dir.exists())

    def test_apply_creates_verified_sqlite_backup_before_writes(self):
        self._seed_assigned_group("TASK-BACKUP")

        _, report = self._plan_and_apply()
        backup_path = Path(report["backup_path"])

        self.assertTrue(backup_path.is_file())
        with self._connection(backup_path) as connection:
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
            self.assertEqual(0, len(connection.execute("PRAGMA foreign_key_check").fetchall()))
            self.assertEqual(2, connection.execute(
                "SELECT COUNT(*) FROM manual_dispatch_assignments"
            ).fetchone()[0])
        self.assertEqual(1, self._count_assignments())

    def test_mid_transaction_failure_rolls_back_all_assignment_changes(self):
        self._seed_assigned_group("TASK-ROLLBACK-1")
        self._seed_assigned_group("TASK-ROLLBACK-2")
        write_repair_plan(self._inspect(), self.plan_path)
        before = self._all_assignments()

        with patch(
            "tools.repair_assignment_identity_conflicts._after_group_applied",
            side_effect=RuntimeError("simulated repair interruption"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated repair interruption"):
                self._apply()

        self.assertEqual(before, self._all_assignments())
        self.assertEqual(1, len(list(self.backup_dir.glob("*.sqlite3"))))

    def test_idempotent_apply_records_one_isolated_valid_logbook_event(self):
        task_id = "TASK-PRIVATE-IDEMPOTENT"
        self._seed_assigned_group(task_id)
        write_repair_plan(self._inspect(), self.plan_path)
        command = [
            "--db-path",
            str(self.db_path),
            "--decision-file",
            str(self.plan_path),
            "--backup-dir",
            str(self.backup_dir),
            "--logbook-dir",
            str(self.logbook_dir),
            "--actor",
            "Repair Test Operator",
            "--apply",
            "--yes",
        ]

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(0, main(command))
            self.assertEqual(0, main(command))

        post_plan = self._inspect()
        self.assertEqual(0, post_plan["duplicate_group_count"])
        events = self._logbook_events()
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual("ASSIGNMENT_IDENTITY_REPAIR_COMPLETED", event["action"])
        self.assertEqual("SUCCESS", event["result"])
        self.assertEqual("SYSTEM", event["workspace"])
        self.assertEqual("DATABASE_INVARIANT_REPAIR", event["entity_type"])
        self.assertEqual(
            {
                "mode",
                "database_filename",
                "backup_filename",
                "duplicate_groups_repaired",
                "assigned_groups_merged",
                "non_active_groups_cleared",
                "rows_deleted",
                "rows_updated",
                "repair_plan_sha256",
                "integrity_check",
                "foreign_key_violation_count",
            },
            set(event["metadata"]),
        )
        serialized = json.dumps(event)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn(task_id, serialized)
        self.assertTrue(check_logbook_integrity(self.logbook_dir).ok)

    def test_repair_removes_h5_assignment_conflicts_and_allows_h5_apply(self):
        self._seed_assigned_group("TASK-H5")
        self._plan_and_apply()

        with self._connection() as connection:
            audit = audit_database_invariants(connection)
        assignment_conflicts = [
            item
            for item in audit["conflicts"]
            if item["invariant"] == "idx_manual_dispatch_assignments_task_identity"
        ]
        self.assertEqual([], assignment_conflicts)

        report = migrate_database_invariants(
            self.db_path,
            apply=True,
            yes=True,
            backup_dir=self.backup_dir,
        )
        self.assertEqual([], report["conflicts"])
        self.assertEqual([], report["missing_indexes"])
        self.assertEqual("ok", report["integrity_after"])

    def test_console_report_is_aggregate_only(self):
        task_id = "TASK-MUST-NOT-BE-PRINTED"
        self._seed_assigned_group(task_id)
        output = io.StringIO()

        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            exit_code = main(
                [
                    "--db-path",
                    str(self.db_path),
                    "--plan-out",
                    str(self.plan_path),
                ]
            )

        self.assertEqual(0, exit_code)
        self.assertNotIn(task_id, output.getvalue())
        self.assertIn("Duplicate groups: 1", output.getvalue())

    def _inspect(self):
        return inspect_assignment_identity_conflicts(
            self.db_path,
            created_at=self.CREATED_AT,
            repair_timestamp=self.REPAIR_TIMESTAMP,
            git_head="test-head",
        )

    def _apply(self):
        return apply_assignment_identity_repair(
            self.db_path,
            decision_file=self.plan_path,
            apply=True,
            yes=True,
            backup_dir=self.backup_dir,
        )

    def _plan_and_apply(self):
        plan = self._inspect()
        write_repair_plan(plan, self.plan_path)
        return plan, self._apply()

    def _seed_assigned_group(self, task_id):
        self._insert_task(task_id)
        self._insert_assignment(f"{task_id}-A", task_id, "2026-01-01")
        self._insert_assignment(f"{task_id}-B", task_id, "2026-01-02")

    def _insert_task(
        self,
        task_id,
        *,
        status="ASSIGNED",
        dispatch_date="2026-02-01",
        driver_id="DRIVER-1",
        trip_no="trip1",
        ignore_checks=False,
        foreign_keys=True,
    ):
        with self._connection(foreign_keys=foreign_keys) as connection:
            if ignore_checks:
                connection.execute("PRAGMA ignore_check_constraints = ON")
            connection.execute(
                """
                INSERT INTO opshop_pickup_tasks (
                    pickup_task_id, schedule_id, opshop_id, pickup_date,
                    task_type, generated_from, status, dispatch_date,
                    driver_id, trip_no, notes, created_at, updated_at
                ) VALUES (?, NULL, 'SHOP-1', '2026-02-01', 'OPSHOP_PICKUP',
                          'MANUAL', ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    task_id,
                    status,
                    dispatch_date,
                    driver_id,
                    trip_no,
                    self.CREATED_AT,
                    self.CREATED_AT,
                ),
            )

    def _insert_assignment(
        self,
        assignment_id,
        task_id,
        dispatch_date,
        *,
        driver_id="DRIVER-1",
        trip_no="trip1",
        assigned_at="2026-01-01T08:00:00+11:00",
        updated_at="2026-01-01T09:00:00+11:00",
    ):
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO manual_dispatch_assignments (
                    assignment_id, dispatch_date, task_type, task_id,
                    driver_id, trip_no, assigned_at, updated_at
                ) VALUES (?, ?, 'OPSHOP_PICKUP', ?, ?, ?, ?, ?)
                """,
                (
                    assignment_id,
                    dispatch_date,
                    task_id,
                    driver_id,
                    trip_no,
                    assigned_at,
                    updated_at,
                ),
            )

    def _task(self, task_id):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM opshop_pickup_tasks WHERE pickup_task_id = ?",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def _assignments_for(self, task_id):
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM manual_dispatch_assignments
                WHERE task_type = 'OPSHOP_PICKUP' AND task_id = ?
                ORDER BY assignment_id
                """,
                (task_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _all_assignments(self):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM manual_dispatch_assignments ORDER BY assignment_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def _count_assignments(self):
        with self._connection() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM manual_dispatch_assignments"
            ).fetchone()[0]

    def _logbook_events(self):
        events = []
        for path in sorted(self.logbook_dir.glob("manual_dispatch_logbook_*.txt")):
            events.extend(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        return events

    @staticmethod
    def _file_sha256(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @contextlib.contextmanager
    def _connection(self, path=None, *, foreign_keys=True):
        with contextlib.closing(sqlite3.connect(path or self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute(
                f"PRAGMA foreign_keys = {'ON' if foreign_keys else 'OFF'}"
            )
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise


if __name__ == "__main__":
    unittest.main()
