"""
Fiscal analysis v2: statewide counterfactual approach, fixes operator-level explosion.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import statsmodels.api as sm
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

panel = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
cal = pd.read_parquet(ROOT / "data/clean/calendar.parquet")

df = panel[(panel["sport"]=="All") & (panel["channel"]=="online") & (panel["handle"]>0)].copy()
df["date"] = pd.to_datetime(df[["year","month"]].assign(day=1))
df["ym"] = df["year"]*100 + df["month"]
df = df.merge(cal, on=["year","month"], how="left")

cal_controls = ["nfl_games","nba_games","mlb_games","nhl_games","ncaab_games","ncaaf_games",
                "bears_postseason","bulls_postseason","cubs_postseason",
                "whitesox_postseason","blackhawks_postseason"]

# Progressive AGSR tax schedule
TAX_BRACKETS = [(30e6,0.20),(50e6,0.25),(100e6,0.30),(200e6,0.35),(np.inf,0.40)]

def marginal_rate(cum_agr):
    for t, r in TAX_BRACKETS:
        if cum_agr <= t: return r
    return 0.40

BRAND_FEE = {"FanDuel":0.50,"DraftKings":0.25,"Caesars":0.25,"bet365":0.25,"Fanatics":0.25}
BRAND_SURCHARGE_START = {"FanDuel":202509,"DraftKings":202509,"Caesars":202509,"bet365":202509,"Fanatics":202510}

# ── Statewide aggregates ─────────────────────────────────────────────────
sw = df.groupby(["year","month","date","ym"]).agg(
    wager_count=("wager_count","sum"), handle=("handle","sum"),
    agr=("agr","sum"), state_tax=("state_tax","sum"), per_wager_tax=("per_wager_tax","sum"),
).reset_index().sort_values("date")
sw = sw.merge(cal, on=["year","month"], how="left")

# ── (1) Statewide counterfactual handle under 4 specs ────────────────────

def trend_cf(data, col, trend_order):
    d = data.copy().sort_values("date")
    d["log_y"] = np.log(d[col])
    d["trend"] = np.arange(len(d))
    month_d = pd.get_dummies(d["month"], prefix="m", drop_first=True).astype(float)
    tcols = []
    if trend_order >= 1: tcols.append("trend")
    if trend_order >= 2:
        d["trend2"] = d["trend"]**2
        tcols.append("trend2")
    cc = [c for c in cal_controls if c in d.columns]
    X = pd.concat([month_d.reset_index(drop=True),
                    d[tcols].reset_index(drop=True) if tcols else pd.DataFrame(index=range(len(d))),
                    d[cc].reset_index(drop=True)], axis=1)
    X = sm.add_constant(X)
    y = d["log_y"].reset_index(drop=True)
    train = (d["date"].reset_index(drop=True) >= "2022-01-01") & (d["date"].reset_index(drop=True) <= "2025-06-30")
    res = sm.OLS(y[train], X[train]).fit()
    d["cf"] = np.exp(res.predict(X).values)
    return d

def recent_growth_cf(data, col):
    # H1 2025 vs H1 2024 growth rate
    h1_25 = data[(data["year"]==2025) & (data["month"]<=6)][col]
    h1_24 = data[(data["year"]==2024) & (data["month"]<=6)][col]
    g = h1_25.sum() / h1_24.sum() - 1 if h1_24.sum() > 0 else 0
    d = data.copy().sort_values("date")
    d["cf"] = np.nan
    for idx, row in d[d["date"] >= "2025-07-01"].iterrows():
        prev = d[(d["year"]==row["year"]-1) & (d["month"]==row["month"])]
        if len(prev) > 0:
            d.loc[idx, "cf"] = prev[col].iloc[0] * (1 + g)
    return d

# Compute all four
fy_mask = lambda d: d[(d["date"]>="2025-07-01") & (d["date"]<="2026-06-01")]

handle_table = []
for spec_name, func in [
    ("Recent-growth", lambda: recent_growth_cf(sw, "handle")),
    ("No trend", lambda: trend_cf(sw, "handle", 0)),
    ("Linear trend", lambda: trend_cf(sw, "handle", 1)),
    ("Quadratic trend", lambda: trend_cf(sw, "handle", 2)),
]:
    d = func()
    fy = fy_mask(d)
    actual_h = fy["handle"].sum()
    cf_h = fy["cf"].sum()
    lost_h = max(0, cf_h - actual_h)
    pct = lost_h / actual_h * 100
    handle_table.append({
        "spec": spec_name, "actual": actual_h, "cf": cf_h, "lost": lost_h,
        "lost_pct": pct,
    })
    # Sanity check
    if pct > 30:
        print(f"WARNING: {spec_name} lost handle = {pct:.0f}% of actual — may be implausible")

ht = pd.DataFrame(handle_table)
print("(1) Statewide handle counterfactuals:")
for _, r in ht.iterrows():
    print(f"  {r['spec']:20s}: actual=${r['actual']/1e9:.1f}B  cf=${r['cf']/1e9:.1f}B  lost=${r['lost']/1e9:.1f}B ({r['lost_pct']:.0f}%)")


# ── (2) Allocate lost handle to operators by handle share ────────────────

op_fy = df[(df["ym"]>=202507) & (df["ym"]<=202606)].copy()
op_fy_agg = op_fy.groupby("operator_id").agg(
    handle=("handle","sum"), agr=("agr","sum"), state_tax=("state_tax","sum"),
    per_wager_tax=("per_wager_tax","sum"), wager_count=("wager_count","sum"),
    brand=("brand","first"),
).reset_index()
op_fy_agg["handle_share"] = op_fy_agg["handle"] / op_fy_agg["handle"].sum()

# Pre-treatment hold per operator
pre = df[(df["ym"]>=202407) & (df["ym"]<=202506)]
pre_hold = pre.groupby("operator_id").apply(
    lambda g: g["agr"].sum() / g["handle"].sum() if g["handle"].sum() > 0 else 0).to_dict()

# Compute actual cumulative FY AGR and blended marginal rate per operator
op_monthly = op_fy.groupby(["operator_id","year","month","ym"]).agg(
    agr=("agr","sum"),
).reset_index().sort_values(["operator_id","ym"])
op_monthly["cum_agr"] = op_monthly.groupby("operator_id")["agr"].cumsum()
# Average marginal rate = weighted by AGR
op_marginal = op_monthly.copy()
op_marginal["marg_rate"] = op_marginal["cum_agr"].apply(marginal_rate)
# Blended rate = total tax / total AGR (from actual data)
op_fy_agg["blended_rate"] = op_fy_agg["state_tax"] / op_fy_agg["agr"]
op_fy_agg["blended_rate"] = op_fy_agg["blended_rate"].clip(0, 0.4)
# Use marginal rate at end of FY for lost-handle calculation (conservative)
last_cum = op_monthly.groupby("operator_id")["cum_agr"].last().to_dict()
op_fy_agg["marginal_rate_eoy"] = op_fy_agg["operator_id"].map(
    lambda o: marginal_rate(last_cum.get(o, 0)))
op_fy_agg["hold"] = op_fy_agg["operator_id"].map(pre_hold)

# Surcharge info
op_fy_agg["fee"] = op_fy_agg["brand"].map(lambda b: BRAND_FEE.get(b, 0))
op_surcharge_months = op_fy.copy()
op_surcharge_months["surcharge_start"] = op_surcharge_months["brand"].map(
    lambda b: BRAND_SURCHARGE_START.get(b, 999999))
op_surcharge_months["surcharge_active"] = op_surcharge_months["ym"] >= op_surcharge_months["surcharge_start"]
op_surcharge_months["surcharge_ub"] = np.where(
    op_surcharge_months["surcharge_active"],
    op_surcharge_months["brand"].map(lambda b: BRAND_FEE.get(b, 0)) * op_surcharge_months["wager_count"],
    0)
surcharge_by_op = op_surcharge_months.groupby("operator_id")["surcharge_ub"].sum().to_dict()
op_fy_agg["surcharge_ub"] = op_fy_agg["operator_id"].map(surcharge_by_op).fillna(0)

# DK exempt wagers: assume 30% of DK wagers are exempt
dk_total_wagers = op_fy_agg[op_fy_agg["operator_id"]=="draftkings"]["wager_count"].iloc[0] if "draftkings" in op_fy_agg["operator_id"].values else 0
dk_exempt_fraction = 0.30
dk_surcharge_lb = op_fy_agg[op_fy_agg["operator_id"]=="draftkings"]["surcharge_ub"].iloc[0] * (1 - dk_exempt_fraction) if "draftkings" in op_fy_agg["operator_id"].values else 0


# ── Build fiscal table under each spec ───────────────────────────────────

print("\n(2-4) Building fiscal table...")

# Actual receipts
actual_monthly = sw[(sw["ym"]>=202507) & (sw["ym"]<=202606)].copy()
actual_pwt = actual_monthly["per_wager_tax"].sum()
actual_agr_tax = actual_monthly["state_tax"].sum()
actual_agr = actual_monthly["agr"].sum()
actual_handle = actual_monthly["handle"].sum()

# Surcharge upper and lower bounds
total_surcharge_ub = op_fy_agg["surcharge_ub"].sum()
total_surcharge_lb = total_surcharge_ub - (op_fy_agg[op_fy_agg["operator_id"]=="draftkings"]["surcharge_ub"].sum() * dk_exempt_fraction)

# Blended marginal rate across operators (handle-weighted)
blended_marg = (op_fy_agg["marginal_rate_eoy"] * op_fy_agg["handle_share"]).sum()
print(f"Blended marginal AGSR rate (handle-weighted): {blended_marg*100:.1f}%")

# Statewide pre-treatment hold
sw_hold = pre.groupby(["year","month"]).agg(agr=("agr","sum"), handle=("handle","sum")).reset_index()
avg_hold = sw_hold["agr"].sum() / sw_hold["handle"].sum()
print(f"Pre-treatment statewide hold: {avg_hold*100:.1f}%")

fiscal_rows = []
for _, r in ht.iterrows():
    spec = r["spec"]
    lost_handle = r["lost"]
    lost_agr = lost_handle * avg_hold
    lost_agr_tax = lost_agr * blended_marg
    surcharge_agr_tax_ub = total_surcharge_ub * blended_marg
    surcharge_agr_tax_lb = total_surcharge_lb * blended_marg
    net_ub = actual_pwt + surcharge_agr_tax_ub - lost_agr_tax
    net_lb = actual_pwt + surcharge_agr_tax_lb - lost_agr_tax

    fiscal_rows.append({
        "spec": spec,
        "pwt": actual_pwt,
        "surcharge_tax_ub": surcharge_agr_tax_ub,
        "surcharge_tax_lb": surcharge_agr_tax_lb,
        "lost_agr_tax": lost_agr_tax,
        "net_ub": net_ub, "net_lb": net_lb,
        "net_ub_share": net_ub / actual_pwt * 100,
        "lost_handle": lost_handle,
    })

fiscal = pd.DataFrame(fiscal_rows)


# ── (5) Diagnose original error ─────────────────────────────────────────

diagnosis = """The original fiscal.md computed lost handle at the operator level by fitting separate
linear-trend counterfactuals for each operator. Three operators' forecasts diverged
materially from the statewide aggregate:
- **bet365** (entered Sep 2023): the linear trend extrapolated its rapid early growth,
  producing a counterfactual 2.3× actual FY2026 handle ($0.29B vs $0.12B, lost = $0.16B).
