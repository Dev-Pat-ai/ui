#!/usr/bin/env python3
"""
import_cdra_flood_data.py

Extracts authoritative flood vulnerability and hazard data from:
  "Climate and Disaster Risk Assessment (CDRA) Report for Quezon City 2022.pdf"

Tables extracted:
  - Table 71 (Page 239): 3-Tier Barangay Vulnerability Index (BVI) Flood Hotspot Barangays
  - Tables 14-19 (Pages 67-72): MGB Flood Susceptibility in Districts 1 to 6

Outputs:
  - data/authoritative/cdra/qc_flood_vulnerability_2022.json
  - frontend/js/cdra-flood-data.js
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pypdf import PdfReader

DEFAULT_PDF = os.path.join("data", "raw", "Climate and Disaster Risk Assessment (CDRA) Report for Quezon City 2022.pdf")
DEFAULT_CPDD_JSON = os.path.join("data", "authoritative", "cpdd", "district_profiles_2020.json")
OUTPUT_JSON = os.path.join("data", "authoritative", "cdra", "qc_flood_vulnerability_2022.json")
OUTPUT_JS = os.path.join("frontend", "js", "cdra-flood-data.js")

ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
INT_TO_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}


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
    canonical_list = []
    for d_id, dist_info in cpdd["districts"].items():
        for b in dist_info["barangays"]:
            c_name = b["barangay_name"]
            k = normalize_key(c_name)
            canonical_by_key[(d_id, k)] = {
                "barangay_name": c_name,
                "district_id": d_id,
                "population_2020": b.get("population_2020", 0),
                "population_density_per_ha": b.get("population_density_per_ha", 0),
                "land_area_ha": b.get("land_area_ha", 0.0)
            }
            canonical_list.append((d_id, c_name))
    return canonical_by_key, canonical_list, cpdd


def extract_table_71_hotspots(reader, canonical_by_key):
    # Page 239 in 1-indexed (index 238)
    page_text = reader.pages[238].extract_text() or ""
    hotspots = []
    
    # Line pattern: rank, barangay name, BVI score, district number
    pattern = re.compile(r"^(\d+)\s+(.+?)\s+(\d+)\s+(\d+)$")
    
    for line in page_text.splitlines():
        line_s = line.strip()
        m = pattern.match(line_s)
        if m:
            rank = int(m.group(1))
            raw_name = m.group(2).strip()
            bvi = int(m.group(3))
            d_num = int(m.group(4))
            d_id = INT_TO_ROMAN.get(d_num, str(d_num))

            if rank <= 9:
                tier = "Tier 1: Very High Vulnerability"
                tier_level = "Tier 1"
            elif rank <= 12:
                tier = "Tier 2: High Vulnerability"
                tier_level = "Tier 2"
            else:
                tier = "Tier 3: Moderate Vulnerability"
                tier_level = "Tier 3"

            # Match to canonical
            k = normalize_key(raw_name)
            match = canonical_by_key.get((d_id, k))
            if not match:
                # fallback search across keys
                for (cand_d, cand_k), cand_data in canonical_by_key.items():
                    if cand_d == d_id and (k in cand_k or cand_k in k):
                        match = cand_data
                        break

            canon_name = match["barangay_name"] if match else raw_name

            hotspots.append({
                "rank": rank,
                "raw_name": raw_name,
                "barangay_name": canon_name,
                "district_id": d_id,
                "bvi_score": bvi,
                "tier": tier,
                "tier_level": tier_level
            })

    if len(hotspots) != 21:
        raise ValueError(f"Expected 21 hotspot barangays from Table 71, found {len(hotspots)}")

    return hotspots


def extract_mgb_flood_tables(reader, canonical_by_key):
    # Table 14: Dist I (page 67)
    # Table 15: Dist II (page 68)
    # Table 16: Dist III (page 69)
    # Table 17: Dist IV (page 70)
    # Table 18: Dist V (page 72, upper half)
    # Table 19: Dist VI (page 72, lower half)

    row_pattern = re.compile(r"^(.*?)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)$")
    
    district_slices = []

    # District 1 (p67)
    district_slices.append(("I", reader.pages[66].extract_text() or ""))
    # District 2 (p68)
    district_slices.append(("II", reader.pages[67].extract_text() or ""))
    # District 3 (p69)
    district_slices.append(("III", reader.pages[68].extract_text() or ""))
    # District 4 (p70)
    district_slices.append(("IV", reader.pages[69].extract_text() or ""))
    
    # Page 72 contains both Table 18 (District 5) and Table 19 (District 6)
    p72_text = reader.pages[71].extract_text() or ""
    split_marker = "Table 19. Flood Susceptibility in District 6"
    if split_marker in p72_text:
        d5_text, d6_text = p72_text.split(split_marker, 1)
    else:
        d5_text = p72_text
        d6_text = ""

    district_slices.append(("V", d5_text))
    district_slices.append(("VI", d6_text))

    mgb_records = {}

    for d_id, text in district_slices:
        for line in text.splitlines():
            line_s = line.strip()
            if any(h in line_s.lower() for h in ["table ", "barangay", "depth", "source of data", "flood susceptibility", "district "]):
                continue
            m = row_pattern.match(line_s)
            if m:
                raw_name = m.group(1).strip()
                v_0_5_to_1 = float(m.group(2))
                v_1_to_2 = float(m.group(3))
                v_gt_2 = float(m.group(4))
                total = float(m.group(5))

                k = normalize_key(raw_name)
                match = canonical_by_key.get((d_id, k))
                if not match:
                    for (cand_d, cand_k), cand_data in canonical_by_key.items():
                        if cand_d == d_id and (k in cand_k or cand_k in k):
                            match = cand_data
                            break

                canon_name = match["barangay_name"] if match else raw_name

                if (d_id, canon_name) in mgb_records:
                    raise ValueError(f"Duplicate MGB row: {d_id} / {canon_name}")
                if not match:
                    raise ValueError(f"Unmatched MGB barangay: {d_id} / {raw_name}")
                if any(not 0 <= value <= 100 for value in (v_0_5_to_1, v_1_to_2, v_gt_2, total)):
                    raise ValueError(f"Invalid flood percentage: {d_id} / {raw_name}")
                mgb_records[(d_id, canon_name)] = {
                    "raw_name": raw_name,
                    "depth_0_5m_to_1m_pct": v_0_5_to_1,
                    "depth_1m_to_2m_pct": v_1_to_2,
                    "depth_gt_2m_pct": v_gt_2,
                    "total_flooded_area_pct": total
                }

    return mgb_records


def build_unified_dataset(pdf_path, cpdd_path):
    sha256 = compute_sha256(pdf_path)
    canonical_by_key, canonical_list, cpdd = load_canonical_barangays(cpdd_path)

    reader = PdfReader(pdf_path)
    hotspots = extract_table_71_hotspots(reader, canonical_by_key)
    mgb_records = extract_mgb_flood_tables(reader, canonical_by_key)
    if len(mgb_records) != 119:
        raise ValueError(f"Expected 119 source MGB records, found {len(mgb_records)}")

    hotspot_by_name = {h["barangay_name"]: h for h in hotspots}

    districts_output = {}
    city_hotspot_count = len(hotspots)
    city_mgb_record_count = len(mgb_records)

    for d_id, dist_info in cpdd["districts"].items():
        barangay_list = []
        flooded_percentages = []
        d_hotspots = []

        for b in dist_info["barangays"]:
            b_name = b["barangay_name"]
            mgb = mgb_records.get((d_id, b_name))
            hs = hotspot_by_name.get(b_name)

            if mgb:
                flooded_pct = mgb["total_flooded_area_pct"]
                depth_0_5_1 = mgb["depth_0_5m_to_1m_pct"]
                depth_1_2 = mgb["depth_1m_to_2m_pct"]
                depth_gt_2 = mgb["depth_gt_2m_pct"]
                has_mgb = True
            else:
                flooded_pct = None
                depth_0_5_1 = None
                depth_1_2 = None
                depth_gt_2 = None
                has_mgb = False

            if has_mgb:
                flooded_percentages.append(flooded_pct)

            # Assign Vulnerability Level
            if hs and hs["tier_level"] == "Tier 1":
                vuln_level = "Very High"
                vuln_score = 4
            elif hs and hs["tier_level"] == "Tier 2":
                vuln_level = "High"
                vuln_score = 3
            elif flooded_pct is not None and flooded_pct >= 50.0:
                vuln_level = "High"
                vuln_score = 3
            elif (hs and hs["tier_level"] == "Tier 3") or (flooded_pct is not None and flooded_pct >= 20.0):
                vuln_level = "Moderate"
                vuln_score = 2
            elif flooded_pct is not None and flooded_pct > 0.0:
                vuln_level = "Low"
                vuln_score = 1
            elif has_mgb:
                vuln_level = "Minimal / None"
                vuln_score = 0
            else:
                vuln_level = "Unknown"
                vuln_score = None

            entry = {
                "barangay_name": b_name,
                "district_id": d_id,
                "population_2020": b.get("population_2020", 0),
                "population_density_per_ha": b.get("population_density_per_ha", 0),
                "land_area_ha": b.get("land_area_ha", 0.0),
                "flood_hazard": {
                    "has_mgb_record": has_mgb,
                    "missing_reason": None if has_mgb else "Barangay not listed in source MGB tables; not a measured zero.",
                    "submerged_pct_0_5m_to_1m": depth_0_5_1,
                    "submerged_pct_1m_to_2m": depth_1_2,
                    "submerged_pct_gt_2m": depth_gt_2,
                    "total_flooded_area_pct": flooded_pct,
                    "vulnerability_level": vuln_level,
                    "vulnerability_score": vuln_score
                },
                "hotspot_profile": {
                    "is_hotspot": hs is not None,
                    "bvi_rank": hs["rank"] if hs else None,
                    "bvi_score": hs["bvi_score"] if hs else None,
                    "tier": hs["tier"] if hs else None,
                    "tier_level": hs["tier_level"] if hs else None
                }
            }

            if hs:
                d_hotspots.append(entry)

            barangay_list.append(entry)

        avg_flooded = round(sum(flooded_percentages) / len(flooded_percentages), 2) if flooded_percentages else None
        max_flooded = max(flooded_percentages) if flooded_percentages else None
        max_b_name = next((b["barangay_name"] for b in barangay_list if b["flood_hazard"]["total_flooded_area_pct"] == max_flooded), "")

        districts_output[d_id] = {
            "district_id": d_id,
            "name": dist_info["name"],
            "barangay_count": len(barangay_list),
            "hotspot_count": len(d_hotspots),
            "tier1_count": sum(1 for b in d_hotspots if b["hotspot_profile"]["tier_level"] == "Tier 1"),
            "tier2_count": sum(1 for b in d_hotspots if b["hotspot_profile"]["tier_level"] == "Tier 2"),
            "tier3_count": sum(1 for b in d_hotspots if b["hotspot_profile"]["tier_level"] == "Tier 3"),
            "average_flooded_area_pct": avg_flooded,
            "flood_record_count": len(flooded_percentages),
            "missing_flood_record_count": len(barangay_list) - len(flooded_percentages),
            "average_scope": "Unweighted mean of listed barangays only; not district land-area exposure.",
            "max_flooded_area_pct": max_flooded,
            "most_susceptible_barangay": max_b_name,
            "barangays": barangay_list
        }

    dataset = {
        "dataset_id": "qc_cdra_flood_vulnerability_2022",
        "title": "Quezon City CDRA Flood Vulnerability and BVI Hotspots (2022)",
        "is_authoritative_reference": True,
        "reference_year": 2022,
        "publisher": "Quezon City Government (CPDDO / QCDRRMO) & Earthquakes and Megacities Initiative (EMI)",
        "sources": [
            "Climate and Disaster Risk Assessment (CDRA) Report for Quezon City 2022",
            "Mines and Geosciences Bureau (MGB) Flood Susceptibility Map (2021)",
            "Quezon City Drainage Master Plan (QC-DMP) Study (2021-2022)"
        ],
        "source_document": {
            "title": "Climate and Disaster Risk Assessment (CDRA) Report for Quezon City 2022.pdf",
            "sha256": sha256
        },
        "epidemiological_relevance": (
            "Static flood susceptibility is a candidate environmental covariate. "
            "Its association with dengue has not been estimated by this project. "
            "BVI tiers and project-derived vulnerability labels are not dengue probabilities."
        ),
        "missing_data_policy": "Unlisted MGB records are null, not zero; summaries exclude unlisted barangays.",
        "classification_method": "BVI tiers where listed; otherwise project thresholds at >0%, 20%, 50% flooded area. Not an official dengue risk taxonomy.",
        "city_summary": {
            "total_districts": 6,
            "total_barangays": 142,
            "bvi_hotspots_total": city_hotspot_count,
            "barangays_with_mgb_flood_records": city_mgb_record_count,
            "tier1_hotspots": sum(1 for h in hotspots if h["tier_level"] == "Tier 1"),
            "tier2_hotspots": sum(1 for h in hotspots if h["tier_level"] == "Tier 2"),
            "tier3_hotspots": sum(1 for h in hotspots if h["tier_level"] == "Tier 3")
        },
        "hotspots": hotspots,
        "districts": districts_output
    }

    return dataset


def write_outputs(dataset, json_path, js_path=None):
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    print(f"Wrote authoritative JSON to: {json_path}")

    if js_path is None:
        return
    # Offline-safe JavaScript asset
    os.makedirs(os.path.dirname(js_path), exist_ok=True)
    js_content = f"// Authoritative CDRA Flood Vulnerability Reference Dataset (2022)\n// Generated automatically from {dataset['source_document']['title']}\nwindow.QC_CDRA_FLOOD_DATA = {json.dumps(dataset, indent=2, ensure_ascii=False)};\n"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"Wrote offline JS file to: {js_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract CDRA 2022 flood vulnerability dataset.")
    parser.add_argument("--pdf", default=DEFAULT_PDF, help="Path to CDRA PDF")
    parser.add_argument("--cpdd", default=DEFAULT_CPDD_JSON, help="Path to CPDD reference JSON")
    parser.add_argument("--out-json", default=OUTPUT_JSON, help="Output JSON path")
    parser.add_argument("--out-js", default=OUTPUT_JS, help="Output JS path")
    parser.add_argument("--backend-only", action="store_true", help="Update canonical JSON without changing frontend assets")
    args = parser.parse_args()

    print(f"Reading PDF: {args.pdf}")
    dataset = build_unified_dataset(args.pdf, args.cpdd)
    write_outputs(dataset, args.out_json, None if args.backend_only else args.out_js)

    print("\nExtraction complete and verified:")
    print(f"  Districts: {len(dataset['districts'])}")
    total_b = sum(len(d['barangays']) for d in dataset['districts'].values())
    print(f"  Barangays processed: {total_b} (Expected 142)")
    print(f"  BVI Hotspots: {len(dataset['hotspots'])} (Expected 21)")
    for d_id, d_data in dataset["districts"].items():
        print(f"    District {d_id}: {d_data['barangay_count']} barangays, {d_data['hotspot_count']} hotspots, Avg flooded area: {d_data['average_flooded_area_pct']}% (Max: {d_data['most_susceptible_barangay']} {d_data['max_flooded_area_pct']}%)")


if __name__ == "__main__":
    main()
