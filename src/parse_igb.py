"""
Parse downloaded IGB monthly CSVs into a long panel parquet.

Input:  data/raw/{YYYY-MM}_activity.csv  and  data/raw/{YYYY-MM}_tax.csv
Output: data/clean/il_sports_wagering_panel.parquet

Panel columns:
  year, month, operator, channel, sport,
  handle, agr, state_tax, wager_count, per_wager_tax

Activity CSVs provide: sport × channel × operator with wager_count and handle.
Tax CSVs provide: channel × operator with agr, state_tax, per_wager_tax.
Since tax data isn't available by sport, AGR/tax fields are null on sport-level
rows but filled on sport="All" rows.

Idempotent: re-running overwrites the output parquet.
"""

import csv
import io
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from operator_mapping import get_operator_id, get_brand

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

CHANNEL_MAP = {
    "In-Person Wagering": "retail",
    "Online Wagering": "online",
}


def parse_month_from_header(text):
    """Extract (year, month) from a header line like 'July 2025'."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # lines[0] = title, lines[1] = month/year, lines[2] = report date
    m = re.match(r'"?(\w+)\s+(\d{4})"?', lines[1])
    if not m:
        raise ValueError(f"Cannot parse month from: {lines[1]}")
    month_name, year = m.group(1), int(m.group(2))
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    month = month_names.index(month_name) + 1
    return year, month


def parse_activity_csv(path):
    """
    Parse an activity CSV.

    Returns DataFrame with columns: operator, channel, sport, wager_count, handle
    Includes all sport-level rows (Professional, College, etc.) plus any
    unlabeled bottom-section rows tagged as sport="Other".
    Excludes "Total" location type rows (we keep only retail/online).
    """
    text = path.read_text(encoding="utf-8")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    data_lines = []
    started = False
    for line in lines:
        if started:
            data_lines.append(line)
        elif line.startswith('"Sport Level"'):
            started = True

    rows = []
    for line in data_lines:
        fields = list(csv.reader(io.StringIO(line)))[0]
        fields = [f for f in fields if f != ""]

        if len(fields) == 7:
            sport, loc_type, licensee = fields[0], fields[1], fields[2]
            t1w, t1h, t2w, t2h = fields[3], fields[4], fields[5], fields[6]
        elif len(fields) == 6:
            # Bottom section: no sport column
            sport = "Other"
            loc_type, licensee = fields[0], fields[1]
            t1w, t1h, t2w, t2h = fields[2], fields[3], fields[4], fields[5]
        else:
            continue

        if loc_type == "Total":
            continue
        channel = CHANNEL_MAP.get(loc_type)
        if channel is None:
            continue

        try:
            wager_count = int(t1w.replace(",", "")) + int(t2w.replace(",", ""))
            handle = float(t1h.replace(",", "")) + float(t2h.replace(",", ""))
        except (ValueError, TypeError):
            wager_count = None
            handle = None

        rows.append({
            "operator": licensee.strip(),
            "channel": channel,
            "sport": sport,
            "wager_count": wager_count,
            "handle": handle,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def parse_tax_csv(path):
    """
    Parse a tax CSV.

    Returns DataFrame with columns:
      operator, channel, agr, state_tax, per_wager_tax
    """
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "")
    lines = text.strip().splitlines()

    data_lines = []
    started = False
    for line in lines:
        if started:
            if line.strip():
                data_lines.append(line)
        elif line.startswith('"Location Type"'):
            started = True

    rows = []
    for line in data_lines:
        fields = list(csv.reader(io.StringIO(line)))[0]
        fields = [f for f in fields if f != ""]

        if len(fields) < 8:
            continue

        loc_type, licensee = fields[0], fields[1]
        state_agr, state_tax = fields[2], fields[3]
        sports_wager_tax = fields[6]

        if loc_type == "Total":
            continue

        channel = CHANNEL_MAP.get(loc_type)
        if channel is None:
            continue

        def safe_float(x):
            try:
                return float(x.replace(",", ""))
            except (ValueError, TypeError):
                return None

        rows.append({
            "operator": licensee.strip(),
            "channel": channel,
            "agr": safe_float(state_agr),
            "state_tax": safe_float(state_tax),
            "per_wager_tax": safe_float(sports_wager_tax),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def main():
    all_rows = []

    activity_files = sorted(RAW_DIR.glob("*_activity.csv"))

    for act_path in activity_files:
        tag = act_path.stem.replace("_activity", "")
        tax_path = RAW_DIR / f"{tag}_tax.csv"

        act_text = act_path.read_text(encoding="utf-8")
        year, month = parse_month_from_header(act_text)

        act_df = parse_activity_csv(act_path)
        tax_df = parse_tax_csv(tax_path) if tax_path.exists() else pd.DataFrame()

        # 1) Sport-level rows: handle + wager_count, AGR/tax left null
        if not act_df.empty:
            sport_df = act_df.copy()
            sport_df["year"] = year
            sport_df["month"] = month
            sport_df["agr"] = None
            sport_df["state_tax"] = None
            sport_df["per_wager_tax"] = None
            all_rows.append(sport_df)

        # 2) "All" sport rows: sum handle/wager_count across sports, merge with tax
        if not act_df.empty:
            channel_totals = (
                act_df.groupby(["operator", "channel"], as_index=False)
                .agg({"handle": "sum", "wager_count": "sum"})
            )
        else:
            channel_totals = pd.DataFrame(columns=["operator", "channel", "handle", "wager_count"])

        if not tax_df.empty:
            merged = channel_totals.merge(
                tax_df, on=["operator", "channel"], how="outer"
            )
        else:
            merged = channel_totals.copy()
            merged["agr"] = None
            merged["state_tax"] = None
            merged["per_wager_tax"] = None

        merged["year"] = year
        merged["month"] = month
        merged["sport"] = "All"
        all_rows.append(merged)

    panel = pd.concat(all_rows, ignore_index=True)

    # Add operator_id and brand
    panel["operator_id"] = panel["operator"].map(get_operator_id)
    panel["brand"] = panel["operator"].map(get_brand)

    # Reorder columns
    cols = [
        "year", "month", "operator", "operator_id", "brand", "channel", "sport",
        "handle", "agr", "state_tax", "wager_count", "per_wager_tax",
    ]
    panel = panel[cols]

    # Sort
    panel = panel.sort_values(["year", "month", "operator", "channel", "sport"]).reset_index(drop=True)

    # Save
    out_path = CLEAN_DIR / "il_sports_wagering_panel.parquet"
    panel.to_parquet(out_path, index=False)
    print(f"Wrote {len(panel)} rows to {out_path}")
    print(f"Date range: {panel['year'].min()}-{panel['month'].min():02d} to {panel['year'].max()}-{panel['month'].max():02d}")
    print(f"Operators: {panel['operator'].nunique()}")
    print(f"Channels: {panel['channel'].unique().tolist()}")
    print(f"Sports: {panel['sport'].unique().tolist()}")

    # Quick validation: July 2025 statewide totals
    jul25 = panel[(panel["year"] == 2025) & (panel["month"] == 7) & (panel["sport"] == "All")]
    print(f"\n--- July 2025 (sport=All) statewide ---")
    print(f"  Handle:       ${jul25['handle'].sum():,.0f}")
    print(f"  AGR:          ${jul25['agr'].sum():,.0f}")
    print(f"  Per-wager tax: ${jul25['per_wager_tax'].sum():,.0f}")


if __name__ == "__main__":
    main()
