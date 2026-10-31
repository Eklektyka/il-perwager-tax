"""
Download all monthly sports wagering CSVs from the Illinois Gaming Board.

Two report types per month:
  1. All Wagering Activity Detail — wager counts and handle by sport/channel/operator
  2. Completed Events Tax Summary — AGR, state tax, per-wager tax by channel/operator

Reports are downloaded one month at a time to data/raw/.
Idempotent: skips files that already exist.
"""

import requests
import re
import time
from pathlib import Path
from datetime import date

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://igbapps.illinois.gov/SportsReports_AEM.aspx"

# March 2020 (launch) through June 2026
START = (2020, 3)
END = (2026, 6)

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def month_range(start, end):
    """Yield (year, month_1indexed) tuples from start to end inclusive."""
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def get_viewstate(session):
    """GET the form page and extract ASP.NET hidden fields."""
    r = session.get(BASE_URL, timeout=30)
    r.raise_for_status()
    vs = re.search(r'__VIEWSTATE.*?value="(.*?)"', r.text).group(1)
    vsg = re.search(r'__VIEWSTATEGENERATOR.*?value="(.*?)"', r.text).group(1)
    ev = re.search(r'__EVENTVALIDATION.*?value="(.*?)"', r.text).group(1)
    return vs, vsg, ev


def download_csv(session, vs, vsg, ev, month_name, year, report_type):
    """
    POST the form and return CSV text.
    report_type: 'activity' or 'tax'
    """
    if report_type == "activity":
        search_type = "TypeCash"
        extra = {"SearchCash": "Detail Report"}
    else:
        search_type = "TypeAccrual"
        extra = {"SearchAccrual": "Tax Summary Report"}

    data = {
        "__VIEWSTATE": vs,
        "__VIEWSTATEGENERATOR": vsg,
        "__EVENTVALIDATION": ev,
        "SearchType": search_type,
        "SearchCash": extra.get("SearchCash", "Detail Report"),
        "SearchAccrual": extra.get("SearchAccrual", "Tax Summary Report"),
        "SearchStartMonth": month_name,
        "SearchStartYear": str(year),
        "SearchEndMonth": month_name,
        "SearchEndYear": str(year),
        "ViewType": "ViewCSV",
        "ButtonSearch.x": "50",
        "ButtonSearch.y": "15",
    }
    r = session.post(BASE_URL, data=data, timeout=60)
    r.raise_for_status()
    return r.text


def main():
    session = requests.Session()
    vs, vsg, ev = get_viewstate(session)

    for year, month in month_range(START, END):
        month_name = MONTHS[month - 1]
        tag = f"{year}-{month:02d}"

        for rtype in ("activity", "tax"):
            fname = f"{tag}_{rtype}.csv"
            fpath = RAW_DIR / fname

            if fpath.exists():
                print(f"  skip {fname} (exists)")
                continue

            print(f"  downloading {fname} ...", end=" ", flush=True)
            try:
                csv_text = download_csv(session, vs, vsg, ev, month_name, year, rtype)
                fpath.write_text(csv_text, encoding="utf-8")
                print(f"OK ({len(csv_text)} bytes)")
            except Exception as e:
                print(f"FAILED: {e}")
                # Re-fetch viewstate in case session expired
                try:
                    vs, vsg, ev = get_viewstate(session)
                except Exception:
                    pass

            time.sleep(0.5)  # polite delay


if __name__ == "__main__":
    main()
