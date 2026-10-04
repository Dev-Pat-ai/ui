"""Extract and validate CPDD/PSA 2020 district reference data from six map PDFs.

Usage:
    python scripts/import_cpdd_district_maps.py --pdf-dir /path/to/pdfs

The script requires Poppler's ``pdftotext`` command. It writes a canonical JSON
file for the backend and a compact JavaScript copy for offline frontend use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any


ROMAN_BY_NUMBER = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}
EXPECTED_BARANGAY_COUNTS = {"I": 37, "II": 5, "III": 37, "IV": 38, "V": 14, "VI": 11}
EXPECTED_CITY_POPULATION = 2_960_048

STANDARD_ROW_RE = re.compile(
    r"^\s*(?P<source_area_id>\d+)\s+(?P<barangay_name>.+?)\s+"
    r"(?P<land_area_sqm>[\d,]+\.\d{2})\s+"
    r"(?P<land_area_sq_km>\d+\.\d{2})\s+"
    r"(?P<land_area_ha>[\d,]+\.\d{2})\s+"
    r"(?P<population_2020>[\d,]+)\s+"
    r"(?P<population_density_per_ha>\d+)\s*$"
)

TOTAL_RE_TEMPLATE = (
    r"^DISTRICT\s+{roman}\s+TOTAL\s+"
    r"(?P<land_area_sqm>[\d,]+\.\d{{2}})\s+"
    r"(?P<land_area_sq_km>\d+\.\d{{2}})\s+"
    r"(?P<land_area_ha>[\d,]+\.\d{{2}})\s+"
    r"(?P<population_2020>[\d,]+)\s+"
    r"(?P<population_density_per_ha>\d+)\s*$"
)

D2_NAMES = {
    "BagongSilangan": "Bagong Silangan",
    "BatasanHills": "Batasan Hills",
    "Commonwealth": "Commonwealth",
    "HolySpirit": "Holy Spirit",
    "Payatas": "Payatas",
}

D2_ROW_RE = re.compile(
    r"^(?P<source_area_id>\d+)(?P<compact_name>[A-Za-z]+)"
    r"(?P<land_area_sqm>[\d,]+\.\d{2})"
    r"(?P<land_area_sq_km>\d+\.\d{2})"
    r"(?P<land_area_ha>[\d,]+\.\d{2})"
    r"(?P<population_2020>[\d,]+)"
    r"(?P<population_density_per_ha>\d{3})$"
)

D2_TOTAL_RE = re.compile(
    r"^DISTRICTIITOTAL"
    r"(?P<land_area_sqm>[\d,]+\.\d{2})"
    r"(?P<land_area_sq_km>\d+\.\d{2})"
    r"(?P<land_area_ha>[\d,]+\.\d{2})"
    r"(?P<population_2020>[\d,]+)"
    r"(?P<population_density_per_ha>\d{3})$"
)


def decimal_value(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def integer_value(value: str) -> int:
    return int(value.replace(",", ""))


def row_from_groups(groups: dict[str, str], *, name: str | None = None) -> dict[str, Any]:
    return {
        "source_area_id": int(groups["source_area_id"]),
        "barangay_name": name or groups["barangay_name"].strip(),
        "land_area_sqm": float(decimal_value(groups["land_area_sqm"])),
        "land_area_sq_km": float(decimal_value(groups["land_area_sq_km"])),
        "land_area_ha": float(decimal_value(groups["land_area_ha"])),
        "population_2020": integer_value(groups["population_2020"]),
        "population_density_per_ha": integer_value(groups["population_density_per_ha"]),
    }


def summary_from_groups(groups: dict[str, str]) -> dict[str, Any]:
    return {
        "land_area_sqm": float(decimal_value(groups["land_area_sqm"])),
        "land_area_sq_km": float(decimal_value(groups["land_area_sq_km"])),
        "land_area_ha": float(decimal_value(groups["land_area_ha"])),
        "population_2020": integer_value(groups["population_2020"]),
        "population_density_per_ha": integer_value(groups["population_density_per_ha"]),
    }


def extract_pdf_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-raw", str(pdf_path), "-"],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def parse_special_barangay(text: str, pattern: str, name: str) -> dict[str, Any]:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"Could not extract special multi-line row: {name}")
    return row_from_groups(match.groupdict(), name=name)


def parse_standard_district(text: str, number: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    roman = ROMAN_BY_NUMBER[number]
    rows = []
    for line in text.splitlines():
        match = STANDARD_ROW_RE.match(line)
        if match:
            rows.append(row_from_groups(match.groupdict()))

    if number == 1:
        rows.append(
            parse_special_barangay(
                text,
                r"^(?P<source_area_id>6)\s*\nN\. S\. Amoranto\s*\n\(Gintong Silahis\)\s*\n"
                r"(?P<land_area_sqm>[\d,]+\.\d{2})\s+"
                r"(?P<land_area_sq_km>\d+\.\d{2})\s+"
                r"(?P<land_area_ha>[\d,]+\.\d{2})\s+"
                r"(?P<population_2020>[\d,]+)\s+"
                r"(?P<population_density_per_ha>\d+)\s*$",
                "N. S. Amoranto (Gintong Silahis)",
            )
        )
    if number == 4:
        rows.append(
            parse_special_barangay(
                text,
                r"^(?P<source_area_id>20)\s*\nBagong Lipunan ng\s*\nCrame\s*\n"
                r"(?P<land_area_sqm>[\d,]+\.\d{2})\s+"
                r"(?P<land_area_sq_km>\d+\.\d{2})\s+"
                r"(?P<land_area_ha>[\d,]+\.\d{2})\s+"
                r"(?P<population_2020>[\d,]+)\s+"
                r"(?P<population_density_per_ha>\d+)\s*$",
                "Bagong Lipunan ng Crame",
            )
        )
    total_pattern = re.compile(TOTAL_RE_TEMPLATE.format(roman=roman))
    total_match = next((total_pattern.match(line) for line in text.splitlines() if total_pattern.match(line)), None)
    if not total_match:
        raise ValueError(f"Could not extract District {roman} total")

    rows.sort(key=lambda row: row["barangay_name"].casefold())
    return rows, summary_from_groups(total_match.groupdict())


def parse_district_two(text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    total = None
    for line in text.splitlines():
        compact = re.sub(r"\s+", "", line)
        row_match = D2_ROW_RE.match(compact)
        if row_match and row_match.group("compact_name") in D2_NAMES:
            groups = row_match.groupdict()
            groups["barangay_name"] = D2_NAMES[groups.pop("compact_name")]
            rows.append(row_from_groups(groups))
        total_match = D2_TOTAL_RE.match(compact)
        if total_match:
            total = summary_from_groups(total_match.groupdict())

    if total is None:
        raise ValueError("Could not extract District II total")
    rows.sort(key=lambda row: row["barangay_name"].casefold())
    return rows, total


def parse_non_barangay_areas(text: str, number: int) -> list[dict[str, Any]]:
    if number == 4:
        pattern = re.compile(
            r"^0\s*\nQuezon Memorial Circle\s*\n\(QMC\)\s*\n"
            r"(?P<land_area_sqm>[\d,]+\.\d{2})\s+"
            r"(?P<land_area_sq_km>\d+\.\d{2})\s+"
            r"(?P<land_area_ha>[\d,]+\.\d{2})\s*$",
            flags=re.MULTILINE,
        )
        match = pattern.search(text)
        name = "Quezon Memorial Circle (QMC)"
    elif number == 5:
        pattern = re.compile(
            r"^0\s+Reservoir\s+"
            r"(?P<land_area_sqm>[\d,]+\.\d{2})\s+"
            r"(?P<land_area_sq_km>\d+\.\d{2})\s+"
            r"(?P<land_area_ha>[\d,]+\.\d{2})\s*$",
            flags=re.MULTILINE,
        )
        match = pattern.search(text)
        name = "Reservoir"
    else:
        return []

    if not match:
        raise ValueError(f"Could not extract non-barangay area for District {ROMAN_BY_NUMBER[number]}")
    groups = match.groupdict()
    return [{
        "source_area_id": 0,
        "name": name,
        "land_area_sqm": float(decimal_value(groups["land_area_sqm"])),
        "land_area_sq_km": float(decimal_value(groups["land_area_sq_km"])),
        "land_area_ha": float(decimal_value(groups["land_area_ha"])),
    }]


def find_source_pdf(pdf_dir: Path, number: int) -> Path:
    matches = sorted(pdf_dir.glob(f"District {number} Map (2020)*.pdf"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected exactly one District {number} Map (2020) PDF in {pdf_dir}; found {len(matches)}"
        )
    return matches[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_dataset(dataset: dict[str, Any]) -> None:
    all_names: list[str] = []
    city_population = 0

    for district_id, district in dataset["districts"].items():
        barangays = district["barangays"]
        expected_count = EXPECTED_BARANGAY_COUNTS[district_id]
        if len(barangays) != expected_count:
            raise ValueError(f"District {district_id}: expected {expected_count} barangays, found {len(barangays)}")

        population_sum = sum(row["population_2020"] for row in barangays)
        if population_sum != district["population_2020"]:
            raise ValueError(
                f"District {district_id}: barangay population sum {population_sum:,} "
                f"does not match printed total {district['population_2020']:,}"
            )

        area_sum = sum(Decimal(str(row["land_area_sqm"])) for row in barangays)
        area_sum += sum(Decimal(str(row["land_area_sqm"])) for row in district["non_barangay_areas"])
        printed_area = Decimal(str(district["land_area_sqm"]))
        if abs(area_sum - printed_area) > Decimal("0.02"):
            raise ValueError(
                f"District {district_id}: component area {area_sum} does not match printed total {printed_area}"
            )

        city_population += district["population_2020"]
        all_names.extend(row["barangay_name"] for row in barangays)

    if len(all_names) != 142 or len({name.casefold() for name in all_names}) != 142:
        raise ValueError("Expected 142 unique barangays across the six districts")
    if city_population != EXPECTED_CITY_POPULATION:
        raise ValueError(
            f"Expected city population {EXPECTED_CITY_POPULATION:,}; found {city_population:,}"
        )


def build_dataset(pdf_dir: Path) -> dict[str, Any]:
    districts: dict[str, Any] = {}
    sources = []

    for number, roman in ROMAN_BY_NUMBER.items():
        pdf_path = find_source_pdf(pdf_dir, number)
        text = extract_pdf_text(pdf_path)
        rows, total = parse_district_two(text) if number == 2 else parse_standard_district(text, number)
        non_barangay_areas = parse_non_barangay_areas(text, number)

        districts[roman] = {
            "district_id": roman,
            "name": f"District {roman}",
            "barangay_count": len(rows),
            **total,
            "barangays": rows,
            "non_barangay_areas": non_barangay_areas,
        }
        sources.append({
            "district_id": roman,
            "document_title": f"District {number} Map (2020)",
            "uploaded_filename": pdf_path.name,
            "sha256": sha256(pdf_path),
        })

    dataset = {
        "dataset_id": "qc_cpdd_district_reference_2020",
        "title": "Quezon City District and Barangay Reference Data (2020)",
        "is_authoritative_reference": True,
        "reference_year": 2020,
        "geographic_scope": "Quezon City",
        "publisher": "Quezon City Planning and Development Department (CPDD)",
        "source_label_on_maps": "Quezon City Planning and Development Office",
        "population_source": "Philippine Statistics Authority (PSA), 2020 Census",
        "coordinate_reference": {
            "projected_coordinate_system": "Philippines Zone III",
            "geographic_coordinate_system": "GCS_PRS_1992",
            "datum": "Philippine Reference System 1992",
        },
        "source_documents": sources,
        "notes": [
            "Population, land area, density, barangay membership, and printed district totals were transcribed from the six CPDD district map tables.",
            "Quezon Memorial Circle in District IV and Reservoir in District V are retained as non-barangay areas because they contribute to printed land-area totals but have no population entry.",
            "This reference dataset contains no dengue cases, weather observations, forecasts, or outbreak-risk labels.",
        ],
        "city_summary": {
            "district_count": 6,
            "barangay_count": 142,
            "population_2020": sum(district["population_2020"] for district in districts.values()),
            "land_area_sqm": float(sum(Decimal(str(district["land_area_sqm"])) for district in districts.values())),
            "land_area_sq_km": float(sum(Decimal(str(district["land_area_sq_km"])) for district in districts.values())),
            "land_area_ha": float(sum(Decimal(str(district["land_area_ha"])) for district in districts.values())),
        },
        "districts": districts,
    }
    validate_dataset(dataset)
    return dataset


def frontend_payload(dataset: dict[str, Any]) -> dict[str, Any]:
    districts = {}
    for district_id, district in dataset["districts"].items():
        districts[district_id] = {
            "district_id": district_id,
            "name": district["name"],
            "barangay_count": district["barangay_count"],
            "population_2020": district["population_2020"],
            "land_area_sq_km": district["land_area_sq_km"],
            "population_density_per_ha": district["population_density_per_ha"],
            "barangays": [row["barangay_name"] for row in district["barangays"]],
        }
    return {
        "dataset_id": dataset["dataset_id"],
        "is_authoritative_reference": True,
        "reference_year": dataset["reference_year"],
        "data_source": "CPDD district maps / PSA 2020 Census population",
        "city_summary": dataset["city_summary"],
        "districts": districts,
    }


def write_outputs(dataset: dict[str, Any], project_root: Path) -> None:
    json_path = project_root / "data" / "authoritative" / "cpdd" / "district_profiles_2020.json"
    js_path = project_root / "frontend" / "js" / "cpdd-data.js"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    js_payload = json.dumps(frontend_payload(dataset), ensure_ascii=False, indent=2)
    js_path.write_text(
        "// Generated by scripts/import_cpdd_district_maps.py. Do not edit by hand.\n"
        f"window.CPDD_REFERENCE_2020 = Object.freeze({js_payload});\n",
        encoding="utf-8",
    )

    print(f"Validated 6 districts and {dataset['city_summary']['barangay_count']} barangays.")
    print(f"Population total: {dataset['city_summary']['population_2020']:,}")
    print(f"Wrote {json_path}")
    print(f"Wrote {js_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", type=Path, required=True, help="Directory containing the six district-map PDFs")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="DengueSense project root",
    )
    args = parser.parse_args()
    dataset = build_dataset(args.pdf_dir.resolve())
    write_outputs(dataset, args.project_root.resolve())


if __name__ == "__main__":
    main()
