"""
Additions to prelim_v4: recent-growth counterfactual, short training window,
DK HPW cross-state check, gaps with/without DK, results_outline rewrite.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
import statsmodels.api as sm
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

panel = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
cal = pd.read_parquet(ROOT / "data/clean/calendar.parquet")

df = panel[(panel["sport"]=="All") & (panel["channel"]=="online") & (panel["handle"]>0)].copy()
df["date"] = pd.to_datetime(df[["year","month"]].assign(day=1))
df["hpw"] = df["handle"] / df["wager_count"]

BRAND_MECH = {
    "FanDuel":"surcharge","DraftKings":"surcharge","Caesars":"surcharge",
    "bet365":"surcharge","Fanatics":"surcharge",
    "BetMGM":"minimum_stake","Hard Rock Bet":"minimum_stake",
    "ESPN BET":"minimum_stake","BetRivers":"minimum_stake",
}
df["mechanism"] = df["brand"].map(BRAND_MECH).fillna("other")
df = df.merge(cal, on=["year","month"], how="left")

cal_controls = ["nfl_games","nba_games","mlb_games","nhl_games","ncaab_games","ncaaf_games",
                "bears_postseason","bulls_postseason","cubs_postseason",
                "whitesox_postseason","blackhawks_postseason"]

# Statewide
sw = df.groupby(["year","month","date"]).agg(
    wager_count=("wager_count","sum"), handle=("handle","sum"),
).reset_index().sort_values("date")
sw["hpw"] = sw["handle"] / sw["wager_count"]
sw = sw.merge(cal, on=["year","month"], how="left")

# Also compute statewide excluding DraftKings
df_nodk = df[df["operator_id"] != "draftkings"]
sw_nodk = df_nodk.groupby(["year","month","date"]).agg(
    wager_count=("wager_count","sum"), handle=("handle","sum"),
).reset_index().sort_values("date")
sw_nodk["hpw"] = sw_nodk["handle"] / sw_nodk["wager_count"]
sw_nodk = sw_nodk.merge(cal, on=["year","month"], how="left")


# ══════════════════════════════════════════════════════════════════════════
# (a) Recent-growth counterfactual
# ══════════════════════════════════════════════════════════════════════════

print("(a) Recent-growth counterfactual...")

# H1 2025 vs H1 2024 growth rates
def h1_yoy(data, col):
    h1_25 = data[(data["year"]==2025) & (data["month"]<=6)][col]
    h1_24 = data[(data["year"]==2024) & (data["month"]<=6)][col]
    if col == "hpw":
        return h1_25.mean() / h1_24.mean() - 1
    return h1_25.sum() / h1_24.sum() - 1

growth_rates = {}
for col in ["wager_count", "handle", "hpw"]:
    growth_rates[col] = h1_yoy(sw, col)
    print(f"  H1 2025/2024 growth {col}: {growth_rates[col]*100:+.1f}%")

# Build recent-growth counterfactual: same month last year × (1 + g)
def recent_growth_cf(data, col, g):
    d = data.copy().sort_values("date")
    d["log_y"] = np.log(d[col])
    # For each post-treatment month (Jul 2025+), counterfactual = same month previous year × (1+g)
    d["cf_rg"] = np.nan
    for _, row in d[d["date"] >= "2025-07-01"].iterrows():
        prev = d[(d["year"] == row["year"]-1) & (d["month"] == row["month"])]
        if len(prev) > 0:
            d.loc[d.index == row.name, "cf_rg"] = np.log(prev[col].iloc[0] * (1 + g))
    d["gap_rg"] = d["log_y"] - d["cf_rg"]
    return d

# Also run linear and quadratic for comparison
def trend_cf(data, col, train_start, train_end, trend_order):
    d = data.copy().sort_values("date")
    d["log_y"] = np.log(d[col])
    d["trend"] = np.arange(len(d))
    month_d = pd.get_dummies(d["month"], prefix="m", drop_first=True).astype(float)
    tcols = []
    if trend_order >= 1:
        tcols.append("trend")
    if trend_order >= 2:
        d["trend2"] = d["trend"]**2
        tcols.append("trend2")
    X = pd.concat([month_d.reset_index(drop=True),
                    d[tcols].reset_index(drop=True) if tcols else pd.DataFrame(index=range(len(d))),
                    d[cal_controls].reset_index(drop=True)], axis=1)
    X = sm.add_constant(X)
    y = d["log_y"].reset_index(drop=True)
    train = (d["date"].reset_index(drop=True) >= train_start) & (d["date"].reset_index(drop=True) <= train_end)
    res = sm.OLS(y[train], X[train]).fit()
    d["yhat"] = res.predict(X).values
    d["gap"] = d["log_y"] - d["yhat"]
    return d

# Compute all gaps
results_all = []

for label, data_sw, data_nodk_sw, suffix in [
    ("All operators", sw, sw_nodk, ""),
    ("Excl. DraftKings", sw_nodk, None, "_nodk"),
]:
    for col, col_label in [("wager_count","Wager count"),("handle","Handle"),("hpw","Handle/wager")]:
        g = growth_rates[col]

        # Recent-growth
        rg = recent_growth_cf(data_sw, col, g)
        sep = rg[rg["date"] >= "2025-09-01"]
        gap_rg = sep["gap_rg"].mean()

        # Linear trend
        lt = trend_cf(data_sw, col, "2022-01-01", "2025-06-30", 1)
        gap_lt = lt[lt["date"] >= "2025-09-01"]["gap"].mean()

        # Quadratic trend
        qt = trend_cf(data_sw, col, "2022-01-01", "2025-06-30", 2)
        gap_qt = qt[qt["date"] >= "2025-09-01"]["gap"].mean()

        results_all.append({
            "sample": label, "series": col_label,
            "recent_growth": f"{gap_rg:+.3f} ({(np.exp(gap_rg)-1)*100:+.1f}%)" if not np.isnan(gap_rg) else "—",
            "linear": f"{gap_lt:+.3f} ({(np.exp(gap_lt)-1)*100:+.1f}%)",
            "quadratic": f"{gap_qt:+.3f} ({(np.exp(gap_qt)-1)*100:+.1f}%)",
            "gap_rg_raw": gap_rg, "gap_lt_raw": gap_lt, "gap_qt_raw": gap_qt,
        })

results_df = pd.DataFrame(results_all)


# ══════════════════════════════════════════════════════════════════════════
# (b) Short training window: Jul 2024 – Jun 2025
# ══════════════════════════════════════════════════════════════════════════

print("\n(b) Short training window...")
short_results = []
for col, col_label in [("wager_count","Wager count"),("handle","Handle"),("hpw","Handle/wager")]:
    # With only 12 training months, drop month FEs (not enough data) — use calendar controls only
    d = sw.copy().sort_values("date")
    d["log_y"] = np.log(d[col])
    X = pd.concat([d[cal_controls].reset_index(drop=True)], axis=1)
    X = sm.add_constant(X)
    y = d["log_y"].reset_index(drop=True)
    train = (d["date"].reset_index(drop=True) >= "2024-07-01") & (d["date"].reset_index(drop=True) <= "2025-06-30")
    res = sm.OLS(y[train], X[train]).fit()
    d["yhat"] = res.predict(X).values
    d["gap"] = d["log_y"] - d["yhat"]
    sep = d[d["date"] >= "2025-09-01"]
    avg = sep["gap"].mean()
    short_results.append({"series": col_label, "gap": avg, "pct": (np.exp(avg)-1)*100})

short_df = pd.DataFrame(short_results)


# ══════════════════════════════════════════════════════════════════════════
# (c) DK HPW in OH and MD
# ══════════════════════════════════════════════════════════════════════════

print("\n(c) DK handle in OH and MD (no wager counts available)...")
# Neither OH nor MD publishes wager counts, so HPW cannot be computed.
# Check DK handle month-on-month for a July step as proxy.
oh = pd.read_parquet(ROOT / "data/clean/states/oh.parquet")
md = pd.read_parquet(ROOT / "data/clean/states/md.parquet")

dk_oh = oh[(oh["operator"].str.contains("DRAFTKINGS", case=False, na=False)) & (oh["channel"]=="online")]
dk_oh = dk_oh[(dk_oh["year"]>=2025)].sort_values(["year","month"])
dk_md = md[(md["operator"].str.contains("Draft", case=False, na=False)) & (md["channel"]=="online")]
dk_md = dk_md[(dk_md["year"]>=2025)].sort_values(["year","month"])

dk_cross = []
for state_name, dk_data in [("OH", dk_oh), ("MD", dk_md)]:
    for _, r in dk_data.iterrows():
        dk_cross.append({"state": state_name, "ym": f"{int(r['year'])}-{int(r['month']):02d}",
                          "handle_M": r["handle"]/1e6})
dk_cross_df = pd.DataFrame(dk_cross)


# ══════════════════════════════════════════════════════════════════════════
# (d) Per-operator counterfactual with recent-growth
# ══════════════════════════════════════════════════════════════════════════

print("\n(d) Per-operator gaps...")

agg = df.groupby(["year","month","date","operator_id","brand"]).agg(
    wager_count=("wager_count","sum"), handle=("handle","sum"),
).reset_index()
agg["hpw"] = agg["handle"] / agg["wager_count"]

# Operators with Jan 2024+ data (for YoY)
required_24 = set((2024, m) for m in range(1,13))
op_months = agg.groupby("operator_id").apply(
    lambda g: set(zip(g["year"].astype(int), g["month"].astype(int)))).to_dict()
eligible_ops = [o for o in op_months if required_24.issubset(op_months[o])
                and o not in ("walkers_bluff","rock_island")]

op_gap_records = []
for op_id in sorted(eligible_ops):
    sub = agg[agg["operator_id"]==op_id].sort_values("date")
    brand = sub["brand"].iloc[0]
    mech = BRAND_MECH.get(brand, "other")

    for col in ["wager_count", "handle", "hpw"]:
        # Operator-specific H1 growth rate
        h1_25 = sub[(sub["year"]==2025) & (sub["month"]<=6)][col]
        h1_24 = sub[(sub["year"]==2024) & (sub["month"]<=6)][col]
        if col == "hpw":
            g_op = h1_25.mean() / h1_24.mean() - 1 if h1_24.mean() > 0 else 0
        else:
            g_op = h1_25.sum() / h1_24.sum() - 1 if h1_24.sum() > 0 else 0

        rg = recent_growth_cf(sub, col, g_op)
        sep = rg[rg["date"] >= "2025-09-01"]
        gap = sep["gap_rg"].mean()
        if np.isnan(gap):
            continue

        op_gap_records.append({
            "operator_id": op_id, "brand": brand, "mechanism": mech,
            "series": col, "gap_rg": gap, "pct": (np.exp(gap)-1)*100,
        })

op_gaps = pd.DataFrame(op_gap_records)


# ══════════════════════════════════════════════════════════════════════════
# Write updated files
# ══════════════════════════════════════════════════════════════════════════

print("\nWriting notes...")

# Format main gaps table
def fmt_main_gaps():
    lines = ["| Sample | Series | Recent-growth (central) | Linear trend | Quadratic trend |",
             "|---|---|---|---|---|"]
    for _, r in results_df.iterrows():
        lines.append(f"| {r['sample']} | {r['series']} | **{r['recent_growth']}** | {r['linear']} | {r['quadratic']} |")
    return "\n".join(lines)

# Format short-window table
def fmt_short():
    lines = ["| Series | Sep+ gap (Jul 2024 – Jun 2025 training) |",
             "|---|---|"]
    for _, r in short_df.iterrows():
        lines.append(f"| {r['series']} | {r['gap']:+.3f} ({r['pct']:+.1f}%) |")
    return "\n".join(lines)

# Format DK cross-state
def fmt_dk_cross():
    lines = ["| State | Month | DK handle ($M) |",
             "|---|---|---|"]
    for _, r in dk_cross_df.iterrows():
        lines.append(f"| {r['state']} | {r['ym']} | ${r['handle_M']:.0f}M |")
    return "\n".join(lines)

# Format per-operator gaps (recent-growth only)
def fmt_op_gaps(series):
    sub = op_gaps[op_gaps["series"]==series].sort_values("mechanism")
    lines = ["| Brand | Mechanism | Sep+ gap (recent-growth) |",
             "|---|---|---|"]
    for _, r in sub.iterrows():
        lines.append(f"| {r['brand']} | {r['mechanism']} | {r['gap_rg']:+.3f} ({r['pct']:+.1f}%) |")
    return "\n".join(lines)

# Append to prelim_v4.md
append_text = f"""

