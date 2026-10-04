from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.cpdd_data_service import (
    load_cpdd_barangays,
    load_cpdd_district_detail,
    load_cpdd_districts,
    load_psa_household_reference,
)
from services.cdra_data_service import (
    load_cdra_flood_vulnerability,
    load_cdra_hotspots,
)
from services.wacs_data_service import (
    load_wacs_waste_generation,
    load_wacs_top_generators,
)
from services.facilities_service import (
    load_facilities_catalog,
    get_facility_category,
)


reference_bp = Blueprint("reference_bp", __name__)


@reference_bp.route("/reference/cpdd/households", methods=["GET"])
def get_psa_households():
    try:
        return jsonify(load_psa_household_reference())
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/cpdd/districts", methods=["GET"])
def get_cpdd_districts():
    try:
        return jsonify(load_cpdd_districts())
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/cpdd/districts/<district_id>", methods=["GET"])
def get_cpdd_district_detail(district_id: str):
    try:
        return jsonify(load_cpdd_district_detail(district_id))
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": "invalid_id"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/cpdd/barangays", methods=["GET"])
def get_cpdd_barangays():
    try:
        district_id = request.args.get("district")
        return jsonify(load_cpdd_barangays(district_id))
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": "invalid_id"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/cdra/flood-vulnerability", methods=["GET"])
def get_cdra_flood_vulnerability():
    try:
        district_id = request.args.get("district")
        return jsonify(load_cdra_flood_vulnerability(district_id))
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": "invalid_id"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/cdra/flood-vulnerability/<district_id>", methods=["GET"])
def get_cdra_district_flood(district_id: str):
    try:
        return jsonify(load_cdra_flood_vulnerability(district_id))
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": "invalid_id"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/cdra/hotspots", methods=["GET"])
def get_cdra_hotspots():
    try:
        return jsonify(load_cdra_hotspots())
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/wacs/waste-generation", methods=["GET"])
def get_wacs_waste_generation():
    try:
        district_id = request.args.get("district")
        return jsonify(load_wacs_waste_generation(district_id))
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": "invalid_id"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/wacs/waste-generation/<district_id>", methods=["GET"])
def get_wacs_district_waste(district_id: str):
    try:
        return jsonify(load_wacs_waste_generation(district_id))
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": "invalid_id"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/wacs/top-generators", methods=["GET"])
def get_wacs_top_generators():
    try:
        return jsonify(load_wacs_top_generators())
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/facilities/catalog", methods=["GET"])
def get_facilities_catalog():
    try:
        return jsonify(load_facilities_catalog())
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500


@reference_bp.route("/reference/facilities/<category_id>", methods=["GET"])
def get_facility_category_route(category_id: str):
    try:
        cat = get_facility_category(category_id)
        if not cat:
            return jsonify({"error": f"Facility category '{category_id}' not found", "status": "not_found"}), 404
        return jsonify(cat)
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 500



