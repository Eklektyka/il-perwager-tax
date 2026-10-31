"""
Parse Colorado Division of Gaming monthly sports betting proceeds PDFs.

Input:  data/raw/states/co/*.pdf
Output: data/clean/states/co.parquet

CO reports "Net Sports Betting Proceeds" (NSBP) = Handle − Payouts − Free bets − Voided.
This is the taxable amount. The PDFs show monthly and FY-annual tables with
On-Site (retail) and Internet (online) columns.

Revenue definition: Net Proceeds (after limited deductions including free bets).
The tax rate is 10% of NSBP.
"""

import re
from pathlib import Path

import pandas as pd
import pdfplumber

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "states" / "co"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean" / "states"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def parse_num(s):
    if s is None:
        return None
    s = str(s).strip().replace("$", "").replace(",", "").replace(" ", "")
    if s in ("", "-", "*"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        val = float(s)
        return -val if neg else val
    except ValueError:
        return None


def parse_co_pdf(path):
    """Parse a single CO monthly PDF."""
    # Extract month/year from filename
    fname = path.stem.lower()

    # Try various filename patterns
    month_num = None
    year = None

    # Pattern: "HB 21-1292 Report September 2025"
    m = re.search(r"(\w+)\s+(\d{4})", fname)
    if m:
        month_name = m.group(1)
        year_candidate = int(m.group(2))
        if month_name in MONTH_MAP:
            month_num = MONTH_MAP[month_name]
            year = year_candidate

    # Pattern: "60 Monthly Summary (April '25)"
    if month_num is None:
        m = re.search(r"\((\w+)\s+'(\d{2})\)", fname)
        if m:
            month_name = m.group(1).lower()
            year_short = int(m.group(2))
            if month_name in MONTH_MAP:
                month_num = MONTH_MAP[month_name]
                year = 2000 + year_short

    # Pattern: "Monthly Summary (Month 'YY)"
    if month_num is None:
        m = re.search(r"(\w+)\s*'(\d{2})", fname)
        if m:
            month_name = m.group(1).lower()
            year_short = int(m.group(2))
            if month_name in MONTH_MAP:
                month_num = MONTH_MAP[month_name]
                year = 2000 + year_short

    if month_num is None or year is None:
        return None

    try:
        pdf = pdfplumber.open(str(path))
    except Exception:
        return None

    result = {"year": year, "month": month_num, "online_nsbp": None, "retail_nsbp": None}

    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = text.split("\n")

        for i, line in enumerate(lines):
            # New format (2021+): "Statewide $retail $internet $total $tax_r $tax_i $tax_t"
            if "Statewide" in line and "NSBP" not in line:
                nums = re.findall(r"\$[\d,]+\.?\d*", line)
                if len(nums) >= 3 and result["online_nsbp"] is None:
                    result["retail_nsbp"] = parse_num(nums[0])
                    result["online_nsbp"] = parse_num(nums[1])
                    break

            # Old format (2020): "Total NSBP**  $retail  $internet  $total"
            if "Total NSBP" in line and result["online_nsbp"] is None:
                nums = re.findall(r"\$[\d,]+\.?\d*", line)
                if len(nums) >= 3:
                    result["retail_nsbp"] = parse_num(nums[0])
                    result["online_nsbp"] = parse_num(nums[1])
                    break

    pdf.close()
    return result


def main():
    all_rows = []
    skipped = []

    for pdf_path in sorted(RAW_DIR.glob("*.pdf")):
        # Skip non-monthly files
        fname_lower = pdf_path.stem.lower()
        if "top" in fname_lower or "sport" in fname_lower.replace("sports betting", ""):
            if "monthly" not in fname_lower and "report" not in fname_lower and "summary" not in fname_lower:
                continue

        result = parse_co_pdf(pdf_path)
        if not result:
            skipped.append(pdf_path.name)
            continue

        y, m = result["year"], result["month"]
        on = result["online_nsbp"]
        ret = result["retail_nsbp"]

        if on is None and ret is None:
            skipped.append(f"{pdf_path.name} (no data)")
            continue

        if on is not None:
            all_rows.append({
                "state": "CO", "year": y, "month": m,
                "operator": "STATEWIDE", "channel": "online",
                "handle": None,  # CO doesn't report handle in this format
                "revenue": on,
                "hold_pct": None,
                "revenue_type": "net_proceeds",
            })
        if ret is not None:
            all_rows.append({
                "state": "CO", "year": y, "month": m,
                "operator": "STATEWIDE", "channel": "retail",
                "handle": None,
                "revenue": ret,
                "hold_pct": None,
                "revenue_type": "net_proceeds",
            })

    for s in skipped[:5]:
        print(f"  SKIP: {s}")
    if len(skipped) > 5:
        print(f"  ... and {len(skipped)-5} more skipped")

    if not all_rows:
        print("No data parsed.")
        return

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["year", "month", "channel"]).reset_index(drop=True)

    out_path = CLEAN_DIR / "co.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {len(df)} rows to {out_path}")
    print(f"Date range: {df['year'].min()}-{df['month'].min():02d} to {df['year'].max()}-{df['month'].max():02d}")

    online = df[df["channel"] == "online"]
    print(f"\n--- CO statewide online (last 6 months) ---")
    print(online.tail(6)[["year", "month", "revenue"]].to_string(index=False))


if __name__ == "__main__":
    main()
