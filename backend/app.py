from __future__ import annotations

import os
from pathlib import Path
from flask import Flask, send_from_directory
from flask_cors import CORS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SOURCE_DIR = PROJECT_ROOT / "frontend"
FRONTEND_BUILD_DIR = PROJECT_ROOT / "dist"
FRONTEND_DIR = (
    FRONTEND_BUILD_DIR
    if os.getenv("DENGUESENSE_SERVE_BUILD") == "1"
    else FRONTEND_SOURCE_DIR
)

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
CORS(app)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "backend" / ".env")

# Configure SQLAlchemy PostgreSQL Database
from db import db
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/denguesense_qc")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Import routes for registration
from routes.analysis_routes import analysis_bp
from routes.prediction_routes import prediction_bp
from routes.prototype_routes import prototype_bp
from routes.reference_routes import reference_bp
from routes.auth_routes import auth_bp

# Check for prototype-only mode
# Must be exactly '1' to enable
is_prototype_only = os.getenv("DENGUESENSE_PROTOTYPE_ONLY") == "1"

print("=" * 60)
print("  DENGUE RISK PREDICTION - FLASK SERVER (PostgreSQL Enabled)")
print("=" * 60)

# Register all blueprints regardless of mode
app.register_blueprint(prediction_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(prototype_bp)
app.register_blueprint(reference_bp)
app.register_blueprint(auth_bp)

if is_prototype_only:
    print("RUNNING IN PROTOTYPE-ONLY MODE")
    print("Research models will initialize lazily upon first request.")
else:
    print("Training regularized Bayesian Network on startup...")
    # Lazy imports to avoid triggering model code if in prototype mode
    from services.prediction_service import train_model
    try:
        train_model()
    except RuntimeError as exc:
        if getattr(exc, "code", None) not in {"OBSERVED_WEEKLY_DATA_REQUIRED", "INVALID_OBSERVED_WEEKLY_DATA"}:
            raise
        print(f"Bayesian Network unavailable: {exc}")
        print("Reference endpoints and the independent city forecasting model remain available.")

print("All endpoints (Prototype, Prediction, Analysis) registered.")


@app.route("/", methods=["GET"])
def frontend():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/css/<path:filename>", methods=["GET"])
def frontend_css(filename: str):
    return send_from_directory(str(FRONTEND_DIR / "css"), filename)


@app.route("/js/<path:filename>", methods=["GET"])
def frontend_js(filename: str):
    return send_from_directory(str(FRONTEND_DIR / "js"), filename)


@app.route("/assets/<path:filename>", methods=["GET"])
def frontend_assets(filename: str):
    return send_from_directory(str(FRONTEND_DIR / "assets"), filename)



@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "mode": "prototype" if is_prototype_only else "research"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Server running at http://localhost:{port}")
    print("Open frontend/index.html in your browser.\n")
    app.run(debug=False, port=port)
