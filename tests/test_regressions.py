import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
os.environ["DENGUESENSE_PROTOTYPE_ONLY"] = "1"

from backend.app import app
from backend.services.data_readiness_service import DataReadinessService
from backend.services.research_data_intake_service import ResearchDataIntakeService


class RegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        contract = PROJECT_ROOT / "data" / "contracts" / "research_data_contract.json"
        cls.intake = ResearchDataIntakeService(contract)
        cls.readiness = DataReadinessService(contract)

    def test_numeric_case_input_does_not_trigger_synthetic_training(self):
        from services.observed_weekly_data_service import ObservedWeeklyDataError
        with patch("services.prediction_service.ensure_bn_ready", side_effect=ObservedWeeklyDataError("missing test input", "OBSERVED_WEEKLY_DATA_REQUIRED")):
            response = self.client.post("/predict", json={"city_cases": 20})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "OBSERVED_WEEKLY_DATA_REQUIRED")

    def test_unlearned_environmental_adjustments_are_rejected(self):
        base = {"rain_wk_cat": "Light"}
        adverse = self.client.post("/predict", json={"evidence": {
            **base, "_sim": {"waste": "poor", "water": "yes", "flood": "yes"}
        }})
        self.assertEqual(adverse.status_code, 422)
        self.assertEqual(adverse.get_json()["error"]["code"], "UNSUPPORTED_ENVIRONMENTAL_SCENARIO")

    def test_forecast_endpoint_filters_one_district(self):
        response = self.client.get("/prototype/forecast?district=II")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.get_json()["forecasts"]), ["II"])

    def test_dashboard_and_district_detail_are_consistent(self):
        from services.observed_weekly_data_service import ObservedWeeklyDataError
        with patch("services.prediction_service.ensure_bn_ready", side_effect=ObservedWeeklyDataError("missing test input", "OBSERVED_WEEKLY_DATA_REQUIRED")):
            for path in ["/prototype/dashboard", "/prototype/districts/I"]:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.get_json()["error"]["code"], "OBSERVED_WEEKLY_DATA_REQUIRED")

    def test_fractional_training_parameters_and_unsupported_areas(self):
        response = self.client.post("/lstm/train", json={"epochs": 1.5})
        self.assertEqual(response.status_code, 400)
        with patch.dict(os.environ, {"SKIP_TRAINING": "1"}):
            response = self.client.post("/lstm/forecast", json={"area": "Batasan Hills"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "UNSUPPORTED_AREA")

    def test_invalid_lstm_parameter_returns_json_400(self):
        response = self.client.post("/lstm/forecast", json={"weeks": "not-a-number"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.is_json)
        self.assertEqual(response.get_json()["error"]["code"], "INVALID_INPUT")

    def test_intake_rejects_missing_keys_and_fractional_cases(self):
        report = {"status": "VALID", "errors": [], "warnings": [], "stats": {}}
        frame = pd.DataFrame([{
            "epi_year": float("nan"),
            "epi_week": float("nan"),
            "district_id": "I",
            "dengue_cases": 1.5,
        }])
        self.intake._validate_dengue_cases(frame, report)
        self.assertEqual(report["status"], "ERROR")
        self.assertGreaterEqual(len(report["errors"]), 3)

    def test_readiness_understands_contract_columns_and_blockers(self):
        resolution = self.readiness._infer_resolutions(pd.DataFrame(
            columns=["epi_year", "epi_week", "district_id", "dengue_cases"]
        ))
        self.assertEqual(resolution, {"temporal": "weekly", "geographic": "district"})
        findings = {
            "feature_readiness": [{"status": "AVAILABLE"}],
            "mismatches": ["MISSING_REQUIRED_INPUT"],
            "unresolved_decisions": {},
        }
        self.assertEqual(self.readiness._determine_overall_status(findings), "NOT_READY")


if __name__ == "__main__":
    unittest.main()
