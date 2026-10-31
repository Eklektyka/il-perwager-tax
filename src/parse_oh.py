"""
Parse Ohio Casino Control Commission sports gaming Excel files into panel format.

Input:  data/raw/states/oh/{YYYY}_Sports.xlsx
Output: data/clean/states/oh.parquet

Ohio Excel structure (per monthly sheet):
  - Type A: Online operators with columns:
    Online Proprietor/Services Provider, Total Gross Receipts (handle),
    (-) Winnings Paid, (-) Voided Wagers, Promotional*, Revenue, Taxable Revenue
  - Type B: Retail operators (same columns)
  - Subtotal rows and grand total at bottom

Revenue definition: GGR (Gross Gaming Revenue) = handle - payouts - voids.
Taxable Revenue = GGR (promos are NOT deductible in Ohio).
"""

import re
from pathlib import Path

import pandas as pd
import pdfplumber

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "states" / "oh"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean" / "states"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

MONTH_NAMES = [
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
]


def clean_number(s):
    """Parse a number that may have embedded spaces from PDF extraction.
    E.g., '3 78,848,819' → 378848819.0, '(10,414)' → -10414.0, '-' → 0.
    """
    if s is None:
        return None
    s = str(s).strip()
    if s in ("", "-", "NaN", "nan"):
        return 0.0
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    # Remove embedded spaces (PDF artifact) and commas
    s = s.replace(" ", "").replace(",", "")
    try:
        val = float(s)
        return -val if neg else val
    except ValueError:
        return None


def parse_ohio_pdf(path):
    """Parse Ohio annual/monthly PDF into rows."""
    pdf = pdfplumber.open(str(path))
    rows = []

    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue

        lines = text.split("\n")

        # Find month from first line
        month_num = None
        year = None
        for line in lines[:3]:
            for i, mname in enumerate(MONTH_NAMES):
                if mname in line.upper():
                    month_num = i + 1
                    m = re.search(r"(\d{4})", line)
                    if m:
                        year = int(m.group(1))
                    break
            if month_num:
                break

        if not month_num or not year:
            continue

        current_channel = None
        for line in lines:
            line_upper = line.strip().upper()
            if "TYPE A" in line_upper and "ONLINE" in line_upper:
                current_channel = "online"
                continue
            elif "TYPE B" in line_upper and "RETAIL" in line_upper:
                current_channel = "retail"
                continue
            elif "TYPE A AND TYPE B" in line_upper:
                current_channel = None
                continue

            if current_channel is None:
                continue

            # Skip headers and subtotals
            if any(skip in line for skip in [
                "Proprietor", "Services Provider", "Subtotal",
                "Total Gross", "Promotional",
                "REVENUE REPORTING", "gaming credits",
            ]):
                continue
            if line.strip().startswith("*"):
                continue

            # Parse operator line. Numbers may have embedded spaces from PDF.
            # Strategy: find all "number tokens" (sequences of digits, commas,
            # parens, minus, decimal) possibly with single embedded spaces.
            # Then whatever is before the first number token is the operator name.
            # A number token starts with a digit, '(', or '-' followed by digit.
            m = re.match(
                r"^(.*?)\s+([\d(][\d,. ]*(?:\))?(?:\s+[\d(][\d,. ]*(?:\))?)*)\s*$",
                line.strip(),
            )
            if not m:
                # Try with leading minus
                m = re.match(
                    r"^(.*?)\s+([-\d(][\d,. ]*.*)\s*$",
                    line.strip(),
                )
            if not m:
                continue

            operator = m.group(1).strip()
            nums_raw = m.group(2)

            if not operator or operator.upper() in ("", "TOTAL"):
                continue

            # Split number tokens by finding boundaries: a new number starts
            # after a space when preceded by a digit/paren and followed by a digit/paren/minus
            # Use pdfplumber's character positions would be ideal, but from text:
            # Extract all tokens by splitting on spaces and recombining
            # numbers that have embedded spaces (e.g., "3 78,848,819" = one number)
            tokens = nums_raw.split()
            numbers = []
            current = ""
            for tok in tokens:
                if tok == "-":
                    # Standalone dash = zero
                    if current:
                        numbers.append(clean_number(current))
                        current = ""
                    numbers.append(0.0)
                elif current and (tok.startswith(",") or (not tok[0].isdigit() and tok[0] != "(")):
                    # Continuation of previous number (starts with comma)
                    current += tok
                elif current and tok[0].isdigit() and current[-1] == " ":
                    # Embedded space in number like "3 78,848,819"
                    current = current.rstrip() + tok
                elif not current:
                    current = tok
                else:
                    # New number starts
                    numbers.append(clean_number(current))
                    current = tok
            if current:
                numbers.append(clean_number(current))

            # If we don't have exactly 6 numbers, try a simpler approach:
            # just extract all comma-formatted numbers from the raw string
            if len(numbers) != 6:
                numbers = []
                # Remove operator name prefix, then find all numbers
                # A number: optional paren, optional minus, digits with optional commas/periods/spaces
                for nm in re.finditer(r"\([\d, .]+\)|[\d][\d, .]*\d|(?<!\w)-(?=\s|$)", nums_raw):
                    val = clean_number(nm.group())
                    if val is not None:
                        numbers.append(val)

            if len(numbers) < 6:
                continue

            handle = numbers[0]
            revenue = numbers[4]
            taxable = numbers[5]

            if handle is None:
                continue

            rows.append({
                "state": "OH",
                "year": year,
                "month": month_num,
                "operator": operator,
                "channel": current_channel,
                "handle": handle,
                "revenue": revenue,
                "taxable_revenue": taxable,
                "revenue_type": "GGR",
            })

    pdf.close()
    return rows


