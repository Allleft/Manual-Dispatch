import shutil
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.schemas import (
    CreateOpShopCountrysideRouteGroupRequest,
    CreateOpShopTemplateRequest,
)
from backend.services.manual_dispatch_service import ManualDispatchService
from tools.import_countryside_opshop_pickups_to_db import (
    REQUIRED_COLUMNS,
    WORKBOOK_IMPORT_COUNTRYSIDE,
    import_countryside_opshop_pickups_to_db,
)


class CountrysideOpShopImporterTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="countryside-import-test-"))
        self.db_path = self.temp_dir / "manual_dispatch.sqlite3"
        SQLiteManualDispatchRepository(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_import_creates_route_groups_countryside_schedules_and_no_tasks(self):
        workbook_path = self._write_workbook(
            {
                "North Route": [
                    self._row(
                        "Shared Country Shop",
                        "Countryville",
                        "1 High Street",
                        assigned_to="",
                        status_start_date=45076,
                    )
                ],
                "South Route": [
                    self._row(
                        "Shared Country Shop",
                        "Countryville",
                        "1 High Street",
                        assigned_to="Mystery Driver",
                    )
                ],
            }
        )

        summary = import_countryside_opshop_pickups_to_db(workbook_path, self.db_path)
        repository = SQLiteManualDispatchRepository(self.db_path)
        groups = repository.list_countryside_route_groups()
        schedules = repository.list_opshop_pickup_schedules()
        locations = repository.list_opshop_locations()

        self.assertEqual(2, summary.sheets_read)
        self.assertEqual(2, summary.rows_imported)
        self.assertEqual(2, len(groups))
        self.assertEqual(1, len(locations))
        self.assertEqual(2, len(schedules))
        self.assertEqual([], repository.list_opshop_pickup_tasks())
        self.assertEqual(1, summary.duplicate_locations_reused)
        self.assertEqual({"Mystery Driver": 1}, summary.unresolved_assigned_to)
        self.assertEqual({"ON_CALL"}, {schedule.run_type for schedule in schedules})
        self.assertEqual(
            {"COUNTRYSIDE"},
            {schedule.pickup_category for schedule in schedules},
        )
        self.assertEqual(
            2,
            len({schedule.route_group_id for schedule in schedules}),
        )
        self.assertIn("Status start date: 2023-", locations[0].status_notes)
        self.assertNotIn("45076", locations[0].status_notes)

    def test_rerun_soft_disables_only_missing_workbook_backed_rows(self):
        first = self._write_workbook(
            {
                "North Route": [self._row("North Shop", "North", "1 A Street")],
                "South Route": [self._row("South Shop", "South", "2 B Street")],
            },
            name="first.xlsx",
        )
        import_countryside_opshop_pickups_to_db(first, self.db_path)

        repository = SQLiteManualDispatchRepository(self.db_path)
        service = ManualDispatchService(repository)
        ui_group = service.create_countryside_route_group(
            CreateOpShopCountrysideRouteGroupRequest(route_group_name="UI Managed")
        )
        ui_template = service.create_opshop_template(
            CreateOpShopTemplateRequest(
                run_type="ON_CALL",
                pickup_category="COUNTRYSIDE",
                route_group_id=ui_group.route_group_id,
                name="UI Shop",
                suburb="Office",
                street_address="3 C Street",
                pickup_frequency="On Call",
            )
        )

        second = self._write_workbook(
            {"North Route": [self._row("North Shop", "North", "1 A Street")]},
            name="second.xlsx",
        )
        summary = import_countryside_opshop_pickups_to_db(second, self.db_path)
        repository = SQLiteManualDispatchRepository(self.db_path)
        inactive_groups = repository.list_countryside_route_groups(include_inactive=True)
        inactive_schedules = repository.list_opshop_pickup_schedules()

        self.assertEqual(1, summary.route_groups_deactivated)
        self.assertEqual(1, summary.schedules_deactivated)
        self.assertTrue(repository.get_countryside_route_group(ui_group.route_group_id).active_flag)
        self.assertTrue(repository.get_opshop_pickup_schedule(ui_template.schedule_id).active_flag)
        self.assertEqual(
            ["North Route", "UI Managed"],
            sorted(group.route_group_name for group in repository.list_countryside_route_groups()),
        )
        self.assertIn(
            "South Route",
            [group.route_group_name for group in inactive_groups if not group.active_flag],
        )
        self.assertEqual(
            1,
            len(
                [
                    schedule
                    for schedule in inactive_schedules
                    if schedule.review_reason == WORKBOOK_IMPORT_COUNTRYSIDE
                    and not schedule.active_flag
                ]
            ),
        )

    def test_import_creates_backup_when_target_db_exists(self):
        workbook_path = self._write_workbook(
            {"North Route": [self._row("Backup Shop", "North", "1 Backup Street")]}
        )

        summary = import_countryside_opshop_pickups_to_db(workbook_path, self.db_path)

        self.assertIsNotNone(summary.backup_path)
        self.assertTrue(Path(summary.backup_path).exists())

    def _write_workbook(self, sheets, name="countryside.xlsx"):
        path = self.temp_dir / name
        workbook = Workbook()
        default_sheet = workbook.active
        workbook.remove(default_sheet)
        for sheet_name, rows in sheets.items():
            worksheet = workbook.create_sheet(sheet_name)
            worksheet.append(REQUIRED_COLUMNS)
            for row in rows:
                worksheet.append([row.get(column, "") for column in REQUIRED_COLUMNS])
        workbook.save(path)
        return path

    def _row(
        self,
        name,
        suburb,
        street_address,
        assigned_to="",
        status_start_date="",
    ):
        return {
            "Op_Shop_Name": name,
            "Run_Day": "",
            "Run_Type": "On_Call",
            "Active_Flag": "1",
            "Suburb": suburb,
            "Street_Address": street_address,
            "Area_Region": "Country",
            "Primary_Contact": "Shop",
            "Primary_Phone": "0400 000 000",
            "Secondary_Contact": "",
            "Secondary_Phone": "",
            "Pickup_Frequency": "On Call",
            "Time_Window": "MON-FRI",
            "Call_Before_Arrival": "No",
            "Call_Timing": "",
            "Access_Type": "Rear access",
            "Key_Required": "No",
            "Trailer_Restriction": "No",
            "Status": "Active",
            "Status_Start_Date": status_start_date,
            "Status_Notes": "Long notes are preserved for the driver.",
            "Assigned to": assigned_to,
        }


if __name__ == "__main__":
    unittest.main()
