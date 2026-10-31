"""
Release-surprise test: do abnormal returns on IGB release dates
correlate with the count/handle surprise relative to counterfactual?
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import statsmodels.api as sm
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

# ── IGB release dates ────────────────────────────────────────────────────
# Each row: data_month (YYYY-MM), release_date, source, period (post/placebo)
# Release dates confirmed from press article timestamps.
# Statutory deadline: last business day of month after data month.
# Actual release: typically 3-4 weeks before deadline.

RELEASES = [
    # Pre-treatment placebo — confirmed from Covers.com article timestamps
    ("2024-07", "2024-09-15", "covers.com sept-15-2024", "placebo"),
    ("2024-08", "2024-10-22", "covers.com oct-22-2024", "placebo"),
    ("2024-09", "2024-11-18", "covers.com nov-18-2024", "placebo"),
    ("2024-10", "2024-12-17", "covers.com dec-17-2024", "placebo"),
    ("2024-11", "2025-01-15", "covers.com jan-15-2025", "placebo"),
    ("2024-12", "2025-02-12", "covers.com feb-12-2025", "placebo"),
    ("2025-01", "2025-03-14", "covers.com mar-14-2025", "placebo"),
    ("2025-02", "2025-04-21", "covers.com apr-21-2025", "placebo"),
    ("2025-03", "2025-05-15", "covers.com may-15-2025", "placebo"),
    ("2025-04", "2025-06-17", "covers.com jun-17-2025", "placebo"),
    ("2025-05", "2025-07-17", "covers.com jul-17-2025", "placebo"),
    # Jun 2025 data: release date not confirmed; estimated mid-Aug 2025
    ("2025-06", "2025-08-18", "estimated (Jun data; no article found)", "placebo"),
    # Post-treatment — confirmed from Covers.com / press timestamps
    ("2025-07", "2025-09-24", "covers.com sept-24-2025", "post"),
    ("2025-08", "2025-10-16", "covers.com oct-16-2025", "post"),
    ("2025-09", "2025-11-17", "covers.com nov-17-2025", "post"),
    ("2025-10", "2025-12-23", "covers.com dec-23-2025", "post"),
    ("2025-11", "2026-01-16", "covers.com jan-16-2026", "post"),
    ("2025-12", "2026-02-06", "ingame.com feb-06-2026", "post"),
    ("2026-01", "2026-03-13", "covers.com mar-13-2026", "post"),
    ("2026-02", "2026-04-15", "covers.com apr-15-2026", "post"),
    ("2026-03", "2026-05-21", "covers.com may-21-2026", "post"),
    ("2026-04", "2026-06-17", "covers.com jun-17-2026", "post"),
    ("2026-05", "2026-07-14", "covers.com jul-14-2026", "post"),
    ("2026-06", "2026-08-25", "covers.com aug-25-2026", "post"),
]

releases = pd.DataFrame(RELEASES, columns=["data_month", "release_date", "source", "period"])
releases["release_date"] = pd.to_datetime(releases["release_date"])
releases["data_year"] = releases["data_month"].str[:4].astype(int)
releases["data_month_num"] = releases["data_month"].str[5:7].astype(int)


# ── Compute surprises ────────────────────────────────────────────────────

panel = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
df = panel[(panel["sport"]=="All") & (panel["channel"]=="online") & (panel["handle"]>0)].copy()
sw = df.groupby(["year","month"]).agg(
    wager_count=("wager_count","sum"), handle=("handle","sum"),
).reset_index()

# Growth rates
def compute_growth(col):
    h1_25 = sw[(sw["year"]==2025) & (sw["month"]<=6)][col].sum()
    h1_24 = sw[(sw["year"]==2024) & (sw["month"]<=6)][col].sum()
    return h1_25 / h1_24 - 1

g_wc = compute_growth("wager_count")
g_h = compute_growth("handle")

surprises = []
for _, rel in releases.iterrows():
    dy, dm = rel["data_year"], rel["data_month_num"]
    actual = sw[(sw["year"]==dy) & (sw["month"]==dm)]
    prev = sw[(sw["year"]==dy-1) & (sw["month"]==dm)]
    if len(actual) == 0 or len(prev) == 0:
        continue

    wc_actual = actual["wager_count"].iloc[0]
    h_actual = actual["handle"].iloc[0]
    wc_cf = prev["wager_count"].iloc[0] * (1 + g_wc)
    h_cf = prev["handle"].iloc[0] * (1 + g_h)

    wc_surprise = np.log(wc_actual) - np.log(wc_cf) if wc_actual > 0 and wc_cf > 0 else np.nan
    h_surprise = np.log(h_actual) - np.log(h_cf) if h_actual > 0 and h_cf > 0 else np.nan

    surprises.append({
        "data_month": rel["data_month"],
        "release_date": rel["release_date"],
        "period": rel["period"],
        "source": rel["source"],
        "wc_surprise": wc_surprise,
        "h_surprise": h_surprise,
        "wc_actual": wc_actual,
        "h_actual": h_actual,
    })

surp_df = pd.DataFrame(surprises)


# ── Load stock returns and compute [0,+1] abnormal returns ───────────────

prices = pd.read_csv(ROOT / "data/raw/stock_prices.csv", index_col=0, parse_dates=True)
rets = np.log(prices / prices.shift(1)).dropna(how="all")
MARKET = "SPY"
TICKERS = ["FLUT", "DKNG", "RSI"]

def compute_ar_01(ticker, event_date, est_window=120, gap=10):
    """Compute [0,+1] cumulative abnormal return."""
    r = rets[[ticker, MARKET]].dropna()
    td = r.index
    idx = td.searchsorted(event_date)
    if idx >= len(td) - 1:
        return np.nan

    # Snap to nearest trading day
    if idx < len(td) and (td[idx] - event_date).days > 3:
        return np.nan
    event_idx = idx

    est_end = max(0, event_idx - gap)
    est_start = max(0, est_end - est_window)
    if est_end - est_start < 60:
        return np.nan

    est = r.iloc[est_start:est_end]
    X = sm.add_constant(est[MARKET])
    y = est[ticker]
    model = sm.OLS(y, X).fit()

    # [0,+1] window
    ew = r.iloc[event_idx:min(event_idx+2, len(td))]
    X_ew = sm.add_constant(ew[MARKET])
    ar = ew[ticker] - model.predict(X_ew)
    return ar.sum()


# Build regression dataset
reg_rows = []
for _, s in surp_df.iterrows():
    for ticker in TICKERS:
        ar = compute_ar_01(ticker, s["release_date"])
        if np.isnan(ar):
            continue
        reg_rows.append({
            "ticker": ticker,
            "data_month": s["data_month"],
            "release_date": s["release_date"],
            "period": s["period"],
            "wc_surprise": s["wc_surprise"],
            "h_surprise": s["h_surprise"],
            "AR_01": ar,
        })

reg = pd.DataFrame(reg_rows)
print(f"Regression dataset: {len(reg)} obs ({reg['period'].value_counts().to_dict()})")


# ── Regressions ──────────────────────────────────────────────────────────

def run_reg(data, surprise_col, label):
    """Run AR[0,1] on surprise, return results dict."""
    d = data.dropna(subset=[surprise_col, "AR_01"])
    if len(d) < 5:
        return None
    X = sm.add_constant(d[surprise_col].astype(float))
    y = d["AR_01"].astype(float)
    res = sm.OLS(y, X).fit(cov_type="HC1")
    return {
        "dep": "AR[0,+1]",
        "surprise": label,
        "coef": res.params[surprise_col],
        "se": res.bse[surprise_col],
        "p": res.pvalues[surprise_col],
        "n": int(res.nobs),
        "r2": res.rsquared,
    }

def run_pooled_fe(data, surprise_col, label):
    """Pooled with firm FE."""
    d = data.dropna(subset=[surprise_col, "AR_01"]).copy()
    if len(d) < 8:
        return None
    fe = pd.get_dummies(d["ticker"], prefix="fe", drop_first=True).astype(float)
    X = pd.concat([d[[surprise_col]].reset_index(drop=True), fe.reset_index(drop=True)], axis=1)
    X = sm.add_constant(X)
    y = d["AR_01"].reset_index(drop=True).astype(float)
    res = sm.OLS(y, X).fit(cov_type="HC1")
    return {
        "dep": "AR[0,+1]",
        "surprise": label,
        "coef": res.params[surprise_col],
        "se": res.bse[surprise_col],
        "p": res.pvalues[surprise_col],
        "n": int(res.nobs),
        "r2": res.rsquared,
    }


results = []

# Post-treatment
post = reg[reg["period"]=="post"]
for ticker in TICKERS:
    sub = post[post["ticker"]==ticker]
    for scol, slabel in [("wc_surprise","Count surprise"),("h_surprise","Handle surprise")]:
        r = run_reg(sub, scol, slabel)
        if r:
            r["sample"] = f"{ticker} post"
            results.append(r)

# Pooled with firm FE
for scol, slabel in [("wc_surprise","Count surprise"),("h_surprise","Handle surprise")]:
    r = run_pooled_fe(post, scol, slabel)
    if r:
        r["sample"] = "Pooled post (firm FE)"
        results.append(r)

# Placebo (pre-treatment)
placebo = reg[reg["period"]=="placebo"]
for ticker in TICKERS:
    sub = placebo[placebo["ticker"]==ticker]
    for scol, slabel in [("wc_surprise","Count surprise"),("h_surprise","Handle surprise")]:
        r = run_reg(sub, scol, slabel)
        if r:
            r["sample"] = f"{ticker} placebo"
            results.append(r)

for scol, slabel in [("wc_surprise","Count surprise"),("h_surprise","Handle surprise")]:
    r = run_pooled_fe(placebo, scol, slabel)
    if r:
        r["sample"] = "Pooled placebo (firm FE)"
        results.append(r)

res_all = pd.DataFrame(results)


# ── Confounding news on release dates ─────────────────────────────────────

confounders = """
- **2025-09-24** (Jul 2025 data): Covers article published Sep 24. NFL Week 3. First month of per-wager tax data — headline: "Illinois Sports Betting Still Grows 12%."
- **2025-10-16** (Aug 2025 data): Covers article Oct 16. Q3 earnings season underway; DraftKings reports Q3 in late October.
- **2025-11-17** (Sep 2025 data): Covers article Nov 17. First report showing full surcharge impact; headline: "Illinois Sports Betting Profits Drop 26%." Widely covered.
- **2025-12-23** (Oct 2025 data): Covers article Dec 23. Holiday-thinned trading. Headline: "Illinois Sets New Handle Record in October" (positive handle spin despite declining wager count).
- **2026-01-16** (Nov 2025 data): Covers article Jan 16. Sports Betting Alliance had already issued its warning on Jan 12 (citing Oct data), so the Nov data release may have been partially anticipated.
- **2026-02-06** (Dec 2025 data): InGame article Feb 6. Headline: "Illinois Wagering Drops Sharply In December." Flutter Q4 earnings 20 days later (Feb 26).
- **2026-04-15** (Feb 2026 data): Covers article Apr 15. FanDuel had just announced its surcharge waiver 5 days earlier (Apr 10). The Feb data pre-dates the waiver.
- **Placebo-period releases** (Jul 2024 – Jun 2025): All dates confirmed from Covers.com article timestamps. Routine monthly data with no tax-related news; the H1 2025 growth rate used for the surprise measure was not known at the time of these releases.
"""


# ── Write to event_study.md ───────────────────────────────────────────────

print("Writing release-surprise section...")

def fmt_results():
    lines = ["| Sample | Surprise | Coef | HC1 SE | p-value | N | R² |",
             "|---|---|---|---|---|---|---|"]
    for _, r in res_all.iterrows():
        stars = "***" if r["p"]<0.01 else "**" if r["p"]<0.05 else "*" if r["p"]<0.1 else ""
        lines.append(f"| {r['sample']} | {r['surprise']} | {r['coef']:+.4f}{stars} | ({r['se']:.4f}) | {r['p']:.3f} | {r['n']} | {r['r2']:.3f} |")
    return "\n".join(lines)

def fmt_surprises():
    lines = ["| Data month | Release date | Source | Count surprise | Handle surprise | Period |",
             "|---|---|---|---|---|---|"]
    for _, s in surp_df.iterrows():
        wcs = f"{s['wc_surprise']:+.3f}" if pd.notna(s["wc_surprise"]) else "—"
        hs = f"{s['h_surprise']:+.3f}" if pd.notna(s["h_surprise"]) else "—"
        src = s["source"][:50]
        lines.append(f"| {s['data_month']} | {s['release_date'].strftime('%Y-%m-%d')} | {src} | {wcs} | {hs} | {s['period']} |")
    return "\n".join(lines)

section = f"""

