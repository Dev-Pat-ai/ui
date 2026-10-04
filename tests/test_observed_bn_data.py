"""TEST ONLY generated surveillance fixtures; never installed as model data."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.observed_weekly_data_service import (
    load_observed_weekly_cases, ObservedWeeklyDataError, get_training_data_status,
)
from models import bn_model as bn


REFERENCE = {"districts": {"I": {"barangays": [{"barangay_name": "Test Alpha"}]},
                            "II": {"barangays": [{"barangay_name": "Test Beta"}]}}}


def fixture(rain=False):
    rows = []
    for index, stamp in enumerate(pd.date_range("2022-10-03", periods=24, freq="7D")):
        year, week, _ = stamp.date().isocalendar()
        for name, district, offset in [("Test Alpha", "I", 0), ("Test Beta", "II", 3)]:
            row = dict(epi_year=year, epi_week=week, geographic_level="barangay",
                       barangay_name=name, district_id=district, dengue_cases=(index + offset) % 9,
                       data_source="TEST ONLY generated fixture", week_calendar="ISO-8601")
            if rain:
                row.update(rainfall_mm=(index * 31) % 220, rainfall_source="TEST ONLY weather fixture")
            rows.append(row)
    return pd.DataFrame(rows)


class ObservedWeeklyIntakeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test_only.csv"

    def load(self, frame):
        frame.to_csv(self.path, index=False)
        return load_observed_weekly_cases(self.path, reference=REFERENCE)

    def test_missing_file_blocks_without_annual_fallback(self):
        with self.assertRaisesRegex(ObservedWeeklyDataError, "OBSERVED_WEEKLY_DATA_REQUIRED"):
            load_observed_weekly_cases(self.path)
        with patch.dict(os.environ, {"DENGUE_WEEKLY_CASES_PATH": str(self.path)}):
            self.assertFalse(get_training_data_status()["observed_weekly_cases_file_exists"])

    def test_observed_integer_labels_and_zero_preserved(self):
        original = fixture()
        loaded = self.load(original)
        expected = original.set_index(["barangay_name", "epi_year", "epi_week"])["dengue_cases"].sort_index()
        actual = loaded.set_index(["barangay", "year", "week"])["cases_bgy_wk"].sort_index()
        self.assertEqual(expected.tolist(), actual.tolist())
        self.assertIn(0, actual.tolist())
        self.assertTrue(loaded.attrs["provenance"]["observed_case_counts"])

    def test_bad_numbers_rejected(self):
        for col, value in [("dengue_cases", 1.5), ("dengue_cases", -1), ("dengue_cases", ""),
                           ("epi_week", 0), ("epi_week", 54), ("epi_week", 1.5), ("epi_year", "")]:
            with self.subTest(col=col, value=value):
                frame = fixture().astype(object)
                frame.loc[0, col] = value
                with self.assertRaises(ObservedWeeklyDataError):
                    self.load(frame)

    def test_duplicates_and_missing_panel_rejected(self):
        frame = fixture()
        for bad in [pd.concat([frame, frame.iloc[[0]]]), frame.iloc[1:],
                    frame[~((frame.epi_year == 2022) & (frame.epi_week == 44))]]:
            with self.subTest(rows=len(bad)), self.assertRaises(ObservedWeeklyDataError):
                self.load(bad)

    def test_exact_geokeys_and_sources_required(self):
        for col, value in [("barangay_name", "test alpha"), ("district_id", "VI"),
                           ("geographic_level", "district"), ("data_source", ""),
                           ("week_calendar", "unknown")]:
            frame = fixture().astype(object)
            frame.loc[0, col] = value
            with self.subTest(col=col), self.assertRaises(ObservedWeeklyDataError):
                self.load(frame)

    def test_invalid_iso_53rd_week_rejected(self):
        frame = fixture()
        frame.loc[:1, ["epi_year", "epi_week"]] = [2022, 53]
        with self.assertRaisesRegex(ObservedWeeklyDataError, "does not exist"):
            self.load(frame)

    def test_calendar_must_be_declared(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ObservedWeeklyDataError, "Declare"):
                self.load(fixture().drop(columns="week_calendar"))

    def test_rain_requires_source_and_complete_observations(self):
        self.assertIn("rainfall_mm", self.load(fixture(rain=True)))
        with self.assertRaises(ObservedWeeklyDataError):
            self.load(fixture(rain=True).drop(columns="rainfall_source"))
        bad = fixture(rain=True).astype(object)
        bad.loc[2, "rainfall_mm"] = ""
        with self.assertRaises(ObservedWeeklyDataError):
            self.load(bad)


class ObservedBNTest(ObservedWeeklyIntakeTest):
    def setUp(self):
        super().setUp()
        names = ["bn_model", "inference", "history_df", "barangay_thresholds",
                 "global_barangay_thresholds", "city_case_thresholds", "training_metadata", "TEST_YEAR"]
        saved = {name: getattr(bn, name) for name in names}
        saved_features = bn.TRAINED_FEATURE_COLS.copy()
        def restore():
            for name, value in saved.items():
                setattr(bn, name, value)
            bn.TRAINED_FEATURE_COLS[:] = saved_features
        self.addCleanup(restore)
        bn.bn_model = bn.inference = bn.history_df = None
        bn.TEST_YEAR = 2023

    def test_cases_only_training_uses_real_labels_and_past_lags(self):
        frame = self.load(fixture())
        with patch.object(bn, "load_observed_weekly_cases", return_value=frame):
            prepared, train, test = bn.prepare_training_frame()
        self.assertTrue(len(train) and len(test))
        first = prepared[prepared.barangay == "Test Alpha"].iloc[0]
        self.assertEqual(first.cases_bgy_wk, 8)
        self.assertEqual(first.cases_bgy_lag4w, 4)
        self.assertEqual(first.cases_bgy_lag8w, 0)
        self.assertEqual(first.cases_city, 10)
        self.assertNotIn("rain_wk_cat", bn.TRAINED_FEATURE_COLS)
        self.assertFalse(bn.get_model_metadata()["is_future_forecast"])

    def test_holdout_values_do_not_change_training_thresholds(self):
        frame = self.load(fixture())
        with patch.object(bn, "load_observed_weekly_cases", return_value=frame):
            bn.prepare_training_frame()
            original = copy.deepcopy(bn.barangay_thresholds), bn.city_case_thresholds
        frame.loc[frame.year >= 2023, "cases_bgy_wk"] = 100000
        with patch.object(bn, "load_observed_weekly_cases", return_value=frame):
            bn.prepare_training_frame()
        self.assertEqual(original, (bn.barangay_thresholds, bn.city_case_thresholds))

    def test_fit_keeps_all_states_and_rejects_untrained_weather(self):
        frame = self.load(fixture())
        with patch.object(bn, "load_observed_weekly_cases", return_value=frame):
            bn.train_model()
        result = bn.what_if({"cases_lag4w_cat": "Low"})
        self.assertAlmostEqual(sum(result["probabilities"].values()), 1)
        self.assertEqual(set(result["probabilities"]), {"Low", "Medium", "High"})
        self.assertIsNone(result["metadata"]["evaluation_metrics"])
        with self.assertRaisesRegex(ValueError, "UNAVAILABLE_EVIDENCE"):
            bn.what_if({"rain_wk_cat": "Heavy"})

    def test_environmental_adjustment_rejected_without_mutating_input(self):
        evidence = {"_sim": {"waste": "poor", "water": "yes", "flood": "yes"}}
        original = copy.deepcopy(evidence)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_ENVIRONMENTAL_SCENARIO"):
            bn.what_if(evidence)
        self.assertEqual(evidence, original)

    def test_training_blocked_by_absent_real_file(self):
        with patch.dict(os.environ, {"DENGUE_WEEKLY_CASES_PATH": str(self.path)}):
            with self.assertRaisesRegex(ObservedWeeklyDataError, "OBSERVED_WEEKLY_DATA_REQUIRED"):
                bn.train_model()
        self.assertIsNone(bn.bn_model)


if __name__ == "__main__":
    unittest.main()
