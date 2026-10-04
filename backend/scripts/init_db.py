from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend directory to python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from flask import Flask
from werkzeug.security import generate_password_hash

from db import db
from models.db_models import User, DistrictReference, ForecastLog, WeeklyDengueObservation

def ensure_database_exists():
    db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/denguesense_qc")
    # Parse connection details or connect to 'postgres' db to create target db
    # URL format: postgresql+psycopg2://user:pass@host:port/dbname
    try:
        # Strip driver prefix for psycopg2 connection
        clean_url = db_url.replace("postgresql+psycopg2://", "postgresql://").replace("postgresql://", "")
        auth_part, host_db = clean_url.split("@")
        user_pass = auth_part.split(":")
        user = user_pass[0]
        password = user_pass[1] if len(user_pass) > 1 else ""
        host_port, dbname = host_db.split("/")
        host = host_port.split(":")[0]
        port = host_port.split(":")[1] if ":" in host_port else "5432"

        print(f"Connecting to PostgreSQL server at {host}:{port} as {user}...")
        conn = psycopg2.connect(dbname="postgres", user=user, password=password, host=host, port=port)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'")
        exists = cursor.fetchone()
        if not exists:
            print(f"Database '{dbname}' does not exist. Creating...")
            cursor.execute(f"CREATE DATABASE {dbname}")
            print(f"Database '{dbname}' created successfully.")
        else:
            print(f"Database '{dbname}' already exists.")

        cursor.close()
        conn.close()
    except Exception as exc:
        print(f"Note on auto-database creation: {exc}")
        print("Please ensure PostgreSQL is running and credentials in .env are correct.")

app = Flask(__name__)
database_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/denguesense_qc")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

def init_database():
    ensure_database_exists()
    with app.app_context():
        print("Dropping existing tables and recreating with latest schema...")
        db.drop_all()
        db.create_all()
        print("Tables created successfully.")

        # Seed default admin user if not exists
        admin_email = "admin@denguesense.qc.gov.ph"
        if not User.query.filter_by(email=admin_email).first():
            print(f"Seeding default admin user: {admin_email}")
            admin_user = User(
                email=admin_email,
                password_hash=generate_password_hash("admin123"),
                role="admin",
            )
            db.session.add(admin_user)

        # Seed default regular user if not exists
        user_email = "user@denguesense.qc.gov.ph"
        if not User.query.filter_by(email=user_email).first():
            print(f"Seeding default regular user: {user_email}")
            regular_user = User(
                email=user_email,
                password_hash=generate_password_hash("user123"),
                role="user",
            )
            db.session.add(regular_user)

        # Seed Quezon City District reference data
        districts_seed = [
            {"district_id": "I", "population_2020": 427854, "land_area_sqkm": 24.71, "barangay_count": 37, "density_persons_ha": 173.1},
            {"district_id": "II", "population_2020": 699932, "land_area_sqkm": 26.60, "barangay_count": 5, "density_persons_ha": 263.1},
            {"district_id": "III", "population_2020": 348425, "land_area_sqkm": 20.21, "barangay_count": 37, "density_persons_ha": 172.4},
            {"district_id": "IV", "population_2020": 479159, "land_area_sqkm": 27.53, "barangay_count": 38, "density_persons_ha": 174.0},
            {"district_id": "V", "population_2020": 596047, "land_area_sqkm": 52.47, "barangay_count": 14, "density_persons_ha": 113.6},
            {"district_id": "VI", "population_2020": 551978, "land_area_sqkm": 19.98, "barangay_count": 27, "density_persons_ha": 276.3},
        ]

        for d_data in districts_seed:
            existing = DistrictReference.query.filter_by(district_id=d_data["district_id"]).first()
            if not existing:
                print(f"Seeding District {d_data['district_id']} reference data")
                d_ref = DistrictReference(**d_data)
                db.session.add(d_ref)

        db.session.commit()
        print("Database initialization and seeding completed successfully!")

if __name__ == "__main__":
    init_database()