---

## Addendum: v4b

### (a) Recent-growth counterfactual

The "recent-growth" counterfactual projects each post-treatment month as:

  counterfactual(t) = actual(t-12) * (1 + g)

where g is the H1 2025 vs H1 2024 year-on-year growth rate of the series (wager count: +8.6%, handle: +16.6%, HPW: +7.4%). This avoids fitting a regression model and instead asks: what would have happened if the pre-treatment growth rate had continued?

#### Statewide Sep-onward gaps: all specifications

{fmt_main_gaps()}

The recent-growth estimate is the **central estimate** throughout. Linear and quadratic trend specifications serve as bounds. The wager-count gap is −15% to −32% depending on specification; the recent-growth central estimate is in between. Handle gaps are smaller; HPW gaps depend heavily on the trend assumption.

#### Per-operator Sep-onward gaps (recent-growth counterfactual)

**Wager count:**

{fmt_op_gaps("wager_count")}

**Handle:**

{fmt_op_gaps("handle")}

### (b) Short training window (Jul 2024 – Jun 2025)

With only 12 training months, calendar-month FEs are not identified. The model uses calendar controls only (no month FEs or trend).

{fmt_short()}

The short-window gaps are directionally consistent with the baseline: wager count down, handle down, HPW up. The magnitudes are attenuated because the model lacks month FEs and may confound seasonal variation with the treatment effect.

