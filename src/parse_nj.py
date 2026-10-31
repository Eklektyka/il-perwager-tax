"""
Parse NJ DGE monthly sports wagering PDF reports.

Five layout eras:
  Era 1 (2019-2021, 5p): p2 has total "Sports Wagering Revenue"; last page has handle by channel
  Era 2 (2022-2023, 6p): same + p3 has operator-level SWR by casino; last page has handle
  Era 3 (2024, 5p): same as Era 1 (some pages amended)
  Era 4 (2025, 8p): p2 splits "Online Sports Wagering"/"Retail Sports Wagering"; p6-7 operators; p8 handle
  Era 5 (2026, 9p): p2 splits "Online Sportsbook"/"Sportsbook Lounge"; p6 operators; p9 handle

Revenue definition: GGR (gross gaming revenue) = handle − payouts.
NJ does not deduct promotional credits from the reported gross revenue figure.
"""

import re
from pathlib import Path

import pandas as pd
import pdfplumber

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "states" / "nj"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean" / "states"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}


def parse_num(s):
    """Parse a properly comma-formatted number. Returns None if unparseable."""
    if s is None:
        return None
    s = str(s).strip().replace("$", "").strip()
    if s in ("", "-", "N/A", "n/a"):
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    # Remove spaces that pdfplumber inserts in large numbers (e.g., "5 3,109,144")
    # Strategy: remove all spaces, then parse
    s = s.replace(" ", "").replace(",", "")
    try:
        val = float(s)
        return -val if neg else val
    except ValueError:
        return None


def fix_pdf_spaces(text):
    """Fix PDF extraction artifacts where numbers have embedded spaces.
    E.g., '5 3,109,144' → '53,109,144', '1 03,358' → '103,358'.
    But NOT '886,656,470 886,656,470' (two separate numbers).
    Rule: a single digit followed by a space then a digit+comma group is one number.
    """
    # Pattern: single digit(s) + space + comma-formatted number continuation
    # "5 3,109,144" → a short digit group, space, then ","-separated groups
    text = re.sub(r"(\d)\s+(\d{1,3},\d{3})", r"\1\2", text)
    # Also: "( 48,312,144)" → "(48,312,144)"
    text = re.sub(r"\(\s+", "(", text)
    return text


def find_nums_on_line(line):
    """Extract all comma-formatted numbers from a line, handling paren negatives."""
    line = fix_pdf_spaces(line)
    # Match proper comma-formatted numbers or paren-wrapped negatives
    # A number: optional $, then either (NUM) for negative or just NUM
    # NUM = digits with commas like 123,456,789 or plain 12345
    tokens = re.findall(
        r"\(\s*\d{1,3}(?:,\d{3})*\s*\)"  # (123,456) negative
        r"|\d{1,3}(?:,\d{3})+"            # 123,456,789 comma-formatted
        r"|\d+",                           # plain digits
        line,
    )
    return [parse_num(t) for t in tokens if parse_num(t) is not None]


def extract_handle(text):
    """Extract online and retail handle from a handle stats page."""
    lines = text.split("\n")
    online_h = None
    retail_h = None

    for i, line in enumerate(lines):
        # Era 1-4: "Internet (On-Line) Sports Wagering  NUMBER  NUMBER"
        # or "On-site (Retail) Sports Wagering  NUMBER  NUMBER"
        # Era 5: just "Online" or "Lounge" on its own line, number on next or same line
        low = line.lower().strip()

        if "internet" in low and "on-line" in low:
            nums = find_nums_on_line(line)
            if nums:
                online_h = nums[0]  # Monthly handle is first number
        elif "on-site" in low and "retail" in low:
            nums = find_nums_on_line(line)
            if nums:
                retail_h = nums[0]
        elif low == "online" or low.startswith("online "):
            # Era 5: "Online  999,222,617" or number on next line
            nums = find_nums_on_line(line)
            if nums:
                online_h = nums[0]
            elif i + 1 < len(lines):
                nums = find_nums_on_line(lines[i + 1])
                if nums:
                    online_h = nums[0]
        elif low.startswith("lounge") or ("lounge" in low and "sportsbook" not in low):
            nums = find_nums_on_line(line)
            if nums:
                retail_h = nums[0]
            elif i + 1 < len(lines):
                nums = find_nums_on_line(lines[i + 1])
                if nums:
                    retail_h = nums[0]

    return online_h, retail_h


