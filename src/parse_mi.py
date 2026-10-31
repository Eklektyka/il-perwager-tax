"""
Parse Michigan MGCB Internet Sports Betting Excel files.
Layout: each operator block is 4 columns wide (Handle, Qualified Promo, GGR, Tax).
Rows 6-17 are months (Jan-Dec). Multiple operators side by side.
"""
import re
from pathlib import Path
import pandas as pd, numpy as np

RAW = Path(__file__).resolve().parent.parent / "data/raw/states/mi"
OUT = Path(__file__).resolve().parent.parent / "data/clean/states"
OUT.mkdir(parents=True, exist_ok=True)

MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]

def parse_mi_sheet(xls, sheet_name):
    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
    # Find the year from sheet name
    m = re.search(r"(\d{4})", sheet_name)
    if not m:
        return []
    year = int(m.group(1))

    # Row 3 has platform provider names, row 5 has "Total Handle"
    # Find all columns with "Total Handle" in row 5
    handle_cols = []
    for c in range(df.shape[1]):
        v = str(df.iloc[5, c]).strip() if 5 < df.shape[0] and pd.notna(df.iloc[5, c]) else ""
        if "Total Handle" in v:
            # Get operator name from row 3
            op = str(df.iloc[3, c]).strip() if pd.notna(df.iloc[3, c]) else ""
            if not op or op == "nan":
                op = str(df.iloc[2, c]).strip() if pd.notna(df.iloc[2, c]) else f"Unknown_c{c}"
            handle_cols.append((c, op))

    rows = []
    for month_idx, month_name in enumerate(MONTH_NAMES):
        row_idx = 6 + month_idx
        if row_idx >= df.shape[0]:
            break
        month_num = month_idx + 1

        for col, operator in handle_cols:
            handle = df.iloc[row_idx, col]
            if pd.isna(handle):
                continue
            try:
                handle = float(handle)
            except (ValueError, TypeError):
                continue
            if handle <= 0:
                continue

            # GGR is typically 2 columns after handle
            ggr = None
            for offset in [2, 3]:
                if col + offset < df.shape[1]:
                    v = df.iloc[row_idx, col + offset]
                    if pd.notna(v):
                        try:
                            ggr = float(v)
                            break
                        except (ValueError, TypeError):
                            pass

            rows.append({
                "state": "MI", "year": year, "month": month_num,
                "operator": operator, "channel": "online",
                "handle": handle, "revenue": ggr,
                "revenue_type": "GGR",
            })
    return rows

def main():
    all_rows = []
    for xlsx_path in sorted(RAW.glob("*.xlsx")):
        try:
            xls = pd.ExcelFile(xlsx_path)
        except Exception:
            print(f"  SKIP {xlsx_path.name} (not valid Excel)")
            continue
        for sheet in xls.sheet_names:
            if "Internet Sports Betting" in sheet:
                rows = parse_mi_sheet(xls, sheet)
                if rows:
                    print(f"  {xlsx_path.name} / {sheet}: {len(rows)} rows")
                    all_rows.extend(rows)

    if not all_rows:
        print("No data parsed.")
        return

    df = pd.DataFrame(all_rows).sort_values(["year","month","operator"]).reset_index(drop=True)
    df.to_parquet(OUT / "mi.parquet", index=False)
    print(f"\nWrote {len(df)} rows")
    monthly = df.groupby(["year","month"]).agg(handle=("handle","sum")).reset_index()
    print(f"Range: {monthly.iloc[0]['year']:.0f}-{monthly.iloc[0]['month']:02.0f} to {monthly.iloc[-1]['year']:.0f}-{monthly.iloc[-1]['month']:02.0f}")

if __name__ == "__main__":
    main()
