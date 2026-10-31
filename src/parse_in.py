"""
Parse Indiana Gaming Commission monthly revenue Excel files.

Input:  data/raw/states/in/{YYYY}-{MM}-Revenue.xlsx
Output: data/clean/states/in.parquet

Sheet7 has: Summary of Sports Wagering Tax with operator-level Handle and Taxable AGR.
Note: IN reports combined online+retail per operator (no channel split in Sheet7).

Revenue definition: AGR = Handle − Payouts − Adjustments. "Taxable AGR" is the tax base
(9.5% tax rate). Negative AGR in a month can carry forward.
"""

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "states" / "in"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean" / "states"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)


def parse_in_excel(path):
    """Parse a single IN monthly Excel file."""
    # Extract year/month from filename
    m = re.match(r"(\d{4})-(\d{2})-Revenue", path.stem)
    if not m:
        return []
    year, month = int(m.group(1)), int(m.group(2))

    try:
        xls = pd.ExcelFile(path)
    except Exception:
        return []

    # Find the sports wagering summary sheet (has "SPORTS WAGERING AGR" header)
    target_sheet = None
    for s in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=s, header=None)
            for r in range(min(10, df.shape[0])):
                for c in range(min(df.shape[1], 5)):
                    v = str(df.iloc[r, c]) if pd.notna(df.iloc[r, c]) else ""
                    if "SPORTS WAGERING AGR" in v.upper():
                        target_sheet = s
                        break
                if target_sheet:
                    break
        except Exception:
            continue
        if target_sheet:
            break

    if not target_sheet:
        return []

    df = pd.read_excel(xls, sheet_name=target_sheet, header=None)
    rows = []

    # Find column indices for Handle and Taxable AGR
    handle_col = None
    agr_col = None
    for r in range(min(10, df.shape[0])):
        for c in range(df.shape[1]):
            v = str(df.iloc[r, c]).strip() if pd.notna(df.iloc[r, c]) else ""
            if v == "Handle":
                handle_col = c
            elif "Taxable AGR" in v:
                agr_col = c

    if handle_col is None or agr_col is None:
        return []

    # Parse operator rows — stop at TOTAL row
    past_header = False
    for r in range(df.shape[0]):
        cell0 = str(df.iloc[r, 0]).strip() if pd.notna(df.iloc[r, 0]) else ""
        if "SPORTS WAGERING AGR" in cell0.upper():
            past_header = True
            continue
        if not past_header:
            continue
        if cell0 == "TOTAL":
            break  # Stop here — below this are sport breakdowns, not operators
        if not cell0 or cell0 in ("NaN", ""):
            continue
        if cell0.startswith("*") or cell0.startswith("In accordance"):
            break

        handle_val = df.iloc[r, handle_col] if handle_col < df.shape[1] else None
        agr_val = df.iloc[r, agr_col] if agr_col < df.shape[1] else None

        if pd.isna(handle_val) and pd.isna(agr_val):
            continue

        try:
            handle = float(handle_val) if pd.notna(handle_val) else None
            agr = float(agr_val) if pd.notna(agr_val) else None
        except (ValueError, TypeError):
            continue

        if handle is None or handle == 0:
            continue

        hold = (agr / handle * 100) if (agr and handle and handle > 0) else None

        rows.append({
            "state": "IN",
            "year": year,
            "month": month,
            "operator": cell0,
            "channel": "combined",  # IN Sheet7 doesn't split online/retail
            "handle": handle,
            "revenue": agr,
            "hold_pct": hold,
            "revenue_type": "AGR",
        })

    return rows


def main():
    all_rows = []

    for xlsx_path in sorted(RAW_DIR.glob("*.xlsx")):
        rows = parse_in_excel(xlsx_path)
        if rows:
            all_rows.extend(rows)
        else:
            print(f"  EMPTY {xlsx_path.name}")

    if not all_rows:
        print("No data parsed.")
        return

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["year", "month", "operator"]).reset_index(drop=True)

    out_path = CLEAN_DIR / "in.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {len(df)} rows to {out_path}")
    print(f"Date range: {df['year'].min()}-{df['month'].min():02d} to {df['year'].max()}-{df['month'].max():02d}")
    print(f"Operators: {df['operator'].nunique()}")

    monthly = df.groupby(["year", "month"]).agg(
        handle=("handle", "sum"), revenue=("revenue", "sum"),
    ).reset_index()
    monthly["hold"] = monthly["revenue"] / monthly["handle"] * 100
    monthly = monthly.sort_values(["year", "month"])
    print(f"Months: {len(monthly)}")
    print(f"\n--- IN statewide (last 6 months) ---")
    print(monthly.tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
