
from __future__ import annotations

import copy
import hashlib
import json
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

from utils.path_utils import resolve_data_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(__file__).resolve().parent / "trained"
OUTPUT_DIR = PROJECT_ROOT / "output" / "model-evaluation"
XLSX_PATH = resolve_data_path("Dengue-Rainfall_Dataset.xlsx", "DENGUE_XLSX_PATH")
SEQUENCE_LENGTH = 12
ARTIFACT_VERSION = 3
CITY_ALIASES = {"city", "quezon city (all)", "qc", "quezon city"}
FEATURE_NAMES = ["rainfall_mm", "rain_lag4w", "rain_lag8w", "cases_city", "city_lag4w", "city_lag8w"]
WEEK_CONVENTION = "source_52_period_year; calendar week start and week-53 treatment unverified"
LIMITATIONS = [
    "The workbook attributes cases to QCESD and rainfall to NASA; these attributions have not been independently verified.",
    "The source defines 52 periods per year. Actual calendar week boundaries and treatment of week 53 are unverified.",
    "Holdout metrics measure rolling one-period-ahead forecasts using observations available before each target; they do not validate recursive multi-period forecasts.",
    "No prospective 2026 observations are available in this workbook; forecasts begin immediately after the final 2025 source period, not the current date.",
    "Only city totals are supported. Barangay forecasts require observed weekly targets, aligned weather, and separate validation.",
    "CPDD static features have not been fitted as city forecast predictors. No causal effects or calibrated prediction intervals are established.",
]


class DengueLSTM(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 64, output_size: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size, num_layers=2, batch_first=True)
        self.dropout = nn.Dropout(0.2)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.fc(self.dropout(out[:, -1, :]))


def _require_city(area: str | None) -> None:
    if area and str(area).strip().lower() not in CITY_ALIASES:
        raise ValueError("UNSUPPORTED_AREA: Barangay LSTM forecasting is unavailable: observed weekly barangay targets and a validated model are required. Annual allocations are not observations.")


