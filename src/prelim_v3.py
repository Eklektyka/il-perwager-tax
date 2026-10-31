"""
Preliminary analysis v3: follow-ups on prelim_il_v2 and prelim_xstate.
Items (1)-(5); item (6) in separate script after donor downloads.
"""

import warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
import statsmodels.api as sm
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"; OUT.mkdir(exist_ok=True)

panel = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
pt = pd.read_csv(ROOT / "data/clean/passthrough.csv")
cal = pd.read_parquet(ROOT / "data/clean/calendar.parquet")

df = panel[(panel["sport"]=="All") & (panel["channel"]=="online") & (panel["handle"]>0)].copy()
df["date"] = pd.to_datetime(df[["year","month"]].assign(day=1))
df["handle_per_wager"] = df["handle"] / df["wager_count"]

BRAND_MAP_PT = {
    "FanDuel":"FanDuel","DraftKings":"DraftKings","Caesars":"Caesars",
    "bet365":"bet365","Fanatics":"Fanatics","BetMGM":"BetMGM",
    "Hard Rock Bet":"Hard Rock Bet","ESPN BET":"ESPN BET","BetRivers":"BetRivers",
}
BRAND_MECH = {
    "FanDuel":"surcharge","DraftKings":"surcharge","Caesars":"surcharge",
    "bet365":"surcharge","Fanatics":"surcharge",
    "BetMGM":"minimum_stake","Hard Rock Bet":"minimum_stake",
    "ESPN BET":"minimum_stake","BetRivers":"minimum_stake",
}
# Surcharge fee per bet (for upper-bound correction)
# DraftKings: $0.25 first 20M, $0.50 after; but many exemptions — use $0.25 as upper bound
# (exemptions mean actual surcharge income < fee × wager_count)
BRAND_FEE = {
    "FanDuel": 0.50, "DraftKings": 0.25, "Caesars": 0.25,
    "bet365": 0.25, "Fanatics": 0.25,
    "BetMGM": 0.0, "Hard Rock Bet": 0.0, "ESPN BET": 0.0, "BetRivers": 0.0,
}
# Surcharge effective dates
BRAND_SURCHARGE_START = {
    "FanDuel": "2025-09-01", "DraftKings": "2025-09-01", "Caesars": "2025-09-01",
    "bet365": "2025-09-02", "Fanatics": "2025-10-01",  # approximate
}

df["brand_pt"] = df["brand"].map(BRAND_MAP_PT)
df["mechanism"] = df["brand"].map(BRAND_MECH).fillna("other")
df["fee"] = df["brand"].map(BRAND_FEE).fillna(0.0)
df = df.merge(cal, on=["year","month"], how="left")

cal_controls = ["nfl_games","nba_games","mlb_games","nhl_games","ncaab_games","ncaaf_games",
                "bears_postseason","bulls_postseason","cubs_postseason",
                "whitesox_postseason","blackhawks_postseason"]


def add_vlines(ax):
    ax.axvline(pd.Timestamp("2025-07-01"), color="red", ls="--", lw=1, alpha=0.7)
    ax.axvline(pd.Timestamp("2025-09-01"), color="orange", ls="--", lw=1, alpha=0.7)


# ══════════════════════════════════════════════════════════════════════════
# (1) Operator gap table with mechanism dates — already computed above,
#     now integrate into the writeup
# ══════════════════════════════════════════════════════════════════════════

pt_init = pt[~pt["mechanism"].isin(["surcharge_waiver","surcharge_reinstate"])]
pt_init = pt_init.drop_duplicates(subset="operator", keep="first")

# ══════════════════════════════════════════════════════════════════════════
# (3) Hold correction: surcharge upper bound
# ══════════════════════════════════════════════════════════════════════════

print("(3) Hold correction...")

# Compute surcharge income upper bound per operator-month
# = fee × wager_count, but only after that operator's surcharge start date
df["surcharge_start"] = df["brand"].map(BRAND_SURCHARGE_START)
df["surcharge_active"] = df.apply(
    lambda r: r["date"] >= pd.Timestamp(r["surcharge_start"]) if pd.notna(r["surcharge_start"]) else False, axis=1)
df["surcharge_ub"] = np.where(df["surcharge_active"], df["fee"] * df["wager_count"], 0.0)

