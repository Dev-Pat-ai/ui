"""Strict intake for observed barangay surveillance; never allocate annual totals.

The calendar must be declared in ``week_calendar`` or DENGUE_WEEK_CALENDAR.
Supported calendars are ISO-8601 (Monday) and MMWR (Sunday). Both define week 1
as the week containing January 4. A blank/absent row is never a zero case count.
"""
from __future__ import annotations

from datetime import date, timedelta
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from services.cpdd_data_service import load_cpdd_reference


class ObservedWeeklyDataError(RuntimeError):
    def __init__(self, message: str, code: str = "INVALID_OBSERVED_WEEKLY_DATA"):
        self.code = code
        super().__init__(f"{code}: {message}")


def observed_weekly_path() -> Path:
    configured = os.getenv("DENGUE_WEEKLY_CASES_PATH")
    return (Path(configured).expanduser().resolve() if configured else
            Path(__file__).resolve().parents[2] / "data/processed/weekly_dengue_cases.csv")


def get_training_data_status() -> dict[str, Any]:
    path = observed_weekly_path()
    return {
        "observed_weekly_cases_path": str(path),
        "observed_weekly_cases_file_exists": path.is_file(),
        "validation_status": "not_checked" if path.is_file() else "missing",
        "ready": False,
        "reason": ("File exists; validation and model fitting are still required." if path.is_file()
                   else "OBSERVED_WEEKLY_DATA_REQUIRED: Supply observed weekly counts for all 142 barangays."),
        "required_columns": ["epi_year", "epi_week", "geographic_level", "barangay_name",
                             "district_id", "dengue_cases", "data_source"],
        "calendar_requirement": "Declare ISO-8601 or MMWR in week_calendar or DENGUE_WEEK_CALENDAR.",
        "synthetic_weekly_allocation_allowed": False,
    }


def _fail(message: str) -> None:
    raise ObservedWeeklyDataError(message)


def _week_start(year: int, week: int, calendar: str) -> date:
    def first(y: int) -> date:
        anchor = date(y, 1, 4)
        offset = anchor.weekday() if calendar == "ISO-8601" else (anchor.weekday() + 1) % 7
        return anchor - timedelta(days=offset)
    start = first(year) + timedelta(weeks=week - 1)
    if start >= first(year + 1):
        _fail(f"Week {year}-W{week:02d} does not exist in {calendar}.")
    return start


def load_observed_weekly_cases(path: Path | None = None,
                               reference: dict[str, Any] | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else observed_weekly_path()
    if not path.is_file():
        raise ObservedWeeklyDataError(
            f"Supply an observed weekly barangay CSV at {path}, or set DENGUE_WEEKLY_CASES_PATH. "
            "Annual barangay totals and city weekly weights cannot substitute for observations.",
            "OBSERVED_WEEKLY_DATA_REQUIRED")
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, comment="#")
    except Exception as exc:
        raise ObservedWeeklyDataError(f"Cannot read weekly CSV: {exc}") from exc
    required = ["epi_year", "epi_week", "geographic_level", "barangay_name", "district_id",
                "dengue_cases", "data_source"]
    missing = sorted(set(required) - set(df.columns))
    if missing or df.empty:
        _fail(f"Nonempty weekly data required; missing columns: {missing}.")
    for col in required:
        df[col] = df[col].str.strip()
        if df[col].eq("").any():
            _fail(f"Missing {col}; absent observations must not be filled with zero.")
    for col, lower, upper in [("epi_year", 1900, 9998), ("epi_week", 1, 53),
                              ("dengue_cases", 0, np.iinfo(np.int64).max)]:
        value = pd.to_numeric(df[col], errors="coerce")
        if (value.isna() | ~np.isfinite(value) | (value % 1 != 0) |
                (value < lower) | (value > upper)).any():
            _fail(f"{col} must contain integers in [{lower}, {upper}].")
        df[col] = value.astype("int64")
    if not df["geographic_level"].eq("barangay").all():
        _fail("BN training requires observed barangay counts; district totals cannot be allocated to barangays.")
    declared = df.get("week_calendar", pd.Series(os.getenv("DENGUE_WEEK_CALENDAR", ""), index=df.index))
    calendars = declared.str.strip().unique().tolist()
    if len(calendars) != 1 or calendars[0] not in {"ISO-8601", "MMWR"}:
        _fail("Declare one source week_calendar (ISO-8601 or MMWR), or set DENGUE_WEEK_CALENDAR; do not guess.")
    calendar = calendars[0]
    reference = reference if reference is not None else load_cpdd_reference()
    geo = {b["barangay_name"]: district for district, block in reference["districts"].items()
           for b in block["barangays"]}
    unknown = sorted(set(df["barangay_name"]) - set(geo))
    if unknown:
        _fail(f"Unknown/noncanonical barangay names: {unknown[:10]}. Use exact CPDD reference keys.")
    mismatched = df[df["barangay_name"].map(geo) != df["district_id"]]
    if not mismatched.empty:
        _fail(f"District mismatch for {mismatched.iloc[0]['barangay_name']}.")
    if df.duplicated(["epi_year", "epi_week", "barangay_name"]).any():
        _fail("Duplicate year/week/barangay observations; resolve source revisions before training.")
    df["week_start"] = pd.to_datetime([_week_start(int(y), int(w), calendar)
                                     for y, w in zip(df["epi_year"], df["epi_week"])])
    for period, group in df.groupby("week_start"):
        absent = sorted(set(geo) - set(group["barangay_name"]))
        if absent:
            _fail(f"Incomplete barangay panel for {period.date()}: {len(absent)} missing, e.g. {absent[:5]}.")
    periods = pd.DatetimeIndex(df["week_start"].unique()).sort_values()
    if len(periods) > 1 and not (periods[1:] - periods[:-1] == pd.Timedelta(days=7)).all():
        _fail("Missing whole reporting weeks; supply continuous observed weekly coverage.")
    has_rain = "rainfall_mm" in df.columns
    if has_rain:
        if "rainfall_source" not in df.columns or df["rainfall_source"].str.strip().eq("").any():
            _fail("rainfall_mm requires nonblank rainfall_source; do not relabel NASA rainfall as PAGASA.")
        rain = pd.to_numeric(df["rainfall_mm"], errors="coerce")
        if (rain.isna() | ~np.isfinite(rain) | (rain < 0)).any():
            _fail("rainfall_mm must be observed, finite, nonnegative, and complete; no interpolation is applied.")
        df["rainfall_mm"] = rain
    df = df.rename(columns={"epi_year": "year", "epi_week": "week", "barangay_name": "barangay",
                            "dengue_cases": "cases_bgy_wk"})
    df = df.sort_values(["barangay", "week_start"]).reset_index(drop=True)
    df.attrs["provenance"] = {
        "path": str(path.resolve()), "case_sources": sorted(df["data_source"].unique().tolist()),
        "week_calendar": calendar, "geographic_level": "barangay", "observed_case_counts": True,
        "source_verification": "Source labels supplied by dataset; independently unverified.",
        "rainfall_sources": sorted(df["rainfall_source"].str.strip().unique().tolist()) if has_rain else [],
        "rainfall_alignment": "Same declared reporting week in supplied CSV." if has_rain else None,
        "barangay_count": len(geo), "periods": len(periods),
    }
    return df
