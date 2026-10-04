"""Validated intake for the integrated synthetic district-week dengue workbook.

The active Bayesian model is intentionally district-level because the supplied
workbook is district-level. Fractional historical dengue values are preserved
as supplied; they are not rounded into invented surveillance counts.
"""
from __future__ import annotations

from pathlib import Path
import os
from typing import Any

import numpy as np
import pandas as pd

from utils.path_utils import resolve_data_path


DATASET_FILENAME = "Dengue_Integrated_District_Weekly_Dataset_SYNTHETIC_FILLED.xlsx"
DATASET_SHEET = "Weekly_Master"
DISTRICT_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}

REQUIRED_COLUMNS = [
    "district_id", "district_name", "year", "week", "week_start", "week_end",
    "historical_dengue_cases", "minimum_temperature", "maximum_temperature",
    "humidity", "rainfall", "wind_temperature", "wind_speed",
    "mean_diurnal_range", "isothermality", "ndvi", "flood_incidence",
    "palmer_drought_severity_index", "nighttime_light_intensity",
    "male_population", "female_population", "population_density",
    "number_of_households", "poverty_incidence", "income", "employment_status",
    "health_expenditure", "literacy_rate", "fogging", "solid_waste_generation",
    "solid_waste_collection",
]

NUMERIC_COLUMNS = [c for c in REQUIRED_COLUMNS if c not in {
    "district_name", "week_start", "week_end",
}]


class DistrictWeeklyDataError(RuntimeError):
    def __init__(self, message: str, code: str = "INVALID_DISTRICT_WEEKLY_DATA"):
        self.code = code
        super().__init__(f"{code}: {message}")


def dataset_path() -> Path:
    configured = os.getenv("DENGUE_INTEGRATED_DATASET_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return resolve_data_path(DATASET_FILENAME)


def get_training_data_status() -> dict[str, Any]:
    path = dataset_path()
    return {
        "dataset_path": str(path),
        "dataset_file_exists": path.is_file(),
        "sheet": DATASET_SHEET,
        "geographic_level": "district",
        "dataset_type": "synthetic_testing_copy",
        "fractional_dengue_values_allowed": True,
        "synthetic_values_used_for_training_and_testing": True,
        "validation_status": "not_checked" if path.is_file() else "missing",
        "ready": path.is_file(),
        "reason": (
            "Integrated district-week workbook is available; full validation occurs before model fitting."
            if path.is_file()
            else f"DISTRICT_WEEKLY_DATA_REQUIRED: Add {DATASET_FILENAME} to data/raw or set DENGUE_INTEGRATED_DATASET_PATH."
        ),
        "required_columns": REQUIRED_COLUMNS,
    }


def _fail(message: str, code: str = "INVALID_DISTRICT_WEEKLY_DATA") -> None:
    raise DistrictWeeklyDataError(message, code)


def _validate_iso_dates(df: pd.DataFrame) -> None:
    expected_start = pd.to_datetime([
        pd.Timestamp.fromisocalendar(int(y), int(w), 1)
        for y, w in zip(df["year"], df["week"])
    ])
    expected_end = expected_start + pd.Timedelta(days=6)
    supplied_start = pd.to_datetime(df["week_start"], errors="coerce")
    supplied_end = pd.to_datetime(df["week_end"], errors="coerce")
    if supplied_start.isna().any() or supplied_end.isna().any():
        _fail("week_start and week_end must contain valid ISO dates.")
    if not (supplied_start.reset_index(drop=True) == pd.Series(expected_start)).all():
        _fail("week_start does not match the supplied ISO year/week fields.")
    if not (supplied_end.reset_index(drop=True) == pd.Series(expected_end)).all():
        _fail("week_end must be six days after the ISO week start.")
    df["week_start"] = supplied_start
    df["week_end"] = supplied_end


def load_district_weekly_data(path: Path | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else dataset_path()
    if not path.is_file():
        _fail(
            f"Integrated district-week workbook not found at {path}.",
            "DISTRICT_WEEKLY_DATA_REQUIRED",
        )
    try:
        df = pd.read_excel(path, sheet_name=DATASET_SHEET)
    except Exception as exc:
        _fail(f"Cannot read {DATASET_SHEET}: {exc}")

    if df.empty:
        _fail(f"{DATASET_SHEET} is empty.")
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        _fail(f"Missing required columns: {missing}.")

    df = df.copy()
    for col in NUMERIC_COLUMNS:
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any() or (~np.isfinite(values)).any():
            _fail(f"{col} must be complete and numeric for model intake.")
        df[col] = values

    for col in ["district_id", "year", "week"]:
        if (df[col] % 1 != 0).any():
            _fail(f"{col} must contain integer identifiers.")
        df[col] = df[col].astype("int64")

    if sorted(df["district_id"].unique().tolist()) != [1, 2, 3, 4, 5, 6]:
        _fail("district_id must contain exactly districts 1 through 6.")
    expected_names = {i: f"District {i}" for i in range(1, 7)}
    name_mismatch = df["district_name"].astype(str).str.strip() != df["district_id"].map(expected_names)
    if name_mismatch.any():
        bad = df.loc[name_mismatch, ["district_id", "district_name"]].iloc[0].to_dict()
        _fail(f"District name/id mismatch: {bad}.")
    if ((df["week"] < 1) | (df["week"] > 53)).any():
        _fail("week must be an ISO week number from 1 through 53.")
    if (df["historical_dengue_cases"] < 0).any():
        _fail("historical_dengue_cases cannot be negative.")
    if df.duplicated(["district_id", "year", "week"]).any():
        _fail("Duplicate district/year/week rows were found.")

    _validate_iso_dates(df)

    period_counts = df.groupby(["year", "week"])["district_id"].nunique()
    if not period_counts.eq(6).all():
        first_bad = period_counts[~period_counts.eq(6)].index[0]
        _fail(f"Incomplete six-district panel at {first_bad}.")

    periods = (
        df[["year", "week", "week_start"]]
        .drop_duplicates(["year", "week"])
        .sort_values("week_start")["week_start"]
        .reset_index(drop=True)
    )
    if len(periods) > 1 and not periods.diff().dropna().eq(pd.Timedelta(days=7)).all():
        _fail("The district-week panel must be continuous at seven-day intervals.")

    df["district_code"] = df["district_id"].map(DISTRICT_ROMAN)

    # One supplied meteorological week carries a negative missing-data sentinel
    # that propagated into derived weather fields. Preserve the source values in
    # the workbook, but flag those rows so model preparation can exclude them
    # rather than learning from the sentinel.
    df["model_weather_valid"] = (
        (df["minimum_temperature"] > -100)
        & (df["maximum_temperature"] > -100)
        & (df["humidity"] >= 0)
        & (df["wind_speed"] >= 0)
    )

    df = df.sort_values(["district_id", "week_start"]).reset_index(drop=True)
    df.attrs["provenance"] = {
        "path": str(path.resolve()),
        "sheet": DATASET_SHEET,
        "geographic_level": "district",
        "district_count": 6,
        "rows": int(len(df)),
        "periods": int(df[["year", "week"]].drop_duplicates().shape[0]),
        "year_range": [int(df["year"].min()), int(df["year"].max())],
        "dataset_type": "SYNTHETIC / SIMULATED - FOR SOFTWARE AND MODEL TESTING ONLY",
        "fractional_dengue_values_preserved": True,
        "historical_dengue_interpretation": (
            "District-level fractional weekly values derived from historical dengue source data; "
            "not treated as observed integer weekly surveillance counts."
        ),
        "invalid_weather_rows_excluded_from_model": int((~df["model_weather_valid"]).sum()),
    }
    return df
