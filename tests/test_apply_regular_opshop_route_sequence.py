import shutil
import sqlite3
import unittest
import uuid
from pathlib import Path

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import OpShopLocation, OpShopPickupSchedule
from tools.apply_regular_opshop_route_sequence import (
    APPROVED_ALIASES,
    ROUTE_PLAN,
    apply_route_sequence,
    audit_route_sequence,
    normalize_text,
)


DRIVERS = {
    "John G": ("D003", "John G", "John Georgiadis"),
    "Gavin": ("D008", "Gavin", "Gavin Fynn"),
    "Nonda": ("D001", "Nonda", "Epaminondas Tsatsoulis"),
    "Lee": ("D002", "LEE", "Guanlin Li"),
}
POSH_SCHEDULE_IDS = [
    "OPSHOP-SCHEDULE-4719CD0EDEC92F98",
    "OPSHOP-SCHEDULE-59A6194BA7071C64",
]
ST_JAMES_SCHEDULE_ID = "OPSHOP-SCHEDULE-D73155D810582A05"


class ApplyRegularOpShopRouteSequenceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / "tmp" / f"regular-route-sequence-{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True)
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        self.repository = SQLiteManualDispatchRepository(self.db_path)
        self._seed_authoritative_route()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dry_run_resolves_65_positions_without_writing(self):
        before = self._logical_dump()

        report = audit_route_sequence(self.db_path)

        self.assertTrue(report["can_apply"])
        self.assertFalse(report["applied"])
        self.assertEqual(65, report["requested_positions"])
        self.assertEqual(59, report["strict_matches"])
        self.assertEqual(6, report["approved_alias_matches"])
        self.assertEqual(65, report["resolved_schedules"])
        self.assertEqual([], report["issues"])
        self.assertEqual([ST_JAMES_SCHEDULE_ID], report["intentionally_unconfigured"])
        self.assertEqual(before, self._logical_dump())

    def test_aliases_require_exact_schedule_identity_and_posh_is_not_deduplicated(self):
        report = audit_route_sequence(self.db_path)
        alias_mappings = [
            mapping for mapping in report["mappings"]
            if mapping["match_type"] == "APPROVED_ALIAS"
        ]
        friday_posh = [
            mapping for mapping in report["mappings"]
            if mapping["day"] == "FRIDAY"
            and mapping["driver"] == "Nonda"
            and mapping["requested_name"] == "POSH OPP SHOPPE"
        ]

        self.assertEqual(6, len(alias_mappings))
        self.assertEqual(
            {value[0] for value in APPROVED_ALIASES.values()},
            {mapping["schedule_id"] for mapping in alias_mappings},
        )
        self.assertEqual(POSH_SCHEDULE_IDS, [row["schedule_id"] for row in friday_posh])
        self.assertEqual(2, len({row["opshop_id"] for row in friday_posh}))

    def test_apply_updates_only_mapped_schedule_sequence_and_leaves_st_james_null(self):
        schedule_business_rows_before = self._schedule_business_rows()

        report = apply_route_sequence(self.db_path, yes=True)

        self.assertTrue(report["applied"])
        self.assertEqual(65, report["rows_updated"])
        self.assertEqual(schedule_business_rows_before, self._schedule_business_rows())
        with sqlite3.connect(self.db_path) as connection:
            configured = connection.execute(
                """
                SELECT COUNT(*)
                FROM opshop_pickup_schedules
                WHERE regular_route_sequence IS NOT NULL
                """
            ).fetchone()[0]
            st_james_sequence = connection.execute(
                """
                SELECT regular_route_sequence
                FROM opshop_pickup_schedules
                WHERE schedule_id = ?
                """,
                (ST_JAMES_SCHEDULE_ID,),
            ).fetchone()[0]
        self.assertEqual(65, configured)
        self.assertIsNone(st_james_sequence)

    def test_validation_failure_rolls_back_without_sequence_updates(self):
        alias_schedule_id = APPROVED_ALIASES[("MONDAY", "gavin", "rspc frankston")][0]
        with sqlite3.connect(self.db_path) as connection:
            opshop_id = connection.execute(
                "SELECT opshop_id FROM opshop_pickup_schedules WHERE schedule_id = ?",
                (alias_schedule_id,),
            ).fetchone()[0]
            connection.execute(
                "UPDATE opshop_locations SET name = 'Unexpected Replacement' WHERE opshop_id = ?",
                (opshop_id,),
            )
        before = self._logical_dump()

        with self.assertRaisesRegex(ValueError, "mapping validation failed"):
            apply_route_sequence(self.db_path, yes=True)

        self.assertEqual(before, self._logical_dump())
        with sqlite3.connect(self.db_path) as connection:
            configured = connection.execute(
                "SELECT COUNT(*) FROM opshop_pickup_schedules WHERE regular_route_sequence IS NOT NULL"
            ).fetchone()[0]
        self.assertEqual(0, configured)

    def _seed_authoritative_route(self):
        now = "2026-08-24T00:00:00+00:00"
        counter = 0
        posh_index = 0
        for day, driver_routes in ROUTE_PLAN.items():
            for driver, names in driver_routes.items():
                driver_id, driver_alias, driver_name = DRIVERS[driver]
                for requested_name in names:
                    counter += 1
                    alias_key = (day, normalize_text(driver), normalize_text(requested_name))
                    if alias_key in APPROVED_ALIASES:
                        schedule_id, actual_name = APPROVED_ALIASES[alias_key]
                    elif day == "FRIDAY" and driver == "Nonda" and requested_name == "POSH OPP SHOPPE":
                        schedule_id = POSH_SCHEDULE_IDS[posh_index]
                        actual_name = requested_name
                        posh_index += 1
                    else:
                        schedule_id = f"SCHEDULE-{counter:03d}"
                        actual_name = requested_name
                    self._add_schedule(
                        schedule_id,
                        f"OPSHOP-{counter:03d}",
                        actual_name,
                        f"SUBURB-{counter:03d}",
                        day,
                        driver_id,
                        driver_alias,
                        driver_name,
                        now,
                    )
        self._add_schedule(
            ST_JAMES_SCHEDULE_ID,
            "OPSHOP-ST-JAMES",
            "ST JAMES OP SHOP",
            "MALVERN",
            "FRIDAY",
            "D001",
            "Nonda",
            "Epaminondas Tsatsoulis",
            now,
        )

    def _add_schedule(
        self,
        schedule_id,
        opshop_id,
        name,
        suburb,
        run_day,
        driver_id,
        driver_alias,
        driver_name,
        now,
    ):
        self.repository.upsert_opshop_location(
            OpShopLocation(
                opshop_id=opshop_id,
                name=name,
                suburb=suburb,
                street_address=None,
                area_region=None,
                primary_contact=None,
                primary_phone=None,
                secondary_contact=None,
                secondary_phone=None,
                access_type=None,
                key_required=False,
                trailer_restriction=None,
                status_notes=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        self.repository.upsert_opshop_pickup_schedule(
            OpShopPickupSchedule(
                schedule_id=schedule_id,
                opshop_id=opshop_id,
                run_day=run_day,
                run_type="REGULAR",
                pickup_frequency="Weekly",
                time_window=None,
                call_before_arrival=False,
                call_timing=None,
                status="Active",
                active_flag=True,
                fortnight_group=None,
                review_required=False,
                review_reason=None,
                created_at=now,
                updated_at=now,
                default_driver_id=driver_id,
                default_driver_alias=driver_alias,
                default_driver_name_snapshot=driver_name,
                pickup_category="NORMAL",
                regular_route_sequence=None,
            )
        )

    def _logical_dump(self):
        with sqlite3.connect(self.db_path) as connection:
            return "\n".join(connection.iterdump())

    def _schedule_business_rows(self):
        with sqlite3.connect(self.db_path) as connection:
            return connection.execute(
                """
                SELECT
                    schedule_id, opshop_id, run_day, run_type, pickup_category,
                    route_group_id, pickup_frequency, time_window,
                    call_before_arrival, call_timing, status, active_flag,
                    fortnight_group, review_required, review_reason,
                    default_driver_id, default_driver_alias,
                    default_driver_name_snapshot, created_at, updated_at
                FROM opshop_pickup_schedules
                ORDER BY schedule_id
                """
            ).fetchall()


if __name__ == "__main__":
    unittest.main()
