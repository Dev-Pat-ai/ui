import sys
import unittest
from pathlib import Path

from flask import Flask

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.routes.reference_routes import reference_bp
from backend.services.cdra_data_service import (
    load_cdra_flood_vulnerability,
    load_cdra_hotspots,
    load_cdra_reference,
)
from backend.services.cpdd_data_service import load_cpdd_reference


class CdraIngestionTest(unittest.TestCase):
    def test_missing_flood_records_remain_unknown_and_are_excluded_from_means(self):
        data = load_cdra_reference()
        missing = []
        observed = []
        for district in data["districts"].values():
            values = []
            for barangay in district["barangays"]:
                hazard = barangay["flood_hazard"]
                if hazard["has_mgb_record"]:
                    observed.append(barangay)
                    values.append(hazard["total_flooded_area_pct"])
                else:
                    missing.append(barangay)
                    self.assertIsNone(hazard["total_flooded_area_pct"])
                    self.assertIsNone(hazard["submerged_pct_gt_2m"])
                    if not barangay["hotspot_profile"]["is_hotspot"]:
                        self.assertEqual(hazard["vulnerability_level"], "Unknown")
                        self.assertIsNone(hazard["vulnerability_score"])
            self.assertEqual(district["flood_record_count"], len(values))
            self.assertAlmostEqual(district["average_flooded_area_pct"], round(sum(values) / len(values), 2))
        self.assertEqual(len(observed), 119)
        self.assertEqual(len(missing), 23)

    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(reference_bp)
        self.client = self.app.test_client()

    def test_cdra_reference_structure_and_counts(self):
        data = load_cdra_reference()
        self.assertTrue(data["is_authoritative_reference"])
        self.assertEqual(data["reference_year"], 2022)
        self.assertEqual(data["city_summary"]["total_districts"], 6)
        self.assertEqual(data["city_summary"]["total_barangays"], 142)
        self.assertEqual(data["city_summary"]["bvi_hotspots_total"], 21)

        # Expected hotspot counts per district from CDRA Chapter 6
        expected_hotspots = {
            "I": 9,
            "II": 0,
            "III": 5,
            "IV": 5,
            "V": 1,
            "VI": 1
        }
        for d_id, exp_count in expected_hotspots.items():
            self.assertEqual(
                data["districts"][d_id]["hotspot_count"],
                exp_count,
                f"District {d_id} hotspot count mismatch"
            )

    def test_bvi_hotspot_ranking_integrity(self):
        hotspots_data = load_cdra_hotspots()
        self.assertEqual(hotspots_data["hotspot_count"], 21)
        hotspots = hotspots_data["hotspots"]

        # Rank 1: Katipunan, BVI 100, Dist I
        self.assertEqual(hotspots[0]["rank"], 1)
        self.assertEqual(hotspots[0]["barangay_name"], "Katipunan")
        self.assertEqual(hotspots[0]["bvi_score"], 100)
        self.assertEqual(hotspots[0]["district_id"], "I")
        self.assertEqual(hotspots[0]["tier_level"], "Tier 1")

        # Rank 2: Capri, BVI 98, Dist V
        self.assertEqual(hotspots[1]["rank"], 2)
        self.assertEqual(hotspots[1]["barangay_name"], "Capri")
        self.assertEqual(hotspots[1]["bvi_score"], 98)
        self.assertEqual(hotspots[1]["district_id"], "V")

        # Verify ranks 1-21 are contiguous
        ranks = [h["rank"] for h in hotspots]
        self.assertEqual(ranks, list(range(1, 22)))

    def test_alignment_with_cpdd_142_barangays(self):
        cdra = load_cdra_reference()
        cpdd = load_cpdd_reference()

        cdra_barangays = {}
        for d_id, dist in cdra["districts"].items():
            for b in dist["barangays"]:
                cdra_barangays[(d_id, b["barangay_name"])] = b

        cpdd_barangays = {}
        for d_id, dist in cpdd["districts"].items():
            for b in dist["barangays"]:
                cpdd_barangays[(d_id, b["barangay_name"])] = b

        self.assertEqual(len(cdra_barangays), 142)
        self.assertEqual(len(cpdd_barangays), 142)
        self.assertEqual(set(cdra_barangays.keys()), set(cpdd_barangays.keys()))

    def test_reference_api_endpoints(self):
        # Full dataset
        res = self.client.get("/reference/cdra/flood-vulnerability")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["is_authoritative_reference"])
        self.assertEqual(len(json_data["districts"]), 6)

        # District I filter
        res_d1 = self.client.get("/reference/cdra/flood-vulnerability/I")
        self.assertEqual(res_d1.status_code, 200)
        d1_json = res_d1.get_json()
        self.assertEqual(d1_json["district"]["district_id"], "I")
        self.assertEqual(len(d1_json["district"]["barangays"]), 37)
        self.assertEqual(d1_json["district"]["hotspot_count"], 9)

        # Hotspots endpoint
        res_hs = self.client.get("/reference/cdra/hotspots")
        self.assertEqual(res_hs.status_code, 200)
        hs_json = res_hs.get_json()
        self.assertEqual(hs_json["hotspot_count"], 21)

        # Invalid district
        res_inv = self.client.get("/reference/cdra/flood-vulnerability/INVALID")
        self.assertEqual(res_inv.status_code, 400)


if __name__ == "__main__":
    unittest.main()