def validate_city_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Fail visibly on malformed or gapped inputs; never drop/impute observations."""
    names = {"yr": "year", "wn": "week", "dc_qc": "cases_city", "rf_nasa": "rainfall_mm"}
    df = frame.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns=names)
    required = ["year", "week", "cases_city", "rainfall_mm"]
    if df.columns.duplicated().any() or not set(required).issubset(df.columns):
        raise ValueError("DATASET_ERROR: Expected unambiguous YR, WN, DC_QC, RF_NASA columns or their canonical names.")
    df = df[required].copy()
    if df.empty:
        raise ValueError("DATASET_ERROR: City series is empty.")
    for column in required:
        df[column] = pd.to_numeric(df[column], errors="coerce")
        if not np.isfinite(df[column].to_numpy(dtype=float)).all():
            raise ValueError(f"DATASET_ERROR: {column} contains missing, nonnumeric, or nonfinite values.")
    for column in ["year", "week", "cases_city"]:
        if (df[column] % 1 != 0).any():
            raise ValueError(f"DATASET_ERROR: {column} must contain integers.")
        df[column] = df[column].astype(int)
    if not df["year"].between(1900, 2200).all() or not df["week"].between(1, 52).all():
        raise ValueError("DATASET_ERROR: This workbook adapter requires years 1900–2200 and source weeks 1–52. Confirm a different week convention before adapting it.")
    if (df[["cases_city", "rainfall_mm"]] < 0).any().any():
        raise ValueError("DATASET_ERROR: Negative case counts or rainfall are invalid.")
    if df.duplicated(["year", "week"]).any():
        raise ValueError("DATASET_ERROR: Duplicate city year/week observations must be reconciled at source.")
    df = df.sort_values(["year", "week"]).reset_index(drop=True)
    df["period_index"] = df["year"] * 52 + df["week"] - 1
    if not df["period_index"].diff().iloc[1:].eq(1).all():
        raise ValueError("DATASET_ERROR: Missing source weeks: lagging across a gap would create false weekly sequences.")
    df["period"] = df["year"].astype(str) + "-W" + df["week"].astype(str).str.zfill(2)
    return df


def load_city_series() -> pd.DataFrame:
    if not XLSX_PATH.exists():
        raise FileNotFoundError(f"DATASET_ERROR: Weekly city dataset not found: {XLSX_PATH}")
    with pd.ExcelFile(XLSX_PATH) as workbook:
        matches = [sheet for sheet in workbook.sheet_names if sheet.strip().lower() == "qc data"]
        if len(matches) != 1:
            raise ValueError("DATASET_ERROR: Expected exactly one QC Data sheet; arbitrary sheet/column fallbacks are not permitted.")
        df = validate_city_frame(workbook.parse(matches[0]))
        dictionary = workbook.parse("Data Dictionary").fillna("").to_dict(orient="records") if "Data Dictionary" in workbook.sheet_names else []
    provenance = {
        "file": str(XLSX_PATH), "sha256": hashlib.sha256(XLSX_PATH.read_bytes()).hexdigest(),
        "sheet": matches[0], "raw_rows": len(df), "start_period": df["period"].iloc[0], "end_period": df["period"].iloc[-1],
        "case_series": "provided city weekly counts, not annual-to-weekly allocations",
        "case_source_attribution": "QCESD according to workbook Data Dictionary",
        "rainfall_source_attribution": "NASA satellite according to workbook Data Dictionary; not PAGASA",
        "agency_provenance_verified": False, "week_convention": WEEK_CONVENTION,
        "calendar_week_dates_available": False, "data_dictionary": dictionary,
        "invalid_or_missing_rows_dropped": 0, "imputed_observations": 0, "lag_warmup_rows": 8,
    }
    for lag in [4, 8]:
        df[f"rain_lag{lag}w"] = df["rainfall_mm"].shift(lag)
        df[f"city_lag{lag}w"] = df["cases_city"].shift(lag)
    # Exactly eight expected lag warmup rows, with no observation-level dropna.
    df = df.iloc[8:].reset_index(drop=True)
    df.attrs["provenance"] = provenance
    return df


def get_barangay_series(barangay: str) -> pd.DataFrame:
    _require_city(barangay)
    return load_city_series()


def build_sequence_dataset(area: str | None = None, sequence_length: int = SEQUENCE_LENGTH) -> tuple[np.ndarray, np.ndarray, list[str], pd.DataFrame, str, str]:
    _require_city(area)
    if sequence_length < 9:
        raise ValueError("sequence_length must be at least 9 for the eight-period lag features.")
    df = load_city_series()
    if len(df) <= sequence_length:
        raise ValueError("DATASET_ERROR: Not enough contiguous city observations for the requested sequence.")
    values = df[FEATURE_NAMES].to_numpy(dtype=np.float32)
    X = np.stack([values[i - sequence_length:i] for i in range(sequence_length, len(df))])
    y = df["cases_city"].iloc[sequence_length:].to_numpy(dtype=np.float32).reshape(-1, 1)
    return X, y, list(FEATURE_NAMES), df, "cases_city", "Quezon City (All)"


def chronological_splits(targets: pd.DataFrame) -> dict[str, np.ndarray]:
    """Reserve final two complete years for test, preceding two for validation."""
    years = sorted(targets["year"].unique())
    if len(years) < 6:
        raise ValueError("DATASET_ERROR: At least six years are required for this predeclared holdout protocol.")
    for year in years[-4:]:
        if targets.loc[targets["year"] == year, "week"].tolist() != list(range(1, 53)):
            raise ValueError("DATASET_ERROR: Validation/test must each contain two complete 52-period source years.")
    return {
        "train": np.flatnonzero(targets["year"].to_numpy() < years[-4]),
        "validation": np.flatnonzero(targets["year"].isin(years[-4:-2]).to_numpy()),
        "test": np.flatnonzero(targets["year"].isin(years[-2:]).to_numpy()),
    }


def case_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | int]:
    actual, predicted = np.asarray(actual).reshape(-1), np.asarray(predicted).reshape(-1)
    available = np.isfinite(predicted)
    if not available.any():
        return {"rows": 0}
    error = predicted[available] - actual[available]
    return {"rows": int(available.sum()), "mae_cases": float(np.abs(error).mean()), "rmse_cases": float(np.sqrt(np.square(error).mean()))}


def _model_path(area: str | None = None) -> Path:
    _require_city(area)
    return MODEL_DIR / "lstm_dengue_city.pt"


def _load_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Trained model file not found: {path}")
    artifact = torch.load(path, map_location="cpu", weights_only=False)
    if artifact.get("artifact_version") != ARTIFACT_VERSION:
        raise ValueError("MODEL_NOT_READY: Legacy artifact lacks the validated city evaluation schema. Retraining is required.")
    if artifact.get("feature_names") != FEATURE_NAMES or artifact.get("target_name") != "cases_city":
        raise ValueError("MODEL_NOT_READY: Artifact feature/target schema is incompatible.")
    if artifact.get("source_sha256") != hashlib.sha256(XLSX_PATH.read_bytes()).hexdigest():
        raise ValueError("MODEL_NOT_READY: Source workbook changed after training. Retraining is required.")
    return artifact


def train_lstm_model(area: str | None = None, sequence_length: int = SEQUENCE_LENGTH, epochs: int = 80,
                     batch_size: int = 16, hidden_size: int = 64, seed: int = 42,
                     patience: int = 15, output_dir: Path | None = None) -> dict[str, Any]:
    if min(epochs, batch_size, hidden_size, patience) < 1:
        raise ValueError("epochs, batch_size, hidden_size, and patience must be positive.")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    X, y, feature_names, history, target_name, area_label = build_sequence_dataset(area, sequence_length)
    targets = history.iloc[sequence_length:].reset_index(drop=True)
    splits = chronological_splits(targets)
    train, validation = splits["train"], splits["validation"]
    x_scaler = MinMaxScaler().fit(X[train].reshape(-1, X.shape[-1]))
    y_scaler = MinMaxScaler().fit(y[train])
    # All transforms use scalers fitted on training observations only.
    xs = torch.from_numpy(x_scaler.transform(X.reshape(-1, X.shape[-1])).reshape(X.shape).astype(np.float32))
    ys = torch.from_numpy(y_scaler.transform(y).astype(np.float32))
    model = DengueLSTM(len(feature_names), hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()
    best_state, best_mae, best_epoch, stale = None, float("inf"), 0, 0
    trace = []
    for epoch in range(1, epochs + 1):
        model.train()
        permutation = train[torch.randperm(len(train)).numpy()]
        for start in range(0, len(train), batch_size):
            index = permutation[start:start + batch_size]
            optimizer.zero_grad()
            loss = loss_fn(model(xs[index]), ys[index])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            val_predictions = np.maximum(0.0, y_scaler.inverse_transform(model(xs[validation]).numpy()))
        val_mae = case_metrics(y[validation], val_predictions)["mae_cases"]
        trace.append({"epoch": epoch, "validation_mae_cases": val_mae})
        if val_mae < best_mae:
            best_state, best_mae, best_epoch, stale = copy.deepcopy(model.state_dict()), val_mae, epoch, 0
        else:
            stale += 1
        if stale >= patience:
            break
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        lstm_predictions = np.maximum(0.0, y_scaler.inverse_transform(model(xs).numpy())).reshape(-1)
    prediction_frame = targets[["year", "week", "period", "cases_city"]].rename(columns={"cases_city": "actual_cases"}).copy()
    prediction_frame["calendar_week_start"] = None  # Source did not provide dates.
    prediction_frame["lstm_cases"] = lstm_predictions
    prediction_frame["last_observation_cases"] = X[:, -1, feature_names.index("cases_city")]
    case_lookup = dict(zip(history["period_index"], history["cases_city"]))
    prediction_frame["seasonal_52_cases"] = [case_lookup.get(int(period) - 52, np.nan) for period in targets["period_index"]]
    prediction_frame["source_sha256"] = history.attrs["provenance"]["sha256"]
    prediction_frame["week_convention"] = WEEK_CONVENTION
    methods = {"lstm": "lstm_cases", "last_observation": "last_observation_cases", "seasonal_52": "seasonal_52_cases"}
    metrics, split_metadata = {}, {}
    for split, index in splits.items():
        prediction_frame.loc[index, "split"] = split
        metrics[split] = {name: case_metrics(y[index], prediction_frame[column].iloc[index].to_numpy()) for name, column in methods.items()}
        split_metadata[split] = {"rows": len(index), "start_period": targets["period"].iloc[index[0]], "end_period": targets["period"].iloc[index[-1]]}
    # Selection uses validation only. The test set is reported once after selection.
    eligible = {name: score for name, score in metrics["validation"].items() if score["rows"] == len(validation)}
    selected_method = min(eligible, key=lambda name: eligible[name]["mae_cases"])
    prediction_frame["selected_method_cases"] = prediction_frame[methods[selected_method]]
    report = {
        "status": "evaluated", "artifact_version": ARTIFACT_VERSION, "area": area_label,
        "target": target_name, "target_units": "reported city cases per source week", "provenance": history.attrs["provenance"],
        "protocol": {"horizon_periods": 1, "evaluation": "rolling observed-history one-period-ahead; weights and scalers fixed across holdouts",
                     "split_rule": "final two complete source years test; preceding two validation; all earlier eligible targets train",
                     "selection": "lowest validation MAE; LSTM epoch and final method never selected on test",
                     "test_used_in_training_or_selection": False, "scaler_fit": "training inputs and targets only",
                     "baseline_definitions": {"last_observation": "case count in immediately preceding source period", "seasonal_52": "case count 52 source periods earlier (same source week in preceding year)"},
                     "seed_policy": "single prespecified seed; no seed search"},
        "configuration": {"sequence_length": sequence_length, "hidden_size": hidden_size, "layers": 2, "dropout": 0.2,
                          "learning_rate": 0.001, "batch_size": batch_size, "maximum_epochs": epochs, "patience": patience,
                          "seed": seed, "device": "cpu", "threads": 1, "best_epoch": best_epoch, "epochs_run": len(trace)},
        "features": feature_names, "splits": split_metadata, "metrics": metrics, "selected_method": selected_method,
        "lstm_beats_last_observation_on_test_mae": metrics["test"]["lstm"]["mae_cases"] < metrics["test"]["last_observation"]["mae_cases"],
        "fit_scope": "training split only; no full-history refit", "trained_target_through": split_metadata["train"]["end_period"],
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "torch": torch.__version__, "sklearn": sklearn.__version__},
        "limitations": LIMITATIONS, "validation_trace": trace,
    }
    checkpoint = {"artifact_version": ARTIFACT_VERSION, "model_state": model.state_dict(), "x_scaler": x_scaler,
                  "y_scaler": y_scaler, "feature_names": feature_names, "target_name": target_name,
                  "sequence_length": sequence_length, "hidden_size": hidden_size, "area": area_label,
                  "source_sha256": report["provenance"]["sha256"], "evaluation": report}
    path = _model_path(area)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    torch.save(checkpoint, temporary)
    os.replace(temporary, path)
    destination = Path(output_dir) if output_dir is not None else OUTPUT_DIR
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "model_card.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    prediction_frame.to_csv(destination / "holdout_predictions.csv", index=False)
    return {"status": "trained", "area": area_label, "sequence_length": sequence_length,
            "train_rows": len(train), "validation_rows": len(validation), "test_rows": len(splits["test"]),
            "rmse_val": metrics["validation"]["lstm"]["rmse_cases"], "metric_units": "cases",
            "selected_method": selected_method, "metrics": metrics, "splits": split_metadata,
            "model_path": str(path), "report_path": str(destination / "model_card.json")}


def _ensure_artifact(area: str | None, sequence_length: int) -> dict[str, Any]:
    _require_city(area)
    try:
        artifact = _load_artifact(_model_path(area))
        if artifact["sequence_length"] != sequence_length:
            raise ValueError("MODEL_NOT_READY: Requested sequence length differs from the evaluated artifact.")
        return artifact
    except (FileNotFoundError, AttributeError, RuntimeError, TypeError, ValueError, KeyError) as exc:
        if os.getenv("SKIP_TRAINING") == "1":
            raise RuntimeError(f"MODEL_NOT_READY: Compatible city artifact unavailable and training disabled. {exc}") from exc
        train_lstm_model(area=area, sequence_length=sequence_length)
        return _load_artifact(_model_path(area))


def load_trained_model(area: str | None = None, sequence_length: int = SEQUENCE_LENGTH) -> dict[str, Any]:
    artifact = _ensure_artifact(area, sequence_length)
    return {"status": "loaded", "area": artifact["area"], "sequence_length": artifact["sequence_length"],
            "feature_names": artifact["feature_names"], "target_name": artifact["target_name"],
            "model_path": str(_model_path(area)), "selected_method": artifact["evaluation"]["selected_method"]}


def _forecast_window(sequence_df: pd.DataFrame, feature_names: list[str], target_name: str, model: DengueLSTM,
                     x_scaler: MinMaxScaler, y_scaler: MinMaxScaler, sequence_length: int, weeks: int) -> tuple[list[dict[str, Any]], list[str]]:
    window = sequence_df[feature_names].tail(sequence_length).copy().reset_index(drop=True)
    predictions = []
    latest_rain = float(window["rainfall_mm"].iloc[-1])
    for step in range(weeks):
        values = x_scaler.transform(window[feature_names].to_numpy(dtype=float))
        with torch.no_grad():
            value_scaled = model(torch.tensor(values.reshape(1, sequence_length, len(feature_names)), dtype=torch.float32)).item()
        prediction = max(0.0, float(y_scaler.inverse_transform([[value_scaled]])[0, 0]))
        predictions.append({"week": step + 1, "predicted_cases": round(prediction, 2)})
        next_row = window.iloc[-1].copy()
        next_row[target_name], next_row["rainfall_mm"] = prediction, latest_rain
        # Compute lags before discarding the oldest row (lag=1 means last observation).
        for lag in [4, 8]:
            next_row[f"rain_lag{lag}w"] = window["rainfall_mm"].iloc[-lag]
            next_row[f"city_lag{lag}w"] = window["cases_city"].iloc[-lag]
        window = pd.concat([window.iloc[1:], pd.DataFrame([next_row])], ignore_index=True)
    return predictions, ["LSTM future rainfall is held at its latest observed value; this is a scenario assumption, not a weather forecast.",
                         "LSTM case predictions are fed recursively into later inputs; horizons beyond one period have not been evaluated."]


def forecast_next_weeks(weeks: int = 8, area: str | None = None, sequence_length: int = SEQUENCE_LENGTH) -> dict[str, Any]:
    if not 1 <= weeks <= 24:
        raise ValueError("weeks must be between 1 and 24")
    _require_city(area)
    artifact = _ensure_artifact(area, sequence_length)
    history = load_city_series()
    selected = artifact["evaluation"]["selected_method"]
    if selected == "lstm":
        model = DengueLSTM(len(FEATURE_NAMES), artifact["hidden_size"])
        model.load_state_dict(artifact["model_state"])
        model.eval()
        predictions, assumptions = _forecast_window(history, FEATURE_NAMES, "cases_city", model, artifact["x_scaler"], artifact["y_scaler"], sequence_length, weeks)
    else:
        predictions = []
        for step in range(weeks):
            value = float(history["cases_city"].iloc[-1] if selected == "last_observation" else history["cases_city"].iloc[-52 + step])
            predictions.append({"week": step + 1, "predicted_cases": round(value, 2)})
        assumptions = ["The forecast method was selected using validation MAE, not test error.",
                       "Last-observation forecasts hold the latest case count constant." if selected == "last_observation" else "Seasonal forecasts repeat the case count from the same source week of the preceding year.",
                       "Only rolling one-period-ahead accuracy was evaluated; multi-period accuracy is unverified."]
    last_index = int(history["period_index"].iloc[-1])
    for step, prediction in enumerate(predictions, 1):
        year, week0 = divmod(last_index + step, 52)
        prediction.update({"target_year": year, "target_week": week0 + 1, "target_period": f"{year}-W{week0 + 1:02d}", "calendar_week_start": None})
    return {"is_demo": False, "model_status": "retrospectively_evaluated_city_only", "model": {"lstm": "LSTM Time-Series Forecast", "last_observation": "Last-observation baseline", "seasonal_52": "Seasonal 52-period baseline"}[selected],
            "selected_method": selected, "prediction_scope": "Quezon City (All)", "target_name": "cases_city",
            "feature_names": FEATURE_NAMES if selected == "lstm" else ["cases_city"],
            "last_observed": {"year": int(history["year"].iloc[-1]), "week": int(history["week"].iloc[-1]),
                              "period": history["period"].iloc[-1], "rainfall_mm": float(history["rainfall_mm"].iloc[-1]), "cases": int(history["cases_city"].iloc[-1])},
            "forecast_weeks": weeks, "predictions": predictions, "sequence_length": sequence_length,
            "assumptions": assumptions, "limitations": LIMITATIONS, "week_convention": WEEK_CONVENTION,
            "provenance": history.attrs["provenance"], "evaluation": {"metrics": artifact["evaluation"]["metrics"], "splits": artifact["evaluation"]["splits"]}}


def get_lstm_summary(area: str | None = None) -> dict[str, Any]:
    _require_city(area)
    df = load_city_series()
    return {"area": "Quezon City (All)", "rows": len(df), "raw_rows": df.attrs["provenance"]["raw_rows"],
            "start_year": int(df["year"].min()), "end_year": int(df["year"].max()),
            "last_week_cases": int(df["cases_city"].iloc[-1]), "feature_columns": FEATURE_NAMES,
            "sequence_length": SEQUENCE_LENGTH, "model_path": str(_model_path(area)),
            "week_convention": WEEK_CONVENTION, "limitations": LIMITATIONS}


def get_supported_areas() -> list[str]:
    return ["Quezon City (All)"]


if __name__ == "__main__":
    print(json.dumps(train_lstm_model(), indent=2))
