from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


class ResearchDataIntakeService:
    def __init__(self, contract_path: Path):
        self.contract_path = contract_path
        self.contract = self._load_contract()
        self.expected_period = self.contract.get("expected_period", {"start_year": 2018, "end_year": 2024})
        self.valid_districts = ["I", "II", "III", "IV", "V", "VI"]

    def _load_contract(self) -> dict[str, Any]:
        if not self.contract_path.exists():
            raise FileNotFoundError(f"Contract not found at {self.contract_path}")
        with open(self.contract_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def validate_file(self, file_path: Path, file_type: str) -> dict[str, Any]:
        """Validate an authoritative research input file without modifying it."""
        report = {
            "file": file_path.name,
            "type": file_type,
            "status": "VALID",
            "errors": [],
            "warnings": [],
            "info": [],
            "stats": {}
        }

        if not file_path.exists():
            report["status"] = "MISSING_REQUIRED_INPUT"
            report["errors"].append(f"File not found: {file_path}")
            return report

        try:
            df = pd.read_csv(file_path)
            report["stats"]["row_count"] = len(df)
            report["stats"]["columns"] = list(df.columns)

            if file_type == "dengue_cases":
                self._validate_dengue_cases(df, report)
            elif file_type == "mapping":
                self._validate_mapping(df, report)
            elif file_type == "weather":
                self._validate_weather(df, report)
            elif file_type == "candidate_features":
                self._validate_candidate_features(df, report)
            else:
                report["errors"].append(f"Unknown file type: {file_type}")
                report["status"] = "ERROR"

        except Exception as exc:
            report["status"] = "ERROR"
            report["errors"].append(f"Critical failure reading file: {exc}")

        return report

    def _validate_common_keys(self, df: pd.DataFrame, report: dict[str, Any], required_cols: list[str]):
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            report["errors"].append(f"Missing required columns: {', '.join(missing)}")
            report["status"] = "ERROR"
            return False
        return True

    def _validate_dengue_cases(self, df: pd.DataFrame, report: dict[str, Any]):
        required = ["epi_year", "epi_week", "district_id", "dengue_cases"]
        if not self._validate_common_keys(df, report, required): return

        # Year check
        year_values = pd.to_numeric(df["epi_year"], errors="coerce")
        invalid_years = year_values.isna() | (year_values % 1 != 0)
        if invalid_years.any():
            report["errors"].append(f"Found {int(invalid_years.sum())} rows with invalid epi_year")
            report["status"] = "ERROR"
        years = year_values.dropna().unique()
        report["stats"]["year_range"] = {"start": int(min(years)), "end": int(max(years))} if len(years) > 0 else None
        if report["stats"]["year_range"]:
            if report["stats"]["year_range"]["start"] > self.expected_period["start_year"] or \
               report["stats"]["year_range"]["end"] < self.expected_period["end_year"]:
                report["warnings"].append(f"Year coverage {report['stats']['year_range']['start']}-{report['stats']['year_range']['end']} does not fully meet expected period {self.expected_period['start_year']}-{self.expected_period['end_year']}")

        # Week check
        week_values = pd.to_numeric(df["epi_week"], errors="coerce")
        invalid_weeks = week_values.isna() | (week_values % 1 != 0) | (week_values < 1) | (week_values > 53)
        if invalid_weeks.any():
            report["errors"].append(f"Found {int(invalid_weeks.sum())} rows with invalid epi_week (must be an integer from 1-53)")
            report["status"] = "ERROR"

        # District check
        invalid_districts = df[~df["district_id"].astype(str).str.upper().isin(self.valid_districts)]
        if not invalid_districts.empty:
            report["errors"].append(f"Found {len(invalid_districts)} rows with invalid district_id (expected I-VI)")
            report["status"] = "ERROR"

        # Cases check
        case_values = pd.to_numeric(df["dengue_cases"], errors="coerce")
        invalid_cases = case_values.isna() | (case_values % 1 != 0) | (case_values < 0)
        if invalid_cases.any():
            report["errors"].append(f"Found {int(invalid_cases.sum())} rows with invalid dengue_cases (must be non-negative integer)")
            report["status"] = "ERROR"

        # Duplicates check
        dupes = df.duplicated(subset=["epi_year", "epi_week", "district_id", "barangay_name"] if "barangay_name" in df.columns else ["epi_year", "epi_week", "district_id"]).sum()
        if dupes > 0:
            report["errors"].append(f"Found {dupes} duplicate year-week-location records")
            report["status"] = "ERROR"

    def _validate_mapping(self, df: pd.DataFrame, report: dict[str, Any]):
        required = ["barangay_name", "district_id"]
        if not self._validate_common_keys(df, report, required): return

        invalid_districts = df[~df["district_id"].astype(str).str.upper().isin(self.valid_districts)]
        if not invalid_districts.empty:
            report["errors"].append(f"Found {len(invalid_districts)} rows with invalid district_id (expected I-VI)")
            report["status"] = "ERROR"

        normalized_names = df["barangay_name"].astype("string").str.strip()
        missing_names = normalized_names.isna() | normalized_names.eq("")
        duplicate_names = normalized_names.str.casefold().duplicated(keep=False) & ~missing_names
        if missing_names.any():
            report["errors"].append(f"Found {int(missing_names.sum())} rows with missing barangay_name")
            report["status"] = "ERROR"
        if duplicate_names.any():
            report["errors"].append("Found duplicate or conflicting barangay mapping rows")
            report["status"] = "ERROR"

    def _validate_weather(self, df: pd.DataFrame, report: dict[str, Any]):
        required = ["epi_year", "epi_week", "district_id", "rainfall_mm", "min_temp_c", "max_temp_c"]
        if not self._validate_common_keys(df, report, required): return

        week_values = pd.to_numeric(df["epi_week"], errors="coerce")
        invalid_weeks = week_values.isna() | (week_values % 1 != 0) | (week_values < 1) | (week_values > 53)
        invalid_districts = ~df["district_id"].astype(str).str.upper().isin(self.valid_districts)
        rainfall = pd.to_numeric(df["rainfall_mm"], errors="coerce")
        min_temp = pd.to_numeric(df["min_temp_c"], errors="coerce")
        max_temp = pd.to_numeric(df["max_temp_c"], errors="coerce")
        invalid_weather = rainfall.isna() | (rainfall < 0) | min_temp.isna() | max_temp.isna() | (min_temp > max_temp)
        if invalid_weeks.any() or invalid_districts.any() or invalid_weather.any():
            report["errors"].append("Weather data contains invalid week, district, rainfall, or temperature values")
            report["status"] = "ERROR"

        if "data_source" in df.columns:
            sources = df["data_source"].unique()
            if not any("PAGASA" in str(s).upper() for s in sources):
                report["warnings"].append(f"Weather data source does not explicitly mention PAGASA. Found: {sources}")

    def _validate_candidate_features(self, df: pd.DataFrame, report: dict[str, Any]):
        required = ["epi_year", "district_id", "feature_name", "feature_value"]
        if not self._validate_common_keys(df, report, required): return

        # Check against contract feature names
        contract_features = [f["canonical_name"] for f in self.contract.get("feature_registry", [])]
        unknown = df[~df["feature_name"].isin(contract_features)]["feature_name"].unique()
        if len(unknown) > 0:
            report["warnings"].append(f"Found unknown feature names not in contract: {list(unknown)}")
