from __future__ import annotations

import numpy as np


def rain_cat_value(mm: float) -> str:
    """Categorize weekly rainfall using the notebook/PAGASA thresholds."""
    mm = float(mm)
    if mm < 25:
        return "Very_Light"
    if mm < 100:
        return "Light"
    if mm < 200:
        return "Moderate"
    return "Heavy"


def case_cat_value(value: float, thresholds: tuple[float, float] | None) -> str:
    """Categorize a numeric case count using low/medium/high thresholds."""
    if thresholds is None:
        raise RuntimeError("Case thresholds are not ready. Train the model first.")
    p33, p66 = thresholds
    value = float(value)
    if value < p33:
        return "Low"
    if value <= p66:
        return "Medium"
    return "High"


def normalize_choice(value, allowed: list[str]) -> str | None:
    """Normalize UI strings like 'very light' to canonical state names."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lookup = {choice.lower().replace("_", " "): choice for choice in allowed}
    lookup.update({choice.lower(): choice for choice in allowed})
    key = text.lower().replace("_", " ")
    return lookup.get(key)