def extract_ggr_from_stats(text):
    """Extract online and retail GGR from the statistics summary page."""
    lines = text.split("\n")
    online_ggr = None
    retail_ggr = None
    total_ggr = None

    # The stats page may have MONTHLY and YTD sections.
    # We want only the MONTHLY section (appears first on the page).
    # Stop parsing once we hit "YEAR-TO-DATE" or "YTD" header.
    in_ytd = False

    for line in lines:
        low = line.strip().upper()

        # Detect YTD section start — stop capturing after this
        if "YEAR-TO-DATE" in low or "YEAR TO DATE" in low:
            in_ytd = True
            continue
        if in_ytd:
            continue

        # Skip tax/footnote lines
        if "Additional Tax" in line or "IAT" in line or "Tax:" in line:
            continue
        if "Investment" in line or "Development" in line:
            continue
        if "obligations" in line.lower() or "(a)" in line:
            continue

        stripped = line.strip()

        # Era 4 (2025): "Online Sports Wagering  118,549,423  ..."
        if re.match(r"Online Sports Wagering\b", stripped):
            nums = find_nums_on_line(line)
            if nums:
                online_ggr = nums[0]
        # Era 5 (2026): "Online Sportsbook  112,304,808  ..."
        elif re.match(r"Online Sportsbook\b", stripped):
            nums = find_nums_on_line(line)
            if nums:
                online_ggr = nums[0]
        # Era 4: "Retail Sports Wagering  3,645,442  ..."
        elif re.match(r"Retail Sports Wagering\b", stripped):
            nums = find_nums_on_line(line)
            if nums:
                retail_ggr = nums[0]
        # Era 5: "Sportsbook Lounge  1,928,201  ..."
        elif re.match(r"Sportsbook Lounge\b", stripped):
            nums = find_nums_on_line(line)
            if nums:
                retail_ggr = nums[0]
        # Era 1-3: "Sports Wagering Revenue  82,640,979  ..."
        # Only capture if we don't already have online/retail split
        elif re.match(r"Sports Wagering Revenue\b", stripped):
            if online_ggr is None and total_ggr is None:
                nums = find_nums_on_line(line)
                if nums:
                    total_ggr = nums[0]

    return online_ggr, retail_ggr, total_ggr


def extract_operators(text):
    """Extract operator-level online GGR from comparison page (2025+)."""
    lines = text.split("\n")
    operators = []
    in_table = False

    for line in lines:
        if "Brand" in line and ("Casino/Racetrack" in line or "Racetrack" in line):
            in_table = True
            continue
        if not in_table:
            continue
        if line.strip().startswith("Total:"):
            break
        if line.strip().startswith("("):
            break

        nums = find_nums_on_line(line)
        if not nums:
            continue

        # Operator name is everything before "$ " or the first number
        # Find where the first number starts
        first_num_match = re.search(r"\$?\s*\(?\s*\d[\d, ]*\d", line)
        if first_num_match:
            op_name = line[:first_num_match.start()].strip()
            if op_name and len(op_name) > 2:
                operators.append({"operator": op_name, "ggr": nums[0]})

    return operators


