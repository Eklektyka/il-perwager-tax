"""
Parse Maryland Lottery & Gaming sports wagering Excel files into panel format.

Input:  data/raw/states/md/{Month}-{YYYY}-Sports-Wagering-Data.xlsx
Output: data/clean/states/md.parquet

Maryland Excel structure (sheet 1):
  - RETAIL section then ONLINE section, each listing operators with:
    Licensee, Month (date), Handle, Prizes Paid, Hold%, Promotion Play,
    Other Deductions, Taxable Win, Contributions to the State, Expired Prizes
  - Each operator has a month row + FYTD row; we only take the month row.

Revenue definition: "Taxable Win" = Handle - Prizes Paid - Promos - Other Deductions.
This is adjusted gross revenue (AGR) after promotional deductions.
"""

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "states" / "md"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean" / "states"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def parse_md_excel(path):
    """Parse a single Maryland monthly Excel file."""
    xls = pd.ExcelFile(path)
    # First sheet has the operator data
    sheet_name = xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

    # Extract month/year from the filename or cell
    fname = path.stem
    # Try multiple filename patterns
    month_name = None
    year = None
    for pattern in [
        r"(\w+)-(\d{4})-Sports",       # January-2025-Sports-Wagering-Data
        r"Sports-Wagering-Data-(\w+)-(\d{4})",  # Sports-Wagering-Data-December-2021
        r"(\w+)(\d{4})-SportsWagering", # January2024-SportsWagering-Data1
        r"(\w+)-(\d{4})",               # fallback
    ]:
        m = re.match(pattern, fname)
        if m:
            month_name = m.group(1)
            year = int(m.group(2))
            break

    if month_name is None or year is None:
        return []

    month_num = MONTH_MAP.get(month_name)
    if month_num is None:
        return []

    rows = []
    current_channel = None

    for idx in range(len(df)):
        cell0 = str(df.iloc[idx, 0]).strip() if pd.notna(df.iloc[idx, 0]) else ""

        # Detect section headers
        if cell0.upper() == "RETAIL":
            current_channel = "retail"
            continue
        elif cell0.upper() in ("ONLINE", "MOBILE"):
            current_channel = "online"
            continue
        elif cell0.upper() in ("LICENSEE", ""):
            continue
        elif cell0.upper().startswith("COMBINED") or cell0.upper().startswith("MARYLAND"):
            current_channel = None  # skip combined/header sections
            continue

        if current_channel is None:
            continue

        # Skip FYTD rows (column 1 contains "FYTD")
        cell1 = str(df.iloc[idx, 1]).strip() if pd.notna(df.iloc[idx, 1]) else ""
        if cell1 == "FYTD":
            continue

        # Skip total/subtotal rows
        if "total" in cell0.lower() or "grand" in cell0.lower():
            current_channel = None  # reset after totals
            continue

        # Skip header rows
        if cell0 in ("Licensee", "Month"):
            continue

        # Parse operator data row
        operator = cell0
        if not operator or operator.startswith("NaN"):
            continue

        def to_float(v):
            if pd.isna(v):
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        handle = to_float(df.iloc[idx, 2])
        prizes_paid = to_float(df.iloc[idx, 3])
        hold_pct = to_float(df.iloc[idx, 4])
        promo_play = to_float(df.iloc[idx, 5])
        taxable_win = to_float(df.iloc[idx, 7])

        if handle is None and taxable_win is None:
            continue

        # GGR = handle - prizes_paid (before promo deductions)
        ggr = (handle - prizes_paid) if (handle is not None and prizes_paid is not None) else None

        rows.append({
            "state": "MD",
            "year": year,
            "month": month_num,
            "operator": operator,
            "channel": current_channel,
            "handle": handle,
            "revenue": ggr,  # GGR (before promos)
            "taxable_revenue": taxable_win,  # AGR (after promos)
            "hold_pct": hold_pct,
            "revenue_type": "GGR_and_AGR",
        })

    return rows


def main():
    all_rows = []

    for xlsx_path in sorted(RAW_DIR.glob("*.xlsx")):
        rows = parse_md_excel(xlsx_path)
        if rows:
            print(f"  {xlsx_path.name}: {len(rows)} rows")
            all_rows.extend(rows)
        else:
            print(f"  {xlsx_path.name}: SKIPPED (no data parsed)")

    if not all_rows:
        print("No data parsed.")
        return

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["year", "month", "channel", "operator"]).reset_index(drop=True)

    out_path = CLEAN_DIR / "md.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {len(df)} rows to {out_path}")
    print(f"Date range: {df['year'].min()}-{df['month'].min():02d} to {df['year'].max()}-{df['month'].max():02d}")
    print(f"Operators: {df['operator'].nunique()}")

    # Statewide monthly totals
    monthly = df.groupby(["year", "month"]).agg(
        handle=("handle", "sum"),
        revenue=("revenue", "sum"),
    ).reset_index()
    monthly["hold"] = monthly["revenue"] / monthly["handle"] * 100
    print("\n--- Monthly statewide totals (last 6 months) ---")
    print(monthly.tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