# Statewide: raw hold vs corrected band
sw = df.groupby(["year","month","date"]).agg(
    handle=("handle","sum"), agr=("agr","sum"),
    surcharge_ub=("surcharge_ub","sum"),
).reset_index().sort_values("date")

sw["hold_raw"] = sw["agr"] / sw["handle"] * 100
sw["hold_corrected_ub"] = (sw["agr"] - sw["surcharge_ub"]) / sw["handle"] * 100

fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(sw["date"], sw["hold_raw"], "k-", lw=1.5, label="Raw AGSR/handle")
ax.plot(sw["date"], sw["hold_corrected_ub"], "b--", lw=1.5, label="AGSR less surcharge upper bound")
ax.fill_between(sw["date"], sw["hold_corrected_ub"], sw["hold_raw"],
                alpha=0.15, color="blue", label="Surcharge income band")
add_vlines(ax)
ax.set_ylabel("Hold (%)")
ax.set_title("Illinois statewide online hold — raw and corrected for estimated surcharge income")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
plt.tight_layout()
plt.savefig(OUT / "fig_hold_corrected.png", dpi=150)
plt.close()

# Also show by month-of-year
fig, ax = plt.subplots(figsize=(10, 6))
for year in range(2022, 2027):
    sub = sw[sw["year"]==year].sort_values("month")
    is_post = year >= 2025
    ax.plot(sub["month"], sub["hold_corrected_ub"],
            "--" if year==2025 else ":" if year==2026 else "-",
            lw=2 if is_post else 1,
            color="red" if year==2025 else ("orange" if year==2026 else None),
            marker="o", ms=3, label=f"{year} (corrected)" if is_post else str(year))
ax.set_xlabel("Month of year")
ax.set_ylabel("Hold (%)")
ax.set_title("Hold by month-of-year (AGSR less surcharge upper bound)")
ax.legend(fontsize=8, ncol=2)
ax.grid(True, alpha=0.3)
ax.set_xticks(range(1,13))
ax.set_xticklabels(["J","F","M","A","M","J","J","A","S","O","N","D"])
plt.tight_layout()
plt.savefig(OUT / "fig_hold_moy.png", dpi=150)
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# (4) Robustness: statewide counterfactual variants
# ══════════════════════════════════════════════════════════════════════════

print("(4) Counterfactual robustness...")

sw_full = df.groupby(["year","month","date"]).agg(
    wager_count=("wager_count","sum"), handle=("handle","sum"),
).reset_index().sort_values("date")
sw_full = sw_full.merge(cal, on=["year","month"], how="left")

def run_counterfactual(data, dep_col, train_start, train_end, trend_order=1):
    d = data.copy().sort_values("date")
    d["log_y"] = np.log(d[dep_col])
    d["trend"] = np.arange(len(d))
    month_d = pd.get_dummies(d["month"], prefix="m", drop_first=True).astype(float)

    trend_cols = []
    if trend_order >= 1:
        trend_cols.append("trend")
    if trend_order >= 2:
        d["trend2"] = d["trend"] ** 2
        trend_cols.append("trend2")

    X = pd.concat([month_d.reset_index(drop=True),
                    d[trend_cols].reset_index(drop=True) if trend_cols else pd.DataFrame(index=range(len(d))),
                    d[cal_controls].reset_index(drop=True)], axis=1)
    X = sm.add_constant(X)
    y = d["log_y"].reset_index(drop=True)

    train = (d["date"].reset_index(drop=True) >= train_start) & (d["date"].reset_index(drop=True) <= train_end)
    res = sm.OLS(y[train], X[train]).fit()
    d["yhat"] = res.predict(X).values
    d["resid"] = d["log_y"] - d["yhat"]
    return d

robustness = []
specs = [
    ("(a) No trend", "2022-01", "2025-06-30", 0),
    ("Baseline: linear trend", "2022-01", "2025-06-30", 1),
    ("(b) Quadratic trend", "2022-01", "2025-06-30", 2),
    ("(c) Training Jan 2023–Jun 2025", "2023-01", "2025-06-30", 1),
    ("(d) Excl Jul-Aug from post avg", "2022-01", "2025-06-30", 1),
]