def parse_nj_pdf(path):
    """Parse a single NJ monthly PDF."""
    fname = path.stem
    m = re.match(r"(\w+?)(\d{4})", fname)
    if not m:
        return None
    month_name, year = m.group(1), int(m.group(2))
    month_num = MONTH_MAP.get(month_name)
    if not month_num:
        return None

    try:
        pdf = pdfplumber.open(str(path))
    except Exception:
        return None

    result = {
        "year": year, "month": month_num,
        "online_handle": None, "retail_handle": None,
        "online_ggr": None, "retail_ggr": None,
        "total_ggr": None,
        "operators": [],
    }

    for page in pdf.pages:
        text = page.extract_text() or ""

        # Handle stats page (identified by "Handle" keyword)
        if "Handle" in text and ("Retail" in text or "Lounge" in text or "On-site" in text):
            oh, rh = extract_handle(text)
            if oh is not None:
                result["online_handle"] = oh
            if rh is not None:
                result["retail_handle"] = rh

        # Statistics summary page (identified by "STATISTICS" in first line)
        first_line = text.split("\n")[0] if text else ""
        if "STATISTICS" in first_line or "REVENUE STATISTICS" in first_line:
            og, rg, tg = extract_ggr_from_stats(text)
            if og is not None:
                result["online_ggr"] = og
            if rg is not None:
                result["retail_ggr"] = rg
            if tg is not None:
                result["total_ggr"] = tg

        # Operator comparison page (2025+)
        if "GROSS REVENUE COMPARISON" in text and "ONLINE" in text.upper():
            ops = extract_operators(text)
            if ops:
                result["operators"] = ops
        elif "SPORTSBOOK GROSS REVENUE COMPARISON" in text.upper() and "ONLINE" in text.upper():
            ops = extract_operators(text)
            if ops:
                result["operators"] = ops

    pdf.close()

    # For Era 1-3, if we only have total GGR (no online/retail split),
    # use handle ratio to split
    if result["online_ggr"] is None and result["total_ggr"] is not None:
        oh = result["online_handle"]
        rh = result["retail_handle"]
        if oh and rh and (oh + rh) > 0:
            online_share = oh / (oh + rh)
            result["online_ggr"] = result["total_ggr"] * online_share
            result["retail_ggr"] = result["total_ggr"] * (1 - online_share)
        else:
            # Can't split, assign all to online (dominates)
            result["online_ggr"] = result["total_ggr"]

    return result


def main():
    all_rows = []
    issues = []

    for pdf_path in sorted(RAW_DIR.glob("*.pdf")):
        result = parse_nj_pdf(pdf_path)
        if not result:
            issues.append(f"  SKIP {pdf_path.name} (cannot parse filename or corrupted)")
            continue

        y, m = result["year"], result["month"]
        oh = result["online_handle"]
        og = result["online_ggr"]
        rh = result["retail_handle"]
        rg = result["retail_ggr"]

        if oh is None and og is None:
            issues.append(f"  EMPTY {pdf_path.name} (no handle or GGR extracted)")
            continue

        # Online statewide row
        hold = (og / oh * 100) if (oh and og and oh > 0) else None
        all_rows.append({
            "state": "NJ", "year": y, "month": m,
            "operator": "STATEWIDE", "channel": "online",
            "handle": oh, "revenue": og, "hold_pct": hold,
            "revenue_type": "GGR",
        })

        # Retail statewide row
        if rh is not None or rg is not None:
            hold_r = (rg / rh * 100) if (rh and rg and rh > 0) else None
            all_rows.append({
                "state": "NJ", "year": y, "month": m,
                "operator": "STATEWIDE", "channel": "retail",
                "handle": rh, "revenue": rg, "hold_pct": hold_r,
                "revenue_type": "GGR",
            })

        # Operator-level online rows
        for op in result["operators"]:
            all_rows.append({
                "state": "NJ", "year": y, "month": m,
                "operator": op["operator"], "channel": "online",
                "handle": None, "revenue": op["ggr"], "hold_pct": None,
                "revenue_type": "GGR",
            })

        n_ops = len(result["operators"])
        tag = "total_split" if result["total_ggr"] and not result.get("_had_channel_ggr") else "direct"
        print(f"  OK {pdf_path.name}: online_h={oh:,.0f}, online_ggr={og:,.0f}, {n_ops} ops" if oh and og else f"  PARTIAL {pdf_path.name}: h={oh}, g={og}")

    for issue in issues:
        print(issue)

    if not all_rows:
        print("No data parsed.")
        return

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["year", "month", "channel", "operator"]).reset_index(drop=True)

    out_path = CLEAN_DIR / "nj.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nWrote {len(df)} rows to {out_path}")

    # Statewide online summary
    sw = df[(df["operator"] == "STATEWIDE") & (df["channel"] == "online")].sort_values(["year", "month"])
    print(f"Months: {len(sw)}, range: {sw.iloc[0]['year']:.0f}-{sw.iloc[0]['month']:02.0f} to {sw.iloc[-1]['year']:.0f}-{sw.iloc[-1]['month']:02.0f}")
    print(f"\n--- NJ statewide online (last 6 months) ---")
    print(sw.tail(6)[["year", "month", "handle", "revenue", "hold_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
