"""District-level Bayesian Network for DengueSense QC synthetic model testing.

The model uses the integrated district-week testing workbook and preserves the
supplied fractional dengue values. Risk classes are project test labels:
Below / Alert / Epidemic. They are derived from training-only district-level
percentiles and are not official DOH outbreak thresholds.
"""
from __future__ import annotations

import os
import threading
from typing import Any

import numpy as np
import pandas as pd
from pgmpy.estimators import BayesianEstimator
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.inference import VariableElimination
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from models.district_lstm_model import forecast_next_week, predict_sequence_frame
from services.district_weekly_data_service import (
    DistrictWeeklyDataError,
    get_training_data_status,
    load_district_weekly_data,
)


TEST_YEAR = int(os.getenv("DENGUE_BN_TEST_YEAR", "2023"))
ESS = 10

CLASS_ORDER = ["Below", "Alert", "Epidemic"]
RISK_TO_VISUAL = {"Below": "low", "Alert": "medium", "Epidemic": "high"}
LEVEL_ORDER = ["Low", "Moderate", "High"]
RAIN_LABELS = ["Very_Light", "Light", "Moderate", "Heavy"]
DISTRICT_ORDER = ["I", "II", "III", "IV", "V", "VI"]
TARGET_COL = "risk_class"

RAIN_BINS = [-np.inf, 25, 100, 200, np.inf]

NUMERIC_FEATURE_SOURCES = {
    "min_temperature": "minimum_temperature",
    "max_temperature": "maximum_temperature",
    "humidity": "humidity",
    "wind_temperature": "wind_temperature",
    "wind_speed": "wind_speed",
    "mean_diurnal_range": "mean_diurnal_range",
    "isothermality": "isothermality",
    "ndvi": "ndvi",
    "pdsi": "palmer_drought_severity_index",
    "nighttime_light_intensity": "nighttime_light_intensity",
    "population_density": "population_density",
    "number_of_households": "number_of_households",
    "poverty_incidence": "poverty_incidence",
    "income": "income",
    "employment_status": "employment_status",
    "health_expenditure": "health_expenditure",
    "literacy_rate": "literacy_rate",
    "solid_waste_generation": "solid_waste_generation",
    "solid_waste_collection": "solid_waste_collection",
}

BASIC_FEATURE_COLS = [
    "district_id",
    "historical_dengue_cases",
    "min_temperature",
    "max_temperature",
    "humidity",
    "rainfall",
    "flood_incidence",
]