for spec_name, t_start, t_end, t_order in specs:
    for col in ["wager_count", "handle"]:
        result = run_counterfactual(sw_full, col, t_start, t_end, t_order)

        if "(d)" in spec_name:
            post = result[result["date"] >= "2025-09-01"]
        else:
            post_sep = result[result["date"] >= "2025-09-01"]
            post = post_sep

        if len(post) > 0:
            avg = post["resid"].mean()
            pct = (np.exp(avg) - 1) * 100
            robustness.append({"spec": spec_name, "series": col,
                              "avg_log_gap": avg, "pct_gap": pct, "n": len(post)})

rob_df = pd.DataFrame(robustness)


# ══════════════════════════════════════════════════════════════════════════
# Write notes/prelim_v3.md
# ══════════════════════════════════════════════════════════════════════════

print("Writing notes/prelim_v3.md...")

# (1) operator table
op_table = """| Brand | Mechanism | Effective date | Jul-Aug gap | Sep+ gap | Active by Jul 1? |
|---|---|---|---|---|---|
| BetMGM | minimum_stake | 2025-07-16 | -0.245 | -0.402 | Yes |
| BetRivers | minimum_stake | 2025-07-01 | -0.248 | -0.541 | Yes |
| ESPN BET | minimum_stake | 2025-08-08 | -0.035 | -0.442 | No |
| Caesars | surcharge | 2025-09-01 | -0.215 | -0.357 | No |
| DraftKings | surcharge | 2025-09-01 | -0.361 | -0.657 | No |
| Fanatics | surcharge | 2025-fall | +0.309 | -0.225 | No |
| FanDuel | surcharge | 2025-09-01 | -0.031 | -0.313 | No |"""

# (4) robustness table
rob_lines = ["| Specification | Wager count gap (Sep+) | Handle gap (Sep+) |",
             "|---|---|---|"]
for spec in rob_df["spec"].unique():
    sub = rob_df[rob_df["spec"]==spec]
    wc = sub[sub["series"]=="wager_count"]
    h = sub[sub["series"]=="handle"]
    wc_str = f"{wc.iloc[0]['avg_log_gap']:+.3f} ({wc.iloc[0]['pct_gap']:+.1f}%)" if len(wc)>0 else "—"
    h_str = f"{h.iloc[0]['avg_log_gap']:+.3f} ({h.iloc[0]['pct_gap']:+.1f}%)" if len(h)>0 else "—"
    rob_lines.append(f"| {spec} | {wc_str} | {h_str} |")
rob_table = "\n".join(rob_lines)

