import json
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from manual_dispatch_test_bootstrap import configure_test_environment


_TEST_ENVIRONMENT = configure_test_environment()

from backend.repositories.in_memory_manual_dispatch_repository import (
    InMemoryManualDispatchRepository,
)
from backend.repositories.sqlite_manual_dispatch_repository import (
    SQLiteManualDispatchRepository,
)
from backend.services.manual_dispatch import delivery_suburb_region_service
from backend.schemas import (
    CreateOrderRequest,
    UpdateDeliveryOrderAreaRequest,
    UpdateOrderRequest,
)
from backend.services.manual_dispatch.delivery_suburb_region_service import (
    DELIVERY_AREA_LOCAL,
    DELIVERY_AREA_SOUTHEAST,
    REGION_TO_DELIVERY_AREA,
    classify_delivery_suburb,
)
from backend.services.manual_dispatch.logbook_file_service import LogbookFileService
from backend.services.manual_dispatch_service import ManualDispatchService


class DeliverySuburbRegionServiceTest(unittest.TestCase):
    def test_regions_map_to_the_two_business_areas(self):
        examples = {
            ("Richmond", "3121"): ("EAST", DELIVERY_AREA_SOUTHEAST),
            ("Box Hill", "3128"): ("EAST", DELIVERY_AREA_SOUTHEAST),
            ("South Yarra", "3141"): ("SOUTH", DELIVERY_AREA_SOUTHEAST),
            ("Frankston", "3199"): ("SOUTH", DELIVERY_AREA_SOUTHEAST),
            ("Dandenong South", "3175"): (
                "SOUTHEAST",
                DELIVERY_AREA_SOUTHEAST,
            ),
            ("Clayton", "3168"): ("SOUTHEAST", DELIVERY_AREA_SOUTHEAST),
            ("Pakenham", "3810"): ("SOUTHEAST", DELIVERY_AREA_SOUTHEAST),
            ("Somerton", "3062"): ("NORTH", DELIVERY_AREA_LOCAL),
            ("Broadmeadows", "3047"): ("NORTH", DELIVERY_AREA_LOCAL),
            ("Preston", "3072"): ("NORTH", DELIVERY_AREA_LOCAL),
            ("Melbourne", "3000"): ("CITY", DELIVERY_AREA_LOCAL),
            ("Southbank", "3006"): ("CITY", DELIVERY_AREA_LOCAL),
            ("Footscray", "3011"): ("WEST", DELIVERY_AREA_LOCAL),
            ("Sunshine", "3020"): ("WEST", DELIVERY_AREA_LOCAL),
            ("Werribee", "3030"): ("WEST", DELIVERY_AREA_LOCAL),
            ("Altona", "3018"): ("SOUTHWEST", DELIVERY_AREA_LOCAL),
            ("Geelong", "3220"): ("SOUTHWEST", DELIVERY_AREA_LOCAL),
            ("Ballarat", "3350"): ("WEST", DELIVERY_AREA_LOCAL),
            ("Bendigo", "3550"): ("NORTH", DELIVERY_AREA_LOCAL),
            ("Bairnsdale", "3875"): ("EAST", DELIVERY_AREA_SOUTHEAST),
            ("Traralgon", "3844"): ("EAST", DELIVERY_AREA_SOUTHEAST),
            ("Wodonga", "3690"): ("NORTH", DELIVERY_AREA_LOCAL),
        }

        for (suburb, postcode), expected in examples.items():
            with self.subTest(suburb=suburb):
                actual = classify_delivery_suburb(suburb, postcode)
                self.assertTrue(actual.known)
                self.assertEqual(expected, (actual.region, actual.auto_delivery_area))

    def test_normalization_and_required_aliases_are_deterministic(self):
        examples = {
            ("  dAnDeNoNg   sTh ", "3175"): "Dandenong South",
            ("CBD", "3000"): "Melbourne",
            ("Melbourne CBD", "3000"): "Melbourne",
            ("Tulla", "3043"): "Tullamarine",
        }

        for (suburb, postcode), canonical in examples.items():
            with self.subTest(suburb=suburb):
                result = classify_delivery_suburb(suburb, postcode)
                self.assertTrue(result.known)
                self.assertEqual(canonical, result.normalized_suburb)

    def test_regional_aliases_resolve_to_mapped_canonical_suburbs(self):
        examples = {
            ("Ballarat Central", "3350"): ("WEST", DELIVERY_AREA_LOCAL),
            ("Bendigo Central", "3550"): ("NORTH", DELIVERY_AREA_LOCAL),
        }

        for (suburb, postcode), expected in examples.items():
            with self.subTest(suburb=suburb):
                result = classify_delivery_suburb(suburb, postcode)
                self.assertTrue(result.known)
                self.assertEqual(expected, (result.region, result.auto_delivery_area))

    def test_unknown_never_defaults_to_local(self):
        for suburb, postcode in (
            ("Unconfigured Test Suburb", "3999"),
            ("Date Safe", None),
        ):
            with self.subTest(suburb=suburb):
                result = classify_delivery_suburb(suburb, postcode)
                self.assertFalse(result.known)
                self.assertIsNone(result.region)
                self.assertIsNone(result.auto_delivery_area)

    def test_unique_suburb_fallback_requires_postcode_to_be_absent(self):
        without_postcode = classify_delivery_suburb("Box Hill", None)
        conflicting_postcode = classify_delivery_suburb("Box Hill", "9999")

        self.assertTrue(without_postcode.known)
        self.assertEqual("EAST", without_postcode.region)
        self.assertFalse(conflicting_postcode.known)
        self.assertIsNone(conflicting_postcode.region)
        self.assertIsNone(conflicting_postcode.auto_delivery_area)

    def test_duplicate_suburb_postcodes_require_an_exact_match(self):
        lookup = (
            {
                ("shared suburb", "3001"): "CITY",
                ("shared suburb", "3999"): "SOUTH",
            },
            {
                "shared suburb": [
                    ("3001", "CITY"),
                    ("3999", "SOUTH"),
                ],
            },
            {"shared suburb": "Shared Suburb"},
        )
        with patch(
            "backend.services.manual_dispatch.delivery_suburb_region_service._region_lookup",
            return_value=lookup,
        ):
            exact = classify_delivery_suburb("Shared Suburb", "3001")
            absent = classify_delivery_suburb("Shared Suburb", None)
            conflicting = classify_delivery_suburb("Shared Suburb", "3002")

        self.assertEqual("CITY", exact.region)
        self.assertFalse(absent.known)
        self.assertFalse(conflicting.known)

    def test_region_loader_rejects_identical_duplicate_keys(self):
        with tempfile.TemporaryDirectory(prefix="delivery-area-duplicate-") as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(
                json.dumps(
                    {
                        "records": [
                            {"suburb": "Box Hill", "postcode": "3128", "region": "EAST"},
                            {"suburb": "Box Hill", "postcode": "3128", "region": "EAST"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            delivery_suburb_region_service._region_lookup.cache_clear()
            try:
                with patch.object(
                    delivery_suburb_region_service,
                    "DELIVERY_SUBURB_REGION_DATA_PATH",
                    path,
                ):
                    with self.assertRaisesRegex(ValueError, "Duplicate"):
                        delivery_suburb_region_service._region_lookup()
            finally:
                delivery_suburb_region_service._region_lookup.cache_clear()

    def test_production_mapping_is_valid_and_covers_the_curated_inventory(self):
        repository_root = Path(__file__).resolve().parents[1]
        mapping_payload = json.loads(
            (
                repository_root
                / "backend"
                / "data"
                / "delivery_suburb_regions.json"
            ).read_text(encoding="utf-8")
        )
        inventory_payload = json.loads(
            (
                repository_root
                / "tools"
                / "data"
                / "suburb_centroids_from_somerton_curated.json"
            ).read_text(encoding="utf-8")
        )
        records = mapping_payload["records"]
        self.assertEqual(112, len(records))
        self.assertEqual(112, len({record["suburb"].casefold() for record in records}))

        exact_keys = set()
        region_counts = {region: 0 for region in REGION_TO_DELIVERY_AREA}
        for record in records:
            self.assertEqual({"suburb", "postcode", "region"}, set(record))
            self.assertIsInstance(record["suburb"], str)
            self.assertTrue(record["suburb"].strip())
            self.assertIsInstance(record["postcode"], str)
            self.assertRegex(record["postcode"], r"^\d{4}$")
            self.assertIn(record["region"], REGION_TO_DELIVERY_AREA)
            self.assertNotEqual("date safe", record["suburb"].strip().casefold())
            key = (record["suburb"].strip().casefold(), record["postcode"])
            self.assertNotIn(key, exact_keys)
            exact_keys.add(key)
            region_counts[record["region"]] += 1

        self.assertEqual(
            {
                "EAST": 19,
                "SOUTH": 7,
                "SOUTHEAST": 17,
                "NORTH": 32,
                "CITY": 10,
                "WEST": 19,
                "SOUTHWEST": 8,
            },
            region_counts,
        )
        area_counts = {DELIVERY_AREA_SOUTHEAST: 0, DELIVERY_AREA_LOCAL: 0}
        for region, count in region_counts.items():
            area_counts[REGION_TO_DELIVERY_AREA[region]] += count
        self.assertEqual(
            {DELIVERY_AREA_SOUTHEAST: 43, DELIVERY_AREA_LOCAL: 69},
            area_counts,
        )

        inventory_keys = {
            (str(record["suburb"]).strip().casefold(), str(record.get("postcode") or "").strip())
            for record in inventory_payload["records"]
            if str(record["suburb"]).strip().casefold() != "date safe"
        }
        self.assertEqual(set(), inventory_keys - exact_keys)
        self.assertEqual(
            inventory_keys | {("south yarra", "3141")},
            exact_keys,
        )


class DeliveryOrderAreaRepositoryContractTest(unittest.TestCase):
    def setUp(self):
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        self.temp_dir = temp_parent / f"delivery-area-repository-{uuid.uuid4().hex}"
        self.temp_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sqlite_and_inmemory_override_contracts_match(self):
        sqlite_path = self.temp_dir / "manual_dispatch.sqlite3"
        with patch.dict("os.environ", {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            sqlite_repository = SQLiteManualDispatchRepository(sqlite_path)

        for repository in (InMemoryManualDispatchRepository(), sqlite_repository):
            with self.subTest(repository=type(repository).__name__):
                self.assertIsNone(
                    repository.get_delivery_order_area_override("ORD-001")
                )
                self.assertEqual(
                    DELIVERY_AREA_LOCAL,
                    repository.set_delivery_order_area_override(
                        "ORD-001",
                        DELIVERY_AREA_LOCAL,
                        updated_by="Area Operator",
                    ),
                )
                self.assertEqual(
                    DELIVERY_AREA_LOCAL,
                    repository.get_delivery_order_area_override("ORD-001"),
                )
                repository.set_delivery_order_area_override(
                    "ORD-001",
                    DELIVERY_AREA_SOUTHEAST,
                    updated_by="Area Operator",
                )
                self.assertEqual(
                    DELIVERY_AREA_SOUTHEAST,
                    repository.get_delivery_order_area_override("ORD-001"),
                )
                self.assertTrue(
                    repository.clear_delivery_order_area_override("ORD-001")
                )
                self.assertIsNone(
                    repository.get_delivery_order_area_override("ORD-001")
                )
                self.assertFalse(
                    repository.clear_delivery_order_area_override("ORD-001")
                )
                with self.assertRaisesRegex(ValueError, "delivery_area"):
                    repository.set_delivery_order_area_override(
                        "ORD-001",
                        "UNKNOWN",
                    )
                with self.assertRaisesRegex(ValueError, "does not exist"):
                    repository.set_delivery_order_area_override(
                        "MISSING-ORDER",
                        DELIVERY_AREA_LOCAL,
                    )

    def test_sqlite_override_survives_reopen_and_cascades_with_order_delete(self):
        db_path = self.temp_dir / "manual_dispatch.sqlite3"
        with patch.dict("os.environ", {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            repository = SQLiteManualDispatchRepository(db_path)
        repository.set_delivery_order_area_override(
            "ORD-001",
            DELIVERY_AREA_SOUTHEAST,
            updated_by="Area Operator",
        )

        reopened = SQLiteManualDispatchRepository(db_path)
        self.assertEqual(
            DELIVERY_AREA_SOUTHEAST,
            reopened.get_delivery_order_area_override("ORD-001"),
        )
        with sqlite3.connect(db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "DELETE FROM manual_orders WHERE order_id = ?",
                ("ORD-001",),
            )
            connection.commit()
            count = connection.execute(
                "SELECT COUNT(*) FROM delivery_order_area_overrides WHERE order_id = ?",
                ("ORD-001",),
            ).fetchone()[0]
        self.assertEqual(0, count)

    def test_address_update_and_override_clear_roll_back_together(self):
        sqlite_path = self.temp_dir / "atomic.sqlite3"
        with patch.dict("os.environ", {"MANUAL_DISPATCH_SEED_DEMO_DATA": "true"}):
            sqlite_repository = SQLiteManualDispatchRepository(sqlite_path)

        repositories = (
            InMemoryManualDispatchRepository(),
            sqlite_repository,
        )
        for repository in repositories:
            with self.subTest(repository=type(repository).__name__):
                repository.set_delivery_order_area_override(
                    "ORD-001",
                    DELIVERY_AREA_LOCAL,
                    updated_by="Area Operator",
                )
                original = repository.get_order("ORD-001")
                service = ManualDispatchService(
                    repository,
                    LogbookFileService(
                        self.temp_dir / f"logbook-{type(repository).__name__}"
                    ),
                )

                with patch.object(
                    type(repository),
                    "clear_delivery_order_area_override",
                    side_effect=RuntimeError("simulated override clear failure"),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "simulated override clear failure",
                    ):
                        service.update_delivery_order(
                            "ORD-001",
                            UpdateOrderRequest(
                                suburb="Sunshine",
                                postcode="3020",
                            ),
                        )

                persisted_repository = repository
                if isinstance(repository, SQLiteManualDispatchRepository):
                    persisted_repository = SQLiteManualDispatchRepository(sqlite_path)
                persisted = persisted_repository.get_order("ORD-001")
                self.assertEqual(original.suburb, persisted.suburb)
                self.assertEqual(original.postcode, persisted.postcode)
                self.assertEqual(
                    DELIVERY_AREA_LOCAL,
                    persisted_repository.get_delivery_order_area_override("ORD-001"),
                )


class DeliveryOrderAreaServiceIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.logbook_temp_dir = tempfile.TemporaryDirectory(
            prefix="manual-dispatch-delivery-area-logbook-"
        )
        self.logbook_dir = Path(self.logbook_temp_dir.name) / "logbook"
        self.repository = InMemoryManualDispatchRepository()
        self.service = ManualDispatchService(
            self.repository,
            LogbookFileService(self.logbook_dir),
        )

    def tearDown(self):
        self.logbook_temp_dir.cleanup()

    def test_create_known_and_unknown_orders_exposes_effective_area(self):
        southeast = self.service.create_delivery_order(
            self._create_request("Dandenong South", "3175", "INV-SE")
        )
        local = self.service.create_delivery_order(
            self._create_request("Sunshine", "3020", "INV-LOCAL")
        )
        unknown = self.service.create_delivery_order(
            self._create_request("Unconfigured Test Suburb", "3999", "INV-UNKNOWN")
        )

        self.assertEqual(DELIVERY_AREA_SOUTHEAST, southeast.delivery_area)
        self.assertEqual("AUTO", southeast.delivery_area_source)
        self.assertEqual(DELIVERY_AREA_LOCAL, local.delivery_area)
        self.assertEqual("AUTO", local.delivery_area_source)
        self.assertIsNone(unknown.delivery_area)
        self.assertEqual("AUTO", unknown.delivery_area_source)
        self.assertEqual(
            ["ORDER_CREATED", "ORDER_CREATED", "ORDER_CREATED"],
            [entry["action"] for entry in self._logbook_entries()],
        )

    def test_edit_location_clears_override_but_unrelated_edit_preserves_it(self):
        self.repository.set_delivery_order_area_override(
            "ORD-001",
            DELIVERY_AREA_LOCAL,
            updated_by="Area Operator",
        )

        note_only = self.service.update_delivery_order(
            "ORD-001",
            UpdateOrderRequest(note="Keep the manual area"),
        )
        self.assertEqual(DELIVERY_AREA_LOCAL, note_only.delivery_area_override)

        location_change = self.service.update_delivery_order(
            "ORD-001",
            UpdateOrderRequest(suburb="Sunshine", postcode="3020"),
        )
        self.assertIsNone(location_change.delivery_area_override)
        self.assertEqual(DELIVERY_AREA_LOCAL, location_change.delivery_area)
        self.assertEqual("AUTO", location_change.delivery_area_source)
        entries = self._logbook_entries()
        self.assertEqual(
            [
                "ORDER_UPDATED",
                "ORDER_UPDATED",
                "ORDER_DELIVERY_AREA_OVERRIDE_CLEARED",
            ],
            [entry["action"] for entry in entries],
        )
        clear_entry = entries[-1]
        self.assertEqual(DELIVERY_AREA_LOCAL, clear_entry["metadata"]["previous_override_area"])
        self.assertIsNone(clear_entry["metadata"]["new_override_area"])
        self.assertEqual(DELIVERY_AREA_LOCAL, clear_entry["metadata"]["new_effective_area"])
        self.assertEqual("Sunshine", clear_entry["metadata"]["suburb"])
        self.assertEqual("3020", clear_entry["metadata"]["postcode"])

    def test_area_override_audit_writes_only_to_temporary_logbook(self):
        with self.service.logbook_actor("Area Operator"):
            updated = self.service.update_delivery_order_area(
                "ORD-001",
                UpdateDeliveryOrderAreaRequest(delivery_area=DELIVERY_AREA_LOCAL),
            )

        self.assertEqual(DELIVERY_AREA_LOCAL, updated.delivery_area_override)
        entries = self._logbook_entries()
        self.assertEqual(1, len(entries))
        self.assertEqual("ORDER_DELIVERY_AREA_OVERRIDDEN", entries[0]["action"])
        self.assertEqual("Area Operator", entries[0]["actor"])
        self.assertEqual("ORD-001", entries[0]["metadata"]["order_id"])

    def test_add_unknown_order_can_persist_an_explicit_manual_area(self):
        request = self._create_request(
            "Unconfigured Test Suburb",
            "3999",
            "INV-MANUAL-AREA",
        )
        request.delivery_area = DELIVERY_AREA_LOCAL

        with self.service.logbook_actor("Area Operator"):
            created = self.service.create_delivery_order(request)

        self.assertIsNone(created.auto_delivery_area)
        self.assertEqual(DELIVERY_AREA_LOCAL, created.delivery_area_override)
        self.assertEqual(DELIVERY_AREA_LOCAL, created.delivery_area)
        self.assertEqual("MANUAL", created.delivery_area_source)
        entries = self._logbook_entries()
        self.assertEqual(
            ["ORDER_CREATED", "ORDER_DELIVERY_AREA_OVERRIDDEN"],
            [entry["action"] for entry in entries],
        )
        self.assertEqual("Area Operator", entries[-1]["actor"])

    def test_area_noops_do_not_persist_override_or_write_audit(self):
        automatic = self.service.update_delivery_order_area(
            "ORD-001",
            UpdateDeliveryOrderAreaRequest(
                delivery_area=DELIVERY_AREA_SOUTHEAST,
            ),
        )
        self.assertIsNone(automatic.delivery_area_override)
        self.assertEqual([], list(self.logbook_dir.glob("manual_dispatch_logbook_*.txt")))

        self.service.update_delivery_order_area(
            "ORD-001",
            UpdateDeliveryOrderAreaRequest(delivery_area=DELIVERY_AREA_LOCAL),
        )
        self.service.update_delivery_order_area(
            "ORD-001",
            UpdateDeliveryOrderAreaRequest(delivery_area=DELIVERY_AREA_LOCAL),
        )
        self.service.update_delivery_order_area(
            "ORD-001",
            UpdateDeliveryOrderAreaRequest(delivery_area=None),
        )
        automatic_again = self.service.update_delivery_order_area(
            "ORD-001",
            UpdateDeliveryOrderAreaRequest(delivery_area=None),
        )

        self.assertIsNone(automatic_again.delivery_area_override)
        self.assertEqual(DELIVERY_AREA_SOUTHEAST, automatic_again.delivery_area)
        self.assertEqual(
            [
                "ORDER_DELIVERY_AREA_OVERRIDDEN",
                "ORDER_DELIVERY_AREA_OVERRIDE_CLEARED",
            ],
            [entry["action"] for entry in self._logbook_entries()],
        )

    def _logbook_entries(self):
        paths = list(self.logbook_dir.glob("manual_dispatch_logbook_*.txt"))
        self.assertEqual(1, len(paths))
        return [
            json.loads(line)
            for line in paths[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _create_request(suburb, postcode, invoice_number):
        return CreateOrderRequest(
            invoice_number=invoice_number,
            company_name="Area Customer",
            delivery_address="1 Area Road",
            suburb=suburb,
            postcode=postcode,
            delivery_date="2026-08-20",
            zone="Existing Zone Value",
        )


if __name__ == "__main__":
    unittest.main()
