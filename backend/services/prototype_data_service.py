from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.cpdd_data_service import ALLOWED_DISTRICTS, load_cpdd_reference


def _get_sample_path(filename: str) -> Path:
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "data" / "sample" / filename


def load_prototype_json(filename: str, required_fields: list[str]) -> dict[str, Any]:
    """Load and validate a prototype JSON file."""
    path = _get_sample_path(filename)

    if not path.exists():
        raise FileNotFoundError(f"Prototype data file not found: {filename}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Malformed prototype JSON in {filename}") from None

    # Core validation
    if data.get("is_sample") is not True:
        raise ValueError(f"File {filename} is missing 'is_sample: true' marker.")

    for field in required_fields:
        if field not in data:
            raise ValueError(f"File {filename} missing required field: {field}")

    return data


def _cpdd_context(district: dict[str, Any]) -> dict[str, Any]:
    barangay_names = [row["barangay_name"] for row in district["barangays"]]
    return {
        "coverage": ", ".join(barangay_names),
        "barangays": barangay_names,
        "barangay_count": district["barangay_count"],
        "population": f"{district['population_2020']:,}",
        "population_2020": district["population_2020"],
        "land_area_sq_km": district["land_area_sq_km"],
        "land_area_ha": district["land_area_ha"],
        "population_density_per_ha": district["population_density_per_ha"],
        "demographic_reference_year": 2020,
        "demographic_source": "CPDD district maps / PSA 2020 Census population",
    }


def _mixed_provenance(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "authoritative_reference": {
            "dataset_id": reference["dataset_id"],
            "fields": [
                "barangay membership",
                "barangay count",
                "land area",
                "population_2020",
                "population_density_per_ha",
            ],
            "source": "CPDD district maps / PSA 2020 Census population",
            "reference_year": 2020,
        },
        "demonstration_only": {
            "fields": ["dengue cases", "rainfall", "forecast", "risk", "status", "alerts"],
            "source": "Static demonstration dataset",
        },
    }


def load_prototype_dashboard() -> dict[str, Any]:
    data = load_prototype_json("dashboard.json", ["districts", "alerts", "prototype_version", "sample_updated_at"])
    reference = load_cpdd_reference()
    districts = []
    for row in data["districts"]:
        district_id = row["district"].split()[-1]
        districts.append({**row, **_cpdd_context(reference["districts"][district_id])})

    return {
        **data,
        "contains_authoritative_reference": True,
        "data_source": "Mixed: CPDD/PSA 2020 reference plus demonstration epidemiological values",
        "data_provenance": _mixed_provenance(reference),
        "districts": districts,
    }


def load_prototype_forecast() -> dict[str, Any]:
    return load_prototype_json("forecast.json", ["forecasts", "prototype_version", "sample_updated_at"])


def load_prototype_historical() -> dict[str, Any]:
    return load_prototype_json("historical.json", ["historical_data", "prototype_version", "sample_updated_at"])


def load_prototype_districts() -> dict[str, Any]:
    data = load_prototype_json("districts.json", ["districts", "prototype_version", "sample_updated_at"])
    reference = load_cpdd_reference()
    districts = {
        district_id: {**row, **_cpdd_context(reference["districts"][district_id])}
        for district_id, row in data["districts"].items()
    }
    return {
        **data,
        "contains_authoritative_reference": True,
        "data_source": "Mixed: CPDD/PSA 2020 reference plus demonstration epidemiological values",
        "data_provenance": _mixed_provenance(reference),
        "districts": districts,
    }


def load_prototype_district_detail(district_id: str) -> dict[str, Any]:
    # Strict validation against allowed IDs
    if district_id not in ALLOWED_DISTRICTS:
        raise ValueError(f"Invalid district identifier: {district_id}. Must be I-VI.")

    data = load_prototype_districts()
    district_data = data["districts"].get(district_id)
    if not district_data:
        raise KeyError(f"District {district_id} data not found in districts.json")

    # Return matched district with original metadata
    return {
        "is_sample": True,
        "prototype_version": data["prototype_version"],
        "sample_updated_at": data["sample_updated_at"],
        "data_source": data["data_source"],
        "disclaimer": data["disclaimer"],
        "contains_authoritative_reference": True,
        "data_provenance": data["data_provenance"],
        "district": district_data
    }
