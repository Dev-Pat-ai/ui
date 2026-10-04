import numpy as np
import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor
from pathlib import Path

from services.prediction_service import prepare_training_frame

CONTINUOUS_PREDICTORS = [
    "rainfall_mm",
    "rain_lag4w",
    "rain_lag8w",
    "cases_city",
    "city_lag4w",
    "city_lag8w",
    "cases_bgy_lag4w",
    "cases_bgy_lag8w",
]
CONTINUOUS_TARGET = "cases_bgy_wk"


def main() -> None:
    df, _train, _test = prepare_training_frame()
    cols = CONTINUOUS_PREDICTORS + [CONTINUOUS_TARGET]
    data = df[cols].dropna().copy()

    print(f"Rows used for analysis: {len(data):,}\n")

    # ---- Pearson correlation matrix ----
    corr = data.corr(method="pearson")
    print("=" * 70)
    print("PEARSON CORRELATION MATRIX")
    print("=" * 70)
    print(corr.round(3).to_string())

    # ---- Correlation of each predictor with the (continuous) target ----
    print("\n" + "=" * 70)
    print("CORRELATION WITH TARGET (cases_bgy_wk)")
    print("=" * 70)
    target_corr = corr[CONTINUOUS_TARGET].drop(CONTINUOUS_TARGET).sort_values(key=abs, ascending=False)
    print(target_corr.round(3).to_string())

    # ---- VIF among predictors only (never include the target in VIF) ----
    X = data[CONTINUOUS_PREDICTORS].copy()
    X.insert(0, "const", 1.0)  # VIF needs an intercept column to be meaningful

    vif_rows = []
    for i, col in enumerate(X.columns):
        if col == "const":
            continue
        vif = variance_inflation_factor(X.values, i)
        vif_rows.append((col, vif))

    vif_df = pd.DataFrame(vif_rows, columns=["feature", "VIF"]).sort_values("VIF", ascending=False)
    print("\n" + "=" * 70)
    print("VARIANCE INFLATION FACTOR (predictors only)")
    print("=" * 70)
    print(vif_df.round(2).to_string(index=False))

    # ---- Flag problem pairs / features ----
    print("\n" + "=" * 70)
    print("FLAGS")
    print("=" * 70)
    high_corr_pairs = []
    for i, a in enumerate(CONTINUOUS_PREDICTORS):
        for b in CONTINUOUS_PREDICTORS[i + 1:]:
            r = corr.loc[a, b]
            if abs(r) >= 0.7:
                high_corr_pairs.append((a, b, r))
    if high_corr_pairs:
        for a, b, r in high_corr_pairs:
            print(f"  High |r| >= 0.7: {a} <-> {b}  (r = {r:.3f})")
    else:
        print("  No predictor pair with |r| >= 0.7")

    high_vif = vif_df[vif_df["VIF"] >= 5]
    if not high_vif.empty:
        for _, row in high_vif.iterrows():
            print(f"  High VIF >= 5: {row['feature']} (VIF = {row['VIF']:.2f})")
    else:
        print("  No feature with VIF >= 5")

    PROJECT_DIR = Path(__file__).resolve().parents[2]
    OUTPUT_DIR = PROJECT_DIR / "output" / "reports"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    corr.round(4).to_csv(OUTPUT_DIR / "pearson_correlation_matrix.csv")
    vif_df.round(4).to_csv(OUTPUT_DIR / "vif_results.csv", index=False)
    target_corr.round(4).to_csv(OUTPUT_DIR / "target_correlation.csv")

    print(f"\nSaved CSV files to: {OUTPUT_DIR.resolve()}")

if __name__ == "__main__":
    main()

