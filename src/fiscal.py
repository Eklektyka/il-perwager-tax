"""
Fiscal analysis: net revenue effect of the per-wager tax.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import statsmodels.api as sm
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

panel = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
cal = pd.read_parquet(ROOT / "data/clean/calendar.parquet")

BRAND_FEE = {
    "FanDuel": 0.50, "DraftKings": 0.25, "Caesars": 0.25,
    "bet365": 0.25, "Fanatics": 0.25,
    "BetMGM": 0.0, "Hard Rock Bet": 0.0, "ESPN BET": 0.0, "BetRivers": 0.0,
}
BRAND_SURCHARGE_START_YM = {
    "FanDuel": 202509, "DraftKings": 202509, "Caesars": 202509,
    "bet365": 202509, "Fanatics": 202510,
}

# Progressive AGSR tax schedule (FY brackets, effective Jul 2024)
TAX_BRACKETS = [
    (30_000_000, 0.20),
    (50_000_000, 0.25),
    (100_000_000, 0.30),
    (200_000_000, 0.35),
    (np.inf, 0.40),
]

def marginal_rate(cum_agr):
    """Return marginal AGSR tax rate given cumulative FY AGR."""
    for threshold, rate in TAX_BRACKETS:
        if cum_agr <= threshold:
            return rate
    return 0.40

def compute_agsr_tax(agr, cum_agr_before):
    """Compute AGSR tax on incremental AGR given cumulative FY AGR before this month."""
    if agr <= 0:
        return 0.0
    tax = 0.0
    remaining = agr
    cum = cum_agr_before
    for threshold, rate in TAX_BRACKETS:
        bracket_space = max(0, threshold - cum)
        taxable = min(remaining, bracket_space)
        tax += taxable * rate
        remaining -= taxable
        cum += taxable
        if remaining <= 0:
            break
    return tax


# ── Load FY2026 operator data ───────────────────────────────────────────

df = panel[(panel["sport"]=="All") & (panel["channel"]=="online")].copy()
df["date"] = pd.to_datetime(df[["year","month"]].assign(day=1))
df["ym"] = df["year"] * 100 + df["month"]
df = df.merge(cal, on=["year","month"], how="left")

# Aggregate by operator_id
agg = df.groupby(["year","month","date","ym","operator_id","brand"]).agg(
    wager_count=("wager_count","sum"), handle=("handle","sum"),
    agr=("agr","sum"), state_tax=("state_tax","sum"),
    per_wager_tax=("per_wager_tax","sum"),
).reset_index()
agg = agg.merge(cal, on=["year","month"], how="left", suffixes=("","_cal"))

# FY2026
fy26 = agg[(agg["ym"]>=202507) & (agg["ym"]<=202606)].copy().sort_values(["operator_id","ym"])

cal_controls = ["nfl_games","nba_games","mlb_games","nhl_games","ncaab_games","ncaaf_games",
                "bears_postseason","bulls_postseason","cubs_postseason",
                "whitesox_postseason","blackhawks_postseason"]


# ── (2) Counterfactual handle forecasts ──────────────────────────────────

def fit_operator_cf(op_data, trend_order=1):
    """Fit log(handle) on month FEs + trend + cal controls, training Jan 2022 – Jun 2025."""
    d = op_data.copy().sort_values("date")
    d["log_h"] = np.log(d["handle"].clip(lower=1))
    d["trend"] = np.arange(len(d))
    month_d = pd.get_dummies(d["month"], prefix="m", drop_first=True).astype(float)
    tcols = ["trend"] if trend_order >= 1 else []
    if trend_order >= 2:
        d["trend2"] = d["trend"]**2
        tcols.append("trend2")
    cc = [c for c in cal_controls if c in d.columns]
    X = pd.concat([month_d.reset_index(drop=True),
                    d[tcols].reset_index(drop=True) if tcols else pd.DataFrame(index=range(len(d))),
                    d[cc].reset_index(drop=True)], axis=1)
    X = sm.add_constant(X)
    y = d["log_h"].reset_index(drop=True)
    train = (d["date"].reset_index(drop=True) >= "2022-01-01") & (d["date"].reset_index(drop=True) <= "2025-06-30")
    if train.sum() < 12:
        return d
    res = sm.OLS(y[train], X[train]).fit()
    d["cf_handle"] = np.exp(res.predict(X).values)
    return d

# Pre-treatment average hold per operator
pre = agg[(agg["ym"]>=202401) & (agg["ym"]<=202506)]
pre_hold = pre.groupby("operator_id").apply(
    lambda g: g["agr"].sum() / g["handle"].sum() if g["handle"].sum() > 0 else 0
).to_dict()

# Build fiscal table
fiscal_rows = []

for trend_order, spec_name in [(0,"no_trend"),(1,"linear"),(2,"quadratic")]:
    # Compute counterfactual per operator
    cum_agr_actual = {}  # track actual FY cumulative AGR per operator
    cum_agr_cf = {}      # track counterfactual FY cumulative AGR

    for op_id in fy26["operator_id"].unique():
        op_all = agg[agg["operator_id"]==op_id].copy()
        if op_all[op_all["handle"]>0].shape[0] < 12:
            continue
        op_cf = fit_operator_cf(op_all, trend_order)
        if "cf_handle" not in op_cf.columns:
            continue

        brand = op_all["brand"].iloc[0]
        fee = BRAND_FEE.get(brand, 0.0)
        surcharge_start = BRAND_SURCHARGE_START_YM.get(brand, 999999)
        hold = pre_hold.get(op_id, 0.08)

        cum_agr_actual.setdefault(op_id, 0)
        cum_agr_cf.setdefault(op_id, 0)

        for _, row in op_cf[(op_cf["ym"]>=202507) & (op_cf["ym"]<=202606)].iterrows():
            ym = int(row["ym"])
            actual_handle = row["handle"]
            cf_handle = row.get("cf_handle", actual_handle)
            actual_agr = row["agr"] if pd.notna(row["agr"]) else 0
            actual_tax = row["state_tax"] if pd.notna(row["state_tax"]) else 0
            actual_pwt = row["per_wager_tax"] if pd.notna(row["per_wager_tax"]) else 0
            wc = row["wager_count"] if pd.notna(row["wager_count"]) else 0

            # Lost handle
            lost_handle = max(0, cf_handle - actual_handle)
            lost_agr = lost_handle * hold

            # Marginal rate for lost AGR tax (based on actual cumulative AGR position)
            marg_rate = marginal_rate(cum_agr_actual[op_id])
            lost_agr_tax = lost_agr * marg_rate

            # Surcharge income upper bound
            surcharge_active = ym >= surcharge_start
            surcharge_ub = fee * wc if surcharge_active else 0
            surcharge_tax = surcharge_ub * marg_rate  # taxed as part of AGSR

            # Update cumulative AGR
            cum_agr_actual[op_id] += actual_agr

            fiscal_rows.append({
                "spec": spec_name, "operator_id": op_id, "brand": brand,
                "year": int(row["year"]), "month": int(row["month"]),
                "actual_handle": actual_handle,
                "cf_handle": cf_handle,
                "actual_agr_tax": actual_tax,
                "per_wager_tax": actual_pwt,
                "lost_handle": lost_handle,
                "lost_agr": lost_agr,
                "lost_agr_tax": lost_agr_tax,
                "surcharge_ub": surcharge_ub,
                "surcharge_tax": surcharge_tax,
                "marginal_rate": marg_rate,
            })

fiscal = pd.DataFrame(fiscal_rows)


# ── Build summary tables ────────────────────────────────────────────────

print("Building fiscal tables...")

# (1) Actual receipts by month
actual = fy26.groupby(["year","month"]).agg(
    per_wager_tax=("per_wager_tax","sum"),
    agr_tax=("state_tax","sum"),
    agr=("agr","sum"),
).reset_index().sort_values(["year","month"])
actual["total_tax"] = actual["per_wager_tax"] + actual["agr_tax"]

# (4) Net fiscal effect
net_rows = []
for spec in ["no_trend","linear","quadratic"]:
    sf = fiscal[fiscal["spec"]==spec]
    by_month = sf.groupby(["year","month"]).agg(
        per_wager_tax=("per_wager_tax","sum"),
        lost_agr_tax=("lost_agr_tax","sum"),
        surcharge_tax=("surcharge_tax","sum"),
    ).reset_index().sort_values(["year","month"])

    # Use ACTUAL per-wager tax from IGB data (not from modelled operators)
    actual_pwt_total = actual["per_wager_tax"].sum()
    fy_lost = by_month["lost_agr_tax"].sum()
    fy_surcharge = by_month["surcharge_tax"].sum()
    fy_net = actual_pwt_total + fy_surcharge - fy_lost

    net_rows.append({
        "spec": spec,
        "fy_pwt": actual_pwt_total,
        "fy_surcharge_tax": fy_surcharge,
        "fy_lost_agr_tax": fy_lost,
        "fy_net": fy_net,
        "net_share": fy_net / actual_pwt_total * 100 if actual_pwt_total > 0 else 0,
    })

net_df = pd.DataFrame(net_rows)

# (5) Efficiency metrics (using linear as central)
linear_fy = fiscal[fiscal["spec"]=="linear"].groupby(["year","month"]).agg(
    per_wager_tax=("per_wager_tax","sum"),
    lost_handle=("lost_handle","sum"),
    surcharge_tax=("surcharge_tax","sum"),
    lost_agr_tax=("lost_agr_tax","sum"),
).reset_index()
linear_total = linear_fy.sum(numeric_only=True)

# Lost wagers: from statewide counterfactual
sw = panel[(panel["sport"]=="All") & (panel["channel"]=="online") & (panel["handle"]>0)].copy()
sw_agg = sw.groupby(["year","month"]).agg(wager_count=("wager_count","sum"), handle=("handle","sum")).reset_index()
sw_agg["date"] = pd.to_datetime(sw_agg[["year","month"]].assign(day=1))
sw_agg = sw_agg.merge(cal, on=["year","month"], how="left")

# Linear counterfactual for wager count
d = sw_agg.copy().sort_values("date")
d["log_wc"] = np.log(d["wager_count"])
d["trend"] = np.arange(len(d))
month_d = pd.get_dummies(d["month"], prefix="m", drop_first=True).astype(float)
cc = [c for c in cal_controls if c in d.columns]
X = pd.concat([month_d.reset_index(drop=True), d[["trend"]].reset_index(drop=True),
                d[cc].reset_index(drop=True)], axis=1)
X = sm.add_constant(X)
y = d["log_wc"].reset_index(drop=True)
train = (d["date"].reset_index(drop=True) >= "2022-01-01") & (d["date"].reset_index(drop=True) <= "2025-06-30")
res = sm.OLS(y[train], X[train]).fit()
d["cf_wc"] = np.exp(res.predict(X).values)
d["lost_wc"] = d["cf_wc"] - d["wager_count"]
fy_lost_wc = d[(d["date"]>="2025-07-01") & (d["date"]<="2026-06-01")]["lost_wc"].sum()

net_rev = linear_total["per_wager_tax"] + linear_total["surcharge_tax"] - linear_total["lost_agr_tax"]
net_per_lost_wager = net_rev / fy_lost_wc if fy_lost_wc > 0 else 0
net_per_lost_handle = net_rev / linear_total["lost_handle"] if linear_total["lost_handle"] > 0 else 0

# Equivalent uniform AGSR rate increase
# What uniform rate increase Δr would raise net_rev on counterfactual base?
# net_rev = Δr × counterfactual_FY_AGR
# counterfactual AGR ≈ counterfactual handle × average hold
fy_actual_agr = actual["agr"].sum()
# Counterfactual AGR from linear spec
cf_fy_handle = fiscal[fiscal["spec"]=="linear"].groupby(["year","month"])["cf_handle"].sum().sum()
actual_fy_handle = fy26.groupby(["year","month"])["handle"].sum().sum()
avg_hold = fy_actual_agr / actual_fy_handle if actual_fy_handle > 0 else 0.08
cf_agr_total = cf_fy_handle * avg_hold
equiv_rate = net_rev / cf_agr_total * 100 if cf_agr_total > 0 else 0

# (6) Concentration
fy_pwt_by_op = fy26.groupby("operator_id")["per_wager_tax"].sum()
total_pwt = fy_pwt_by_op.sum()
fd_dk_share = (fy_pwt_by_op.get("fanduel",0) + fy_pwt_by_op.get("draftkings",0)) / total_pwt * 100

# $0.50 tier share
# FD and DK cross 20M in Sep 2025; from Oct onward they're at $0.50
fy26_monthly = fy26.copy()
fy26_monthly["cum_wc"] = fy26_monthly.groupby("operator_id")["wager_count"].cumsum()
tier_050 = fy26_monthly[fy26_monthly["cum_wc"] >= 20_000_000]
pwt_050 = tier_050["per_wager_tax"].sum()
share_050 = pwt_050 / total_pwt * 100


# ── Write fiscal.md ─────────────────────────────────────────────────────

def fmt_actual():
    lines = ["| Month | Per-wager tax | AGSR tax | Total tax | AGSR |",
             "|---|---|---|---|---|"]
    for _, r in actual.iterrows():
        lines.append(f"| {int(r['year'])}-{int(r['month']):02d} | ${r['per_wager_tax']/1e6:.1f}M | ${r['agr_tax']/1e6:.1f}M | ${r['total_tax']/1e6:.1f}M | ${r['agr']/1e6:.0f}M |")
    totals = actual.sum(numeric_only=True)
    lines.append(f"| **FY2026 total** | **${totals['per_wager_tax']/1e6:.1f}M** | **${totals['agr_tax']/1e6:.1f}M** | **${totals['total_tax']/1e6:.1f}M** | **${totals['agr']/1e6:.0f}M** |")
    return "\n".join(lines)

def fmt_net():
    lines = ["| Specification | Per-wager tax | + Surcharge AGSR tax | − Lost AGSR tax | = Net | Net / PWT |",
             "|---|---|---|---|---|---|"]
    for _, r in net_df.iterrows():
        lines.append(f"| {r['spec']} | ${r['fy_pwt']/1e6:.1f}M | +${r['fy_surcharge_tax']/1e6:.1f}M | −${r['fy_lost_agr_tax']/1e6:.1f}M | **${r['fy_net']/1e6:.1f}M** | {r['net_share']:.0f}% |")
    return "\n".join(lines)


md = f"""# Fiscal analysis: per-wager tax revenue effect

