from __future__ import annotations

from flask import Blueprint, jsonify, request

from models.lstm_model import forecast_next_weeks, get_lstm_summary, load_trained_model, train_lstm_model
from services.prediction_service import build_evidence_from_payload, get_feature_info, get_history, train_model, what_if
from utils.api_errors import model_error_response

prediction_bp = Blueprint("prediction_bp", __name__)


def _integer_parameter(data, name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = data.get(name, request.args.get(name, default))
    try:
        if isinstance(raw_value, bool) or (isinstance(raw_value, float) and not raw_value.is_integer()):
            raise ValueError
        value = int(raw_value if raw_value not in (None, "") else default)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}.") from None
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _error_response(exc: Exception, *, action: str = "Check the submitted values."):
    return model_error_response(exc, action)


@prediction_bp.route("/model/health", methods=["GET"])
def health():
    from models import bn_model
    return jsonify({
        "status": "ready" if bn_model.inference is not None else "not_ready",
        "model": "Regularized Bayesian Network",
        "model_ready": bn_model.inference is not None,
        "supports_partial_evidence": True,
        "training_data": bn_model.get_training_data_status(),
        "model_use": "Contemporaneous case-burden inference; not an independently validated barangay forecast.",
        "environmental_effects_learned": False,
    })


@prediction_bp.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    try:
        evidence, raw_inputs, district_context = build_evidence_from_payload(data)
        result = what_if(evidence, district_context=district_context)

        # Save forecast log to PostgreSQL database
        try:
            from db import db
            from models.db_models import ForecastLog
            
            district_val = raw_inputs.get("district") or data.get("district") or "District I"
            barangays_val = raw_inputs.get("barangays") or data.get("barangays") or []
            
            log_entry = ForecastLog(
                district=district_val,
                selected_barangays=barangays_val,
                prediction_method="Bayesian Network",
                rain_now=evidence.get("Rain_Now"),
                city_cases_now=evidence.get("City_Cases_Now"),
                sim_waste=raw_inputs.get("sim_waste"),
                sim_water=raw_inputs.get("sim_water"),
                sim_flood=raw_inputs.get("sim_flood"),
                predicted_cases=result.get("predicted_cases"),
                risk_level=result.get("risk_level"),
                confidence=result.get("confidence"),
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as db_exc:
            print(f"Warning: Failed to save forecast log to PostgreSQL: {db_exc}")

        return jsonify(result)
    except Exception as exc:
        return model_error_response(exc)


@prediction_bp.route("/api/forecast/history", methods=["GET"])
def forecast_history():
    try:
        from models.db_models import ForecastLog
        logs = ForecastLog.query.order_by(ForecastLog.created_at.desc()).limit(50).all()
        return jsonify({
            "status": "success",
            "count": len(logs),
            "forecasts": [log.to_dict() for log in logs],
        })
    except Exception as exc:
        return model_error_response(exc)


@prediction_bp.route("/lstm/health", methods=["GET"])
def lstm_health():
    try:
        return jsonify({
            "status": "ok",
            "model": "City-level LSTM research forecast",
            "summary": get_lstm_summary(),
        })
    except Exception as exc:
        return model_error_response(exc)


@prediction_bp.route("/lstm/train", methods=["POST"])
def lstm_train():
    data = request.get_json(silent=True) or {}
    try:
        area = data.get("area") or request.args.get("area") or "city"
        sequence_length = _integer_parameter(data, "sequence_length", 12, 9, 52)
        epochs = _integer_parameter(data, "epochs", 80, 1, 500)
        batch_size = _integer_parameter(data, "batch_size", 16, 1, 512)
        hidden_size = _integer_parameter(data, "hidden_size", 64, 1, 1024)
        result = train_lstm_model(
            area=area,
            sequence_length=sequence_length,
            epochs=epochs,
            batch_size=batch_size,
            hidden_size=hidden_size,
        )
        return jsonify(result)
    except Exception as exc:
        return _error_response(exc, action="Use valid training parameters and a supported area.")


@prediction_bp.route("/lstm/evaluation", methods=["GET"])
def lstm_evaluation():
    """Read the saved, source-checked evaluation without starting training."""
    from models.lstm_model import _load_artifact, _model_path
    try:
        return jsonify(_load_artifact(_model_path("city"))["evaluation"])
    except Exception as exc:
        return model_error_response(exc, "Run scripts/evaluate_city_forecast.py to create a current evaluation artifact.")


@prediction_bp.route("/lstm/areas", methods=["GET"])
def lstm_areas():
    from models.lstm_model import get_supported_areas
    return jsonify({"areas": get_supported_areas()})


@prediction_bp.route("/lstm/forecast", methods=["GET", "POST"])
def lstm_forecast():
    data = request.get_json(silent=True) or {}
    try:
        area = data.get("area") or request.args.get("area") or "city"
        weeks = _integer_parameter(data, "weeks", 8, 1, 24)
        sequence_length = _integer_parameter(data, "sequence_length", 12, 9, 52)
    except ValueError as exc:
        return _error_response(exc)

    try:
        load_trained_model(area=area, sequence_length=sequence_length)
        result = forecast_next_weeks(weeks=weeks, area=area, sequence_length=sequence_length)
        return jsonify(result)
    except Exception as exc:
        return _error_response(exc, action="Check area selection or dataset availability.")
