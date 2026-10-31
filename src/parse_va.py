"""
Parse Virginia Lottery monthly sports betting PDF reports.
VA reports statewide: Total wagers (handle), Virginia AGR.
Revenue definition: AGR = wagers − cash winnings − noncash wagers − federal excise − adjustments.
"""
import re
from pathlib import Path
import pandas as pd, numpy as np
import pdfplumber

RAW = Path(__file__).resolve().parent.parent / "data/raw/states/va"
OUT = Path(__file__).resolve().parent.parent / "data/clean/states"
OUT.mkdir(parents=True, exist_ok=True)


def parse_num(s):
    s = str(s).replace("$", "").replace(",", "").replace(" ", "").strip()
    if s.startswith("(") and s.endswith(")"):
        return -float(s[1:-1])
    try:
        return float(s)
    except ValueError:
        return None


def parse_va(path):
    m = re.match(r"(\d{4})-(\d{2})", path.stem)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    try:
        pdf = pdfplumber.open(str(path))
    except Exception:
        return None

    handle = None
    agr = None
    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.split("\n"):
            # "Total wagers $652,879,750.42 $3,629,169,301.59"
            if line.strip().startswith("Total wagers"):
                nums = re.findall(r"\$[\d,]+\.?\d*", line)
                if nums:
                    handle = parse_num(nums[0])  # first number is monthly
            # "Total, Virginia Adjusted Gross Revenues $67,507,323.45"
            elif "Virginia Adjusted Gross Revenue" in line:
                nums = re.findall(r"\$[\d,]+\.?\d*|\(\$[\d,]+\.?\d*\)", line)
                if nums:
                    agr = parse_num(nums[0])
    pdf.close()

    if handle is None:
        return None
    return {"state": "VA", "year": year, "month": month,
            "operator": "STATEWIDE", "channel": "online",
            "handle": handle, "revenue": agr, "revenue_type": "AGR"}


def main():
    rows = []
    for p in sorted(RAW.glob("*.pdf")):
        r = parse_va(p)
        if r:
            rows.append(r)
        else:
            print(f"  SKIP {p.name}")
    df = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
    df.to_parquet(OUT / "va.parquet", index=False)
    print(f"Wrote {len(df)} rows")
    print(f"Range: {df.iloc[0]['year']:.0f}-{df.iloc[0]['month']:02.0f} to {df.iloc[-1]['year']:.0f}-{df.iloc[-1]['month']:02.0f}")
    # Show last few months
    for _, r in df.tail(6).iterrows():
        print(f"  {int(r['year'])}-{int(r['month']):02d}: handle=${r['handle']/1e6:.0f}M  agr=${r['revenue']/1e6:.0f}M")

if __name__ == "__main__":
    main()