## (1) Actual FY2026 receipts

{fmt_actual()}

Per-wager tax receipts total **${actual['per_wager_tax'].sum()/1e6:.1f}M** for FY2026. AGSR tax receipts total **${actual['agr_tax'].sum()/1e6:.1f}M**. The per-wager tax represents {actual['per_wager_tax'].sum()/actual['total_tax'].sum()*100:.1f}% of total sports wagering tax revenue.

## (2) Counterfactual AGSR tax lost

For each operator-month, we estimate:
- **Lost handle** = counterfactual handle − actual handle (floored at zero)
- **Lost AGSR** = lost handle × operator's pre-treatment average hold (Jul 2024 – Jun 2025)
- **Lost AGSR tax** = lost AGSR × marginal AGSR tax rate, using the progressive schedule (20% up to $30M FY AGR, 25% $30–50M, 30% $50–100M, 35% $100–200M, 40% above $200M) and the operator's actual cumulative FY AGR to locate the tier

Three counterfactual specifications: no-trend (month FEs + calendar controls only), linear trend, and quadratic trend, all trained Jan 2022 – Jun 2025.

## (3) Surcharge income tax

Operators that charge consumer surcharges book that income within AGSR, which is then subject to the progressive AGSR tax. The upper-bound surcharge income = fee × wager count per operator (see prelim_v3 for fee schedule). The AGSR tax on this surcharge income is computed at the operator's marginal rate.

