import unittest
import json
import pandas as pd
from pathlib import Path
from tempfile import NamedTemporaryFile
import sys

# Add backend to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.services.research_data_intake_service import ResearchDataIntakeService

class ResearchDataIntakeTest(unittest.TestCase):
    def setUp(self):
        self.contract_path = project_root / "data" / "contracts" / "research_data_contract.json"
        self.service = ResearchDataIntakeService(self.contract_path)

    def test_missing_file(self):
        report = self.service.validate_file(Path("non_existent.csv"), "dengue_cases")
        self.assertEqual(report["status"], "MISSING_REQUIRED_INPUT")

    def test_invalid_dengue_cases_columns(self):
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp.write("epi_year,epi_week,wrong_col\n2024,1,10")
            tmp_path = Path(tmp.name)

        try:
            report = self.service.validate_file(tmp_path, "dengue_cases")
            self.assertEqual(report["status"], "ERROR")
            self.assertTrue(any("Missing required columns" in e for e in report["errors"]))
        finally:
            tmp_path.unlink()

    def test_invalid_week_and_district(self):
        df = pd.DataFrame({
            "epi_year": [2024, 2024],
            "epi_week": [60, 5],
            "district_id": ["VII", "I"],
            "dengue_cases": [10, -5]
        })
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            df.to_csv(tmp.name, index=False)
            tmp_path = Path(tmp.name)

        try:
            report = self.service.validate_file(tmp_path, "dengue_cases")
            self.assertEqual(report["status"], "ERROR")
            self.assertTrue(any("invalid epi_week" in e for e in report["errors"]))
            self.assertTrue(any("invalid district_id" in e for e in report["errors"]))
            self.assertTrue(any("invalid dengue_cases" in e for e in report["errors"]))
        finally:
            tmp_path.unlink()

    def test_duplicate_records(self):
        df = pd.DataFrame({
            "epi_year": [2024, 2024],
            "epi_week": [1, 1],
            "district_id": ["I", "I"],
            "dengue_cases": [10, 20]
        })
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            df.to_csv(tmp.name, index=False)
            tmp_path = Path(tmp.name)

        try:
            report = self.service.validate_file(tmp_path, "dengue_cases")
            self.assertEqual(report["status"], "ERROR")
            self.assertTrue(any("duplicate year-week-location records" in e for e in report["errors"]))
        finally:
            tmp_path.unlink()

    def test_valid_file_detection(self):
        df = pd.DataFrame({
            "epi_year": [2018, 2019, 2024],
            "epi_week": [1, 20, 52],
            "district_id": ["I", "II", "VI"],
            "dengue_cases": [0, 5, 100]
        })
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            df.to_csv(tmp.name, index=False)
            tmp_path = Path(tmp.name)

        try:
            report = self.service.validate_file(tmp_path, "dengue_cases")
            self.assertEqual(report["status"], "VALID")
            self.assertEqual(report["stats"]["row_count"], 3)
        finally:
            tmp_path.unlink()

if __name__ == "__main__":
    unittest.main()
