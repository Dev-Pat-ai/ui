import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from models import lstm_model as lm


def source_frame(years=6):
    count = 52 * years
    return pd.DataFrame({"year": np.repeat(np.arange(2010, 2010 + years), 52), "week": np.tile(np.arange(1, 53), years),
                         "cases_city": 20 + np.arange(count) % 30, "rainfall_mm": np.arange(count) % 20})


def feature_frame(frame):
    df = lm.validate_city_frame(frame)
    for lag in [4, 8]:
        df[f"rain_lag{lag}w"] = df["rainfall_mm"].shift(lag)
        df[f"city_lag{lag}w"] = df["cases_city"].shift(lag)
    df = df.iloc[8:].reset_index(drop=True)
    df.attrs["provenance"] = {"sha256": "test-fixture", "raw_rows": len(frame)}
    return df


class CityEvaluationTests(unittest.TestCase):
    def test_rejects_duplicate_missing_fractional_and_nonfinite_observations(self):
        original = source_frame()
        invalid_frames = [pd.concat([original, original.iloc[[0]]]), original.drop(index=30)]
        for column, value in [("cases_city", 1.5), ("week", 53), ("year", 2020.5), ("rainfall_mm", -1), ("rainfall_mm", np.inf), ("cases_city", None)]:
            modified = original.astype({column: float}).copy()
            modified.loc[20, column] = value
            invalid_frames.append(modified)
        for frame in invalid_frames:
            with self.subTest(), self.assertRaisesRegex(ValueError, "DATASET_ERROR"):
                lm.validate_city_frame(frame)

    def test_year_boundary_uses_documented_52_periods_and_sorts(self):
        df = lm.validate_city_frame(source_frame().iloc[::-1])
        self.assertEqual(df.iloc[51]["period"], "2010-W52")
        self.assertEqual(df.iloc[52]["period"], "2011-W01")
        self.assertTrue(df["period_index"].diff().iloc[1:].eq(1).all())

    def test_sequences_exclude_target_and_future_weather(self):
        frame = feature_frame(source_frame())
        with patch.object(lm, "load_city_series", return_value=frame):
            X, y, features, history, _, _ = lm.build_sequence_dataset()
        self.assertEqual(X[0, -1, features.index("cases_city")], history.iloc[11]["cases_city"])
        self.assertEqual(y[0, 0], history.iloc[12]["cases_city"])
        changed = frame.copy()
        changed.loc[12:, ["cases_city", "rainfall_mm"]] = 9999
        with patch.object(lm, "load_city_series", return_value=changed):
            changed_X, *_ = lm.build_sequence_dataset()
        np.testing.assert_array_equal(X[0], changed_X[0])

    def test_complete_holdout_years_and_error_units(self):
        targets = feature_frame(source_frame()).iloc[12:].reset_index(drop=True)
        splits = lm.chronological_splits(targets)
        self.assertEqual(len(splits["validation"]), 104)
        self.assertEqual(len(splits["test"]), 104)
        self.assertLess(max(splits["train"]), min(splits["validation"]))
        self.assertLess(max(splits["validation"]), min(splits["test"]))
        self.assertEqual(lm.case_metrics([100, 200], [110, 180])["mae_cases"], 15)
        self.assertAlmostEqual(lm.case_metrics([100, 200], [110, 180])["rmse_cases"], np.sqrt(250))
        with self.assertRaisesRegex(ValueError, "complete"):
            lm.chronological_splits(targets.iloc[:-1])

    def test_legacy_artifact_rejected_and_barangay_allocation_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.pt"
            torch.save({"artifact_version": 2}, path)
            with self.assertRaisesRegex(ValueError, "Legacy"):
                lm._load_artifact(path)
        with self.assertRaisesRegex(ValueError, "observed weekly"):
            lm.build_sequence_dataset("Batasan Hills")
        self.assertEqual(lm.get_supported_areas(), ["Quezon City (All)"])

    def test_training_selection_and_scalers_do_not_depend_on_test_values(self):
        original = source_frame()
        altered = original.copy()
        altered.loc[altered["year"] >= 2014, ["cases_city", "rainfall_mm"]] *= 100
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            reports, artifacts = [], []
            for number, frame in enumerate([original, altered]):
                with patch.object(lm, "load_city_series", return_value=feature_frame(frame)), patch.object(lm, "MODEL_DIR", destination):
                    result = lm.train_lstm_model(epochs=2, hidden_size=4, seed=42, output_dir=destination / str(number))
                    reports.append(json.loads(Path(result["report_path"]).read_text(encoding="utf-8")))
                    artifacts.append(torch.load(result["model_path"], weights_only=False))
            self.assertEqual(reports[0]["validation_trace"], reports[1]["validation_trace"])
            self.assertEqual(reports[0]["selected_method"], reports[1]["selected_method"])
            np.testing.assert_array_equal(artifacts[0]["x_scaler"].data_max_, artifacts[1]["x_scaler"].data_max_)
            np.testing.assert_array_equal(artifacts[0]["y_scaler"].data_max_, artifacts[1]["y_scaler"].data_max_)
            for key in artifacts[0]["model_state"]:
                torch.testing.assert_close(artifacts[0]["model_state"][key], artifacts[1]["model_state"][key], rtol=0, atol=0)
            predictions = pd.read_csv(destination / "0" / "holdout_predictions.csv")
            self.assertEqual(len(predictions[predictions["split"] == "test"]), 104)
            self.assertTrue(predictions["calendar_week_start"].isna().all())

    def test_mismatched_sequence_cannot_silently_reuse_artifact(self):
        with patch.object(lm, "_load_artifact", return_value={"sequence_length": 12}), patch.dict(os.environ, {"SKIP_TRAINING": "1"}):
            with self.assertRaisesRegex(RuntimeError, "sequence length"):
                lm._ensure_artifact("city", 24)


if __name__ == "__main__":
    unittest.main()
