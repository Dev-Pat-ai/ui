"""Service layer for Bayesian Network predictions and real-data analysis.

This module delegates model logic to models.bn_model while providing
higher-level utilities for dashboard aggregation and real data intake.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

from models import bn_model as bn_state
from models.bn_model import (
    FEATURE_COLS, FEATURE_META, TARGET_COL, CLASS_ORDER,
    BASIC_FEATURE_COLS, ADVANCED_FEATURE_COLS,
    ensure_bn_ready, what_if, rain_cat_value, case_cat_value,
    validate_evidence, train_model
)
from services.cpdd_data_service import load_cpdd_reference


prepare_training_frame = bn_state.prepare_training_frame


def build_evidence_from_payload(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    """Build evidence from frontend payload."""
    data = data or {}
    raw_inputs: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    district_context = data.get("district")

    # Direct evidence dictionary from the frontend.
    direct = data.get("evidence") or {}
    if isinstance(direct, dict):
        evidence.update({k: v for k, v in direct.items() if k in FEATURE_COLS})
        simulation = direct.get("_sim")
        if simulation is not None:
            if not isinstance(simulation, dict):
                raise ValueError("Simulation factors must be an object.")
            allowed_simulation = {
                "waste": {"standard", "poor", "efficient"},
                "water": {"no", "yes"},
                "flood": {"no", "yes"},
            }
            simulation_defaults = {"waste": "standard", "water": "no", "flood": "no"}
            cleaned_simulation = {}
            for key, allowed in allowed_simulation.items():
                value = str(simulation.get(key, simulation_defaults[key])).strip().lower()
                if value not in allowed:
                    raise ValueError(f"Invalid simulation value '{value}' for '{key}'.")
                cleaned_simulation[key] = value
            if cleaned_simulation != simulation_defaults:
                raise ValueError("UNSUPPORTED_ENVIRONMENTAL_SCENARIO: Waste, water and flood effects have not been learned from observations.")

    # Direct top-level categorical evidence.
    for key in FEATURE_COLS:
        if key in data and data[key] not in (None, ""):
            evidence[key] = data[key]
            raw_inputs[key] = data[key]

    # Numeric rainfall helpers.
    rainfall_helpers = {
        "rainfall_mm": "rain_wk_cat",
        "rain_lag4w_mm": "rain_lag4w_cat",
        "rain_lag8w_mm": "rain_lag8w_cat",
    }
    for input_key, evidence_key in rainfall_helpers.items():
        if data.get(input_key) not in (None, ""):
            evidence[evidence_key] = rain_cat_value(float(data[input_key]))
            raw_inputs[input_key] = float(data[input_key])

    # Numeric city case helpers.
    city_helpers = {
        "city_cases": "city_wk_cat",
        "city_lag4w_cases": "city_lag4w_cat",
        "city_lag8w_cases": "city_lag8w_cat",
    }
    for input_key, evidence_key in city_helpers.items():
        if data.get(input_key) not in (None, ""):
            ensure_bn_ready()
            evidence[evidence_key] = case_cat_value(float(data[input_key]), bn_state.city_case_thresholds)
            raw_inputs[input_key] = float(data[input_key])

    # Numeric barangay lag case helpers.
    barangay = str(data.get("barangay") or "").strip().title()
    ensure_bn_ready()
    thresholds = bn_state.barangay_thresholds.get(barangay, bn_state.global_barangay_thresholds)

    barangay_helpers = {
        "cases_lag4w": "cases_lag4w_cat",
        "cases_lag8w": "cases_lag8w_cat",
    }
    for input_key, evidence_key in barangay_helpers.items():
        if data.get(input_key) not in (None, ""):
            evidence[evidence_key] = case_cat_value(float(data[input_key]), thresholds)
            raw_inputs[input_key] = float(data[input_key])

    simulation = evidence.pop("_sim", None)
    cleaned = validate_evidence(evidence)
    if simulation is not None:
        cleaned["_sim"] = simulation
    return cleaned, raw_inputs, district_context


def get_feature_info() -> dict[str, Any]:
    ensure_bn_ready()
    return {
        "target": TARGET_COL,
        "class_order": CLASS_ORDER,
        "features": FEATURE_META,
        "feature_order": FEATURE_COLS,
        "basic_feature_order": BASIC_FEATURE_COLS,
        "advanced_feature_order": ADVANCED_FEATURE_COLS,
        "supports_partial_evidence": True,
        "rain_thresholds_mm": {
            "Very_Light": "< 25",
            "Light": "25 to < 100",
            "Moderate": "100 to < 200",
            "Heavy": ">= 200",
        },
        "city_case_thresholds": bn_state.city_case_thresholds,
        "trained_feature_order": list(bn_state.TRAINED_FEATURE_COLS),
        "model_metadata": bn_state.get_model_metadata(),
    }


def get_history(limit: int = 200) -> list[dict[str, Any]]:
    """Return recent historical predictions using full available evidence."""
    from models.bn_model import history_df as hdf
    if hdf is None: return []

    records: list[dict[str, Any]] = []
    cols = ["barangay", "year", "week", "rainfall_mm", "cases_city", "cases_bgy_wk"] + FEATURE_COLS
    recent = hdf[[c for c in cols if c in hdf.columns]].tail(limit).copy()

    for _, row in recent.iterrows():
        ev = {feature: str(row[feature]) for feature in bn_state.TRAINED_FEATURE_COLS if feature in row and pd.notna(row[feature])}
        try:
            result = what_if(ev)
        except Exception: continue
        probs = result["probabilities"]
        records.append({
            "barangay": str(row.get("barangay", "Quezon City")),
            "year": int(row["year"]),
            "week": int(row["week"]),
            "rainfall": round(float(row["rainfall_mm"]), 1) if "rainfall_mm" in row else None,
            "city_cases": int(round(float(row.get("cases_city", 0)))),
            "estimated_barangay_cases": round(float(row.get("cases_bgy_wk", 0)), 2),
            "observed_barangay_cases": int(row["cases_bgy_wk"]),
            "is_estimated": False,
            "risk": result["map_label"],
            "prob_low": round(probs.get("Low", 0) * 100, 1),
            "prob_med": round(probs.get("Medium", 0) * 100, 1),
            "prob_high": round(probs.get("High", 0) * 100, 1),
            "evidence_used": ev,
        })

    records.reverse()
    return records


def _barangay_match_key(name: Any) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s*\([^)]*\)", "", text).casefold()
    key = re.sub(r"[^a-z0-9]", "", text)
    aliases = {
        "aurora": "donaaurora",
        "balongbato": "balonbato",
        "santodomingo": "stodomingo",
        "santonino": "santonio",
    }
    return aliases.get(key, key)


def get_real_dashboard_data() -> dict[str, Any]:
    """Aggregate real epidemiological data for the dashboard view."""
    ensure_bn_ready()
    from models.bn_model import history_df as hdf
    if hdf is None: return {}

    # 1. Latest Week Data
    latest_row = hdf.sort_values(["year", "week"]).iloc[-1]
    # 2. District Aggregation
    cpdd = load_cpdd_reference()
    district_list = []
    
    latest_week_data = hdf[(hdf["year"] == latest_row["year"]) & (hdf["week"] == latest_row["week"])]
    available_weeks = hdf[["year", "week"]].drop_duplicates().sort_values(["year", "week"])
    previous_period = available_weeks.iloc[-2] if len(available_weeks) > 1 else available_weeks.iloc[-1]
    previous_week_data = hdf[
        (hdf["year"] == previous_period["year"]) & (hdf["week"] == previous_period["week"])
    ]
    latest_keys = latest_week_data["barangay"].map(_barangay_match_key)
    previous_keys = previous_week_data["barangay"].map(_barangay_match_key)
    
    for dist_id, dist_info in cpdd["districts"].items():
        bgy_keys = {_barangay_match_key(b["barangay_name"]) for b in dist_info["barangays"]}
        dist_df = latest_week_data[latest_keys.isin(bgy_keys)]
        previous_dist_df = previous_week_data[previous_keys.isin(bgy_keys)]
        
        dist_cases = int(dist_df["cases_bgy_wk"].sum())
        prev_dist_cases = int(previous_dist_df["cases_bgy_wk"].sum())
        
        # Determine District Risk by evaluating each barangay in the district and taking the mode/max risk
        bgy_risks = []
        for _, bgy_row in dist_df.iterrows():
            bgy_ev = {feature: bgy_row[feature] for feature in bn_state.TRAINED_FEATURE_COLS}
            try:
                res = what_if(bgy_ev)
                bgy_risks.append(res["map_label"])
            except: continue
        
        # Aggregate Risk: Use "High" if any high exists, else "Medium" if any medium exists, else "Low"
        if "High" in bgy_risks:
            final_risk = "high"
        elif "Medium" in bgy_risks:
            final_risk = "medium"
        else:
            final_risk = "low"
        
        district_list.append({
            "district": dist_info["name"],
            "population_2020": dist_info["population_2020"],
            "barangay_count": dist_info["barangay_count"],
            "sampleCases": dist_cases,
            "prevCases": prev_dist_cases,
            "risk": final_risk,
            "forecast": None,
        })

    return {
        "is_sample": False,
        "is_experimental": True,
        "is_estimated": False,
        "data_provenance": {
            "weekly_barangay_cases": "Observed weekly barangay counts from the validated training input.",
            "risk": "Project percentile-based burden categories; district label is the highest barangay label, not a validated outbreak threshold.",
            "forecast": "District forecasts are unavailable until separately evaluated on observed district targets.",
        },
        "sample_updated_at": f"{int(latest_row['year'])}-W{int(latest_row['week'])}",
        "prototype_version": "1.5.0-final",
        "districts": district_list,
        "alerts": [
            {
                "level": "medium",
                "title": "Rainfall Alert",
                "description": f"Latest observed rainfall category: {latest_row.get('rain_wk_cat', 'unavailable').replace('_', ' ')}.",
                "time": "Active"
            }
        ] if "rain_wk_cat" in latest_row else []
    }
