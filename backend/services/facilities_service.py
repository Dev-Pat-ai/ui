"""
backend/services/facilities_service.py

Service for retrieving authoritative Quezon City facilities maps catalog and metadata
published by CPDDO (2026).
"""

import os
import json
from typing import Dict, Any, Optional

_FACILITIES_METADATA_CACHE: Optional[Dict[str, Any]] = None

def get_metadata_file_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "data", "authoritative", "cpdd", "facilities_metadata.json")

def load_facilities_catalog() -> Dict[str, Any]:
    global _FACILITIES_METADATA_CACHE
    if _FACILITIES_METADATA_CACHE is not None:
        return _FACILITIES_METADATA_CACHE

    path = get_metadata_file_path()
    if not os.path.exists(path):
        return {
            "is_authoritative_reference": True,
            "is_sample": False,
            "publisher": "Quezon City Planning and Development Department (CPDDO)",
            "publication_year": 2026,
            "total_categories": 0,
            "categories": []
        }

    with open(path, "r", encoding="utf-8") as f:
        _FACILITIES_METADATA_CACHE = json.load(f)

    return _FACILITIES_METADATA_CACHE

def get_facility_category(category_id: str) -> Optional[Dict[str, Any]]:
    catalog = load_facilities_catalog()
    for cat in catalog.get("categories", []):
        if cat.get("id") == category_id:
            return cat
    return None
