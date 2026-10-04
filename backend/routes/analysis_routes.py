from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.prediction_service import get_feature_info, get_history
from utils.api_errors import model_error_response

analysis_bp = Blueprint("analysis_bp", __name__)


@analysis_bp.route("/features", methods=["GET"])
def features():
    try:
        return jsonify(get_feature_info())
    except Exception as exc:
        return model_error_response(exc)


@analysis_bp.route("/history", methods=["GET"])
def history():
    limit = request.args.get("limit", default=200, type=int)
    limit = max(1, min(limit, 1000))
    return jsonify(get_history(limit=limit))
