"""Render the saved city evaluation into a shareable report without retraining."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METHODS = [("lstm", "LSTM", "#245baf"),
           ("last_observation", "Last observation", "#d2761d"),
           ("seasonal_52", "Seasonal (52 periods)", "#7d8896")]


def build_report(input_dir: Path, report_path: Path) -> None:
    card = json.loads((input_dir / "model_card.json").read_text(encoding="utf-8"))
    predictions = pd.read_csv(input_dir / "holdout_predictions.csv")
    test = predictions.loc[predictions["split"].eq("test")].reset_index(drop=True)
    if len(test) != card["splits"]["test"]["rows"]:
        raise ValueError("Prediction count does not match model card.")
    if set(test["source_sha256"]) != {card["provenance"]["sha256"]}:
        raise ValueError("Prediction provenance does not match model card.")
    # Verify that the plotted CSV and reported card describe the same evaluation.
    for method, _, _ in METHODS:
        errors = test[f"{method}_cases"] - test["actual_cases"]
        calculated = [errors.abs().mean(), np.sqrt((errors ** 2).mean())]
        saved = [card["metrics"]["test"][method][key] for key in ("mae_cases", "rmse_cases")]
        if not np.allclose(calculated, saved, rtol=1e-5, atol=1e-4):
            raise ValueError(f"Saved metrics and predictions disagree for {method}.")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig = plt.figure(figsize=(12, 8), layout="constrained")
    grid = fig.add_gridspec(2, 2, height_ratios=[1.8, 1])
    ax = fig.add_subplot(grid[0, :])
    ax.plot(test.index, test["actual_cases"], color="#172b39", label="Observed city cases", lw=2)
    for method, label, color in METHODS[:2]:
        ax.plot(test.index, test[f"{method}_cases"], color=color, label=label, lw=1.5, alpha=.9)
    tick_indices = list(range(0, len(test), 13)) + [len(test) - 1]
    ax.set_xticks(tick_indices, test.loc[tick_indices, "period"], rotation=25, ha="right")
    ax.set_ylabel("Reported cases / source week")
    ax.set_title("Held-out city observations and one-period-ahead predictions", loc="left", fontweight="bold")
    ax.grid(axis="y", alpha=.15)
    ax.legend(frameon=False, loc="upper left")
    for index, (metric, label) in enumerate((("mae_cases", "MAE"), ("rmse_cases", "RMSE"))):
        axis = fig.add_subplot(grid[1, index])
        values = [card["metrics"]["test"][method][metric] for method, _, _ in METHODS]
        bars = axis.barh([label for _, label, _ in METHODS], values,
                         color=[color for _, _, color in METHODS], height=.58)
        axis.invert_yaxis()
        axis.bar_label(bars, fmt="%.2f", padding=5)
        axis.set_xlim(0, max(values) * 1.19)
        axis.set_xlabel("Cases; lower error is better")
        axis.set_title(f"Test {label}", loc="left", fontweight="bold")
        axis.grid(axis="x", alpha=.15)
        axis.set_axisbelow(True)
    fig.suptitle("Quezon City | chronological holdout: 2024–2025\n"
                 "LSTM selected on 2022–2023 validation; last-observation baseline has lower test error",
                 fontsize=13, fontweight="bold")
    fig.supxlabel("104 held-out source weeks • Fixed weights and scalers • Actual calendar boundaries unverified",
                  fontsize=9, color="#485866")
    figure_dir = report_path.parent / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure_path = figure_dir / "city_holdout_evaluation.png"
    fig.savefig(figure_path, dpi=180, facecolor="white")
    plt.close(fig)

    rows = []
    for method, label, _ in METHODS:
        val, heldout = card["metrics"]["validation"][method], card["metrics"]["test"][method]
        rows.append(f"| {label} | {val['mae_cases']:.2f} | {heldout['mae_cases']:.2f} | {heldout['rmse_cases']:.2f} |")
    split_rows = []
    for split, description in card["splits"].items():
        split_rows.append(f"| {split.title()} | {description['start_period']} to {description['end_period']} | {description['rows']} |")
    config = card["configuration"]
    report = "\n".join([
        "# Saved city forecasting evaluation", "",
        "The LSTM has lower validation MAE, but the last-observation baseline has lower error on the untouched 2024–2025 test period. This run does not establish LSTM superiority.", "",
        "This is a supplementary **city-level feasibility study**. It does not validate the original district-level 2018–2024 research scope, a combined BN–LSTM model, or a deployed early-warning system.", "",
        "![City held-out evaluation](figures/city_holdout_evaluation.png)", "",
        "| Method | Validation MAE (cases) | Test MAE (cases) | Test RMSE (cases) |",
        "|---|---:|---:|---:|", *rows, "",
        "MAE is mean absolute error in case counts; RMSE penalizes larger errors more strongly. Neither is an accuracy percentage. No statistical significance claim is made.", "",
        "| Split | Target source periods | Targets |", "|---|---|---:|", *split_rows, "",
        "The workbook has 832 rows (2010–2025). Eight rows form lag warm-up; twelve more form the initial sequence, leaving 812 targets. The seasonal baseline has only 564 eligible training targets because it requires 52 earlier periods; all methods share the same 104 validation and 104 test targets.", "",
        "At each holdout target, the model receives only earlier observed periods. Parameters and scalers stay fixed. This measures rolling one-period-ahead forecasting; later holdout observations become available as history for later targets. It is not a single 104-step forecast made at the start of 2024.", "",
        f"Configuration: {config['layers']} LSTM layers; {config['hidden_size']} hidden units; {config['sequence_length']}-period input; dropout {config['dropout']}; Adam learning rate {config['learning_rate']}; batch {config['batch_size']}; seed {config['seed']}; CPU with {config['threads']} thread. Best epoch {config['best_epoch']} of {config['epochs_run']} executed (maximum {config['maximum_epochs']}, patience {config['patience']}).",
        "", "Features: observed rainfall and city cases, plus their four- and eight-period lags. Input sequences end before the target. Scaling is fitted on training data only; epoch and method selection use validation MAE only. The saved model is not refitted on validation or test observations.", "",
        "Workbook: `data/raw/Dengue-Rainfall_Dataset.xlsx`, sheet `QC Data`. Its dictionary attributes case counts to QCESD and rainfall to NASA satellite data. Those agency attributions have not been independently verified; rainfall is not labelled PAGASA.", "",
        f"Source SHA-256: `{card['provenance']['sha256']}`.", "",
        "The workbook defines weeks 1–52 for every source year. Calendar dates and treatment of week 53 remain unverified. Outputs preserve source period labels. The last observation is 2025-W52, so extrapolations begin at 2026-W01, not the current date. Recursive multi-period forecasts and constant future rainfall scenarios have not been validated; no calibrated prediction intervals are available.", "",
        "CPDD population, households, area, flood and waste references are prepared separately. They are not learned predictors in this city model. The Bayesian Network requires observed weekly barangay data and remains unavailable with the currently supplied data.", "",
        "Reproduce from the repository root in PowerShell:", "", "```powershell",
        "& ./venv/Scripts/python.exe scripts/evaluate_city_forecast.py",
        "& ./venv/Scripts/python.exe scripts/build_defense_report.py", "```", "",
        "The first command retrains and replaces the saved city artifact. The second reads saved results without retraining and checks the chart data against the model-card metrics. Do not choose seeds or settings by inspecting test performance; use a new holdout for future model selection.", "",
        "Full evidence: `output/model-evaluation/model_card.json` and `holdout_predictions.csv`; runtime versions and per-epoch validation errors are recorded in the card. The API serves the same saved evidence at `GET /lstm/evaluation`. Further defense notes: [defense guide](defense_guide.md).", "",
        "Method references: [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html) supports fitting preprocessing only on training observations; [chronological split guidance](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) explains why future observations must not train earlier predictions. This implementation uses fixed year holdouts, not that class. [PyTorch reproducibility guidance](https://docs.pytorch.org/docs/stable/notes/randomness.html) describes the limits of reproducibility across environments.", "",
    ])
    report_path.write_text(report, encoding="utf-8")
    print(f"Report: {report_path}\nFigure: {figure_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "output" / "model-evaluation")
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "model_evaluation.md")
    args = parser.parse_args()
    build_report(args.input_dir, args.report)
