import sys
import unittest
from pathlib import Path

from flask import Flask


project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.routes.prototype_routes import prototype_bp
from backend.routes.reference_routes import reference_bp
from backend.services.cpdd_data_service import (
    load_cpdd_barangays,
    load_cpdd_district_detail,
    load_cpdd_reference,
)
from backend.services.data_readiness_service import DataReadinessService


class CpddReferenceTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(reference_bp)
        self.app.register_blueprint(prototype_bp)
        self.client = self.app.test_client()

    def test_city_and_district_totals(self):
        data = load_cpdd_reference()
        self.assertTrue(data["is_authoritative_reference"])
        self.assertEqual(data["reference_year"], 2020)
        self.assertEqual(data["city_summary"]["district_count"], 6)
        self.assertEqual(data["city_summary"]["barangay_count"], 142)
        self.assertEqual(data["city_summary"]["population_2020"], 2_960_048)

        expected = {
            "I": (37, 384_384, 19.59, 196),
            "II": (5, 738_328, 21.82, 338),
            "III": (37, 319_371, 21.85, 146),
            "IV": (38, 407_402, 23.42, 174),
            "V": (14, 596_047, 52.47, 114),
            "VI": (11, 514_516, 21.97, 234),
        }
        for district_id, values in expected.items():
            district = data["districts"][district_id]
            self.assertEqual(district["barangay_count"], values[0])
            self.assertEqual(district["population_2020"], values[1])
            self.assertEqual(district["land_area_sq_km"], values[2])
            self.assertEqual(district["population_density_per_ha"], values[3])

    def test_all_barangays_are_unique_and_filterable(self):
        all_barangays = load_cpdd_barangays()["barangays"]
        self.assertEqual(len(all_barangays), 142)
        self.assertEqual(len({row["barangay_name"].casefold() for row in all_barangays}), 142)

        district_two = load_cpdd_barangays("ii")
        self.assertEqual(district_two["district_filter"], "II")
        self.assertEqual(district_two["barangay_count"], 5)
        self.assertEqual(
            {row["barangay_name"] for row in district_two["barangays"]},
            {"Bagong Silangan", "Batasan Hills", "Commonwealth", "Holy Spirit", "Payatas"},
        )

    def test_non_barangay_areas_are_not_counted_as_barangays(self):
        district_four = load_cpdd_district_detail("IV")["district"]
        district_five = load_cpdd_district_detail("V")["district"]
        self.assertEqual(district_four["non_barangay_areas"][0]["name"], "Quezon Memorial Circle (QMC)")
        self.assertEqual(district_five["non_barangay_areas"][0]["name"], "Reservoir")
        self.assertNotIn(
            "Quezon Memorial Circle (QMC)",
            {row["barangay_name"] for row in district_four["barangays"]},
        )

    def test_reference_api_metadata_and_filter(self):
        response = self.client.get("/reference/cpdd/districts")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["is_sample"])
        self.assertTrue(data["is_authoritative_reference"])

        response = self.client.get("/reference/cpdd/barangays?district=II")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["barangay_count"], 5)

        response = self.client.get("/reference/cpdd/barangays?district=VII")
        self.assertEqual(response.status_code, 400)

    def test_prototype_response_separates_provenance(self):
        # Static reference/sample composition is separate from gated observed-data endpoints.
        from backend.services.prototype_data_service import load_prototype_district_detail
        data = load_prototype_district_detail("I")
        self.assertTrue(data["is_sample"])
        self.assertTrue(data["contains_authoritative_reference"])
        self.assertEqual(data["district"]["population_2020"], 384_384)
        self.assertEqual(data["district"]["barangay_count"], 37)
        self.assertIn("authoritative_reference", data["data_provenance"])
        self.assertIn("demonstration_only", data["data_provenance"])

    def test_readiness_audit_no_longer_reports_missing_mapping(self):
        contract = project_root / "data" / "contracts" / "research_data_contract.json"
        findings = DataReadinessService(contract).audit_raw_data()
        self.assertNotIn("MISSING_BARANGAY_TO_DISTRICT_MAPPING", findings["mismatches"])
        self.assertNotIn("INVALID_BARANGAY_TO_DISTRICT_MAPPING", findings["mismatches"])


if __name__ == "__main__":
    unittest.main()
