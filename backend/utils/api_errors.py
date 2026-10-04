"""Consistent, actionable model errors without replacing missing data with estimates."""
from flask import jsonify


def model_error_response(exc: Exception, action: str = "Check input values and model data availability."):
    message = str(exc)
    explicit_code = getattr(exc, "code", None)
    if explicit_code == "OBSERVED_WEEKLY_DATA_REQUIRED" or "OBSERVED_WEEKLY_DATA_REQUIRED" in message:
        code, status = "OBSERVED_WEEKLY_DATA_REQUIRED", 503
        action = "Provide validated observed weekly barangay cases. Annual totals cannot replace weekly observations. City evaluation remains separate."
    elif explicit_code == "INVALID_OBSERVED_WEEKLY_DATA" or "INVALID_OBSERVED_WEEKLY_DATA" in message:
        code, status = "INVALID_OBSERVED_WEEKLY_DATA", 422
        action = "Correct the observed weekly dataset using the reported validation error."
    elif "UNSUPPORTED_ENVIRONMENTAL_SCENARIO" in message:
        code, status = "UNSUPPORTED_ENVIRONMENTAL_SCENARIO", 422
        action = "Environmental effects have not been learned. Use supported model evidence only."
    elif "MODEL_NOT_READY" in message:
        code, status = "MODEL_NOT_READY", 503
    elif "UNSUPPORTED_AREA" in message:
        code, status = "UNSUPPORTED_AREA", 422
    elif "DATASET_ERROR" in message or isinstance(exc, FileNotFoundError):
        code, status = "DATASET_ERROR", 422
    elif isinstance(exc, ValueError):
        code, status = "INVALID_INPUT", 400
    else:
        code, status = "SERVER_ERROR", 500
    return jsonify({"error": {"code": code, "message": message, "action": action}}), status