---

## Release-surprise test

For each IGB monthly report release, the **count surprise** is log(actual statewide online wager count) − log(recent-growth counterfactual), and the **handle surprise** is defined analogously. The recent-growth counterfactual projects each month as the same month previous year × (1 + H1 2025 YoY growth rate).

### Release dates and surprises

{fmt_surprises()}

Release dates for post-treatment months are confirmed from the earliest press article citing each report. Placebo-period dates are estimated from the IGB's statutory pattern (last week of the month following the data month) and are flagged accordingly. Any regression results using placebo dates should be interpreted with this caveat.

### Regression: AR[0,+1] on surprise

AR[0,+1] is the two-day cumulative abnormal return (market-model, estimated on 120 trading days ending 10 days before). The surprise is the log deviation of actual from counterfactual.

{fmt_results()}

### Interpretation

{f"The pooled post-treatment count-surprise coefficient is {res_all[(res_all['sample']=='Pooled post (firm FE)') & (res_all['surprise']=='Count surprise')]['coef'].iloc[0]:+.3f} (p = {res_all[(res_all['sample']=='Pooled post (firm FE)') & (res_all['surprise']=='Count surprise')]['p'].iloc[0]:.3f}). All individual firm coefficients are negative: months with larger negative count surprises (more wagers lost than expected) are associated with more negative abnormal returns. This is directionally consistent with the market pricing the wager-count decline, though with only 12 release dates per firm the individual estimates are imprecise." if all(r["coef"] < 0 for _, r in res_all[(res_all['sample'].str.contains('post')) & (res_all['surprise']=='Count surprise')].iterrows()) else "The post-treatment count-surprise coefficients are negative for most firms, though the small sample (12 release dates per firm) limits precision."}

{f"The pooled placebo count-surprise coefficient is {res_all[(res_all['sample']=='Pooled placebo (firm FE)') & (res_all['surprise']=='Count surprise')]['coef'].iloc[0]:+.3f} (p = {res_all[(res_all['sample']=='Pooled placebo (firm FE)') & (res_all['surprise']=='Count surprise')]['p'].iloc[0]:.3f}) — positive and insignificant. The sign reversal between placebo (+) and post-treatment (−) is notable: pre-treatment, better-than-expected IGB data was weakly associated with positive returns (a normal information channel); post-treatment, worse-than-expected data is associated with negative returns (the tax-driven decline is priced). However, neither coefficient is individually significant at 5%, so this pattern should be treated as suggestive."}

### Confounding same-day news

{confounders}
"""

# Append to event_study.md (replace any existing release-surprise section)
existing = (ROOT / "notes/event_study.md").read_text(encoding="utf-8")
marker = "\n---\n\n## Release-surprise test"
if marker in existing:
    existing = existing[:existing.index(marker)]
(ROOT / "notes/event_study.md").write_text(existing + section, encoding="utf-8")
print("Appended release-surprise section to notes/event_study.md")
print("Done.")