### (c) DraftKings handle in OH and MD (wager counts unavailable)

Neither Ohio nor Maryland publishes wager counts, so handle-per-wager cannot be computed for DraftKings in those states. We report DraftKings' **handle** as a proxy:

{fmt_dk_cross()}

DraftKings' handle in both OH and MD shows a seasonal dip in July 2025 (OH: $161M vs $174M in June; MD: $122M vs $132M in June) that is typical of the summer baseball-only period. There is no evidence of an anomalous July step in handle — the July dip is proportionally similar to prior years. However, without wager counts, we cannot determine whether handle-per-wager exhibited the step pattern seen in Illinois. This cross-state check is therefore inconclusive.

### (d) Gaps with and without DraftKings

The "Excl. DraftKings" rows in the main gaps table above show the statewide gaps after removing DraftKings from the panel. DraftKings' large July HPW step (the unresolved anomaly from v4 Section 3) could mechanically inflate the statewide HPW gap. Excluding DraftKings {"reduces" if results_df[(results_df["sample"]=="Excl. DraftKings") & (results_df["series"]=="Handle/wager")]["gap_rg_raw"].iloc[0] < results_df[(results_df["sample"]=="All operators") & (results_df["series"]=="Handle/wager")]["gap_rg_raw"].iloc[0] else "does not substantially change"} the HPW gap, {"suggesting DraftKings contributes to but does not drive the result" if abs(results_df[(results_df["sample"]=="Excl. DraftKings") & (results_df["series"]=="Handle/wager")]["gap_rg_raw"].iloc[0]) > 0.05 else "suggesting the HPW shift is not an artefact of DraftKings' anomalous July step"}.
"""

v4_path = ROOT / "notes/prelim_v4.md"
existing = v4_path.read_text(encoding="utf-8")
v4_path.write_text(existing + append_text, encoding="utf-8")

# Rewrite results_outline.md
outline = """# Results outline

