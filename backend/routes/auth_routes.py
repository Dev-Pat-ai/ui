from __future__ import annotations

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from db import db
from models.db_models import User

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required.", "status": "error"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password.", "status": "unauthorized"}), 401

    return jsonify({
        "status": "success",
        "message": "Login successful",
        "user": user.to_dict(),
    })


@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role") or "user"

    if not email or not password:
        return jsonify({"error": "Email and password are required.", "status": "error"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email is already registered.", "status": "conflict"}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(email=email, password_hash=hashed_password, role=role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "User registered successfully",
        "user": new_user.to_dict(),
    }), 201


@auth_bp.route("/api/me", methods=["GET"])
def me():
    # Helper endpoint for frontend session check if needed
    return jsonify({"status": "ok", "service": "DengueSense QC Auth"})


@auth_bp.route("/api/profile/<int:user_id>", methods=["GET"])
def get_profile(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "status": "not_found"}), 404
    return jsonify({"status": "success", "profile": user.to_dict()})


@auth_bp.route("/api/profile/<int:user_id>", methods=["PUT"])
def update_profile(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "status": "not_found"}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        user.name = data["name"].strip()
    if "title" in data:
        user.title = data["title"].strip()
    if "organization" in data:
        user.organization = data["organization"].strip()
    if "location" in data:
        user.location = data["location"].strip()
    if "avatar" in data:
        user.avatar = data["avatar"]
    if data.get("password"):
        user.password_hash = generate_password_hash(data["password"])

    db.session.commit()
    return jsonify({"status": "success", "message": "Profile updated", "profile": user.to_dict()})
