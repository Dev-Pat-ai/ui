"""District-level LSTM forecast model for the integrated synthetic workbook.

This model is used as an optional next-week forecast input to the Bayesian
Network. It trains and evaluates against the same district-week
SYNTHETIC_FILLED workbook as the Bayesian backend. The source dengue values are
preserved as fractional values; they are not rounded into invented counts.

The saved artifact is separate from the legacy city LSTM artifact so historical
model files are retained unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import os
import platform
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.preprocessing import MinMaxScaler
from torch import nn

from services.district_weekly_data_service import dataset_path, load_district_weekly_data


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(__file__).resolve().parent / "trained"
ARTIFACT_PATH = MODEL_DIR / "lstm_district_forecast.pt"
ARTIFACT_VERSION = 1
SEQUENCE_LENGTH = int(os.getenv("DENGUE_DISTRICT_LSTM_SEQUENCE_LENGTH", "12"))
VALIDATION_YEAR = int(os.getenv("DENGUE_DISTRICT_LSTM_VALIDATION_YEAR", "2022"))
TEST_YEAR = int(os.getenv("DENGUE_DISTRICT_LSTM_TEST_YEAR", "2023"))
DISTRICT_ORDER = ["I", "II", "III", "IV", "V", "VI"]
DISTRICT_NUMBER = {roman: index + 1 for index, roman in enumerate(DISTRICT_ORDER)}

# All numeric predictors come directly from the supplied district-week workbook.
# The case series is included in each historical sequence and the target is the
# following supplied district-week dengue value.
CONTINUOUS_FEATURES = [
    "historical_dengue_cases",
    "minimum_temperature",
    "maximum_temperature",
    "humidity",
    "rainfall",
    "wind_temperature",
    "wind_speed",
    "mean_diurnal_range",
    "isothermality",
    "ndvi",
    "flood_incidence",
    "palmer_drought_severity_index",
    "nighttime_light_intensity",
    "population_density",
    "number_of_households",
    "poverty_incidence",
    "income",
    "employment_status",
    "health_expenditure",
    "literacy_rate",
    "fogging",
    "solid_waste_generation",
    "solid_waste_collection",
]
DISTRICT_FEATURES = [f"district_{roman}" for roman in DISTRICT_ORDER]
FEATURE_NAMES = CONTINUOUS_FEATURES + DISTRICT_FEATURES
TARGET_NAME = "historical_dengue_cases"


class DistrictDengueLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 48, output_size: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            dropout=0.2,
        )
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(x)
        return self.fc(output[:, -1, :])


def _source_sha256() -> str:
    path = dataset_path()
    if not path.is_file():
        raise FileNotFoundError(f"DISTRICT_WEEKLY_DATA_REQUIRED: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_district(value: Any) -> str:
    text = str(value or "").strip().upper().replace("DISTRICT", "").strip()
    numbers = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}
    text = numbers.get(text, text)
    if text not in DISTRICT_ORDER:
        raise ValueError(f"UNSUPPORTED_AREA: Invalid district '{value}'. Allowed districts: {DISTRICT_ORDER}")
    return text


def _row_features(row: pd.Series) -> np.ndarray:
    values = [float(row[name]) for name in CONTINUOUS_FEATURES]
    district = str(row["district_code"])
    values.extend(1.0 if district == roman else 0.0 for roman in DISTRICT_ORDER)
    return np.asarray(values, dtype=np.float32)


def build_sequence_dataset(sequence_length: int = SEQUENCE_LENGTH) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, dict[str, Any]]:
    """Build next-week district sequences without bridging missing/invalid weeks."""
    if sequence_length < 2:
        raise ValueError("sequence_length must be at least 2.")

    source = load_district_weekly_data()
    provenance = dict(source.attrs.get("provenance", {}))
    samples: list[np.ndarray] = []
    targets: list[float] = []
    meta_rows: list[dict[str, Any]] = []

    for district, group in source.groupby("district_code", sort=False):
        group = group.sort_values("week_start").reset_index(drop=True)
        feature_matrix = np.stack([_row_features(row) for _, row in group.iterrows()])
        valid = group["model_weather_valid"].to_numpy(dtype=bool)
        dates = pd.to_datetime(group["week_start"]).to_numpy()

        for target_index in range(sequence_length, len(group)):
            start = target_index - sequence_length
            window_slice = slice(start, target_index)
            # The target's supplied weather can be invalid without affecting a
            # forecast made from prior weeks, but the target dengue value must be finite.
            if not valid[window_slice].all():
                continue
            date_window = pd.to_datetime(group["week_start"].iloc[start:target_index + 1])
            if not date_window.diff().dropna().eq(pd.Timedelta(days=7)).all():
                continue
            target_value = float(group.iloc[target_index][TARGET_NAME])
            if not np.isfinite(target_value):
                continue

            samples.append(feature_matrix[window_slice])
            targets.append(target_value)
            target_row = group.iloc[target_index]
            meta_rows.append({
                "district_id": int(target_row["district_id"]),
                "district_code": str(district),
                "district_name": str(target_row["district_name"]),
                "year": int(target_row["year"]),
                "week": int(target_row["week"]),
                "week_start": pd.Timestamp(target_row["week_start"]),
                "actual_cases": target_value,
            })

    if not samples:
        raise ValueError("DATASET_ERROR: No valid district LSTM sequences could be built.")

    X = np.stack(samples).astype(np.float32)
    y = np.asarray(targets, dtype=np.float32).reshape(-1, 1)
    metadata = pd.DataFrame(meta_rows)
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        raise ValueError("DATASET_ERROR: LSTM sequences contain nonfinite values.")

    provenance.update({
        "lstm_sequence_length": int(sequence_length),
        "lstm_sequence_rows": int(len(metadata)),
        "lstm_features": list(FEATURE_NAMES),
        "lstm_target": TARGET_NAME,
        "source_sha256": _source_sha256(),
        "invalid_weather_rows_not_used_as_lstm_inputs": int((~source["model_weather_valid"]).sum()),
    })
    return X, y, metadata, provenance


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | int]:
    actual = np.asarray(actual, dtype=float).reshape(-1)
    predicted = np.asarray(predicted, dtype=float).reshape(-1)
    if len(actual) != len(predicted):
        raise ValueError("Metric arrays have different lengths.")
    error = predicted - actual
    nonzero = np.abs(actual) > 1e-8
    mape = float(np.mean(np.abs(error[nonzero] / actual[nonzero])) * 100) if nonzero.any() else float("nan")
    return {
        "rows": int(len(actual)),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "mape_percent": mape,
    }


def _fit_scalers(X: np.ndarray, y: np.ndarray, indexes: np.ndarray) -> tuple[MinMaxScaler, MinMaxScaler]:
    x_scaler = MinMaxScaler().fit(X[indexes].reshape(-1, X.shape[-1]))
    y_scaler = MinMaxScaler().fit(y[indexes])
    return x_scaler, y_scaler


def _scale_inputs(X: np.ndarray, scaler: MinMaxScaler) -> torch.Tensor:
    scaled = scaler.transform(X.reshape(-1, X.shape[-1])).reshape(X.shape).astype(np.float32)
    return torch.from_numpy(scaled)


def _train_network(
    X: np.ndarray,
    y: np.ndarray,
    train_indexes: np.ndarray,
    validation_indexes: np.ndarray,
    *,
    hidden_size: int,
    epochs: int,
    batch_size: int,
    patience: int,
    seed: int,
) -> tuple[dict[str, Any], int, list[dict[str, float]]]:
    x_scaler, y_scaler = _fit_scalers(X, y, train_indexes)
    xs = _scale_inputs(X, x_scaler)
    ys = torch.from_numpy(y_scaler.transform(y).astype(np.float32))
    model = DistrictDengueLSTM(len(FEATURE_NAMES), hidden_size=hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()

    best_state: dict[str, Any] | None = None
    best_mae = float("inf")
    best_epoch = 1
    stale = 0
    trace: list[dict[str, float]] = []

    for epoch in range(1, epochs + 1):
        model.train()
        permutation = train_indexes[torch.randperm(len(train_indexes)).numpy()]
        for start in range(0, len(permutation), batch_size):
            indexes = permutation[start:start + batch_size]
            optimizer.zero_grad()
            loss = loss_fn(model(xs[indexes]), ys[indexes])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        model.eval()
        with torch.no_grad():
            validation_scaled = model(xs[validation_indexes]).numpy()
        validation_predictions = np.maximum(0.0, y_scaler.inverse_transform(validation_scaled)).reshape(-1)
        validation_mae = float(_metrics(y[validation_indexes], validation_predictions)["mae"])
        trace.append({"epoch": float(epoch), "validation_mae": validation_mae})
        if validation_mae < best_mae:
            best_mae = validation_mae
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            stale = 0
        else:
            stale += 1
        if stale >= patience:
            break

    if best_state is None:
        raise RuntimeError("LSTM training did not produce a usable model state.")
    return best_state, best_epoch, trace


def _refit_final_network(
    X: np.ndarray,
    y: np.ndarray,
    fit_indexes: np.ndarray,
    *,
    hidden_size: int,
    epochs: int,
    batch_size: int,
    seed: int,
) -> tuple[DistrictDengueLSTM, MinMaxScaler, MinMaxScaler]:
    x_scaler, y_scaler = _fit_scalers(X, y, fit_indexes)
    xs = _scale_inputs(X, x_scaler)
    ys = torch.from_numpy(y_scaler.transform(y).astype(np.float32))
    model = DistrictDengueLSTM(len(FEATURE_NAMES), hidden_size=hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()

    for _ in range(max(1, epochs)):
        model.train()
        permutation = fit_indexes[torch.randperm(len(fit_indexes)).numpy()]
        for start in range(0, len(permutation), batch_size):
            indexes = permutation[start:start + batch_size]
            optimizer.zero_grad()
            loss = loss_fn(model(xs[indexes]), ys[indexes])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
    model.eval()
    return model, x_scaler, y_scaler


def train_district_lstm(
    *,
    sequence_length: int = SEQUENCE_LENGTH,
    epochs: int = 80,
    batch_size: int = 32,
    hidden_size: int = 48,
    patience: int = 12,
    seed: int = 42,
    artifact_path: Path = ARTIFACT_PATH,
) -> dict[str, Any]:
    """Train a district-level LSTM and save a source-bound artifact."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    try:
        torch.use_deterministic_algorithms(True)
    except Exception:
        pass

    X, y, metadata, provenance = build_sequence_dataset(sequence_length)
    years = metadata["year"].to_numpy()
    train_indexes = np.flatnonzero(years < VALIDATION_YEAR)
    validation_indexes = np.flatnonzero(years == VALIDATION_YEAR)
    pretest_indexes = np.flatnonzero(years < TEST_YEAR)
    test_indexes = np.flatnonzero(years >= TEST_YEAR)
    if min(len(train_indexes), len(validation_indexes), len(test_indexes)) == 0:
        raise ValueError(
            f"DATASET_ERROR: LSTM requires train (<{VALIDATION_YEAR}), validation ({VALIDATION_YEAR}), "
            f"and test (>={TEST_YEAR}) samples."
        )

    _, best_epoch, trace = _train_network(
        X, y, train_indexes, validation_indexes,
        hidden_size=hidden_size,
        epochs=epochs,
        batch_size=batch_size,
        patience=patience,
        seed=seed,
    )

    # Refit from scratch on all pre-test rows for the selected number of epochs.
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    model, x_scaler, y_scaler = _refit_final_network(
        X, y, pretest_indexes,
        hidden_size=hidden_size,
        epochs=best_epoch,
        batch_size=batch_size,
        seed=seed,
    )

    xs = _scale_inputs(X, x_scaler)
    with torch.no_grad():
        predictions = np.maximum(0.0, y_scaler.inverse_transform(model(xs).numpy())).reshape(-1)

    evaluation = {
        "validation_selection": _metrics(y[validation_indexes], predictions[validation_indexes]),
        "holdout_test": _metrics(y[test_indexes], predictions[test_indexes]),
        "split": {
            "training_and_refit": f"target years < {TEST_YEAR}",
            "validation_for_epoch_selection": str(VALIDATION_YEAR),
            "holdout_test": f"target years >= {TEST_YEAR}",
            "test_used_for_training": False,
        },
        "claim_limit": "Synthetic testing metric only; not real-world outbreak forecast validation.",
    }

    artifact = {
        "artifact_version": ARTIFACT_VERSION,
        "source_sha256": _source_sha256(),
        "source_file": str(dataset_path()),
        "dataset_type": "SYNTHETIC_FILLED",
        "geographic_level": "district",
        "feature_names": list(FEATURE_NAMES),
        "target_name": TARGET_NAME,
        "sequence_length": int(sequence_length),
        "hidden_size": int(hidden_size),
        "best_epoch": int(best_epoch),
        "seed": int(seed),
        "model_state_dict": model.state_dict(),
        "x_scaler": x_scaler,
        "y_scaler": y_scaler,
        "evaluation": evaluation,
        "provenance": provenance,
        "training_trace": trace,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": torch.__version__,
            "sklearn": sklearn.__version__,
        },
        "limitations": [
            "The dataset is synthetic/simulated and is used for software and model testing.",
            "Fractional district-week dengue values are preserved as supplied.",
            "The LSTM forecasts the next supplied district-week dengue value from the preceding district sequence.",
            "No claim of operational or clinical forecast validity is made.",
        ],
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(artifact, artifact_path)
    return {
        "status": "trained",
        "artifact_path": str(artifact_path),
        "sequence_rows": int(len(metadata)),
        "training_rows": int(len(pretest_indexes)),
        "test_rows": int(len(test_indexes)),
        "best_epoch": int(best_epoch),
        "evaluation": evaluation,
        "source_sha256": artifact["source_sha256"],
    }