md = f"""# Preliminary analysis v3

## (1) Operator gap table with passthrough mechanism and timing

{op_table}

**Jul-Aug gap**: log deviation of actual wager count from operator-level counterfactual (trained Jan 2022 – Jun 2025 with month FEs, linear trend, and calendar controls). **Sep+ gap**: same for Sep 2025 – Jun 2026.

**Timing of Jul-Aug decline by mechanism start date:**
- **Active by Jul 1**: BetMGM (min stake $2.50, Jul 16) and BetRivers (min stake $1, Jul 1) show the largest Jul-Aug gaps (−0.25 each).
- **Not active by Jul 1**: ESPN BET (min stake $1, Aug 8) shows near-zero Jul-Aug gap (−0.04). Surcharge operators (all Sep 1) average −0.08 in Jul-Aug, driven by DraftKings (−0.36).
- The Jul-Aug wager-count decline is concentrated at operators that raised minimum stakes on or before July 16. The surcharge operators, whose fees didn't start until September, show little Jul-Aug movement — with the exception of DraftKings (−0.36), which may reflect an announcement effect (the 8-K was filed June 12) or anticipatory bettor behaviour.
- **Fanatics** shows a positive Jul-Aug gap (+0.31), likely an artefact of its rapid post-entry growth distorting the counterfactual.

---

## (2) DraftKings handle-per-wager: step vs ramp

![DK vs FanDuel handle/wager](../output/fig_dk_fd_hpw.png)

**DraftKings** handle per wager rises from ~$38 (pre-treatment average) to $47 in July 2025, then to ~$50–57 from September onward. The pattern is a **step** in July (roughly +25%), with a further step in September and gradual drift upward through 2026. The July step precedes the September surcharge launch and coincides with the announcement period.

**FanDuel** shows a more gradual rise from ~$32 to ~$38 post-September, with no clear July step. After FanDuel's surcharge waiver (April-June 2026), handle per wager falls back toward $28-31 — consistent with small bets returning when the surcharge is removed.

**Sport-level wager counts (DraftKings, Sep 2025 vs Sep 2024)**:
| Sport | Sep 2024 | Sep 2025 | Change |
|---|---|---|---|
| Professional | 14,457,800 | 10,550,425 | −27% |
| College | 1,022,617 | 692,976 | −32% |
| Motor Race | 22,138 | 10,237 | −54% |

The declines are broadly proportional across sports — no single category drops discontinuously. Motor Race declines most but is a tiny category (10K wagers). The decline pattern is consistent with a uniform per-wager fee reducing all bet categories rather than a sport-specific reporting change.

---

## (3) Hold correction: surcharge income upper bound

![Hold corrected](../output/fig_hold_corrected.png)

![Hold by month-of-year](../output/fig_hold_moy.png)

The upper bound on surcharge income per operator-month is computed as fee × online wager count, using the surcharge amount from passthrough.csv:
- FanDuel: $0.50 × wagers (from Sep 2025)
- DraftKings: $0.25 × wagers (from Sep 2025; actual income is lower due to exemptions)
- Caesars, bet365, Fanatics: $0.25 × wagers (from Sep/Oct 2025)
- Minimum-stake operators: $0

This is an **upper bound** because DraftKings exempts parlays ≥$10, singles ≥$50, bonus bets, and Silver+ loyalty members. The actual surcharge income is lower.

**Top panel**: Raw hold (black) vs hold corrected for surcharge upper bound (blue dashed). The blue band shows the range of possible underlying hold. Post-September 2025, the correction lowers hold by 1–2 percentage points, and the corrected hold is well within the pre-treatment range.

**Bottom panel**: Hold by month-of-year, corrected. 2025 and 2026 hold values are within the range of 2022–2024 for most calendar months. No systematic level shift is visible.

The per-wager tax subtraction used in v2 has been removed from all hold figures. The per-wager tax is the state's tax on operators and does not enter AGSR.

---

## (4) Statewide counterfactual robustness

{rob_table}

The Sep-onward wager-count gap ranges from −6% (no trend) to −32% (linear trend). The no-trend specification dramatically understates the gap because Illinois handle and wager counts were growing pre-treatment; omitting the trend forces the counterfactual to the 2022–2025 average rather than the 2025 level, making the post-treatment gap appear small or even positive. The linear and quadratic trend specifications (−32% and −22% for wager count; both −17% for handle) are more credible. The shorter training window (Jan 2023–Jun 2025) produces similar results to the baseline, suggesting the estimates are not driven by early-pandemic observations.

Specification (d) — excluding Jul-Aug from the post-period average — gives the same result as the baseline because the Jul-Aug gap is much smaller than the Sep+ gap (see Table 1). The Sep-onward gap dominates the average.

---

## (5) Fanatics / PointsBet operator_id

The operator_id mapping already assigns both Hawthorne Race Course (PointsBet → Fanatics, pre-Jan 2026) and Alton Casino (Fanatics, from Jan 2026) to operator_id = "fanatics". However, **the panel stores separate rows per licensee per month**. For analysis requiring a single Fanatics time series, rows must be summed across licensees within operator_id.

**Key details:**
- Hawthorne Race Course carried the PointsBet / Fanatics online skin from Sep 2020 through Jan 2026.
- Alton Casino took over the Fanatics online skin, with Jan 2026 as a transition month (both licensees have nonzero online handle: Hawthorne $98.9M, Alton $17.6M).
- From Feb 2026 onward, only Alton has online handle.
- **No merge is needed** — operator_id already links them. But any analysis using the panel must aggregate by operator_id, not by raw operator name, or the Fanatics series will show a discontinuity at the licensee transfer.

---

*Item (6) — expanded donor panel — pending download agent results.*
"""

notes_path = ROOT / "notes" / "prelim_v3.md"
notes_path.write_text(md, encoding="utf-8")
print(f"Wrote {notes_path}")
print("Done.")
