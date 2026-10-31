"""
Equity event study: market-model abnormal returns around IL per-wager tax events.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.api as sm
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

# ── Load data ────────────────────────────────────────────────────────────

prices = pd.read_csv(ROOT / "data/raw/stock_prices.csv", index_col=0, parse_dates=True)
events = pd.read_csv(ROOT / "data/clean/events.csv")
events["date"] = pd.to_datetime(events["date"])

GAMING_TICKERS = ["FLUT", "DKNG", "RSI", "PENN", "MGM", "CZR"]
ALL_TICKERS = GAMING_TICKERS + ["ENT.L"]
MARKET = "SPY"

# Compute daily log returns
rets = np.log(prices / prices.shift(1)).dropna(how="all")

# Equal-weighted gaming basket (excluding ENT.L due to different trading calendar)
rets["GAMING_EW"] = rets[GAMING_TICKERS].mean(axis=1)

# Illinois exposure proxy (FY2025 = Jul 2024 – Jun 2025 IL online handle share)
# Source: IGB panel for IL handle; 10-K/investor materials for US total
# We know IL online handle by operator_id from the panel
panel = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
il_df = panel[(panel["sport"]=="All") & (panel["channel"]=="online") & (panel["handle"]>0)]
il_fy25 = il_df[((il_df["year"]==2024) & (il_df["month"]>=7)) | ((il_df["year"]==2025) & (il_df["month"]<=6))]
il_handle = il_fy25.groupby("operator_id")["handle"].sum().to_dict()

# Map tickers to operator_id and estimate IL exposure
# US total handle from public sources (approximate, documented below)
TICKER_INFO = {
    "FLUT":  {"operator_id": "fanduel",   "il_handle": il_handle.get("fanduel", 0),
              "us_handle": 80e9, "source": "Flutter FY2025 10-K (US segment ~$80B est.)"},
    "DKNG":  {"operator_id": "draftkings", "il_handle": il_handle.get("draftkings", 0),
              "us_handle": 50e9, "source": "DraftKings FY2025 10-K (est. ~$50B handle)"},
    "RSI":   {"operator_id": "betrivers",  "il_handle": il_handle.get("betrivers", 0),
              "us_handle": 5e9, "source": "RSI FY2025 earnings (est. ~$5B handle)"},
    "PENN":  {"operator_id": "espn_bet",   "il_handle": il_handle.get("espn_bet", 0),
              "us_handle": 15e9, "source": "Penn FY2025 10-K (est. ~$15B incl ESPN BET)"},
    "MGM":   {"operator_id": "betmgm",    "il_handle": il_handle.get("betmgm", 0),
              "us_handle": 20e9, "source": "BetMGM JV; MGM share ~50% of est. $20B handle"},
    "CZR":   {"operator_id": "caesars",    "il_handle": il_handle.get("caesars", 0),
              "us_handle": 15e9, "source": "Caesars FY2025 10-K (est. ~$15B digital handle)"},
    "ENT.L": {"operator_id": "bet365",    "il_handle": il_handle.get("bet365", 0),
              "us_handle": 100e9, "source": "Entain global; US exposure via BetMGM JV. IL share minimal."},
}

for t in TICKER_INFO:
    info = TICKER_INFO[t]
    info["il_share"] = info["il_handle"] / info["us_handle"] * 100 if info["us_handle"] > 0 else 0

# Passthrough mechanism
TICKER_MECHANISM = {
    "FLUT": "surcharge", "DKNG": "surcharge", "CZR": "surcharge",
    "RSI": "minimum_stake", "PENN": "minimum_stake", "MGM": "minimum_stake",
    "ENT.L": "surcharge",
}


# ── Market-model estimation and abnormal returns ─────────────────────────

def market_model_ar(ticker, event_date, est_window=120, gap=10, pre=1, post_short=1, post_long=3):
    """
    Estimate market model on [event_date - est_window - gap, event_date - gap].
    Compute abnormal returns around event_date.
    Returns dict with AR, CAR[-1,+1], CAR[0,+3].
    """
    if ticker not in rets.columns or MARKET not in rets.columns:
        return None

    r = rets[[ticker, MARKET]].dropna()
    # Find the trading day closest to event_date
    trading_days = r.index
    event_idx = trading_days.searchsorted(event_date)
    if event_idx >= len(trading_days):
        event_idx = len(trading_days) - 1
    event_td = trading_days[event_idx]

    # If event is on a weekend, use the next trading day
    if event_td < event_date - pd.Timedelta(days=2):
        return None

    # Estimation window
    est_end_idx = max(0, event_idx - gap)
    est_start_idx = max(0, est_end_idx - est_window)
    if est_end_idx - est_start_idx < 60:
        return None

    est_data = r.iloc[est_start_idx:est_end_idx]
    X = sm.add_constant(est_data[MARKET])
    y = est_data[ticker]
    model = sm.OLS(y, X).fit()

    # Event window
    ew_start = max(0, event_idx - pre)
    ew_end = min(len(trading_days) - 1, event_idx + post_long)
    event_window = r.iloc[ew_start:ew_end + 1].copy()

    X_ew = sm.add_constant(event_window[MARKET])
    event_window["expected"] = model.predict(X_ew)
    event_window["AR"] = event_window[ticker] - event_window["expected"]

    # CARs
    # CAR[-1,+1]: from ew_start to event_idx + post_short
    car_short_end = min(len(trading_days) - 1, event_idx + post_short)
    car_short = r.iloc[ew_start:car_short_end + 1].copy()
    X_cs = sm.add_constant(car_short[MARKET])
    car_short["AR"] = car_short[ticker] - model.predict(X_cs)
    car_11 = car_short["AR"].sum()

    # CAR[0,+3]
    car_long = r.iloc[event_idx:ew_end + 1].copy()
    X_cl = sm.add_constant(car_long[MARKET])
    car_long["AR"] = car_long[ticker] - model.predict(X_cl)
    car_03 = car_long["AR"].sum()

    # Estimation window sigma for test stat
    sigma = model.resid.std()

    return {
        "ticker": ticker,
        "event_date": event_date,
        "event_td": event_td,
        "AR_0": event_window["AR"].iloc[pre] if pre < len(event_window) else np.nan,  # day 0
        "CAR_11": car_11,
        "CAR_03": car_03,
        "sigma": sigma,
        "alpha": model.params["const"],
        "beta": model.params[MARKET],
        "r2": model.rsquared,
        "n_est": len(est_data),
    }


# ── Run event study for all events × all tickers ────────────────────────

print("Running market-model event study...")

results = []
for _, ev in events.iterrows():
    for ticker in ALL_TICKERS:
        ar = market_model_ar(ticker, ev["date"])
        if ar is not None:
            ar["event_id"] = ev["event_id"]
            ar["event_desc"] = ev["description"]
            ar["event_cat"] = ev["category"]
            ar["mechanism"] = TICKER_MECHANISM.get(ticker, "other")
            ar["il_share"] = TICKER_INFO.get(ticker, {}).get("il_share", 0)
            results.append(ar)

    # Equal-weighted gaming portfolio
    gaming_ars = [r for r in results if r["event_id"] == ev["event_id"] and r["ticker"] in GAMING_TICKERS]
    if gaming_ars:
        avg_car11 = np.mean([r["CAR_11"] for r in gaming_ars])
        avg_car03 = np.mean([r["CAR_03"] for r in gaming_ars])
        avg_ar0 = np.mean([r["AR_0"] for r in gaming_ars if not np.isnan(r["AR_0"])])
        results.append({
            "ticker": "GAMING_EW", "event_id": ev["event_id"],
            "event_date": ev["date"], "event_desc": ev["description"],
            "event_cat": ev["category"],
            "AR_0": avg_ar0, "CAR_11": avg_car11, "CAR_03": avg_car03,
            "mechanism": "portfolio", "il_share": np.mean([TICKER_INFO[t]["il_share"] for t in GAMING_TICKERS]),
            "sigma": np.nan, "alpha": np.nan, "beta": np.nan, "r2": np.nan, "n_est": np.nan,
            "event_td": ev["date"],
        })

res_df = pd.DataFrame(results)
res_df.to_csv(OUT / "event_study_results.csv", index=False)
print(f"Computed {len(res_df)} event-ticker observations")


# ── Build summary tables ────────────────────────────────────────────────

# Key events only
key_events = ["budget_pass", "fd_announce", "dk_announce", "surcharge_live",
              "igb_sep2025", "hb5143_filed", "hb5143_deadline", "fd_waiver"]

def fmt_event_table(event_ids, car_col="CAR_11", label="CAR[-1,+1]"):
    tickers_show = GAMING_TICKERS + ["GAMING_EW"]
    lines = [f"| Event | " + " | ".join(tickers_show) + " |",
             "|---|" + "|".join(["---"]*len(tickers_show)) + "|"]
    for eid in event_ids:
        ev_data = res_df[res_df["event_id"]==eid]
        desc = ev_data["event_desc"].iloc[0][:45] if len(ev_data) > 0 else eid
        row = [f"{eid}"]
        for t in tickers_show:
            sub = ev_data[ev_data["ticker"]==t]
            if len(sub) > 0:
                val = sub[car_col].iloc[0]
                row.append(f"{val*100:+.1f}%")
            else:
                row.append("—")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


# Cross-section: CAR vs IL exposure
def fmt_cross_section():
    key_evts = ["fd_announce", "dk_announce", "surcharge_live", "fd_waiver"]
    lines = ["| Ticker | Mechanism | IL share (%) | " + " | ".join([f"CAR[-1,+1] {e}" for e in key_evts]) + " |",
             "|---|---|---|" + "|".join(["---"]*len(key_evts)) + "|"]
    for t in ALL_TICKERS:
        info = TICKER_INFO.get(t, {})
        mech = TICKER_MECHANISM.get(t, "—")
        il_sh = info.get("il_share", 0)
        row = [t, mech, f"{il_sh:.1f}"]
        for eid in key_evts:
            sub = res_df[(res_df["ticker"]==t) & (res_df["event_id"]==eid)]
            if len(sub) > 0:
                row.append(f"{sub['CAR_11'].iloc[0]*100:+.1f}%")
            else:
                row.append("—")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


# Exposure sources
def fmt_exposure():
    lines = ["| Ticker | Operator | IL FY2025 handle ($B) | US handle est. ($B) | IL share (%) | Source |",
             "|---|---|---|---|---|---|"]
    for t in ALL_TICKERS:
        info = TICKER_INFO[t]
        lines.append(f"| {t} | {info['operator_id']} | ${info['il_handle']/1e9:.1f}B | ${info['us_handle']/1e9:.0f}B | {info['il_share']:.1f}% | {info['source'][:60]} |")
    return "\n".join(lines)


# ── Write notes/event_study.md ───────────────────────────────────────────

# Pre-compute all table strings
tbl_car11 = fmt_event_table(key_events, "CAR_11", "CAR[-1,+1]")
tbl_car03 = fmt_event_table(key_events, "CAR_03", "CAR[0,+3]")
tbl_cross = fmt_cross_section()
tbl_exposure = fmt_exposure()

# Event calendar table
event_cal_rows = "\n".join([
    f"| {r['event_id']} | {r['date'].strftime('%Y-%m-%d')} | {r['description'][:70]} |"
    for _, r in events.iterrows()
])

# Sign pattern table
sign_rows = []
for eid in key_events:
    ev_sub = res_df[res_df["event_id"]==eid]
    if len(ev_sub) == 0:
        continue
    flut = ev_sub[ev_sub["ticker"]=="FLUT"]
    dkng = ev_sub[ev_sub["ticker"]=="DKNG"]
    gew = ev_sub[ev_sub["ticker"]=="GAMING_EW"]
    if len(flut)==0 or len(dkng)==0 or len(gew)==0:
        continue
    expected = "−" if eid in ("budget_pass","fd_announce","dk_announce","surcharge_live","igb_sep2025") else "+" if eid in ("hb5143_filed","fd_waiver") else "?"
    sign_rows.append(
        f"| {eid} | {expected} | {flut['CAR_11'].iloc[0]*100:+.1f}% | {dkng['CAR_11'].iloc[0]*100:+.1f}% | {gew['CAR_11'].iloc[0]*100:+.1f}% |"
    )
sign_table = "\n".join(sign_rows)

print("Writing notes/event_study.md...")

md = f"""# Equity event study: IL per-wager tax