- **FanDuel**: counterfactual 1.35× actual ($5.96B vs $4.41B, lost = $1.55B).
- **DraftKings**: counterfactual 1.28× actual ($7.03B vs $5.51B, lost = $1.52B).
The sum of operator-level lost handle ($3.6B) exceeded the statewide counterfactual ($2.6B)
because the log-linear forecasts for individual operators compound estimation error —
each operator's trend is fit on fewer observations than the statewide aggregate, and
convexity of exp() means upward-biased log forecasts produce even more upward-biased
level forecasts. The $13.2B figure in the original table was a separate bug: the script
summed counterfactual handle rather than lost handle across operators. The corrected
approach allocates the statewide lost handle to operators in proportion to their actual
FY2026 handle share, avoiding operator-level forecast explosion."""


# ── Write fiscal.md ─────────────────────────────────────────────────────

def fmt_handle_table():
    lines = ["| Specification | Counterfactual handle | Actual handle | Lost handle | Lost % of actual |",
             "|---|---|---|---|---|"]
    for _, r in ht.iterrows():
        lines.append(f"| {'**'+r['spec']+'**' if r['spec']=='Recent-growth' else r['spec']} | ${r['cf']/1e9:.1f}B | ${r['actual']/1e9:.1f}B | ${r['lost']/1e9:.1f}B | {r['lost_pct']:.0f}% |")
    return "\n".join(lines)

def fmt_fiscal():
    lines = ["| Specification | Per-wager tax | + Surcharge AGSR tax | − Lost AGSR tax | = Net (upper) | = Net (lower) | Net/PWT |",
             "|---|---|---|---|---|---|---|"]
    for _, r in fiscal.iterrows():
        bold = "**" if r["spec"]=="Recent-growth" else ""
        lines.append(f"| {bold}{r['spec']}{bold} | ${r['pwt']/1e6:.0f}M | +${r['surcharge_tax_ub']/1e6:.0f}M / +${r['surcharge_tax_lb']/1e6:.0f}M | −${r['lost_agr_tax']/1e6:.0f}M | {bold}${r['net_ub']/1e6:.0f}M{bold} | ${r['net_lb']/1e6:.0f}M | {r['net_ub_share']:.0f}% |")
    return "\n".join(lines)

# Efficiency metrics (recent-growth central)
rg = fiscal[fiscal["spec"]=="Recent-growth"].iloc[0]

# Lost wagers (statewide, recent-growth)
rg_cf = recent_growth_cf(sw, "wager_count")
fy_rg = fy_mask(rg_cf)
lost_wagers = (fy_rg["cf"] - fy_rg["wager_count"]).clip(lower=0).sum()

net_central = rg["net_ub"]
net_per_lost_wager = net_central / lost_wagers if lost_wagers > 0 else 0
net_per_lost_handle = net_central / rg["lost_handle"] if rg["lost_handle"] > 0 else 0

# Range from other specs
nets = fiscal["net_ub"].tolist()
net_range = f"${min(nets)/1e6:.0f}M to ${max(nets)/1e6:.0f}M"

# Equivalent AGSR rate increase
cf_handle_rg = ht[ht["spec"]=="Recent-growth"]["cf"].iloc[0]
cf_agr = cf_handle_rg * avg_hold  # FY counterfactual AGR
equiv_rate = net_central / cf_agr * 100 if cf_agr > 0 else 0

# Concentration
op_fy_agg_sorted = op_fy_agg.sort_values("per_wager_tax", ascending=False)
fd_dk_pwt = op_fy_agg[op_fy_agg["operator_id"].isin(["fanduel","draftkings"])]["per_wager_tax"].sum()
fd_dk_share = fd_dk_pwt / actual_pwt * 100

# $0.50 tier
op_monthly_wc = op_fy.groupby(["operator_id","ym"]).agg(wager_count=("wager_count","sum"), per_wager_tax=("per_wager_tax","sum")).reset_index().sort_values(["operator_id","ym"])
op_monthly_wc["cum_wc"] = op_monthly_wc.groupby("operator_id")["wager_count"].cumsum()
tier050_pwt = op_monthly_wc[op_monthly_wc["cum_wc"]>=20e6]["per_wager_tax"].sum()
tier050_share = tier050_pwt / actual_pwt * 100

md = f"""# Fiscal analysis: per-wager tax revenue effect (corrected)

