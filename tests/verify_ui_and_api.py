import unittest
import json
import urllib.request
import urllib.error
import time

BASE_URL = "http://localhost:5000"

class TestUIAndAPI(unittest.TestCase):
    def _get(self, path):
        with urllib.request.urlopen(f"{BASE_URL}{path}") as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8"))

    def _post(self, path, data):
        req = urllib.request.Request(f"{BASE_URL}{path}", data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8"))

    def test_endpoints(self):
        paths = ["/health", "/lstm/health", "/lstm/areas", "/prototype/dashboard"]
        for p in paths:
            code, data = self._get(p)
            self.assertEqual(code, 200, f"Failed at {p}")

    def test_bayesian_predict(self):
        payload = {"district": "District I", "evidence": {"rain_wk_cat": "Light"}}
        code, data = self._post("/predict", payload)
        self.assertEqual(code, 200)
        self.assertFalse(data.get("is_demo", True))
        self.assertEqual(data.get("model_status"), "experimental")
        self.assertIn("probabilities", data)
        self.assertAlmostEqual(sum(data["probabilities"].values()), 1.0, places=3)
        self.assertIn("Quezon City", data["prediction_scope"])

    def test_lstm_forecast(self):
        payload = {"area": "city", "weeks": 4}
        code, data = self._post("/lstm/forecast", payload)
        self.assertEqual(code, 200)
        self.assertFalse(data.get("is_demo", True))
        self.assertEqual(len(data["predictions"]), 4)
        for p in data["predictions"]:
            self.assertGreaterEqual(p["predicted_cases"], 0)
        self.assertIn("assumptions", data)

    def test_area_count(self):
        code, data = self._get("/lstm/areas")
        areas = data["areas"]
        self.assertEqual(len(areas), 143)
        self.assertIn("Quezon City (All)", areas)
        unique_bgy = set(a for a in areas if a != "Quezon City (All)")
        self.assertEqual(len(unique_bgy), 142)

if __name__ == "__main__":
    time.sleep(15) # Wait for server
    unittest.main()
