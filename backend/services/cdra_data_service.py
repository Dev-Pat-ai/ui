"""Validated access to the CDRA 2022 flood vulnerability and BVI hotspot dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_DISTRICTS = ("I", "II", "III", "IV", "V", "VI")
EXPECTED_BARANGAY_COUNTS = {"I": 37, "II": 5, "III": 37, "IV": 38, "V": 14, "VI": 11}
EXPECTED_HOTSPOT_COUNT = 21


def _reference_path() -> Path:
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "data" / "authoritative" / "cdra" / "qc_flood_vulnerability_2022.json"


def _metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_id": data["dataset_id"],
        "is_sample": False,
        "is_authoritative_reference": True,
        "reference_year": data["reference_year"],
        "publisher": data["publisher"],
        "sources": data["sources"],
        "source_document": data["source_document"],
        "missing_data_policy": data.get("missing_data_policy"),
        "classification_method": data.get("classification_method"),
        "epidemiological_relevance": data["epidemiological_relevance"]
    }


def load_cdra_reference() -> dict[str, Any]:
    path = _reference_path()
    if not path.exists():
        raise FileNotFoundError(f"CDRA reference data not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except json.JSONDecodeError:
        raise ValueError("Malformed CDRA reference JSON") from None

    if data.get("is_authoritative_reference") is not True:
        raise ValueError("CDRA reference is missing its authoritative-reference marker")
    if data.get("reference_year") != 2022:
        raise ValueError("Unexpected CDRA reference year")

    districts = data.get("districts")
    if not isinstance(districts, dict) or tuple(districts) != ALLOWED_DISTRICTS:
        raise ValueError("CDRA reference must contain Districts I-VI in order")

    total_barangays = 0
    all_names: list[str] = []
    for district_id, expected_count in EXPECTED_BARANGAY_COUNTS.items():
        dist = districts[district_id]
        barangays = dist.get("barangays", [])
        if len(barangays) != expected_count:
            raise ValueError(f"District {district_id} must contain {expected_count} barangays")
        total_barangays += len(barangays)
        all_names.extend(b["barangay_name"] for b in barangays)
        for barangay in barangays:
            hazard = barangay["flood_hazard"]
            if not hazard["has_mgb_record"]:
                fields = ("total_flooded_area_pct", "submerged_pct_0_5m_to_1m", "submerged_pct_1m_to_2m", "submerged_pct_gt_2m")
                if any(hazard.get(field) is not None for field in fields):
                    raise ValueError("An unlisted MGB barangay must have null flood percentages, not a measured zero")

    if total_barangays != 142 or len({n.casefold() for n in all_names}) != 142:
        raise ValueError("CDRA reference must contain 142 unique barangays")

    hotspots = data.get("hotspots", [])
    if len(hotspots) != EXPECTED_HOTSPOT_COUNT:
        raise ValueError(f"CDRA reference must contain {EXPECTED_HOTSPOT_COUNT} BVI hotspots")

    return data


def load_cdra_flood_vulnerability(district_id: str | None = None) -> dict[str, Any]:
    if district_id is not None:
        district_id = district_id.upper()
        if district_id not in ALLOWED_DISTRICTS:
            raise ValueError(f"Invalid district identifier: {district_id}. Must be I-VI.")

    data = load_cdra_reference()
    if district_id is None:
        return {
            **_metadata(data),
            "city_summary": data["city_summary"],
            "districts": data["districts"]
        }

    return {
        **_metadata(data),
        "district": data["districts"][district_id]
    }


def load_cdra_hotspots() -> dict[str, Any]:
    data = load_cdra_reference()
    return {
        **_metadata(data),
        "city_summary": data["city_summary"],
        "hotspot_count": len(data["hotspots"]),
        "hotspots": data["hotspots"]
    }