def _load_artifact(path: Path = ARTIFACT_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"MODEL_NOT_READY: District LSTM artifact not found: {path}")
    artifact = torch.load(path, map_location="cpu", weights_only=False)
    if artifact.get("artifact_version") != ARTIFACT_VERSION:
        raise ValueError("MODEL_NOT_READY: District LSTM artifact version is incompatible.")
    if artifact.get("source_sha256") != _source_sha256():
        raise ValueError("MODEL_NOT_READY: District workbook changed after LSTM training. Retraining is required.")
    if artifact.get("feature_names") != FEATURE_NAMES or artifact.get("target_name") != TARGET_NAME:
        raise ValueError("MODEL_NOT_READY: District LSTM feature/target schema is incompatible.")
    return artifact


def ensure_district_lstm_ready(*, auto_train: bool = True) -> dict[str, Any]:
    try:
        return _load_artifact()
    except (FileNotFoundError, ValueError):
        if not auto_train or os.getenv("SKIP_TRAINING") == "1":
            raise
        train_district_lstm()
        return _load_artifact()


def _model_from_artifact(artifact: dict[str, Any]) -> DistrictDengueLSTM:
    model = DistrictDengueLSTM(len(FEATURE_NAMES), hidden_size=int(artifact["hidden_size"]))
    model.load_state_dict(artifact["model_state_dict"])
    model.eval()
    return model


