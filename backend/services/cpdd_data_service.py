"""Validated access to the CPDD/PSA 2020 geographic reference dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_DISTRICTS = ("I", "II", "III", "IV", "V", "VI")
EXPECTED_BARANGAY_COUNTS = {"I": 37, "II": 5, "III": 37, "IV": 38, "V": 14, "VI": 11}
EXPECTED_CITY_POPULATION = 2_960_048
PSA_HOUSEHOLD_TOTALS = {
    "population_2020": 2_960_048,
    "household_population_2020": 2_950_493,
    "households_2020": 738_724,
}


def _reference_path() -> Path:
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "data" / "authoritative" / "cpdd" / "district_profiles_2020.json"


def _metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_id": data["dataset_id"],
        "is_sample": False,
        "is_authoritative_reference": True,
        "reference_year": data["reference_year"],
        "data_source": data["publisher"],
        "population_source": data["population_source"],
        "geographic_scope": data["geographic_scope"],
        "notes": data["notes"],
    }


def load_cpdd_reference() -> dict[str, Any]:
    path = _reference_path()
    if not path.exists():
        raise FileNotFoundError(f"CPDD reference data not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except json.JSONDecodeError:
        raise ValueError("Malformed CPDD reference JSON") from None

    if data.get("is_authoritative_reference") is not True:
        raise ValueError("CPDD reference is missing its authoritative-reference marker")
    if data.get("reference_year") != 2020:
        raise ValueError("Unexpected CPDD reference year")

    districts = data.get("districts")
    if not isinstance(districts, dict) or tuple(districts) != ALLOWED_DISTRICTS:
        raise ValueError("CPDD reference must contain Districts I-VI in order")

    all_names: list[str] = []
    total_population = 0
    for district_id, expected_count in EXPECTED_BARANGAY_COUNTS.items():
        district = districts[district_id]
        barangays = district.get("barangays", [])
        if district.get("barangay_count") != expected_count or len(barangays) != expected_count:
            raise ValueError(f"District {district_id} must contain {expected_count} barangays")
        if sum(row["population_2020"] for row in barangays) != district["population_2020"]:
            raise ValueError(f"District {district_id} population total is inconsistent")
        total_population += district["population_2020"]
        all_names.extend(row["barangay_name"] for row in barangays)

    if len(all_names) != 142 or len({name.casefold() for name in all_names}) != 142:
        raise ValueError("CPDD reference must contain 142 unique barangays")
    if total_population != EXPECTED_CITY_POPULATION:
        raise ValueError("CPDD district populations do not match the Quezon City total")

    return data


def load_cpdd_districts() -> dict[str, Any]:
    data = load_cpdd_reference()
    return {
        **_metadata(data),
        "city_summary": data["city_summary"],
        "districts": data["districts"],
    }


def load_cpdd_district_detail(district_id: str) -> dict[str, Any]:
    district_id = district_id.upper()
    if district_id not in ALLOWED_DISTRICTS:
        raise ValueError(f"Invalid district identifier: {district_id}. Must be I-VI.")
    data = load_cpdd_reference()
    return {**_metadata(data), "district": data["districts"][district_id]}


def load_cpdd_barangays(district_id: str | None = None) -> dict[str, Any]:
    if district_id is not None:
        district_id = district_id.upper()
        if district_id not in ALLOWED_DISTRICTS:
            raise ValueError(f"Invalid district identifier: {district_id}. Must be I-VI.")

    data = load_cpdd_reference()
    barangays = []
    for current_id, district in data["districts"].items():
        if district_id is not None and current_id != district_id:
            continue
        barangays.extend({"district_id": current_id, **row} for row in district["barangays"])

    return {
        **_metadata(data),
        "district_filter": district_id,
        "barangay_count": len(barangays),
        "barangays": barangays,
    }


def validate_psa_household_reference(data: dict[str, Any], cpdd: dict[str, Any]) -> None:
    """Check observed household counts independently of any model or projections."""
    if (
        data.get("is_authoritative_reference") is not True
        or data.get("is_sample") is not False
        or data.get("reference_year") != 2020
        or data.get("reference_date") != "2020-05-01"
        or data.get("observation_type") != "census_actual"
    ):
        raise ValueError("PSA household reference must identify the actual May 1, 2020 census")
    canonical = {
        row["barangay_name"]: (district_id, row["population_2020"])
        for district_id, district in cpdd["districts"].items()
        for row in district["barangays"]
    }
    rows = data.get("barangays", [])
    if not isinstance(rows, list) or len(rows) != 142:
        raise ValueError("PSA household reference must contain 142 barangays")
    seen = set()
    for row in rows:
        name = row.get("barangay_name")
        if not isinstance(name, str) or name not in canonical or name in seen:
            raise ValueError("PSA household reference has missing, unmapped or duplicate barangays")
        seen.add(name)
        for field in PSA_HOUSEHOLD_TOTALS:
            if type(row.get(field)) is not int or row[field] < 0:
                raise ValueError(f"Invalid {field} count for {name}")
        if (row.get("district_id"), row["population_2020"]) != canonical[name]:
            raise ValueError(f"PSA/CPDD district or population mismatch for {name}")
        population, households = row["household_population_2020"], row["households_2020"]
        if not 0 <= households <= population <= row["population_2020"] or (not households and population):
            raise ValueError(f"Inconsistent household counts for {name}")
        average = round(population / households, 6) if households else None
        if row.get("average_household_size") != average:
            raise ValueError(f"Incorrect average household size for {name}")
    if seen != set(canonical):
        raise ValueError("PSA household coverage differs from the canonical CPDD mapping")

    def check_summary(summary: dict[str, Any], members: list[dict[str, Any]]) -> None:
        if summary.get("barangay_count") != len(members):
            raise ValueError("PSA household summary has an inconsistent barangay count")
        for field in PSA_HOUSEHOLD_TOTALS:
            if type(summary.get(field)) is not int or summary[field] != sum(row[field] for row in members):
                raise ValueError(f"PSA household summary has an inconsistent {field} total")
        denominator = summary["households_2020"]
        expected_average = round(summary["household_population_2020"] / denominator, 6) if denominator else None
        if summary.get("average_household_size") != expected_average:
            raise ValueError("PSA household summary uses an incorrect household-size denominator")

    city = data.get("city_summary", {})
    check_summary(city, rows)
    if city.get("district_count") != 6 or any(city[field] != value for field, value in PSA_HOUSEHOLD_TOTALS.items()):
        raise ValueError("PSA household city totals do not match the 2020 census controls")
    summaries = data.get("district_summaries", {})
    if set(summaries) != set(ALLOWED_DISTRICTS):
        raise ValueError("PSA household reference must summarize Districts I-VI")
    for district_id, count in EXPECTED_BARANGAY_COUNTS.items():
        members = [row for row in rows if row["district_id"] == district_id]
        if len(members) != count:
            raise ValueError(f"Unexpected PSA household coverage in District {district_id}")
        check_summary(summaries[district_id], members)


def load_psa_household_reference() -> dict[str, Any]:
    """Read the separate census reference without adding fields to model inputs."""
    path = _reference_path().with_name("barangay_households_2020.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Malformed PSA household reference JSON") from None
    validate_psa_household_reference(data, load_cpdd_reference())
    return data