ADVANCED_FEATURE_COLS = [
    "wind_temperature",
    "wind_speed",
    "mean_diurnal_range",
    "isothermality",
    "ndvi",
    "pdsi",
    "nighttime_light_intensity",
    "gender",
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

FEATURE_COLS = BASIC_FEATURE_COLS + ADVANCED_FEATURE_COLS
LSTM_FEATURE = "lstm_forecast"
WITH_LSTM_FEATURE_COLS = FEATURE_COLS + [LSTM_FEATURE]


def _meta(label: str, mode: str, choices: list[str], description: str, feature_type: str = "level") -> dict[str, Any]:
    return {
        "label": label,
        "mode": mode,
        "type": feature_type,
        "choices": choices,
        "description": description,
    }


FEATURE_META: dict[str, dict[str, Any]] = {
    "district_id": _meta("District", "basic", DISTRICT_ORDER, "Quezon City district used as model context.", "district"),
    "historical_dengue_cases": _meta(
        "Previous-week dengue burden", "basic", CLASS_ORDER,
        "Previous supplied district-week dengue value categorized using training-only district thresholds.", "risk"
    ),
    "min_temperature": _meta("Minimum temperature", "basic", LEVEL_ORDER, "Training-tertile category of weekly minimum temperature."),
    "max_temperature": _meta("Maximum temperature", "basic", LEVEL_ORDER, "Training-tertile category of weekly maximum temperature."),
    "humidity": _meta("Humidity", "basic", LEVEL_ORDER, "Training-tertile category of weekly humidity."),
    "rainfall": _meta("Rainfall", "basic", RAIN_LABELS, "Weekly rainfall category using fixed millimetre bands.", "rain"),
    "flood_incidence": _meta("Flood incidence", "basic", ["None", "Moderate", "High"], "Zero versus training-derived positive incident levels.", "count"),
    "wind_temperature": _meta("Wind temperature", "advanced", LEVEL_ORDER, "Training-tertile category of wind temperature."),
    "wind_speed": _meta("Wind speed", "advanced", LEVEL_ORDER, "Training-tertile category of wind speed."),
    "mean_diurnal_range": _meta("Mean diurnal range", "advanced", LEVEL_ORDER, "Training-tertile category of mean diurnal temperature range."),
    "isothermality": _meta("Isothermality", "advanced", LEVEL_ORDER, "Training-tertile category of isothermality."),
    "ndvi": _meta("NDVI", "advanced", LEVEL_ORDER, "Training-tertile category of NDVI."),
    "pdsi": _meta("Palmer drought severity index", "advanced", LEVEL_ORDER, "Training-tertile category of the supplied PDSI value."),
    "nighttime_light_intensity": _meta("Nighttime light intensity", "advanced", LEVEL_ORDER, "Training-tertile category of nighttime light intensity."),
    "gender": _meta("Population sex majority", "advanced", ["Male", "Female"], "Whether the supplied male or female district population is larger.", "category"),
    "population_density": _meta("Population density", "advanced", LEVEL_ORDER, "Training-tertile category of population density."),
    "number_of_households": _meta("Number of households", "advanced", LEVEL_ORDER, "Training-tertile category of household count."),
    "poverty_incidence": _meta("Poverty incidence", "advanced", LEVEL_ORDER, "Training-tertile category of poverty incidence."),
    "income": _meta("Income", "advanced", LEVEL_ORDER, "Training-tertile category of income."),
    "employment_status": _meta("Employment status", "advanced", LEVEL_ORDER, "Training-tertile category of the supplied employment-status measure."),
    "health_expenditure": _meta("Health expenditure", "advanced", LEVEL_ORDER, "Training-tertile category of health expenditure."),
    "literacy_rate": _meta("Literacy rate", "advanced", LEVEL_ORDER, "Training-tertile category of literacy rate."),
    "fogging": _meta("Fogging", "advanced", ["None", "Moderate", "High"], "Zero versus training-derived positive fogging levels.", "count"),
    "solid_waste_generation": _meta("Solid waste generation", "advanced", LEVEL_ORDER, "Training-tertile category of solid waste generation."),
    "solid_waste_collection": _meta("Solid waste collection", "advanced", LEVEL_ORDER, "Training-tertile category of solid waste collection."),
    "lstm_forecast": _meta(
        "LSTM next-week forecast", "internal", CLASS_ORDER,
        "District LSTM next-week case forecast categorized with the same training-only district thresholds.", "risk"
    ),
}


# Two trained Bayesian configurations are maintained side by side. The legacy
# aliases bn_model/inference point to the BN-without-LSTM configuration for
# compatibility with existing health checks and imports.
bn_model: DiscreteBayesianNetwork | None = None
inference: VariableElimination | None = None
bn_model_with_lstm: DiscreteBayesianNetwork | None = None
inference_with_lstm: VariableElimination | None = None
history_df: pd.DataFrame | None = None

# Learned strictly from the training partition.
district_case_thresholds: dict[str, tuple[float, float]] = {}
global_case_thresholds: tuple[float, float] | None = None
feature_thresholds: dict[str, tuple[float, float]] = {}
positive_count_thresholds: dict[str, float] = {}

_bn_lock = threading.Lock()
TRAINED_FEATURE_COLS: list[str] = []
TRAINED_FEATURE_COLS_WITH_LSTM: list[str] = []
training_metadata: dict[str, Any] = {}


def get_model_metadata() -> dict[str, Any]:
    return {
        "task": "district_level_risk_classification",
        "is_future_forecast": False,
        "target_data": "synthetic_testing_district_week_fractional_dengue_values",
        "risk_labels": CLASS_ORDER,
        "threshold_method": "training-only district 33rd and 66th percentiles over unique district-year dengue levels",
        "thresholds_are_official_doh": False,
        "threshold_scope": "district-specific project testing thresholds",
        "geographic_level": "district",
        "trained_feature_keys": list(TRAINED_FEATURE_COLS),
        "trained_feature_keys_with_lstm": list(TRAINED_FEATURE_COLS_WITH_LSTM),
        "bayesian_configurations": ["BN without LSTM forecast", "BN with LSTM forecast"],
        "lstm_forecast_feature": LSTM_FEATURE,
        "synthetic_values_used_for_training_and_testing": True,
        "limitations": [
            "This workbook is explicitly synthetic/simulated and is for software and model testing only.",
            "Historical dengue values are fractional district-week values derived from source data, not observed integer weekly surveillance counts.",
            "Below / Alert / Epidemic are project testing labels derived from training percentiles; they are not official DOH alert or epidemic thresholds.",
            "The BN without LSTM is a contemporaneous district risk classifier; the BN with LSTM adds a one-week district LSTM forecast as model evidence.",
            "The LSTM and both Bayesian configurations are synthetic-testing models, not validated operational outbreak forecasting systems.",
        ],
        **training_metadata,
    }


def ensure_bn_ready() -> None:
    global bn_model, inference, bn_model_with_lstm, inference_with_lstm
    if (
        bn_model is not None
        and inference is not None
        and bn_model_with_lstm is not None
        and inference_with_lstm is not None
    ):
        return
    with _bn_lock:
        if (
            bn_model is not None
            and inference is not None
            and bn_model_with_lstm is not None
            and inference_with_lstm is not None
        ):
            return
        if os.getenv("SKIP_TRAINING") == "1":
            raise RuntimeError("MODEL_NOT_READY: Training is disabled and no model is available.")
        train_model()


def rain_cat_value(mm: float) -> str:
    value = float(mm)
    if value < 25:
        return "Very_Light"
    if value < 100:
        return "Light"
    if value < 200:
        return "Moderate"
    return "Heavy"


def case_cat_value(value: float, thresholds: tuple[float, float] | None) -> str:
    if thresholds is None:
        raise RuntimeError("Case thresholds are not ready. Train the model first.")
    p33, p66 = thresholds
    value = float(value)
    if value < p33:
        return "Below"
    if value <= p66:
        return "Alert"
    return "Epidemic"


def _level_cat_value(value: float, thresholds: tuple[float, float]) -> str:
    p33, p66 = thresholds
    value = float(value)
    if value < p33:
        return "Low"
    if value <= p66:
        return "Moderate"
    return "High"


def _positive_count_cat(value: float, split: float) -> str:
    value = float(value)
    if value <= 0:
        return "None"
    if value <= split:
        return "Moderate"
    return "High"


def _normalize_choice(value: Any, allowed: list[str]) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lookup = {choice.lower().replace("_", " "): choice for choice in allowed}
    lookup.update({choice.lower(): choice for choice in allowed})
    key = text.lower().replace("_", " ")
    return lookup.get(key)


def normalize_district(value: Any) -> str:
    text = str(value or "").strip().upper().replace("DISTRICT", "").strip()
    number_to_roman = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}
    text = number_to_roman.get(text, text)
    if text not in DISTRICT_ORDER:
        raise ValueError(f"Invalid district '{value}'. Allowed districts: {DISTRICT_ORDER}")
    return text


