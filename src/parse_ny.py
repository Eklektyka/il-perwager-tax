"""
Parse NY Gaming Commission monthly mobile sports wagering Excel.

Input:  data/raw/states/ny/*statewide*.xlsx (single file with FY sheets)
Output: data/clean/states/ny.parquet

NY reports statewide (no operator breakdown in this file):
  Handle, GGR, Net Revenue to Platform Provider, Net Revenue to Education

Revenue definition: GGR = Handle − Payouts (cash basis; futures taxed when placed).
NY mobile sports wagering is online-only (no retail component in this report).
"""

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "states" / "ny"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean" / "states"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)


def parse_ny_excel(path):
    """Parse the NY statewide Excel file across all FY sheets."""
    xls = pd.ExcelFile(path)
    rows = []

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

        for row_idx in range(df.shape[0]):
            cell0 = df.iloc[row_idx, 0]
            if pd.isna(cell0):
                continue

            # Check if it's a date
            if hasattr(cell0, "year"):
                year = cell0.year
                month = cell0.month
            elif isinstance(cell0, str) and re.match(r"\d{4}-\d{2}", str(cell0)):
                parts = str(cell0).split("-")
                year, month = int(parts[0]), int(parts[1])
            else:
                continue

            # Columns: 0=date, 2=handle, 3=GGR
            handle = df.iloc[row_idx, 2] if df.shape[1] > 2 else None
            ggr = df.iloc[row_idx, 3] if df.shape[1] > 3 else None

            if pd.isna(handle) or handle == "" or handle is None:
                continue

            try:
                handle = float(handle)
                ggr = float(ggr) if pd.notna(ggr) and ggr != "" else None
            except (ValueError, TypeError):
                continue

            if handle <= 0:
                continue

            hold = (ggr / handle * 100) if (ggr and handle > 0) else None

            rows.append({
                "state": "NY",
                "year": year,
                "month": month,
                "operator": "STATEWIDE",
                "channel": "online",
                "handle": handle,
                "revenue": ggr,
                "hold_pct": hold,
                "revenue_type": "GGR",
            })

    return rows


def main():
    all_rows = []

    for xlsx_path in sorted(RAW_DIR.glob("*.xlsx")):
        print(f"Parsing {xlsx_path.name}...")
        rows = parse_ny_excel(xlsx_path)
        print(f"  {len(rows)} rows")
        all_rows.extend(rows)

    if not all_rows:
        print("No data parsed.")
        return

    # Deduplicate (same month might appear in overlapping FY sheets)
    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["year", "month", "operator", "channel"]).reset_index(drop=True)
    df = df.sort_values(["year", "month"]).reset_index(drop=True)

    out_path = CLEAN_DIR / "ny.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {len(df)} rows to {out_path}")
    print(f"Date range: {df['year'].min()}-{df['month'].min():02d} to {df['year'].max()}-{df['month'].max():02d}")

    print(f"\n--- NY statewide online (last 6 months) ---")
    tail = df.tail(6)
    for _, r in tail.iterrows():
        print(f"  {int(r['year'])}-{int(r['month']):02d}  handle=${r['handle']/1e6:>8.1f}M  ggr=${r['revenue']/1e6:>8.1f}M  hold={r['hold_pct']:.1f}%")


if __name__ == "__main__":
    main()
