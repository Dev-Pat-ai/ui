"""Census import checks: source scope, reconciliation and invalid-data rejection."""

import copy
import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.cpdd_data_service import (
    load_psa_household_reference,
    validate_psa_household_reference,
)
from scripts import import_psa_households as importer


class PsaHouseholdsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(importer.DEFAULT_REFERENCE.read_text(encoding="utf-8"))
        cls.saved = json.loads(importer.DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    def test_census_coverage_controls_and_correct_denominator(self):
        data = load_psa_household_reference()
        self.assertEqual(len(data["barangays"]), 142)
        self.assertEqual(len({row["barangay_name"] for row in data["barangays"]}), 142)
        self.assertEqual(data["city_summary"]["population_2020"], 2_960_048)
        self.assertEqual(data["city_summary"]["household_population_2020"], 2_950_493)
        self.assertEqual(data["city_summary"]["households_2020"], 738_724)
        self.assertEqual(data["city_summary"]["average_household_size"], round(2_950_493 / 738_724, 6))
        for row in data["barangays"]:
            self.assertEqual(row["average_household_size"], round(row["household_population_2020"] / row["households_2020"], 6))
        self.assertEqual(data["source_document"]["barangay_cells"], "A1016:D1157")
        self.assertEqual(data["source_document"]["sheet"], "by Bgy_1")
        self.assertEqual(data["observation_type"], "census_actual")

    @unittest.skipUnless(importer.DEFAULT_SOURCE.exists(), "Original CPDD workbook is not in this checkout")
    def test_real_import_reproduces_saved_json_without_changing_source(self):
        before = hashlib.sha256(importer.DEFAULT_SOURCE.read_bytes()).hexdigest()
        result = importer.build_reference(importer.DEFAULT_SOURCE, importer.DEFAULT_REFERENCE)
        self.assertEqual(result, self.saved)
        self.assertEqual(result["source_document"]["sha256"], before)
        self.assertEqual(hashlib.sha256(importer.DEFAULT_SOURCE.read_bytes()).hexdigest(), before)

    def source_records(self):
        return [
            {key: value for key, value in row.items() if key in (
                "source_barangay_name", "source_cells", *importer.FIELDS,
            )}
            for row in copy.deepcopy(self.saved["barangays"])
        ]

    def build_with_rows(self, records, cpdd=None):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.xlsx"
            source.write_bytes(b"source bytes used only for a mocked extraction")
            mapping = importer.DEFAULT_REFERENCE
            if cpdd is not None:
                mapping = Path(directory) / "mapping.json"
                mapping.write_text(json.dumps(cpdd), encoding="utf-8")
            with patch.object(importer, "read_qc_block", return_value=(records, importer.PSA_HOUSEHOLD_TOTALS, 1015)):
                return importer.build_reference(source, mapping)

    def test_import_rejects_duplicate_missing_unknown_and_mismatched_barangays(self):
        records = self.source_records()
        duplicate = copy.deepcopy(records)
        duplicate[-1] = copy.deepcopy(duplicate[0])
        unknown = copy.deepcopy(records)
        unknown[0]["source_barangay_name"] = "Unknown barangay"
        mismatch = copy.deepcopy(records)
        mismatch[0]["population_2020"] += 1
        for altered, message in (
            (duplicate, "Duplicate"), (records[:-1], "Missing PSA barangays"),
            (unknown, "Unmapped"), (mismatch, "population mismatch"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.build_with_rows(altered)

    def test_numeric_source_counts_require_nonnegative_integers(self):
        for value in (None, -1, 2.5, True, "12", math.nan, math.inf, "#REF!"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                importer.count_value(value, "source cell")
        self.assertEqual(importer.count_value(12.0, "source cell"), 12)

    def test_service_rejects_corrupt_counts_totals_and_denominator(self):
        mutations = [
            lambda data: data["barangays"][0].update(households_2020=-1),
            lambda data: data["barangays"][0].update(household_population_2020=None),
            lambda data: data["barangays"][0].update(households_2020=0),
            lambda data: data["barangays"][0].update(population_2020=1),
            lambda data: data["barangays"][0].update(average_household_size=0),
            lambda data: data["city_summary"].update(households_2020=738_725),
            lambda data: data["district_summaries"]["I"].update(households_2020=0),
            lambda data: data.update(observation_type="projected"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                data = copy.deepcopy(self.saved)
                mutate(data)
                with self.assertRaises(ValueError):
                    validate_psa_household_reference(data, self.reference)

    def test_alias_mapping_and_optional_canonical_codes(self):
        for left, right in (("Aurora", "Doña Aurora"), ("Santo Domingo (Matalahib)", "Sto. Domingo"), ("Balong Bato", "Balon Bato")):
            self.assertEqual(importer.name_key(left), importer.name_key(right))
        reference = copy.deepcopy(self.reference)
        reference["districts"]["I"]["barangays"][0]["pcode"] = "TEST-CODE"
        result = self.build_with_rows(self.source_records(), reference)
        self.assertEqual(result["barangays"][0]["pcode"], "TEST-CODE")

    def workbook_rows(self):
        return [
            ("Total Population and Households as of 01 May 2020", None, None, None),
            (None, None, None, None), (None, None, None, None),
            (None, None, None, None),
            ("Barangay", "Total", "Household", "Number"),
            (None, "Population", "Population", "of Households"),
            ("QUEZON CITY", 2_960_048, 2_950_493, 738_724),
            ("Alicia", 6_119, 6_117, 1_522),
            (None, None, None, None),
            ("CITY OF SAN JUAN", 126_347, 125_000, 30_000),
        ]

    def read_mock_workbook(self, rows, state="visible"):
        sheet = MagicMock()
        sheet.sheet_state = state
        sheet.iter_rows.return_value = iter(rows)
        workbook = MagicMock()
        workbook.sheetnames = [importer.SOURCE_SHEET, "by Bgy"]
        workbook.__getitem__.return_value = sheet
        with patch.object(importer, "load_workbook", return_value=workbook):
            result = importer.read_qc_block(Path("not-written.xlsx"))
        workbook.close.assert_called_once()
        workbook.__getitem__.assert_called_once_with("by Bgy_1")
        return result

    def test_reader_selects_visible_qc_block_and_rejects_wrong_source(self):
        records, totals, city_row = self.read_mock_workbook(self.workbook_rows())
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_barangay_name"], "Alicia")
        self.assertEqual(totals, importer.PSA_HOUSEHOLD_TOTALS)
        self.assertEqual(city_row, 7)
        with self.assertRaisesRegex(ValueError, "visible"):
            self.read_mock_workbook(self.workbook_rows(), "hidden")
        rows = self.workbook_rows()
        rows[0] = ("Projected population as of 01 May 2020", None, None, None)
        with self.assertRaisesRegex(ValueError, "projections"):
            self.read_mock_workbook(rows)
        rows = self.workbook_rows()
        rows[7] = (None, 6119, 6117, 1522)
        with self.assertRaisesRegex(ValueError, "Missing barangay"):
            self.read_mock_workbook(rows)
        rows = self.workbook_rows()
        rows[7] = ("Alicia", 6119, None, 1522)
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            self.read_mock_workbook(rows)


if __name__ == "__main__":
    unittest.main()
