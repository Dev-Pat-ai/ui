"""Run an isolated demonstration server for temporary public sharing.

The normal local server and its database configuration are unaffected. Public
visitors use the demo account, browser-local profiles, and a disposable database.
"""

from __future__ import annotations

import os

# Set these before importing app: dotenv must not select the private database,
# and forecast requests must never start training or overwrite model artifacts.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DENGUESENSE_PROTOTYPE_ONLY"] = "1"
os.environ["DENGUESENSE_SERVE_BUILD"] = "0"
os.environ["SKIP_TRAINING"] = "1"

from flask import jsonify, redirect, request, send_from_directory

from app import FRONTEND_DIR, app
from db import db

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo123"
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

with app.app_context():
    db.create_all()


@app.before_request
def protect_public_demo():
    if request.path == "/health":
        return jsonify(status="ok", mode="demo")

    if request.endpoint == "auth_bp.login":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Use the public demo account.", status="error"), 400
        if data.get("email") != DEMO_EMAIL or data.get("password") != DEMO_PASSWORD:
            return jsonify(
                error="Use demo@example.com and demo123 for this public demo.",
                status="unauthorized",
            ), 401
        # No database ID: the existing frontend keeps profile edits in the
        # visitor's browser instead of calling the private account endpoints.
        return jsonify(status="success", user={
            "email": DEMO_EMAIL,
            "name": "Demo Visitor",
            "role": "user",
            "demo": True,
        })

    if (request.endpoint or "").startswith("auth_bp.") or request.path == "/api/signup":
        return jsonify(
            status="demo_only", error="Account services are disabled in the public demo."
        ), 503

    if request.endpoint == "prediction_bp.lstm_train":
        return jsonify(status="demo_only", error="Training is disabled in the public demo."), 403

    if request.endpoint == "prediction_bp.forecast_history":
        return jsonify(status="success", count=0, forecasts=[])


@app.after_request
def label_public_demo(response):
    if request.path in {"/", "/index.html"} and response.status_code == 200:
        response.direct_passthrough = False
        html = response.get_data(as_text=True).replace(
            "Sign in to access the dengue monitoring dashboard.",
            "Public demo: sign in with demo@example.com and demo123.",
        ).replace(
            "Don't have an account? <a href=\"signup.html\">Create one</a>",
            "Use the demo account above to explore the dashboard.",
        ).replace(
            "<span>SECURE ACCESS</span>", "<span>PUBLIC DEMO</span>",
        )
        response.set_data(html)
        response.headers.pop("ETag", None)
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/index.html")
def demo_index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.get("/robots.txt")
def demo_robots():
    # Permit reading this public demo in ChatGPT. Training crawlers remain
    # opted out; account and training services are unavailable to visitors.
    return app.response_class(
        "User-agent: ChatGPT-User\n"
        "User-agent: OAI-SearchBot\n"
        "Disallow: /api/profile/\n"
        "Disallow: /api/register\n"
        "Disallow: /api/signup\n"
        "Disallow: /lstm/train\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\n"
        "Disallow: /\n\n"
        "User-agent: *\n"
        "Allow: /\n",
        mimetype="text/plain",
    )


@app.get("/signup.html")
def demo_signup():
    return redirect("/")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"Public demo account: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
