from __future__ import annotations

import os
from pathlib import Path

def resolve_data_path(filename: str, env_name: str | None = None) -> Path:
    """Find data file using env var first, then common project layouts."""
    if env_name:
        env_path = os.getenv(env_name)
        if env_path:
            return Path(env_path).expanduser().resolve()

    # Determine project root relative to this utility file (backend/utils/path_utils.py)
    root = Path(__file__).resolve().parents[2]

    candidates = [
        root / "data" / "raw" / filename,
        root / "data" / filename,
        root.parent / "data" / filename,
        Path.cwd() / "data" / "raw" / filename,
        Path.cwd() / "data" / filename,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Return the first candidate as a default (for error reporting later)
    return candidates[0]