def parse_ohio_excel(path):
    """Parse a single Ohio yearly Excel file into rows."""
    xls = pd.ExcelFile(path)
    year_match = re.search(r"(\d{4})", path.stem)
    if not year_match:
        return []

    file_year = int(year_match.group(1))
    rows = []

    for sheet_name in xls.sheet_names:
        month_upper = sheet_name.strip().upper()
        if month_upper not in MONTH_NAMES:
            continue

        month_num = MONTH_NAMES.index(month_upper) + 1
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

        current_channel = None
        header_row_idx = None

        for idx in range(len(df)):
            cell0 = str(df.iloc[idx, 0]).strip() if pd.notna(df.iloc[idx, 0]) else ""

            # Detect section headers
            if "TYPE A" in cell0 and "ONLINE" in cell0:
                current_channel = "online"
                header_row_idx = idx + 1  # next row has column headers
                continue
            elif "TYPE B" in cell0 and "RETAIL" in cell0:
                current_channel = "retail"
                header_row_idx = idx + 1
                continue
            elif "TYPE A AND TYPE B" in cell0 or "TOTALS" in cell0.upper():
                current_channel = None  # skip combined totals
                continue

            if current_channel is None:
                continue

            # Skip header rows and subtotal rows
            if "Proprietor" in cell0 or "Services Provider" in cell0:
                continue
            if "Subtotal" in cell0 or cell0 == "" or "NaN" in cell0:
                continue
            if "*" in cell0 and "Promotional" in cell0:
                continue

            # Parse operator row
            try:
                operator = cell0.strip()
                if not operator or operator.startswith("*"):
                    continue

                handle = df.iloc[idx, 1]
                revenue = df.iloc[idx, 5]
                taxable_revenue = df.iloc[idx, 6]

                # Skip if all NaN
                if pd.isna(handle) and pd.isna(revenue):
                    continue

                def to_float(v):
                    if pd.isna(v):
                        return None
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        return None

                rows.append({
                    "state": "OH",
                    "year": file_year,
                    "month": month_num,
                    "operator": operator,
                    "channel": current_channel,
                    "handle": to_float(handle),
                    "revenue": to_float(revenue),
                    "taxable_revenue": to_float(taxable_revenue),
                    "revenue_type": "GGR",
                })
            except (IndexError, ValueError):
                continue

    return rows


def main():
    all_rows = []

    # Parse Excel files (2024+)
    for xlsx_path in sorted(RAW_DIR.glob("*_Sports.xlsx")):
        if "new" in xlsx_path.stem or "v2" in xlsx_path.stem:
            continue  # skip duplicate downloads
        print(f"Parsing {xlsx_path.name}...")
        rows = parse_ohio_excel(xlsx_path)
        print(f"  {len(rows)} operator-month rows")
        all_rows.extend(rows)

    # Parse PDF files (2023 full-year)
    for pdf_path in sorted(RAW_DIR.glob("FullYear_*.pdf")):
        print(f"Parsing {pdf_path.name}...")
        rows = parse_ohio_pdf(pdf_path)
        print(f"  {len(rows)} operator-month rows")
        all_rows.extend(rows)

    if not all_rows:
        print("No data parsed.")
        return

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["year", "month", "channel", "operator"]).reset_index(drop=True)

    out_path = CLEAN_DIR / "oh.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {len(df)} rows to {out_path}")
    print(f"Date range: {df['year'].min()}-{df['month'].min():02d} to {df['year'].max()}-{df['month'].max():02d}")
    print(f"Operators: {df['operator'].nunique()}")
    print(f"Channels: {df['channel'].unique().tolist()}")

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
