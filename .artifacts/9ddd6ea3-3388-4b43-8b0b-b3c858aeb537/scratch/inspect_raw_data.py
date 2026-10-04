import pandas as pd
from pathlib import Path

def inspect_excel(path):
    print(f"\nInspecting Excel: {path}")
    try:
        xl = pd.ExcelFile(path)
        print(f"Sheets: {xl.sheet_names}")
        for sheet in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, nrows=5)
            print(f"\nSheet: {sheet}")
            print(f"Columns: {df.columns.tolist()}")
            print(f"Head:\n{df.head()}")

            # Count total rows roughly
            df_full = pd.read_excel(path, sheet_name=sheet)
            print(f"Total Rows: {len(df_full)}")
            print(f"Year range: {df_full.iloc[:,0].min()} to {df_full.iloc[:,0].max()}" if len(df_full) > 0 else "Empty")
    except Exception as e:
        print(f"Error inspecting Excel: {e}")

def inspect_csv(path):
    print(f"\nInspecting CSV: {path}")
    try:
        df = pd.read_csv(path, nrows=5)
        print(f"Columns: {df.columns.tolist()}")
        print(f"Head:\n{df.head()}")

        df_full = pd.read_csv(path)
        print(f"Total Rows: {len(df_full)}")
    except Exception as e:
        print(f"Error inspecting CSV: {e}")

if __name__ == "__main__":
    raw_dir = Path("data/raw")
    excel_path = raw_dir / "Dengue-Rainfall_Dataset.xlsx"
    csv_path = raw_dir / "QC_YearlyData-BarangayCSV.csv"

    if excel_path.exists():
        inspect_excel(excel_path)
    else:
        print(f"Excel not found: {excel_path}")

    if csv_path.exists():
        inspect_csv(csv_path)
    else:
        print(f"CSV not found: {csv_path}")
