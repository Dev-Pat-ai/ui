import os
import sys
import unittest
from pathlib import Path

from flask import Flask

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.routes.reference_routes import reference_bp
from backend.services.facilities_service import (
    load_facilities_catalog,
    get_facility_category,
)


class FacilitiesIngestionTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(reference_bp)
        self.client = self.app.test_client()

    def test_facilities_catalog_metadata(self):
        catalog = load_facilities_catalog()
        self.assertTrue(catalog.get("is_authoritative_reference"))
        self.assertEqual(catalog.get("publication_year"), 2026)
        self.assertEqual(catalog.get("publisher"), "Quezon City Planning and Development Department (CPDDO)")
        self.assertEqual(catalog.get("total_categories"), 7)
        self.assertEqual(len(catalog.get("categories", [])), 7)

        category_ids = {c["id"] for c in catalog["categories"]}
        expected_ids = {"health", "schools", "daycare", "higher_ed", "fire", "police", "libraries"}
        self.assertEqual(category_ids, expected_ids)

    def test_full_resolution_images_exist(self):
        catalog = load_facilities_catalog()
        for cat in catalog["categories"]:
            asset_rel_path = cat["web_asset_url"]
            full_path = project_root / "frontend" / asset_rel_path
            self.assertTrue(full_path.exists(), f"Missing web asset: {full_path}")
            size_mb = os.path.getsize(full_path) / (1024 * 1024)
            # Ensure images are full-resolution uncompressed master maps (between 15 MB and 35 MB)
            self.assertGreater(size_mb, 15.0, f"Asset {full_path} should be uncompressed high-res: {size_mb:.2f} MB")
            self.assertLess(size_mb, 35.0, f"Asset {full_path} is unexpectedly large: {size_mb:.2f} MB")
            # Ensure width is the full master resolution (13,244px)
            self.assertEqual(cat["dimensions"]["web"]["width"], 13244)
            self.assertTrue(cat.get("is_uncompressed_high_res", False))

    def test_facilities_api_endpoints(self):
        res = self.client.get("/reference/facilities/catalog")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["total_categories"], 7)

        # Test single category route
        res_health = self.client.get("/reference/facilities/health")
        self.assertEqual(res_health.status_code, 200)
        health_data = res_health.get_json()
        self.assertEqual(health_data["id"], "health")
        self.assertIn("CDRA 2022", health_data["dengue_relevance"]["flood_compound_risk"])

        # Test invalid category
        res_invalid = self.client.get("/reference/facilities/unknown_category")
        self.assertEqual(res_invalid.status_code, 404)


if __name__ == "__main__":
    unittest.main()