def _quantile_threshold(series: pd.Series) -> tuple[float, float]:
    values = pd.to_numeric(series, errors="coerce").dropna().astype(float)
    if values.empty:
        raise DistrictWeeklyDataError("Cannot learn a feature threshold from an empty training series.")
    p33, p66 = values.quantile([0.33, 0.66])
    return float(p33), float(p66)


def _risk_categories(values: pd.Series, p33: pd.Series, p66: pd.Series) -> np.ndarray:
    return np.where(values < p33, "Below", np.where(values <= p66, "Alert", "Epidemic"))


def prepare_training_frame() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Prepare district-level synthetic training and holdout frames.

    The split is temporal: rows before TEST_YEAR are training rows and rows in
    TEST_YEAR onward are holdout rows. All thresholds are learned from training
    data only. One invalid meteorological source week is excluded, not imputed.
    """
    global district_case_thresholds, global_case_thresholds
    global feature_thresholds, positive_count_thresholds, training_metadata

    source = load_district_weekly_data()
    provenance = dict(source.attrs.get("provenance", {}))
    df = source.copy()

    # Preserve original numeric identities before creating categorical model columns.
    df["district_number"] = df["district_id"].astype(int)
    df["district_id"] = df["district_code"].astype(str)
    df["historical_dengue_cases_raw"] = df["historical_dengue_cases"].astype(float)
    df["historical_dengue_cases_lag1_raw"] = (
        df.groupby("district_id")["historical_dengue_cases_raw"].shift(1)
    )

    df = df[
        df["model_weather_valid"]
        & df["historical_dengue_cases_lag1_raw"].notna()
    ].copy().reset_index(drop=True)

    threshold_rows = df[df["year"] < TEST_YEAR].copy()
    if threshold_rows.empty:
        raise DistrictWeeklyDataError(
            f"No training rows are available before holdout year {TEST_YEAR}."
        )

    # Case thresholds use one dengue value per district-year so ISO week 53 does
    # not give one year extra weight relative to other years.
    annual_levels = threshold_rows.drop_duplicates(["district_id", "year"])
    district_case_thresholds = {}
    for district, group in annual_levels.groupby("district_id"):
        district_case_thresholds[str(district)] = _quantile_threshold(group["historical_dengue_cases_raw"])
    global_case_thresholds = _quantile_threshold(annual_levels["historical_dengue_cases_raw"])

    p33 = df["district_id"].map({k: v[0] for k, v in district_case_thresholds.items()})
    p66 = df["district_id"].map({k: v[1] for k, v in district_case_thresholds.items()})
    if p33.isna().any() or p66.isna().any():
        raise DistrictWeeklyDataError("Every district requires pre-holdout dengue history.")

    df[TARGET_COL] = _risk_categories(df["historical_dengue_cases_raw"], p33, p66)
    df["historical_dengue_cases"] = _risk_categories(
        df["historical_dengue_cases_lag1_raw"], p33, p66
    )

    feature_thresholds = {}
    for feature, source_col in NUMERIC_FEATURE_SOURCES.items():
        thresholds = _quantile_threshold(threshold_rows[source_col])
        feature_thresholds[feature] = thresholds
        df[feature] = df[source_col].map(lambda value, t=thresholds: _level_cat_value(value, t))

    df["rainfall"] = df["rainfall"].map(rain_cat_value)
    df["gender"] = np.where(df["male_population"] >= df["female_population"], "Male", "Female")

    positive_count_thresholds = {}
    for feature in ["flood_incidence", "fogging"]:
        positives = threshold_rows.loc[threshold_rows[feature] > 0, feature].astype(float)
        split = float(positives.median()) if not positives.empty else 0.0
        positive_count_thresholds[feature] = split
        df[feature] = df[feature].map(lambda value, s=split: _positive_count_cat(value, s))

    # Generate the optional LSTM evidence from the separately trained district
    # forecast model. Predictions are aligned by district/year/week. The final
    # 2023+ holdout predictions come from an LSTM fitted only on pre-2023 rows.
    lstm_predictions = predict_sequence_frame()[
        ["district_id", "year", "week", "lstm_predicted_cases", "lstm_prediction_training_status"]
    ].copy()
    df = df.merge(
        lstm_predictions,
        left_on=["district_number", "year", "week"],
        right_on=["district_id", "year", "week"],
        how="left",
        suffixes=("", "_lstm_numeric"),
    )
    if "district_id_lstm_numeric" in df.columns:
        df = df.drop(columns=["district_id_lstm_numeric"])
    df[LSTM_FEATURE] = None
    has_lstm = df["lstm_predicted_cases"].notna()
    df.loc[has_lstm, LSTM_FEATURE] = [
        case_cat_value(value, district_case_thresholds.get(str(district), global_case_thresholds))
        for value, district in zip(
            df.loc[has_lstm, "lstm_predicted_cases"],
            df.loc[has_lstm, "district_id"],
        )
    ]

    df_bn = df[FEATURE_COLS + [TARGET_COL, "year"]].copy()
    train = df_bn[df_bn["year"] < TEST_YEAR][FEATURE_COLS + [TARGET_COL]].reset_index(drop=True)
    test = df_bn[df_bn["year"] >= TEST_YEAR][FEATURE_COLS + [TARGET_COL]].reset_index(drop=True)
    if train.empty or test.empty:
        raise DistrictWeeklyDataError(
            f"Temporal split at {TEST_YEAR} requires both training and holdout rows."
        )

    TRAINED_FEATURE_COLS[:] = FEATURE_COLS
    TRAINED_FEATURE_COLS_WITH_LSTM[:] = WITH_LSTM_FEATURE_COLS
    training_metadata = {
        "data_provenance": provenance,
        "training_rows": int(len(train)),
        "holdout_rows": int(len(test)),
        "holdout_start_year": TEST_YEAR,
        "excluded_invalid_weather_rows": int(provenance.get("invalid_weather_rows_excluded_from_model", 0)),
        "district_case_thresholds": {
            key: {"p33": value[0], "p66": value[1]}
            for key, value in district_case_thresholds.items()
        },
        "feature_thresholds": {
            key: {"p33": value[0], "p66": value[1]}
            for key, value in feature_thresholds.items()
        },
        "positive_count_thresholds": dict(positive_count_thresholds),
        "lstm_feature_rows_available": int(df[LSTM_FEATURE].notna().sum()),
        "lstm_feature_training_rows_available": int(((df["year"] < TEST_YEAR) & df[LSTM_FEATURE].notna()).sum()),
        "lstm_feature_holdout_rows_available": int(((df["year"] >= TEST_YEAR) & df[LSTM_FEATURE].notna()).sum()),
        "evaluation_metrics": None,
    }
    return df, train, test


def _posterior_for_model(model: DiscreteBayesianNetwork, evidence: dict[str, str]) -> dict[str, float]:
    target_cpd = model.get_cpds(TARGET_COL)
    target_states = list(target_cpd.state_names[TARGET_COL])
    priors = {state: float(prob) for state, prob in zip(target_states, target_cpd.values)}
    scores = priors.copy()
    for feature, value in evidence.items():
        feature_cpd = model.get_cpds(feature)
        for cls in target_states:
            scores[cls] *= float(feature_cpd.get_value(**{feature: value, TARGET_COL: cls}))
    total = sum(scores.values())
    if total <= 0:
        prior_total = sum(priors.values())
        return {cls: priors.get(cls, 0.0) / prior_total for cls in CLASS_ORDER}
    return {cls: scores.get(cls, 0.0) / total for cls in CLASS_ORDER}


def _evaluate_model(
    model: DiscreteBayesianNetwork,
    test: pd.DataFrame,
    feature_cols: list[str],
    *,
    configuration: str,
) -> dict[str, Any]:
    truth: list[str] = []
    predicted: list[str] = []
    for _, row in test.iterrows():
        evidence = {feature: str(row[feature]) for feature in feature_cols}
        probabilities = _posterior_for_model(model, evidence)
        truth.append(str(row[TARGET_COL]))
        predicted.append(max(probabilities, key=probabilities.get))
    matrix = confusion_matrix(truth, predicted, labels=CLASS_ORDER)
    return {
        "configuration": configuration,
        "dataset_scope": "synthetic_testing_holdout",
        "accuracy": float(accuracy_score(truth, predicted)),
        "macro_f1": float(f1_score(truth, predicted, labels=CLASS_ORDER, average="macro", zero_division=0)),
        "rows": int(len(test)),
        "labels": CLASS_ORDER,
        "confusion_matrix": matrix.astype(int).tolist(),
        "claim_limit": "Testing metric only; not empirical thesis performance or operational validation.",
    }


def _fit_bn(train: pd.DataFrame, feature_cols: list[str]) -> DiscreteBayesianNetwork:
    model = DiscreteBayesianNetwork([(TARGET_COL, feature) for feature in feature_cols])
    states = {
        TARGET_COL: CLASS_ORDER,
        **{feature: FEATURE_META[feature]["choices"] for feature in feature_cols},
    }
    estimator = BayesianEstimator(model, train, state_names=states)
    model.add_cpds(*estimator.get_parameters(prior_type="BDeu", equivalent_sample_size=ESS))
    if not model.check_model():
        raise RuntimeError("Model failed validity check.")
    return model


def train_model() -> VariableElimination:
    global bn_model, inference, bn_model_with_lstm, inference_with_lstm, history_df, training_metadata
    df, train, test = prepare_training_frame()

    model_without = _fit_bn(train, TRAINED_FEATURE_COLS)
    eval_without = _evaluate_model(
        model_without, test, TRAINED_FEATURE_COLS, configuration="BN without LSTM forecast"
    )

    with_lstm_columns = TRAINED_FEATURE_COLS_WITH_LSTM + [TARGET_COL]
    train_with = df.loc[
        (df["year"] < TEST_YEAR) & df[LSTM_FEATURE].notna(),
        with_lstm_columns,
    ].reset_index(drop=True)
    test_with = df.loc[
        (df["year"] >= TEST_YEAR) & df[LSTM_FEATURE].notna(),
        with_lstm_columns,
    ].reset_index(drop=True)
    if train_with.empty or test_with.empty:
        raise RuntimeError("MODEL_NOT_READY: LSTM-aligned rows are required for the BN with LSTM configuration.")

    model_with = _fit_bn(train_with, TRAINED_FEATURE_COLS_WITH_LSTM)
    eval_with = _evaluate_model(
        model_with, test_with, TRAINED_FEATURE_COLS_WITH_LSTM, configuration="BN with LSTM forecast"
    )

    bn_model = model_without
    inference = VariableElimination(model_without)
    bn_model_with_lstm = model_with
    inference_with_lstm = VariableElimination(model_with)
    training_metadata = {
        **training_metadata,
        "evaluation_metrics": {
            "without_lstm": eval_without,
            "with_lstm": eval_with,
        },
        "bn_without_lstm_training_rows": int(len(train)),
        "bn_with_lstm_training_rows": int(len(train_with)),
        "bn_without_lstm_holdout_rows": int(len(test)),
        "bn_with_lstm_holdout_rows": int(len(test_with)),
    }
    history_df = df.copy()
    return inference


def posterior_from_evidence(evidence: dict[str, str], *, use_lstm_forecast: bool = False) -> dict[str, float]:
    model = bn_model_with_lstm if use_lstm_forecast else bn_model
    if model is None:
        raise RuntimeError("Model not trained.")
    return _posterior_for_model(model, evidence)


def validate_evidence(evidence: dict[str, Any]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in evidence.items():
        if value is None or str(value).strip() == "":
            continue
        if key not in FEATURE_COLS:
            raise ValueError(f"Unknown evidence key '{key}'. Allowed keys: {FEATURE_COLS}")
        allowed = FEATURE_META[key]["choices"]
        normalized = _normalize_choice(value, allowed)
        if normalized is None:
            raise ValueError(f"Invalid value '{value}' for '{key}'. Allowed: {allowed}")
        cleaned[key] = normalized
    return cleaned


def what_if(
    evidence: dict[str, Any] | None = None,
    district_context: str | None = None,
    *,
    use_lstm_forecast: bool = False,
) -> dict[str, Any]:
    supplied = dict(evidence or {})
    simulation = supplied.pop("_sim", None)
    if simulation:
        raise ValueError(
            "UNSUPPORTED_ENVIRONMENTAL_SCENARIO: Manual probability adjustments are not applied; "
            "use factors trained from the integrated workbook."
        )

    ensure_bn_ready()
    cleaned = validate_evidence(supplied)
    district = None
    if district_context not in (None, ""):
        district = normalize_district(district_context)
        if "district_id" in cleaned and cleaned["district_id"] != district:
            raise ValueError("District context conflicts with district_id evidence.")
        cleaned["district_id"] = district
    elif "district_id" in cleaned:
        district = cleaned["district_id"]

    lstm_details = None
    model_evidence = dict(cleaned)
    if use_lstm_forecast:
        if not district:
            raise ValueError("District context is required for BN with LSTM forecast.")
        lstm_details = forecast_next_week(district)
        thresholds = district_case_thresholds.get(district, global_case_thresholds)
        lstm_class = case_cat_value(lstm_details["predicted_cases"], thresholds)
        model_evidence[LSTM_FEATURE] = lstm_class
        lstm_details = {**lstm_details, "forecast_class": lstm_class}

    probabilities = posterior_from_evidence(model_evidence, use_lstm_forecast=use_lstm_forecast)
    map_label = max(probabilities, key=probabilities.get)
    metadata = get_model_metadata()
    feature_cols = TRAINED_FEATURE_COLS_WITH_LSTM if use_lstm_forecast else TRAINED_FEATURE_COLS
    configuration = "BN with LSTM forecast" if use_lstm_forecast else "BN without LSTM forecast"
    return {
        "is_demo": False,
        "model_status": "synthetic_test_fit",
        "model_type": configuration,
        "model_configuration": configuration,
        "uses_lstm_forecast": bool(use_lstm_forecast),
        "prediction_scope": "District-level dengue risk classification",
        "threshold_scope": metadata["threshold_scope"],
        "probabilities": probabilities,
        "map_label": map_label,
        "map_key": RISK_TO_VISUAL[map_label],
        "risk_level": map_label,
        "confidence": probabilities[map_label],
        "evidence": model_evidence,
        "evidence_count": len(model_evidence),
        "feature_count": len(feature_cols),
        "lstm_forecast": lstm_details,
        "limitations": list(metadata["limitations"]),
        "metadata": metadata,
    }