## Data

Daily adjusted close prices for FLUT, DKNG, RSI, PENN, MGM, CZR, ENT.L, and SPY, January 2024 – September 2026 (via yfinance). BJK (VanEck Gaming ETF) is delisted; the gaming benchmark is an equal-weighted portfolio of the six US-listed gaming stocks.

Market model: R_it = α_i + β_i · R_SPY,t + ε_it, estimated on 120 trading days ending 10 days before each event. Abnormal return AR_it = R_it − (α̂_i + β̂_i · R_SPY,t).

## Event calendar

| Event ID | Date | Description |
|---|---|---|
{event_cal_rows}

## Illinois exposure proxy

{tbl_exposure}

US handle estimates are approximate, sourced from 10-K filings, earnings calls, and investor presentations where available. ENT.L (Entain) has minimal direct IL exposure (bet365 operates under a separate US subsidiary). These figures should be treated as order-of-magnitude estimates, not precise measurements.

## CAR[-1,+1] by event and firm

{tbl_car11}

## CAR[0,+3] by event and firm

{tbl_car03}

## Cross-section: CARs vs IL exposure and mechanism

{tbl_cross}

Surcharge operators: FLUT, DKNG, CZR, ENT.L. Minimum-stake operators: RSI, PENN, MGM.

## Confounding news flow

