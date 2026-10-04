"""Validated access to the WACS 2021 solid waste generation reference dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_DISTRICTS = ("I", "II", "III", "IV", "V", "VI")
EXPECTED_BARANGAY_COUNTS = {"I": 37, "II": 5, "III": 37, "IV": 38, "V": 14, "VI": 11}


def _reference_path() -> Path:
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "data" / "authoritative" / "wacs" / "qc_waste_generation_2021.json"


def _metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_id": data["dataset_id"],
        "is_sample": False,
        "is_authoritative_reference": True,
        "reference_year": data["reference_year"],
        "publisher": data["publisher"],
        "source_document": data["source_document"],
        "epidemiological_relevance": data["epidemiological_relevance"]
    }


def load_wacs_reference() -> dict[str, Any]:
    path = _reference_path()
    if not path.exists():
        raise FileNotFoundError(f"WACS reference data not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except json.JSONDecodeError:
        raise ValueError("Malformed WACS reference JSON") from None

    if data.get("is_authoritative_reference") is not True:
        raise ValueError("WACS reference is missing its authoritative-reference marker")
    if data.get("reference_year") != 2021:
        raise ValueError("Unexpected WACS reference year")

    districts = data.get("districts")
    if not isinstance(districts, dict) or tuple(districts) != ALLOWED_DISTRICTS:
        raise ValueError("WACS reference must contain Districts I-VI in order")

    total_barangays = 0
    all_names: list[str] = []
    for district_id, expected_count in EXPECTED_BARANGAY_COUNTS.items():
        dist = districts[district_id]
        barangays = dist.get("barangays", [])
        if len(barangays) != expected_count:
            raise ValueError(f"District {district_id} must contain {expected_count} barangays")
        total_barangays += len(barangays)
        all_names.extend(b["barangay_name"] for b in barangays)

    if total_barangays != 142 or len({n.casefold() for n in all_names}) != 142:
        raise ValueError("WACS reference must contain 142 unique barangays")

    return data


def load_wacs_waste_generation(district_id: str | None = None) -> dict[str, Any]:
    if district_id is not None:
        district_id = district_id.upper()
        if district_id not in ALLOWED_DISTRICTS:
            raise ValueError(f"Invalid district identifier: {district_id}. Must be I-VI.")

    data = load_wacs_reference()
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


def load_wacs_top_generators() -> dict[str, Any]:
    data = load_wacs_reference()
    return {
        **_metadata(data),
        "city_summary": data["city_summary"],
        "top_10_waste_generators": data.get("top_10_waste_generators", []),
        "top_10_highest_waste_density": data.get("top_10_highest_waste_density", [])
    }
