"""
Parse PA PGCB monthly sports wagering Excel files into panel format.

Input:  data/raw/states/pa/*.xlsx (one file per fiscal year)
Output: data/clean/states/pa.parquet

PA Excel layout: One sheet per fiscal year. Wide format with 12 monthly columns.
Each operator has blocks of rows:
  - Total Sports Wagering: Handle, Revenue, Promo Credits, Gross Revenue (Taxable), Tax
  - Retail Sports Wagering: Handle, Gross Revenue (Taxable), Tax
  - Online Sports Wagering: Handle, Gross Revenue (Taxable), Tax

Revenue definition:
  "Revenue" = Handle − Payouts (GGR before promo deduction)
  "Gross Revenue (Taxable)" = Revenue − Promotional Credits (tax base, 36% tax rate)
"""

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "states" / "pa"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean" / "states"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def parse_pa_excel(path):
    """Parse a single PA fiscal-year Excel file."""
    xls = pd.ExcelFile(path)
    sheet_name = xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

    # Row 3 has month headers in columns 2, 4, 6, ... (every other column)
    # Parse months from row 3
    months = []
    for col_idx in range(2, min(df.shape[1], 26), 2):
        val = df.iloc[3, col_idx]
        if pd.notna(val):
            val_str = str(val).strip()
            m = re.match(r"(\w+)\s+(\d{4})", val_str)
            if m:
                month_name, year = m.group(1), int(m.group(2))
                month_num = MONTH_MAP.get(month_name)
                if month_num:
                    months.append((col_idx, year, month_num))

    if not months:
        return []

    rows = []
    current_operator = None
    current_section = None  # 'total', 'retail', 'online'

    for row_idx in range(4, df.shape[0]):
        cell0 = str(df.iloc[row_idx, 0]).strip() if pd.notna(df.iloc[row_idx, 0]) else ""

        # Detect operator name (typically ALL CAPS, no numbers)
        if cell0 and cell0 not in ("NaN", "") and not any(kw in cell0 for kw in [
            "Handle", "Revenue", "Promotional", "Gross Revenue", "State Tax",
            "Local Share", "Total Sports", "Retail Sports", "Online Sports",
            "STATEWIDE", "TOTAL", "Footnote", "Note", "*",
        ]):
            # Check if it's an operator name (not a data row)
            nums_in_row = sum(1 for c in range(2, min(df.shape[1], 26), 2)
                              if pd.notna(df.iloc[row_idx, c]) and str(df.iloc[row_idx, c]).strip() not in ("", "NaN"))
            if nums_in_row == 0:
                current_operator = cell0
                current_section = None
                continue

        # Detect section
        if "Total Sports Wagering" in cell0:
            current_section = "total"
            continue
        elif "Retail Sports Wagering" in cell0:
            current_section = "retail"
            continue
        elif "Online Sports Wagering" in cell0:
            current_section = "online"
            continue

        if current_operator is None or current_section is None:
            continue

        # We want online Handle and Gross Revenue (Taxable) for each operator-month
        is_handle = "Handle" in cell0
        is_taxable = "Gross Revenue" in cell0 and "Taxable" in cell0
        is_revenue = cell0 == "Revenue" or cell0.strip() == "Revenue"

        if not (is_handle or is_taxable or is_revenue):
            continue

        # Only collect online and retail sections (skip "total" to avoid double counting)
        if current_section == "total":
            continue

        for col_idx, year, month_num in months:
            val = df.iloc[row_idx, col_idx]
            if pd.isna(val):
                continue
            try:
                num = float(val)
            except (ValueError, TypeError):
                continue

            # Find or create the row for this operator-month-channel
            key = (current_operator, year, month_num, current_section)
            existing = None
            for r in rows:
                if (r["operator"], r["year"], r["month"], r["channel"]) == key:
                    existing = r
                    break
            if existing is None:
                existing = {
                    "state": "PA", "year": year, "month": month_num,
                    "operator": current_operator, "channel": current_section,
                    "handle": None, "revenue": None, "taxable_revenue": None,
                    "revenue_type": "GGR_and_taxable",
                }
                rows.append(existing)

            if is_handle:
                existing["handle"] = num
            elif is_revenue:
                existing["revenue"] = num  # GGR before promo
            elif is_taxable:
                existing["taxable_revenue"] = num  # After promo deduction

    return rows


def main():
    all_rows = []

    for xlsx_path in sorted(RAW_DIR.glob("*.xlsx")):
        print(f"Parsing {xlsx_path.name}...")
        rows = parse_pa_excel(xlsx_path)
        print(f"  {len(rows)} rows")
        all_rows.extend(rows)

    if not all_rows:
        print("No data parsed.")
        return

    df = pd.DataFrame(all_rows)
    # Drop rows with no actual data (zero or null handle AND zero/null revenue)
    df = df[
        (df["handle"].notna() & (df["handle"] > 0))
        | (df["taxable_revenue"].notna() & (df["taxable_revenue"] != 0))
    ]
    df = df.sort_values(["year", "month", "channel", "operator"]).reset_index(drop=True)

    out_path = CLEAN_DIR / "pa.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {len(df)} rows to {out_path}")
    print(f"Date range: {df['year'].min()}-{df['month'].min():02d} to {df['year'].max()}-{df['month'].max():02d}")
    print(f"Operators: {df['operator'].nunique()}")

    # Statewide online monthly
    online = df[df["channel"] == "online"]
    monthly = online.groupby(["year", "month"]).agg(
        handle=("handle", "sum"),
        taxable=("taxable_revenue", "sum"),
    ).reset_index()
    monthly["hold"] = monthly["taxable"] / monthly["handle"] * 100
    print(f"\n--- PA statewide online (last 6 months) ---")
    print(monthly.tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