def predict_sequence_frame() -> pd.DataFrame:
    """Return one-step LSTM predictions aligned to each available target week."""
    artifact = ensure_district_lstm_ready()
    X, y, metadata, _ = build_sequence_dataset(int(artifact["sequence_length"]))
    model = _model_from_artifact(artifact)
    xs = _scale_inputs(X, artifact["x_scaler"])
    with torch.no_grad():
        predicted = np.maximum(0.0, artifact["y_scaler"].inverse_transform(model(xs).numpy())).reshape(-1)
    result = metadata.copy()
    result["lstm_predicted_cases"] = predicted
    result["lstm_error"] = result["lstm_predicted_cases"] - result["actual_cases"]
    result["lstm_prediction_training_status"] = np.where(result["year"] < TEST_YEAR, "in_sample_pretest", "holdout")
    return result


def _latest_valid_sequence(district: str, sequence_length: int) -> tuple[np.ndarray, pd.Series]:
    source = load_district_weekly_data()
    group = source[source["district_code"] == district].sort_values("week_start").reset_index(drop=True)
    # Search backwards for the most recent contiguous, weather-valid sequence.
    for end in range(len(group), sequence_length - 1, -1):
        window = group.iloc[end - sequence_length:end]
        if not window["model_weather_valid"].all():
            continue
        dates = pd.to_datetime(window["week_start"])
        if not dates.diff().dropna().eq(pd.Timedelta(days=7)).all():
            continue
        X = np.stack([_row_features(row) for _, row in window.iterrows()]).astype(np.float32)
        return X, window.iloc[-1]
    raise ValueError(f"DATASET_ERROR: No valid {sequence_length}-week LSTM history for District {district}.")


