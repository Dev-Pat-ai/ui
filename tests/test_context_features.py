import copy
import unittest
from scripts.prepare_context_features import build_context_features
from services.cdra_data_service import load_cdra_reference
from services.cpdd_data_service import load_psa_household_reference


class ContextFeaturesTest(unittest.TestCase):
    def test_actual_totals_and_missingness(self):
        result = build_context_features()
        self.assertEqual(result["barangay_count"], 142)
        self.assertEqual(result["summary"]["population_2020"], 2960048)
        self.assertEqual(result["summary"]["households_2020"], 738724)
        self.assertEqual(result["summary"]["flood_records_present"], 119)
        self.assertEqual(result["summary"]["flood_records_missing"], 23)
        self.assertFalse(result["is_weekly_training_dataset"])
        self.assertFalse(result["used_by_city_forecast"])
        alicia = next(r for r in result["barangays"] if r["barangay_name"] == "Alicia")
        self.assertAlmostEqual(alicia["population_density_people_per_km2_2020"], 6119 / alicia["land_area_ha_cpdd_2020"] * 100, places=5)

    def test_census_conflict_rejected(self):
        psa = copy.deepcopy(load_psa_household_reference())
        psa["barangays"][0]["population_2020"] += 1
        with self.assertRaisesRegex(ValueError, "disagreement"):
            build_context_features(psa=psa)

    def test_missing_flood_replaced_by_zero_rejected(self):
        cdra = copy.deepcopy(load_cdra_reference())
        row = next(b for d in cdra["districts"].values() for b in d["barangays"] if not b["flood_hazard"]["has_mgb_record"])
        row["flood_hazard"]["total_flooded_area_pct"] = 0
        with self.assertRaisesRegex(ValueError, "measured zero"):
            build_context_features(cdra=cdra)

    def test_missing_geographic_key_rejected(self):
        psa = copy.deepcopy(load_psa_household_reference())
        psa["barangays"].pop()
        with self.assertRaisesRegex(ValueError, "142 unique"):
            build_context_features(psa=psa)
