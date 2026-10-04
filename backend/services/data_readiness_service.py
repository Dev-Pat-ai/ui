from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


class DataReadinessService:
    def __init__(self, contract_path: Path):
        self.contract_path = contract_path
        self.contract = self._load_contract()
        self.raw_dir = contract_path.parent.parent / "raw"
        self.cpdd_reference_path = (
            contract_path.parent.parent / "authoritative" / "cpdd" / "district_profiles_2020.json"
        )

    def _load_contract(self) -> dict[str, Any]:
        if not self.contract_path.exists():
            raise FileNotFoundError(f"Contract not found: {self.contract_path}")
        with open(self.contract_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def audit_raw_data(self) -> dict[str, Any]:
        """Perform a read-only audit of files in data/raw/."""
        findings = {
            "inventory": [],
            "feature_readiness": [],
            "mismatches": [],
            "unresolved_decisions": self.contract.get("unresolved_research_decisions", {}),
            "overall_status": "PENDING"
        }

        files = sorted(self.raw_dir.rglob("*"))
        for file in files:
            if file.is_dir(): continue
            file_info = self._inspect_file(file)
            findings["inventory"].append(file_info)

        # Audit each feature in the registry
        for feature in self.contract.get("feature_registry", []):
            feature_audit = self._audit_feature(feature, findings["inventory"])
            findings["feature_readiness"].append(feature_audit)

        findings["mismatches"] = self._detect_global_mismatches(findings)
        findings["overall_status"] = self._determine_overall_status(findings)

        return findings

    def _inspect_file(self, file_path: Path) -> dict[str, Any]:
        info = {
            "filename": file_path.name,
            "relative_path": file_path.relative_to(self.raw_dir).as_posix(),
            "type": file_path.suffix.lower(),
            "sheets": [],
            "columns": {},
            "row_count": 0,
            "year_range": None,
            "temporal_resolution": "unknown",
            "geographic_resolution": "unknown"
        }
        # Inventory raw sources without mistaking a filename, map, or report for validated features.
        info["inspection_scope"] = "column discovery only; source tables still require validation"

        try:
            if info["type"] == ".xlsx":
                xl = pd.ExcelFile(file_path)
                info["sheets"] = xl.sheet_names
                for sheet in info["sheets"]:
                    # Read just enough to get columns and info
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    info["columns"][sheet] = [str(c) for c in df.columns]
                    info["row_count"] += len(df)
                    res = self._infer_resolutions(df)
                    # Use the most specific resolution found across sheets if they differ?
                    # For simplicity, we just take the last one or merge.
                    if res["temporal"] != "unknown": info["temporal_resolution"] = res["temporal"]
                    if res["geographic"] != "unknown": info["geographic_resolution"] = res["geographic"]
                    yr_range = self._infer_year_range(df)
                    if yr_range:
                        if not info["year_range"]:
                            info["year_range"] = yr_range
                        else:
                            info["year_range"]["start"] = min(info["year_range"]["start"], yr_range["start"])
                            info["year_range"]["end"] = max(info["year_range"]["end"], yr_range["end"])

            elif info["type"] == ".csv":
                df = pd.read_csv(file_path)
                info["columns"]["default"] = [str(c) for c in df.columns]
                info["row_count"] = len(df)
                res = self._infer_resolutions(df)
                info["temporal_resolution"] = res["temporal"]
                info["geographic_resolution"] = res["geographic"]
                yr_range = self._infer_year_range(df)
                if yr_range:
                    info["year_range"] = yr_range
        except Exception as e:
            info["error"] = str(e)

        return info

    def _infer_resolutions(self, df: pd.DataFrame) -> dict[str, str]:
        cols = [str(c).lower() for c in df.columns]
        res = {"temporal": "unknown", "geographic": "unknown"}

        # Temporal
        if any(c in cols for c in ["wn", "week", "epi_week", "week_number"]):
            res["temporal"] = "weekly"
        elif any(c in cols for c in ["yr", "year", "epi_year"]) and not res["temporal"] == "weekly":
            res["temporal"] = "annual"

        # Geographic
        if any(c in cols for c in ["barangay", "barangay_name", "bgy", "adm4_pcode"]):
            res["geographic"] = "barangay"
        elif any(c in cols for c in ["district", "district_id", "dist"]):
            res["geographic"] = "district"
        elif any("qc" in c for c in cols) or any("city" in c for c in cols) or "dc_qc" in cols:
            res["geographic"] = "city"

        return res

    def _infer_year_range(self, df: pd.DataFrame) -> dict[str, int] | None:
        cols = [str(c).lower() for c in df.columns]
        year_col = None
        for c in ["yr", "year", "epi_year"]:
            if c in cols:
                year_col = df.columns[cols.index(c)]
                break

        if year_col:
            try:
                years = pd.to_numeric(df[year_col], errors='coerce').dropna().astype(int)
                # Filter plausible years
                years = years[(years > 1900) & (years < 2100)]
                if not years.empty:
                    return {"start": int(years.min()), "end": int(years.max())}
            except:
                pass

        # Check for DC_YYYY pattern (wide format)
        wide_years = []
        for c in df.columns:
            if str(c).startswith("DC_") and str(c)[3:].isdigit():
                wide_years.append(int(str(c)[3:]))
        if wide_years:
            return {"start": min(wide_years), "end": max(wide_years)}

        return None

    def _audit_feature(self, feature: dict[str, Any], inventory: list[dict[str, Any]]) -> dict[str, Any]:
        audit = {
            "canonical_name": feature["canonical_name"],
            "category": feature["category"],
            "status": "MISSING",
            "detected_file": None,
            "detected_sheet": None,
            "detected_column": None,
            "mismatches": [],
            "missing_values": 0,
            "detected_temporal": None,
            "detected_geographic": None
        }

        aliases = [feature["canonical_name"].lower()] + [a.lower() for a in feature.get("known_aliases", [])]

        for file in inventory:
            if "error" in file: continue
            for sheet, columns in file["columns"].items():
                for col in columns:
                    if col.lower() in aliases:
                        # Found a match
                        audit["detected_file"] = file["filename"]
                        audit["detected_sheet"] = sheet if file["type"] == ".xlsx" else None
                        audit["detected_column"] = col
                        audit["detected_temporal"] = file["temporal_resolution"]
                        audit["detected_geographic"] = file["geographic_resolution"]

                        mismatches = []
                        status = "AVAILABLE"

                        if audit["detected_temporal"] != feature["expected_temporal_resolution"]:
                            mismatches.append("WRONG_TEMPORAL_LEVEL")
                            status = "WRONG_TEMPORAL_LEVEL"

                        if audit["detected_geographic"] != feature["expected_geographic_resolution"]:
                            mismatches.append("WRONG_GEOGRAPHIC_LEVEL")
                            if status == "AVAILABLE": status = "WRONG_GEOGRAPHIC_LEVEL"

                        if feature["canonical_name"] == "rainfall" and "nasa" in col.lower():
                            mismatches.append("SOURCE_MISMATCH")
                            if status in ["AVAILABLE", "WRONG_GEOGRAPHIC_LEVEL"]: status = "SOURCE_MISMATCH"

                        audit["status"] = status
                        audit["mismatches"] = mismatches
                        return audit
        return audit

    def _detect_global_mismatches(self, findings: dict[str, Any]) -> list[str]:
        mismatches = []
        expected_period = self.contract["expected_period"]

        # Period Mismatch
        found_start = 9999
        found_end = 0
        has_yr = False
        for file in findings["inventory"]:
            if file.get("year_range"):
                found_start = min(found_start, file["year_range"]["start"])
                found_end = max(found_end, file["year_range"]["end"])
                has_yr = True

        if has_yr:
            if found_start > expected_period["start_year"] or found_end < expected_period["end_year"]:
                mismatches.append(f"STUDY_PERIOD_MISMATCH: Found {found_start}-{found_end}, expected {expected_period['start_year']}-{expected_period['end_year']}")

        if not self.cpdd_reference_path.exists():
            mismatches.append("MISSING_BARANGAY_TO_DISTRICT_MAPPING")
        else:
            try:
                with self.cpdd_reference_path.open("r", encoding="utf-8") as stream:
                    mapping = json.load(stream)
                districts = mapping.get("districts", {})
                barangay_count = sum(len(item.get("barangays", [])) for item in districts.values())
                if set(districts) != {"I", "II", "III", "IV", "V", "VI"} or barangay_count != 142:
                    mismatches.append("INVALID_BARANGAY_TO_DISTRICT_MAPPING")
            except (OSError, json.JSONDecodeError):
                mismatches.append("INVALID_BARANGAY_TO_DISTRICT_MAPPING")

        return mismatches

    def _determine_overall_status(self, findings: dict[str, Any]) -> str:
        statuses = [f["status"] for f in findings["feature_readiness"]]
        if findings.get("mismatches"):
            return "NOT_READY"
        unresolved = findings.get("unresolved_decisions", {})
        if any(item.get("status") != "resolved" for item in unresolved.values()):
            return "NOT_READY"
        if all(s == "AVAILABLE" for s in statuses):
            return "READY"
        if "MISSING" in statuses or "WRONG_TEMPORAL_LEVEL" in statuses or "WRONG_GEOGRAPHIC_LEVEL" in statuses:
            return "NOT_READY"
        return "PARTIALLY_READY"