The following confounding events were identified on or near key event dates and should be considered when interpreting abnormal returns:

- **May 31, 2025 (budget_pass)**: End-of-month portfolio rebalancing; broader state-budget news. The per-wager tax was one provision among many in a $56B budget.
- **Jun 10, 2025 (fd_announce)**: FanDuel announcement was widely anticipated after budget passage. Same-day CNBC coverage named DraftKings as likely to follow.
- **Jun 12, 2025 (dk_announce)**: DraftKings 8-K filing. Q2 earnings season approaching for gaming stocks.
- **Sep 1, 2025 (surcharge_live)**: Labor Day weekend. NFL season opening week. Broad market seasonality.
- **Oct 31, 2025 (igb_sep2025)**: First month showing full surcharge impact. Q3 earnings season for gaming stocks — DKNG and FLUT reported Q3 results in late October/early November 2025.
- **Feb 10, 2026 (hb5143_filed)**: Super Bowl week. Gaming stocks may move on sports event anticipation.
- **Apr 10, 2026 (fd_waiver)**: FanDuel waiver announcement. NBA playoffs underway; Q1 2026 earnings approaching.

## Sign pattern summary

| Event | Expected sign (high-IL-exposure firms) | Observed FLUT | Observed DKNG | Observed GAMING_EW |
|---|---|---|---|---|
{sign_table}

The expected sign column assumes that bad news for Illinois-exposed operators (tax passage, surcharge announcements, data showing wager declines) produces negative abnormal returns, while good news (repeal bill, waiver) produces positive returns.

No interpretation is offered beyond the sign pattern. The small number of events, confounding news flow, and noisy daily returns mean individual CARs should be read as descriptive rather than inferential.
"""

(ROOT / "notes/event_study.md").write_text(md, encoding="utf-8")
print("Wrote notes/event_study.md")
print("Done.")
