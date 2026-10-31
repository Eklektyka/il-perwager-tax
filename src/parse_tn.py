"""
Parse Tennessee SWAC/SWC monthly sports wagering PDF reports.

TN is online-only (no retail). Reports statewide aggregate handle.
Revenue: TN taxes at 1.85% of handle (not revenue), so "revenue" in
the traditional sense (GGR) is not reported. We store handle only.
"""

import re
from pathlib import Path
import pandas as pd
import pdfplumber

RAW = Path(__file__).resolve().parent.parent / "data/raw/states/tn"
OUT = Path(__file__).resolve().parent.parent / "data/clean/states"
OUT.mkdir(parents=True, exist_ok=True)


def parse_num(s):
    s = str(s).replace("$", "").replace(",", "").replace(" ", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_tn(path):
    m = re.match(r"(\d{4})-(\d{2})", path.stem)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    try:
        pdf = pdfplumber.open(str(path))
    except Exception:
        return None
    text = pdf.pages[0].extract_text() or ""
    pdf.close()

    handle = None
    for line in text.split("\n"):
        # Try multiple formats:
        # "Gross Handle $ 386,059,756"
        # "Gross Wagers: $211.3 Million"
        # "Gross Wagers $ 205,863,860"
        m2 = re.search(r"Gross (?:Handle|Wagers)[:\s]*\$?\s*([\d,.]+)\s*Million", line, re.IGNORECASE)
        if m2:
            handle = parse_num(m2.group(1)) * 1_000_000
            break
        # Match numbers with possible embedded spaces (PDF artefact)
        m2 = re.search(r"Gross (?:Handle|Wagers)[:\s]*\$?\s*([\d, ]+\d)", line, re.IGNORECASE)
        if m2:
            handle = parse_num(m2.group(1))
            if handle and handle > 1000:  # sanity check
                break
            handle = None
    if handle is None:
        return None
    return {"state": "TN", "year": year, "month": month,
            "operator": "STATEWIDE", "channel": "online",
            "handle": handle, "revenue": None, "revenue_type": "handle_only"}


def main():
    rows = []
    for p in sorted(RAW.glob("*.pdf")):
        r = parse_tn(p)
        if r:
            rows.append(r)
        else:
            print(f"  SKIP {p.name}")
    df = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
    df.to_parquet(OUT / "tn.parquet", index=False)
    print(f"Wrote {len(df)} rows to tn.parquet")
    print(f"Range: {df.iloc[0]['year']:.0f}-{df.iloc[0]['month']:02.0f} to {df.iloc[-1]['year']:.0f}-{df.iloc[-1]['month']:02.0f}")


if __name__ == "__main__":
    main()
