"""Live checks for the repository's current data availability.

Start backend/app.py on a dedicated port and set BASE_URL before running.
This acceptance profile expects no observed weekly barangay dataset.
"""
import json
import os
import unittest
import urllib.error
import urllib.request

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")


class TestFinalAcceptance(unittest.TestCase):
    def request_json(self, path, data=None):
        request = urllib.request.Request(
            BASE_URL + path,
            data=None if data is None else json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_readonly_routes(self):
        for path in ("/health", "/model/health", "/lstm/health", "/lstm/areas",
                     "/lstm/evaluation", "/reference/cpdd/households"):
            with self.subTest(path=path):
                status, _ = self.request_json(path)
                self.assertEqual(status, 200)

    def test_missing_barangay_cases_are_not_synthesized(self):
        _, health = self.request_json("/model/health")
        self.assertFalse(health["model_ready"])
        status, result = self.request_json("/predict", {"evidence": {"city_wk_cat": "Medium"}})
        self.assertEqual(status, 503)
        self.assertIn(result["error"]["code"], {"OBSERVED_WEEKLY_DATA_REQUIRED", "MODEL_NOT_READY"})
        self.assertNotIn("probabilities", result)

    def test_unlearned_environmental_scenario_is_rejected(self):
        status, result = self.request_json(
            "/predict", {"evidence": {"_sim": {"flood": "yes"}}}
        )
        self.assertEqual(status, 422)
        self.assertEqual(result["error"]["code"], "UNSUPPORTED_ENVIRONMENTAL_SCENARIO")

    def test_city_forecast_uses_last_observation_origin(self):
        status, result = self.request_json("/lstm/forecast", {"area": "city", "weeks": 4})
        self.assertEqual(status, 200)
        self.assertEqual(result["model_status"], "retrospectively_evaluated_city_only")
        self.assertEqual(len(result["predictions"]), 4)
        self.assertEqual(result["last_observed"]["period"], "2025-W52")
        self.assertEqual(result["predictions"][0]["target_period"], "2026-W01")
        for prediction in result["predictions"]:
            self.assertGreaterEqual(prediction["predicted_cases"], 0)
            self.assertIsNone(prediction["calendar_week_start"])
        self.assertTrue(result["limitations"])

    def test_supported_city_only(self):
        _, result = self.request_json("/lstm/areas")
        self.assertEqual(result["areas"], ["Quezon City (All)"])
        status, result = self.request_json("/lstm/forecast", {"area": "Bagong Pag-asa"})
        self.assertEqual(status, 422)
        self.assertEqual(result["error"]["code"], "UNSUPPORTED_AREA")

    def test_saved_evaluation_discloses_protocol(self):
        status, result = self.request_json("/lstm/evaluation")
        self.assertEqual(status, 200)
        self.assertFalse(result["protocol"]["test_used_in_training_or_selection"])
        self.assertEqual(result["splits"]["test"]["rows"], 104)
        self.assertEqual(set(result["metrics"]["test"]), {"lstm", "last_observation", "seasonal_52"})
        self.assertFalse(result["provenance"]["agency_provenance_verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