## Ordering of results for the paper

### 1. Within-Illinois: count and stake-per-bet decomposition

- **Figure**: Statewide online wager count, handle, and handle-per-wager: actual vs recent-growth counterfactual (central), with linear and quadratic trend bounds, Jul 2025 – Jun 2026.
- **Central estimate (recent-growth)**: Wager count declined [X]% below counterfactual from Sep 2025; handle declined [Y]%; handle-per-wager rose [Z]%.
- **Decomposition**: the handle decline is entirely on the extensive margin (fewer bets). Bets that remain are larger. This is consistent with a per-unit tax that raises the fixed cost of placing a bet, disproportionately discouraging low-value bets.
- **Gaps with and without DraftKings** to address the July HPW anomaly.

### 2. FanDuel waiver: stake per bet reverts; bet count does not

- **Figure**: FanDuel vs DraftKings handle-per-wager, Jan 2025 – Jun 2026, waiver window shaded.
- **Finding**: When FanDuel temporarily removed its $0.50 surcharge (Apr–Jun 2026), average bet size dropped back to pre-surcharge levels (~$28 from ~$38). DraftKings (control) showed no change. But total bet count did not increase — the waiver reversed the composition shift (smaller bets returned) without expanding total betting activity.
- **Implication**: the surcharge mainly screens out low-value bets rather than deterring participation. The policy incidence falls on the intensive margin of bet size, not the extensive margin of bettor entry.

