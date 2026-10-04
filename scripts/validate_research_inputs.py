import argparse
import json
import sys
from pathlib import Path

# Add backend to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.services.research_data_intake_service import ResearchDataIntakeService

def run_validation():
    parser = argparse.ArgumentParser(description="Validate authoritative research datasets.")
    parser.add_argument("--dengue", type=str, help="Path to weekly dengue cases CSV")
    parser.add_argument("--mapping", type=str, help="Path to barangay-to-district mapping CSV")
    parser.add_argument("--weather", type=str, help="Path to weekly weather CSV")
    parser.add_argument("--features", type=str, help="Path to candidate features CSV")

    args = parser.parse_args()

    contract_path = project_root / "data" / "contracts" / "research_data_contract.json"
    service = ResearchDataIntakeService(contract_path)

    inputs = {
        "dengue_cases": args.dengue,
        "mapping": args.mapping,
        "weather": args.weather,
        "candidate_features": args.features
    }

    overall_report = {
        "status": "VALID",
        "file_reports": []
    }

    critical_error = False
    missing_required = False

    print("=" * 60)
    print("  RESEARCH DATA INTAKE VALIDATION")
    print("=" * 60)

    for file_type, path_str in inputs.items():
        if not path_str:
            print(f"[-] {file_type}: NOT PROVIDED")
            overall_report["file_reports"].append({
                "type": file_type,
                "status": "MISSING_REQUIRED_INPUT"
            })
            if file_type in ["dengue_cases", "weather"]:
                missing_required = True
            continue

        path = Path(path_str)
        report = service.validate_file(path, file_type)
        overall_report["file_reports"].append(report)

        status_icon = "[+]" if report["status"] == "VALID" else "[!]"
        print(f"{status_icon} {file_type}: {report['status']} ({path.name})")

        for err in report["errors"]:
            print(f"    ERROR: {err}")
            critical_error = True
        for warn in report["warnings"]:
            print(f"    WARNING: {warn}")

    if critical_error:
        overall_report["status"] = "ERROR"
    elif missing_required:
        overall_report["status"] = "INCOMPLETE"

    # Generate report
    reports_dir = project_root / "output" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "research_data_validation_report.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(overall_report, f, indent=2)

    print(f"\nFull report saved to: {report_path}")
    print("=" * 60)

    if critical_error:
        sys.exit(1)
    if missing_required:
        print("Required authoritative inputs are missing. Audit remains NOT_READY.")
        sys.exit(0)

if __name__ == "__main__":
    run_validation()
