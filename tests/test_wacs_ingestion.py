import sys
import unittest
from pathlib import Path

from flask import Flask

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.routes.reference_routes import reference_bp
from backend.services.wacs_data_service import (
    load_wacs_reference,
    load_wacs_waste_generation,
    load_wacs_top_generators,
)
from backend.services.cpdd_data_service import load_cpdd_reference


class WacsIngestionTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(reference_bp)
        self.client = self.app.test_client()

    def test_wacs_reference_structure_and_counts(self):
        data = load_wacs_reference()
        self.assertTrue(data["is_authoritative_reference"])
        self.assertEqual(data["reference_year"], 2021)
        self.assertEqual(data["city_summary"]["total_districts"], 6)
        self.assertEqual(data["city_summary"]["total_barangays"], 142)

        # Expected counts per district
        expected_counts = {"I": 37, "II": 5, "III": 37, "IV": 38, "V": 14, "VI": 11}
        for d_id, exp_count in expected_counts.items():
            self.assertEqual(
                len(data["districts"][d_id]["barangays"]),
                exp_count,
                f"District {d_id} barangay count mismatch in WACS"
            )

    def test_alignment_with_cpdd_barangays(self):
        wacs = load_wacs_reference()
        cpdd = load_cpdd_reference()

        wacs_barangays = {}
        for d_id, dist in wacs["districts"].items():
            for b in dist["barangays"]:
                wacs_barangays[(d_id, b["barangay_name"])] = b

        cpdd_barangays = {}
        for d_id, dist in cpdd["districts"].items():
            for b in dist["barangays"]:
                cpdd_barangays[(d_id, b["barangay_name"])] = b

        self.assertEqual(len(wacs_barangays), 142)
        self.assertEqual(len(cpdd_barangays), 142)
        self.assertEqual(set(wacs_barangays.keys()), set(cpdd_barangays.keys()))

    def test_waste_calculations_and_totals(self):
        data = load_wacs_reference()
        # Verify District II total: ~325.32 tons/day
        d2 = data["districts"]["II"]
        self.assertAlmostEqual(d2["total_waste_tons_per_day"], 325.33, delta=0.5)

        # Verify citywide waste is greater than 1000 tons/day
        city_tons = data["city_summary"]["total_waste_tons_per_day"]
        self.assertGreater(city_tons, 1200)
        self.assertLess(city_tons, 1400)

        # Verify top generator is Commonwealth in Dist II
        top_generators = data["top_10_waste_generators"]
        self.assertEqual(len(top_generators), 10)
        self.assertEqual(top_generators[0]["barangay_name"], "Commonwealth")

    def test_wacs_api_endpoints(self):
        # Full waste generation dataset
        res = self.client.get("/reference/wacs/waste-generation")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["is_authoritative_reference"])
        self.assertEqual(len(json_data["districts"]), 6)

        # District II filter
        res_d2 = self.client.get("/reference/wacs/waste-generation/II")
        self.assertEqual(res_d2.status_code, 200)
        d2_json = res_d2.get_json()
        self.assertEqual(d2_json["district"]["district_id"], "II")
        self.assertEqual(len(d2_json["district"]["barangays"]), 5)

        # Top generators endpoint
        res_top = self.client.get("/reference/wacs/top-generators")
        self.assertEqual(res_top.status_code, 200)
        top_json = res_top.get_json()
        self.assertEqual(len(top_json["top_10_waste_generators"]), 10)

        # Invalid district
        res_inv = self.client.get("/reference/wacs/waste-generation/INVALID")
        self.assertEqual(res_inv.status_code, 400)


if __name__ == "__main__":
    unittest.main()
