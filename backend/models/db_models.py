from __future__ import annotations

from datetime import datetime
from db import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="user", nullable=False)
    name = db.Column(db.String(120), default="Guest User", nullable=False)
    title = db.Column(db.String(120), default="Public User", nullable=False)
    organization = db.Column(db.String(150), nullable=True)
    location = db.Column(db.String(150), default="Quezon City, Philippines", nullable=False)
    avatar = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "name": self.name,
            "title": self.title,
            "organization": self.organization,
            "location": self.location,
            "avatar": self.avatar,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ForecastLog(db.Model):
    __tablename__ = "forecast_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    district = db.Column(db.String(50), nullable=False)
    selected_barangays = db.Column(db.JSON, nullable=True)
    prediction_method = db.Column(db.String(50), default="Bayesian Network", nullable=False)
    rain_now = db.Column(db.String(50), nullable=True)
    city_cases_now = db.Column(db.String(50), nullable=True)
    sim_waste = db.Column(db.String(50), nullable=True)
    sim_water = db.Column(db.String(50), nullable=True)
    sim_flood = db.Column(db.String(50), nullable=True)
    predicted_cases = db.Column(db.Float, nullable=True)
    risk_level = db.Column(db.String(50), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("forecasts", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "district": self.district,
            "selected_barangays": self.selected_barangays or [],
            "prediction_method": self.prediction_method,
            "rain_now": self.rain_now,
            "city_cases_now": self.city_cases_now,
            "sim_waste": self.sim_waste,
            "sim_water": self.sim_water,
            "sim_flood": self.sim_flood,
            "predicted_cases": self.predicted_cases,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WeeklyDengueObservation(db.Model):
    __tablename__ = "weekly_dengue_observations"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    district = db.Column(db.String(50), nullable=False)
    barangay = db.Column(db.String(120), nullable=True)
    case_count = db.Column(db.Integer, default=0, nullable=False)


class DistrictReference(db.Model):
    __tablename__ = "district_references"

    id = db.Column(db.Integer, primary_key=True)
    district_id = db.Column(db.String(10), unique=True, nullable=False)
    population_2020 = db.Column(db.Integer, nullable=False)
    land_area_sqkm = db.Column(db.Float, nullable=False)
    barangay_count = db.Column(db.Integer, nullable=False)
    density_persons_ha = db.Column(db.Float, nullable=False)