def forecast_next_week(district: Any) -> dict[str, Any]:
    """Forecast one week ahead for a selected district using the saved model."""
    district_code = normalize_district(district)
    artifact = ensure_district_lstm_ready()
    sequence_length = int(artifact["sequence_length"])
    X, last_row = _latest_valid_sequence(district_code, sequence_length)
    model = _model_from_artifact(artifact)
    xs = _scale_inputs(X[np.newaxis, ...], artifact["x_scaler"])
    with torch.no_grad():
        scaled_prediction = model(xs).numpy()
    predicted_cases = float(np.maximum(0.0, artifact["y_scaler"].inverse_transform(scaled_prediction))[0, 0])
    next_start = pd.Timestamp(last_row["week_start"]) + pd.Timedelta(days=7)
    iso = next_start.isocalendar()
    return {
        "district_id": district_code,
        "district_name": f"District {DISTRICT_NUMBER[district_code]}",
        "prediction_scope": f"District {DISTRICT_NUMBER[district_code]}",
        "predicted_cases": predicted_cases,
        "forecast_year": int(iso.year),
        "forecast_week": int(iso.week),
        "forecast_week_start": next_start.strftime("%Y-%m-%d"),
        "source_through": pd.Timestamp(last_row["week_start"]).strftime("%Y-%m-%d"),
        "sequence_length": sequence_length,
        "dataset_type": "SYNTHETIC_FILLED",
        "is_synthetic_testing_data": True,
        "evaluation": artifact["evaluation"],
        "limitations": artifact.get("limitations", []),
    }


