from __future__ import annotations

from typing import Any

from utils.preprocessing import normalize_choice


def validate_evidence(evidence: dict[str, Any], feature_cols: list[str], feature_meta: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Validate and canonicalize a partial evidence dictionary."""
    cleaned: dict[str, str] = {}
    for key, value in evidence.items():
        if value is None or str(value).strip() == "":
            continue
        if key not in feature_cols:
            raise ValueError(f"Unknown evidence key '{key}'. Allowed keys: {feature_cols}")
        allowed = feature_meta[key]["choices"]
        normalized = normalize_choice(value, allowed)
        if normalized is None:
            raise ValueError(f"Invalid value '{value}' for '{key}'. Allowed: {allowed}")
        cleaned[key] = normalized
    return cleaned
