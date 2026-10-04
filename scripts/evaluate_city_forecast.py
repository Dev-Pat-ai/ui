"""Reproduce the fixed-seed city holdout study and save the selected artifact.

Run: venv/Scripts/python.exe scripts/evaluate_city_forecast.py
Do not tune the seed/configuration against the saved test results.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from models.lstm_model import OUTPUT_DIR, train_lstm_model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    result = train_lstm_model(epochs=args.epochs, hidden_size=args.hidden_size, seed=args.seed, output_dir=args.output_dir)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