def get_supported_areas() -> list[str]:
    return [f"District {i}" for i in range(1, 7)]


def get_lstm_summary() -> dict[str, Any]:
    artifact = ensure_district_lstm_ready()
    return {
        "model": "District-level LSTM next-week forecast",
        "artifact_path": str(ARTIFACT_PATH),
        "geographic_level": "district",
        "dataset_type": artifact.get("dataset_type"),
        "sequence_length": artifact.get("sequence_length"),
        "features": artifact.get("feature_names"),
        "evaluation": artifact.get("evaluation"),
        "source_sha256": artifact.get("source_sha256"),
        "limitations": artifact.get("limitations", []),
    }


# Compatibility aliases for route code.
train_lstm_model = train_district_lstm


def load_trained_model(area: Any = None, sequence_length: int | None = None) -> dict[str, Any]:
    """Compatibility helper: validate and return the current district artifact."""
    if area not in (None, ""):
        normalize_district(area)
    artifact = ensure_district_lstm_ready()
    if sequence_length is not None and int(sequence_length) != int(artifact["sequence_length"]):
        raise ValueError(
            f"MODEL_NOT_READY: Saved district LSTM uses sequence_length={artifact['sequence_length']}; "
            "retrain to use a different sequence length."
        )
    return artifact


def forecast_next_weeks(weeks: int = 1, area: Any = "I", sequence_length: int | None = None) -> dict[str, Any]:
    """Recursive district projection with explicit persistence assumptions.

    Week 1 uses only observed history. For weeks after W1, future environmental
    predictors are unavailable in the workbook, so the latest observed
    environmental vector is persisted while predicted dengue cases are fed back
    recursively. The BN-with-LSTM path uses W1 only.
    """
    if weeks < 1 or weeks > 24:
        raise ValueError("weeks must be between 1 and 24.")
    district = normalize_district(area)
    artifact = ensure_district_lstm_ready()
    saved_sequence_length = int(artifact["sequence_length"])
    if sequence_length is not None and int(sequence_length) != saved_sequence_length:
        raise ValueError(
            f"MODEL_NOT_READY: Saved district LSTM uses sequence_length={saved_sequence_length}; retrain first."
        )
    X, last_row = _latest_valid_sequence(district, saved_sequence_length)
    sequence = X.copy()
    model = _model_from_artifact(artifact)
    predictions: list[dict[str, Any]] = []
    last_start = pd.Timestamp(last_row["week_start"])
    case_index = FEATURE_NAMES.index("historical_dengue_cases")

    for step in range(1, weeks + 1):
        xs = _scale_inputs(sequence[np.newaxis, ...], artifact["x_scaler"])
        with torch.no_grad():
            scaled_prediction = model(xs).numpy()
        predicted_cases = float(np.maximum(0.0, artifact["y_scaler"].inverse_transform(scaled_prediction))[0, 0])
        next_start = last_start + pd.Timedelta(days=7 * step)
        iso = next_start.isocalendar()
        predictions.append({
            "week_ahead": step,
            "predicted_cases": predicted_cases,
            "forecast_year": int(iso.year),
            "forecast_week": int(iso.week),
            "forecast_week_start": next_start.strftime("%Y-%m-%d"),
        })
        # Persist the final observed exogenous vector and replace only the dengue
        # case value with the recursive prediction for the next step.
        next_vector = sequence[-1].copy()
        next_vector[case_index] = predicted_cases
        sequence = np.concatenate([sequence[1:], next_vector[np.newaxis, :]], axis=0)

    return {
        "prediction_scope": f"District {DISTRICT_NUMBER[district]}",
        "district_id": district,
        "predictions": predictions,
        "model": "District-level LSTM",
        "dataset_type": "SYNTHETIC_FILLED",
        "is_synthetic_testing_data": True,
        "evaluation": artifact["evaluation"],
        "assumptions": [
            "Week 1 uses observed district history from the supplied workbook.",
            "For W2+, future environmental predictors are held at their latest observed values and predicted cases are fed back recursively.",
            "BN with LSTM uses only the next-week (W1) forecast.",
        ],
        "limitations": artifact.get("limitations", []),
    }
