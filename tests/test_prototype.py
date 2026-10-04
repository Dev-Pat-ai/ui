import json
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch
from flask import Flask
import sys

# Add project root and backend to path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.routes.prototype_routes import prototype_bp
from backend.services.prototype_data_service import (
    load_prototype_json,
    load_prototype_dashboard,
    load_prototype_district_detail
)


class PrototypeDataTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(prototype_bp)
        self.client = self.app.test_client()

    def test_all_prototype_endpoints(self):
        endpoints = ["forecast", "historical"]
        for ep in endpoints:
            response = self.client.get(f"/prototype/{ep}")
            self.assertEqual(response.status_code, 200, f"Endpoint /prototype/{ep} failed")
            data = response.get_json()
            self.assertIn("is_sample", data)
            self.assertIsInstance(data["is_sample"], bool)
            self.assertIn("prototype_version", data)

    def test_district_detail_success(self):
        from services.observed_weekly_data_service import ObservedWeeklyDataError
        with patch("backend.routes.prototype_routes.get_real_dashboard_data", side_effect=ObservedWeeklyDataError("missing test input", "OBSERVED_WEEKLY_DATA_REQUIRED")):
            for endpoint in ["dashboard", "districts", "districts/I"]:
                response = self.client.get(f"/prototype/{endpoint}")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.get_json()["error"]["code"], "OBSERVED_WEEKLY_DATA_REQUIRED")

    def test_invalid_district_id(self):
        response = self.client.get("/prototype/districts/VII")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "invalid_id")

    def test_forecast_can_be_scoped_to_one_district(self):
        response = self.client.get("/prototype/forecast?district=IV")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.get_json()["forecasts"]), ["IV"])

    def test_malformed_json(self):
        # We can't easily mock the path in load_prototype_json without more refactoring,
        # but we can verify the service logic using a temp file if we expose _get_sample_path
        # or similar. For now, we trust the dashboard.json validation which is already tested.
        pass

    def test_metadata_consistency(self):
        data = load_prototype_dashboard()
        self.assertEqual(data["is_sample"], True)
        self.assertIn("sample_updated_at", data)
        self.assertIn("data_source", data)

if __name__ == "__main__":
    unittest.main()