## (4) Net fiscal effect

Net = per-wager tax receipts + AGSR tax on surcharge income − lost AGSR tax from handle decline.

{fmt_net()}

Under the linear-trend specification (central), the per-wager tax generated **${net_df[net_df['spec']=='linear']['fy_net'].iloc[0]/1e6:.1f}M** in net revenue for FY2026 — the per-wager tax receipts (${net_df[net_df['spec']=='linear']['fy_pwt'].iloc[0]/1e6:.0f}M) plus AGSR tax on surcharge income (${net_df[net_df['spec']=='linear']['fy_surcharge_tax'].iloc[0]/1e6:.0f}M), less the AGSR tax revenue lost due to the handle decline (${net_df[net_df['spec']=='linear']['fy_lost_agr_tax'].iloc[0]/1e6:.0f}M). The net is {net_df[net_df['spec']=='linear']['net_share'].iloc[0]:.0f}% of gross per-wager receipts.

## (5) Efficiency metrics

All metrics use the linear-trend counterfactual.

| Metric | Value |
|---|---|
| Net revenue per lost wager | ${net_per_lost_wager:.2f} |
| Net revenue per $1 of lost handle | ${net_per_lost_handle:.4f} |
| FY2026 lost wagers (counterfactual − actual) | {fy_lost_wc/1e6:.0f}M |
| FY2026 lost handle | ${linear_total['lost_handle']/1e9:.1f}B |
| Equivalent uniform AGSR rate increase | {'+' if equiv_rate > 0 else ''}{equiv_rate:.2f} pp |

The equivalent uniform AGSR rate increase is the number of percentage points that would need to be added to every tier of the progressive AGSR schedule to raise the same net FY2026 revenue on the counterfactual handle base, **assuming no behavioural response to the ad valorem change**. This assumption means the comparison overstates the efficiency of the ad valorem alternative: an AGSR rate increase would also reduce handle (via reduced operator marketing, odds adjustments, or market exit), but we do not model that response.

## (6) Concentration

| Metric | Value |
|---|---|
| FanDuel + DraftKings share of per-wager tax | {fd_dk_share:.1f}% |
| $0.50-tier share of per-wager tax | {share_050:.1f}% |

FanDuel and DraftKings account for {fd_dk_share:.0f}% of all per-wager tax receipts. Both operators crossed the 20-million-wager threshold in September 2025 and paid the $0.50 rate for the remaining 9 months of FY2026. The $0.50 tier accounts for {share_050:.0f}% of total per-wager receipts.
"""

(ROOT / "notes/fiscal.md").write_text(md, encoding="utf-8")
print(f"Wrote notes/fiscal.md")
print("Done.")
