from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.prediction_service import get_real_dashboard_data
from utils.api_errors import model_error_response
from services.prototype_data_service import (
    load_prototype_forecast,
    load_prototype_historical,
    load_prototype_district_detail
)

prototype_bp = Blueprint("prototype_bp", __name__)


@prototype_bp.route("/prototype/dashboard", methods=["GET"])
def get_dashboard():
    try:
        # Requires observed weekly data; unavailable data must not become invented counts.
        return jsonify(get_real_dashboard_data())
    except Exception as exc:
        return model_error_response(exc)


@prototype_bp.route("/prototype/forecast", methods=["GET"])
def get_forecast():
    try:
        data = load_prototype_forecast()
        district_id = request.args.get("district")
        if district_id:
            district_id = district_id.upper()
            if district_id not in data["forecasts"]:
                raise ValueError(f"Invalid district identifier: {district_id}. Must be I-VI.")
            data["forecasts"] = {district_id: data["forecasts"][district_id]}
            data["selected_district"] = district_id
        return jsonify(data)
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": "invalid_id"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 400


@prototype_bp.route("/prototype/historical", methods=["GET"])
def get_historical():
    try:
        return jsonify(load_prototype_historical())
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "error"}), 400


@prototype_bp.route("/prototype/districts", methods=["GET"])
def get_districts():
    try:
        # Re-using the same real aggregator for districts list
        return jsonify(get_real_dashboard_data())
    except Exception as exc:
        return model_error_response(exc)


@prototype_bp.route("/prototype/districts/<district_id>", methods=["GET"])
def get_district_detail(district_id: str):
    try:
        detail = load_prototype_district_detail(district_id)
        dashboard = get_real_dashboard_data()
        district_name = f"District {district_id}"
        live_summary = next(
            (row for row in dashboard.get("districts", []) if row.get("district") == district_name),
            None,
        )
        if live_summary:
            detail["district"].update(live_summary)
            detail["district"]["recent_cases"] = live_summary["sampleCases"]
        detail["data_provenance"]["observed_weekly_data"] = dashboard.get("data_provenance", {})
        detail.update({
            "is_sample": True,
            "is_experimental": True,
            "sample_updated_at": dashboard.get("sample_updated_at"),
            "data_source": "CPDD/PSA reference and observed weekly counts; remaining sample fields retain demonstration provenance",
        })
        return jsonify(detail)
    except ValueError as exc:
        return jsonify({"error": str(exc), "status": "invalid_id"}), 400
    except KeyError as exc:
        return jsonify({"error": str(exc), "status": "not_found"}), 404
    except Exception as exc:
        return model_error_response(exc)
