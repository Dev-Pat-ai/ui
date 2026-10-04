import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ["DENGUESENSE_PROTOTYPE_ONLY"] = "1"
from backend.app import app


class ModelApiReadinessTest(unittest.TestCase):
    def test_bn_health_does_not_claim_ready_when_data_are_missing(self):
        from models import bn_model
        with patch.object(bn_model, "inference", None), patch.dict(os.environ, {"DENGUE_WEEKLY_CASES_PATH": "missing-test-only-weekly.csv"}):
            response = app.test_client().get("/model/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["model_ready"])
        self.assertEqual(data["status"], "not_ready")
        self.assertFalse(data["training_data"]["observed_weekly_cases_file_exists"])
        self.assertFalse(data["environmental_effects_learned"])

    def test_psa_reference_endpoint_is_available_independently_of_bn(self):
        response = app.test_client().get("/reference/cpdd/households")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data["barangays"]), 142)
        self.assertEqual(data["city_summary"]["households_2020"], 738724)

    def test_city_areas_do_not_advertise_unobserved_barangays(self):
        response = app.test_client().get("/lstm/areas")
        self.assertEqual(response.get_json()["areas"], ["Quezon City (All)"])
