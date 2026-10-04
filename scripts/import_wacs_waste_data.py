#!/usr/bin/env python3
"""
import_wacs_waste_data.py

Extracts authoritative solid waste generation data from:
  "Waste Generated per Barangay 2021.pdf"
Published by Quezon City Task Force on Solid Waste Management (TFSWM) & EPWMD.

Outputs:
  - data/authoritative/wacs/qc_waste_generation_2021.json
  - frontend/js/wacs-waste-data.js
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pypdf import PdfReader

DEFAULT_PDF = os.path.join("data", "raw", "Waste Generated per Barangay 2021.pdf")
DEFAULT_CPDD_JSON = os.path.join("data", "authoritative", "cpdd", "district_profiles_2020.json")
OUTPUT_JSON = os.path.join("data", "authoritative", "wacs", "qc_waste_generation_2021.json")
OUTPUT_JS = os.path.join("frontend", "js", "wacs-waste-data.js")

EXPECTED_BARANGAY_COUNTS = {"I": 37, "II": 5, "III": 37, "IV": 38, "V": 14, "VI": 11}


def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def normalize_key(name):
    n = name.lower()
    n = re.sub(r"\bsaint\b|\bst\b|\bst\.\b", "st", n)
    n = re.sub(r"\bsanta\b|\bsta\b|\bsta\.\b", "sta", n)
    n = re.sub(r"\bsanto\b|\bsto\b|\bsto\.\b", "sto", n)
    n = n.replace("balong-bato", "balonbato").replace("balongbato", "balonbato").replace("balon-bato", "balonbato")
    n = re.sub(r"[^a-z0-9]", "", n)
    return n


def load_canonical_barangays(cpdd_path):
    if not os.path.exists(cpdd_path):
        raise FileNotFoundError(f"CPDD reference not found at: {cpdd_path}")
    with open(cpdd_path, "r", encoding="utf-8") as f:
        cpdd = json.load(f)

    canonical_by_key = {}
    for d_id, dist_info in cpdd["districts"].items():
        for b in dist_info["barangays"]:
            c_name = b["barangay_name"]
            k = normalize_key(c_name)
            canonical_by_key[(d_id, k)] = {
                "barangay_name": c_name,
                "district_id": d_id,
                "population_2020": b.get("population_2020", 0),
                "land_area_ha": b.get("land_area_ha", 0.0)
            }
    return canonical_by_key, cpdd


def extract_wacs_data(pdf_path, cpdd_path):
    sha256 = compute_sha256(pdf_path)
    canonical_by_key, cpdd = load_canonical_barangays(cpdd_path)

    reader = PdfReader(pdf_path)

    # Regex capturing row:
    # AREA_NUM BARANGAY_NAME LAND_AREA POP2020 POP2021 KG_PER_DAY TONS_PER_DAY
    # Allows unicode (including ñ)
    pattern = re.compile(
        r"^(\d+)\s+"
        r"(.+?)\s+"
        r"([\d\.,]+)\s+"
        r"([\d\.,]+)\s+"
        r"([\d\.,]+)\s+"
        r"([\d\.,]+)\s+"
        r"([\d\.,]+)$"
    )

    current_district = "I"
    extracted_records = {}

    for p_idx, page in enumerate(reader.pages):
        text = page.extract_text()
        for line in text.splitlines():
            line_s = line.strip()

            # Track district boundaries
            if "DISTRICT II TOTAL" in line_s:
                current_district = "III"
                continue
            elif "DISTRICT III TOTAL" in line_s:
                current_district = "IV"
                continue
            elif "DISTRICT IV TOTAL" in line_s:
                current_district = "V"
                continue
            elif "DISTRICT V TOTAL" in line_s:
                current_district = "VI"
                continue
            elif "DISTRICT II" in line_s and "TOTAL" not in line_s:
                current_district = "II"
            elif "DISTRICT III" in line_s and "TOTAL" not in line_s:
                current_district = "III"
            elif "DISTRICT IV" in line_s and "TOTAL" not in line_s:
                current_district = "IV"
            elif "DISTRICT V" in line_s and "TOTAL" not in line_s:
                current_district = "V"
            elif "DISTRICT VI" in line_s and "TOTAL" not in line_s:
                current_district = "VI"

            # Page 2 begins with District II
            if p_idx == 1 and current_district == "I":
                current_district = "II"

            m = pattern.match(line_s)
            if m:
                area_num = int(m.group(1))
                raw_name = m.group(2).strip()
                land_area_ha = float(m.group(3).replace(",", ""))
                pop_2020 = int(m.group(4).replace(",", ""))
                pop_2021 = int(m.group(5).replace(",", ""))
                kg_per_day = float(m.group(6).replace(",", ""))
                tons_per_day = float(m.group(7).replace(",", ""))

                # Skip non-barangay areas from general list, keep them in special metadata
                if area_num == 0 or "Quezon Memorial Circle" in raw_name or "Reservoir" in raw_name:
                    continue

                k = normalize_key(raw_name)
                canonical = canonical_by_key.get((current_district, k))
                if not canonical:
                    for (cand_d, cand_k), cand_data in canonical_by_key.items():
                        if cand_d == current_district and (k in cand_k or cand_k in k):
                            canonical = cand_data
                            break

                canon_name = canonical["barangay_name"] if canonical else raw_name

                # Calculate derived indicators
                kg_per_capita = round(kg_per_day / pop_2020, 3) if pop_2020 > 0 else 0.0
                density_kg_per_ha = round(kg_per_day / land_area_ha, 2) if land_area_ha > 0 else 0.0

                # Sanitation Risk Level based on waste density (kg/ha/day)
                if density_kg_per_ha >= 500.0:
                    risk_level = "Very High"
                    risk_score = 4
                elif density_kg_per_ha >= 250.0:
                    risk_level = "High"
                    risk_score = 3
                elif density_kg_per_ha >= 100.0:
                    risk_level = "Moderate"
                    risk_score = 2
                else:
                    risk_level = "Low"
                    risk_score = 1

                record = {
                    "area_id": area_num,
                    "raw_name": raw_name,
                    "barangay_name": canon_name,
                    "district_id": current_district,
                    "land_area_ha": land_area_ha,
                    "population_2020": pop_2020,
                    "projected_population_2021": pop_2021,
                    "waste_kg_per_day": kg_per_day,
                    "waste_tons_per_day": tons_per_day,
                    "waste_kg_per_capita_per_day": kg_per_capita,
                    "waste_generation_density_kg_per_ha": density_kg_per_ha,
                    "sanitation_risk_level": risk_level,
                    "sanitation_risk_score": risk_score
                }

                extracted_records[(current_district, canon_name)] = record

    # Validate barangay counts per district
    districts_output = {}
    citywide_kg_per_day = 0.0
    citywide_tons_per_day = 0.0
    citywide_pop_2020 = 0
    all_records = list(extracted_records.values())

    for d_id, expected_count in EXPECTED_BARANGAY_COUNTS.items():
        dist_info = cpdd["districts"][d_id]
        d_barangays = []
        for b in dist_info["barangays"]:
            b_name = b["barangay_name"]
            rec = extracted_records.get((d_id, b_name))
            if not rec:
                raise ValueError(f"Missing WACS record for District {d_id} barangay: {b_name}")
            d_barangays.append(rec)

        d_kg = round(sum(r["waste_kg_per_day"] for r in d_barangays), 2)
        d_tons = round(sum(r["waste_tons_per_day"] for r in d_barangays), 2)
        d_pop = sum(r["population_2020"] for r in d_barangays)
        d_ha = round(sum(r["land_area_ha"] for r in d_barangays), 2)
        d_density = round(d_kg / d_ha, 2) if d_ha > 0 else 0.0

        top_gen = max(d_barangays, key=lambda r: r["waste_kg_per_day"])
        high_dens = max(d_barangays, key=lambda r: r["waste_generation_density_kg_per_ha"])

        citywide_kg_per_day += d_kg
        citywide_tons_per_day += d_tons
        citywide_pop_2020 += d_pop

        districts_output[d_id] = {
            "district_id": d_id,
            "name": dist_info["name"],
            "barangay_count": len(d_barangays),
            "population_2020": d_pop,
            "total_land_area_ha": d_ha,
            "total_waste_kg_per_day": d_kg,
            "total_waste_tons_per_day": d_tons,
            "average_waste_density_kg_per_ha": d_density,
            "top_waste_generator": {
                "barangay_name": top_gen["barangay_name"],
                "waste_kg_per_day": top_gen["waste_kg_per_day"],
                "waste_tons_per_day": top_gen["waste_tons_per_day"]
            },
            "highest_waste_density_barangay": {
                "barangay_name": high_dens["barangay_name"],
                "waste_generation_density_kg_per_ha": high_dens["waste_generation_density_kg_per_ha"]
            },
            "risk_distribution": {
                "very_high": sum(1 for r in d_barangays if r["sanitation_risk_level"] == "Very High"),
                "high": sum(1 for r in d_barangays if r["sanitation_risk_level"] == "High"),
                "moderate": sum(1 for r in d_barangays if r["sanitation_risk_level"] == "Moderate"),
                "low": sum(1 for r in d_barangays if r["sanitation_risk_level"] == "Low")
            },
            "barangays": d_barangays
        }

    # Top citywide generators
    top_city_generators = sorted(all_records, key=lambda r: r["waste_kg_per_day"], reverse=True)[:10]
    top_city_density = sorted(all_records, key=lambda r: r["waste_generation_density_kg_per_ha"], reverse=True)[:10]

    dataset = {
        "dataset_id": "qc_wacs_waste_generation_2021",
        "title": "Quezon City Waste Generation per Barangay Reference Data (WACS 2021)",
        "is_authoritative_reference": True,
        "reference_year": 2021,
        "publisher": "Quezon City Task Force on Solid Waste Management (TFSWM) & EPWMD",
        "source_document": {
            "title": "Waste Generated per Barangay 2021.pdf",
            "sha256": sha256
        },
        "epidemiological_relevance": (
            "Solid waste accumulation and discarded containers (plastics, tin cans, food wrappers, tires) "
            "provide prime artificial container breeding habitats for Aedes aegypti mosquitoes. High waste "
            "generation density (kg/ha/day) represents an environmental sanitation risk factor targeted under "
            "the DOH 4S Strategy (Search and Destroy)."
        ),
        "city_summary": {
            "total_districts": 6,
            "total_barangays": 142,
            "city_population_2020": citywide_pop_2020,
            "total_waste_kg_per_day": round(citywide_kg_per_day, 2),
            "total_waste_tons_per_day": round(citywide_tons_per_day, 2),
            "city_waste_per_capita_kg_per_day": round(citywide_kg_per_day / citywide_pop_2020, 3) if citywide_pop_2020 > 0 else 0.0,
            "risk_summary": {
                "very_high_risk_barangays": sum(1 for r in all_records if r["sanitation_risk_level"] == "Very High"),
                "high_risk_barangays": sum(1 for r in all_records if r["sanitation_risk_level"] == "High"),
                "moderate_risk_barangays": sum(1 for r in all_records if r["sanitation_risk_level"] == "Moderate"),
                "low_risk_barangays": sum(1 for r in all_records if r["sanitation_risk_level"] == "Low")
            }
        },
        "top_10_waste_generators": [
            {
                "rank": idx + 1,
                "barangay_name": r["barangay_name"],
                "district_id": r["district_id"],
                "population_2020": r["population_2020"],
                "waste_kg_per_day": r["waste_kg_per_day"],
                "waste_tons_per_day": r["waste_tons_per_day"]
            }
            for idx, r in enumerate(top_city_generators)
        ],
        "top_10_highest_waste_density": [
            {
                "rank": idx + 1,
                "barangay_name": r["barangay_name"],
                "district_id": r["district_id"],
                "land_area_ha": r["land_area_ha"],
                "waste_generation_density_kg_per_ha": r["waste_generation_density_kg_per_ha"],
                "sanitation_risk_level": r["sanitation_risk_level"]
            }
            for idx, r in enumerate(top_city_density)
        ],
        "districts": districts_output
    }

    return dataset


def write_outputs(dataset, json_path, js_path):
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    print(f"Wrote authoritative JSON to: {json_path}")

    os.makedirs(os.path.dirname(js_path), exist_ok=True)
    js_content = (
        f"// Authoritative WACS Solid Waste Reference Dataset (2021)\n"
        f"// Generated automatically from {dataset['source_document']['title']}\n"
        f"window.QC_WACS_WASTE_DATA = {json.dumps(dataset, indent=2, ensure_ascii=False)};\n"
    )
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"Wrote offline JS file to: {js_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract WACS 2021 solid waste dataset.")
    parser.add_argument("--pdf", default=DEFAULT_PDF, help="Path to WACS PDF")
    parser.add_argument("--cpdd", default=DEFAULT_CPDD_JSON, help="Path to CPDD reference JSON")
    parser.add_argument("--out-json", default=OUTPUT_JSON, help="Output JSON path")
    parser.add_argument("--out-js", default=OUTPUT_JS, help="Output JS path")
    args = parser.parse_args()

    print(f"Reading PDF: {args.pdf}")
    dataset = extract_wacs_data(args.pdf, args.cpdd)
    write_outputs(dataset, args.out_json, args.out_js)

    print("\nExtraction complete and verified:")
    print(f"  Districts: {len(dataset['districts'])}")
    total_b = sum(len(d['barangays']) for d in dataset['districts'].values())
    print(f"  Barangays processed: {total_b} (Expected 142)")
    print(f"  Citywide Waste: {dataset['city_summary']['total_waste_tons_per_day']} tons/day")
    for d_id, d_data in dataset["districts"].items():
        print(f"    District {d_id}: {d_data['barangay_count']} barangays, {d_data['total_waste_tons_per_day']} tons/day (Top: {d_data['top_waste_generator']['barangay_name']} {d_data['top_waste_generator']['waste_tons_per_day']} tons/day, Density: {d_data['average_waste_density_kg_per_ha']} kg/ha)")


if __name__ == "__main__":
    main()
