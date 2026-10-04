"""Build a dated barangay reference table. This is not a weekly training dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.cpdd_data_service import load_cpdd_reference, load_psa_household_reference
from services.cdra_data_service import load_cdra_reference
from services.wacs_data_service import load_wacs_reference

OUTPUT = ROOT / "data/authoritative/cpdd/barangay_context_features.json"


def _index_districts(data):
    result = {}
    for district_id, district in data["districts"].items():
        for row in district["barangays"]:
            key = (district_id, row["barangay_name"])
            if key in result:
                raise ValueError(f"Duplicate reference key: {key}")
            result[key] = row
    return result


def build_context_features(cpdd=None, psa=None, cdra=None, wacs=None):
    cpdd = load_cpdd_reference() if cpdd is None else cpdd
    psa = load_psa_household_reference() if psa is None else psa
    cdra = load_cdra_reference() if cdra is None else cdra
    wacs = load_wacs_reference() if wacs is None else wacs
    geo = _index_districts(cpdd)
    flood = _index_districts(cdra)
    waste = _index_districts(wacs)
    household = {(r["district_id"], r["barangay_name"]): r for r in psa["barangays"]}
    if len(household) != len(psa["barangays"]):
        raise ValueError("Duplicate PSA barangay key")
    if len(geo) != 142 or not (set(geo) == set(flood) == set(waste) == set(household)):
        raise ValueError("All four sources must have the same 142 unique barangay keys")
    rows = []
    for key, g in geo.items():
        p, f, w = household[key], flood[key]["flood_hazard"], waste[key]
        if p["population_2020"] != g["population_2020"]:
            raise ValueError(f"Census population disagreement for {key}")
        area = g["land_area_ha"]
        if not isinstance(area, (int, float)) or not math.isfinite(area) or area <= 0:
            raise ValueError(f"Positive finite land area required: {key}")
        if not f["has_mgb_record"] and f["total_flooded_area_pct"] is not None:
            raise ValueError(f"Missing flood record cannot be a measured zero: {key}")
        rows.append({
            "district_id": key[0], "barangay_name": key[1],
            "population_2020": p["population_2020"],
            "household_population_2020": p["household_population_2020"],
            "households_2020": p["households_2020"],
            "average_household_size_2020": p["average_household_size"],
            "land_area_ha_cpdd_2020": area,
            "population_density_people_per_km2_2020": round(p["population_2020"] / area * 100, 6),
            "mgb_flood_total_area_pct_2021": f["total_flooded_area_pct"],
            "mgb_flood_depth_gt_2m_pct_2021": f["submerged_pct_gt_2m"],
            "mgb_flood_record_missing": not f["has_mgb_record"],
            "waste_generated_kg_day_estimated_2021": w["waste_kg_per_day"],
            "waste_is_population_derived": True,
        })
    sources = []
    for rel in ["cpdd/district_profiles_2020.json", "cpdd/barangay_households_2020.json",
                "cdra/qc_flood_vulnerability_2022.json", "wacs/qc_waste_generation_2021.json"]:
        path = ROOT / "data/authoritative" / rel
        sources.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {
        "dataset_id": "qc_barangay_context_features_v1", "schema_version": 1,
        "geographic_level": "barangay", "primary_key": ["district_id", "barangay_name"],
        "temporal_resolution": "mixed dated static references; not weekly observations",
        "is_weekly_training_dataset": False, "used_by_city_forecast": False,
        "barangay_count": len(rows), "sources": sources,
        "field_notes": {
            "population_and_households": "Actual 2020 census. Household size uses household population, not total population.",
            "area": "Existing CPDD 2020 barangay area basis. Non-barangay Reservoir/QMC rows and disputed district aggregate density are excluded.",
            "density": "Derived total population / hectares * 100; people/km2.",
            "flood": "MGB 2021 susceptibility from CDRA 2022. 119 listed records; 23 nulls. Not observed weekly flooding.",
            "waste": "Estimated from projected 2021 population times 0.44 kg/person/day; not an independent sanitation measurement.",
            "historical_use": "Reference/publication dates must be respected. Historical application requires explicit assumptions; these are not contemporaneous observations for every prior year.",
        },
        "summary": {
            "population_2020": sum(r["population_2020"] for r in rows),
            "household_population_2020": sum(r["household_population_2020"] for r in rows),
            "households_2020": sum(r["households_2020"] for r in rows),
            "flood_records_present": sum(not r["mgb_flood_record_missing"] for r in rows),
            "flood_records_missing": sum(r["mgb_flood_record_missing"] for r in rows),
        },
        "barangays": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build_context_features()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(".tmp")
    temp.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(args.output)
    print(json.dumps({"output": str(args.output), **result["summary"]}, indent=2))
