from copy import deepcopy
import unittest

from backend.services.manual_dispatch.suburb_distance_service import (
    get_estimated_distance_km,
)
from tools.qa_suburb_distances_from_somerton import load_dataset, validate_dataset


class ManualDispatchSuburbDistanceDatasetQaTest(unittest.TestCase):
    def test_dataset_qa_checks_pass_for_committed_static_table(self):
        result = validate_dataset()
        self.assertEqual(112, result["records"])
        self.assertGreater(result["known_suburbs"], 0)
        self.assertGreater(result["known_aliases"], 0)

    def test_exact_alias_and_unknown_lookup_contracts_remain_stable(self):
        self.assertIsNotNone(get_estimated_distance_km("Dandenong South"))
        self.assertEqual(
            get_estimated_distance_km("Dandenong South"),
            get_estimated_distance_km("Dandenong Sth"),
        )
        self.assertIsNone(get_estimated_distance_km("Unmapped QA Ridge"))

    def test_duplicate_normalized_suburb_is_rejected(self):
        duplicate_dataset = deepcopy(load_dataset())
        duplicate_row = deepcopy(duplicate_dataset["records"][0])
        duplicate_row["suburb"] = f"  {duplicate_row['suburb'].upper()}  "
        duplicate_dataset["records"].append(duplicate_row)

        with self.assertRaisesRegex(ValueError, "duplicate normalized suburbs"):
            validate_dataset(duplicate_dataset)


if __name__ == "__main__":
    unittest.main()
