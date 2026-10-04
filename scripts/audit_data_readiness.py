import csv
import json
import sys
from pathlib import Path

# Add backend to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.services.data_readiness_service import DataReadinessService

def run_audit():
    contract_path = project_root / "data" / "contracts" / "research_data_contract.json"
    service = DataReadinessService(contract_path)

    print("=" * 60)
    print("  DENGUE RESEARCH DATA READINESS AUDIT")
    print("=" * 60)

    findings = service.audit_raw_data()

    # Terminal Summary
    print(f"Overall Status: {findings['overall_status']}")
    print(f"Datasets Inspected: {len(findings['inventory'])}")
    for f in findings["inventory"]:
        yr_range = f"{f['year_range']['start']}-{f['year_range']['end']}" if f.get('year_range') else "unknown"
        print(f" - {f['filename']} ({f['type']}): {f['row_count']} rows, Year range: {yr_range}")
        print(f"   Geographic: {f['geographic_resolution']}, Temporal: {f['temporal_resolution']}")

    print("\nFeature Summary:")
    counts = {"AVAILABLE": 0, "MISSING": 0, "WRONG_TEMPORAL_LEVEL": 0, "WRONG_GEOGRAPHIC_LEVEL": 0, "SOURCE_MISMATCH": 0}
    for feat in findings["feature_readiness"]:
        status = feat["status"]
        counts[status] = counts.get(status, 0) + 1

    for status, count in counts.items():
        print(f" - {status}: {count}")

    print("\nGlobal Mismatches:")
    for m in findings["mismatches"]:
        print(f" [!] {m}")

    print("\nUnresolved Research Decisions:")
    for decision, details in findings["unresolved_decisions"].items():
        print(f" [?] {decision.replace('_', ' ').title()}: {details.get('status')}")

    # Generate Reports
    reports_dir = project_root / "output" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "data_readiness_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2)
    print(f"\nJSON report generated: {json_path}")

    csv_path = reports_dir / "data_readiness_summary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Category", "Canonical Feature", "Expected Source", "Detected File",
            "Detected Sheet", "Detected Column", "Expected Temporal", "Detected Temporal",
            "Expected Geographic", "Detected Geographic", "Readiness Status", "Mismatches", "Notes"
        ])
        for feat in findings["feature_readiness"]:
            writer.writerow([
                feat["category"],
                feat["canonical_name"],
                next((f["expected_source"] for f in service.contract["feature_registry"] if f["canonical_name"] == feat["canonical_name"]), ""),
                feat["detected_file"] or "",
                feat["detected_sheet"] or "",
                feat["detected_column"] or "",
                next((f["expected_temporal_resolution"] for f in service.contract["feature_registry"] if f["canonical_name"] == feat["canonical_name"]), ""),
                feat["detected_temporal"] or "",
                next((f["expected_geographic_resolution"] for f in service.contract["feature_registry"] if f["canonical_name"] == feat["canonical_name"]), ""),
                feat["detected_geographic"] or "",
                feat["status"],
                ", ".join(feat["mismatches"]),
                ""
            ])
    print(f"CSV summary generated: {csv_path}")
    print("=" * 60)

if __name__ == "__main__":
    run_audit()