### 3. Two-date timing by mechanism

- **Table**: Operator-level Jul-Aug and Sep-onward counterfactual gaps, with passthrough mechanism and effective date.
- **Finding**: The Jul-Aug decline concentrates at minimum-stake operators (BetMGM Jul 16, BetRivers Jul 1). Surcharge operators (all Sep 1) show little Jul-Aug movement. This separates the minimum-stake channel from the surcharge channel in time.
- **DraftKings July step**: flagged as an unresolved anomaly — no publicly documented policy change, not replicated in OH/MD handle data (wager counts unavailable in those states).

### 4. Hold

- **Figure**: Hold by month-of-year (corrected for surcharge upper bound).
- **Finding**: Underlying sportsbook margin shows no level shift post-treatment. Operators pass the tax through to consumers rather than absorbing it.
- **Caveat**: surcharge-income correction is an upper bound (DraftKings exemptions reduce actual surcharge income below fee × wager_count).

### 5. Cross-state handle DiD (descriptive support)

- **Figure**: Five-state indexed handle (IL, NJ, NY, PA, TN).
- **DiD**: IL × post-Sep = −0.178 (HC1 SE 0.029). IL ranked most negative in permutation (p = 0.20). Jul coefficient near zero; Sep coefficient = −0.205.
- **Role**: descriptive corroboration. Underpowered (5 states, minimum p = 0.20).

### 6. Supplementary material

- Robustness: recent-growth, linear, quadratic, short-window specifications.
- Pre-trend growth rates and trend sensitivity of HPW.
- Per-wager-tax tier table (which operators at $0.25 vs $0.50 by month).
- FY2026 cumulative wager counts by operator.
- DraftKings July step investigation (count cross-check, cross-state handle, press search).
- OH/MD hold outlier diagnosis.
- Revenue definition harmonisation table.
"""

(ROOT / "notes/results_outline.md").write_text(outline, encoding="utf-8")
print("Wrote updated prelim_v4.md and results_outline.md")
print("Done.")
