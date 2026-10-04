from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.prediction_service import prepare_training_frame


if __name__ == "__main__":
    df, train, test = prepare_training_frame()
    print(f"Total rows: {len(df):,}")
    print(f"Train rows: {len(train):,}")
    print(f"Test rows: {len(test):,}")