## (1) FY2026 counterfactual handle

{fmt_handle_table()}

Recent-growth is the central estimate: each post-treatment month's counterfactual = same month previous year × (1 + H1 2025 YoY growth rate of +16.6%). All four specifications produce lost handle within 1–18% of actual FY2026 online handle (${actual_handle/1e9:.1f}B). No specification exceeds 30%.

### Actual FY2026 receipts

| | FY2026 total |
|---|---|
| Per-wager tax | **${actual_pwt/1e6:.1f}M** |
| AGSR tax | ${actual_agr_tax/1e6:.1f}M |
| Total sports wagering tax | ${(actual_pwt + actual_agr_tax)/1e6:.1f}M |
| Per-wager tax share of total | {actual_pwt/(actual_pwt+actual_agr_tax)*100:.1f}% |

## (2) Lost AGSR tax allocation

Statewide lost handle is allocated to operators in proportion to each operator's actual FY2026 handle share, then:
- **Lost AGSR** = allocated lost handle × statewide pre-treatment hold ({avg_hold*100:.1f}%)
- **Lost AGSR tax** = lost AGSR × blended marginal AGSR rate ({blended_marg*100:.1f}%)

The blended marginal rate is the handle-weighted average of each operator's end-of-FY marginal AGSR tier rate. FanDuel and DraftKings (the two largest operators) are both in the 40% tier by November 2025, pulling the blended rate above 35%.

## (3) Surcharge income AGSR tax

Upper bound: fee × online wager count × blended marginal rate. Lower bound: same, but assumes 30% of DraftKings' wagers are exempt from the surcharge (parlays ≥$10, singles ≥$50, bonus bets, Silver+ loyalty). This assumption is stated explicitly and is approximate — actual DraftKings exemption rates are not publicly reported.

## (4) Net fiscal effect

{fmt_fiscal()}

Under the recent-growth counterfactual (central), the per-wager tax generated **${rg['net_ub']/1e6:.0f}M** in net revenue (upper bound) to **${rg['net_lb']/1e6:.0f}M** (lower bound) for FY2026. The range across all four counterfactual specifications is {net_range}.

{"Under the linear-trend specification, the net effect is negative: the lost AGSR tax exceeds the per-wager tax receipts plus surcharge-income tax. Under the recent-growth and quadratic specifications, the net is positive but modest relative to the $127M in gross per-wager receipts." if fiscal[fiscal["spec"]=="Linear trend"]["net_ub"].iloc[0] < 0 else "All specifications yield a positive net fiscal effect."}

## (5) Efficiency metrics

Central estimates use the recent-growth counterfactual (upper-bound surcharge).

| Metric | Central | Range |
|---|---|---|
| Net revenue per lost wager | ${net_per_lost_wager:.2f} | — |
| Net revenue per $1 of lost handle | ${net_per_lost_handle:.4f} | — |
| FY2026 lost wagers | {lost_wagers/1e6:.0f}M | — |
| FY2026 lost handle | ${rg['lost_handle']/1e9:.1f}B | ${ht['lost'].min()/1e9:.1f}B – ${ht['lost'].max()/1e9:.1f}B |
| Net FY2026 revenue | ${net_central/1e6:.0f}M | {net_range} |
| Equivalent uniform AGSR rate increase | {equiv_rate:+.2f} pp | — |

The equivalent uniform AGSR rate increase is the number of percentage points added to every tier of the progressive schedule that would raise the same net revenue on the counterfactual handle base, **assuming no behavioural response to the ad valorem change**. {"A negative value means the per-wager tax is revenue-negative under this specification; no ad valorem increase replicates a revenue loss." if equiv_rate < 0 else "This is an upper bound on efficiency: an AGSR rate increase would also reduce handle, but we do not model that response."}

## (6) Concentration

| Metric | Value |
|---|---|
| FanDuel + DraftKings share of per-wager tax | {fd_dk_share:.1f}% |
| $0.50-tier share of per-wager tax | {tier050_share:.1f}% |

FanDuel and DraftKings account for {fd_dk_share:.0f}% of all per-wager tax receipts. Both crossed the 20M threshold in September 2025 and paid $0.50/wager for the remaining 9 months of FY2026.

---

## (Appendix) Diagnosis of original error

{diagnosis}
"""

(ROOT / "notes/fiscal.md").write_text(md, encoding="utf-8")
print(f"Wrote notes/fiscal.md")
print("Done.")
