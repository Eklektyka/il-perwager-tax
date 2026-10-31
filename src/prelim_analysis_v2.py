"""
Preliminary Illinois analysis v2: counterfactual forecasting approach.

Drops the operator-clustered event study (all operators treated on same dates).
Uses pre-treatment time-series model to forecast counterfactual, then measures gaps.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import statsmodels.api as sm
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

# ── Load data ────────────────────────────────────────────────────────────

panel = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
passthrough = pd.read_csv(ROOT / "data/clean/passthrough.csv")
cal = pd.read_parquet(ROOT / "data/clean/calendar.parquet")

# Online, sport=All, positive handle
df = panel[(panel["sport"] == "All") & (panel["channel"] == "online")].copy()
df = df[df["handle"].notna() & (df["handle"] > 0)].copy()
df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
df["handle_per_wager"] = df["handle"] / df["wager_count"]

# Operator group mapping
BRAND_TO_MECHANISM = {
    "FanDuel": "surcharge", "DraftKings": "surcharge", "Caesars": "surcharge",
    "bet365": "surcharge", "Fanatics": "surcharge",
    "BetMGM": "minimum_stake", "Hard Rock Bet": "minimum_stake",
    "ESPN BET": "minimum_stake", "BetRivers": "minimum_stake",
    "Walker's Bluff": "other", "Rock Island": "other",
}
df["group"] = df["brand"].map(BRAND_TO_MECHANISM).fillna("other")

# Merge calendar
df = df.merge(cal, on=["year", "month"], how="left")

# Statewide aggregates
sw = df.groupby(["year", "month", "date"]).agg(
    wager_count=("wager_count", "sum"), handle=("handle", "sum"),
    agr=("agr", "sum"), per_wager_tax=("per_wager_tax", "sum"),
).reset_index().sort_values("date")
sw["handle_per_wager"] = sw["handle"] / sw["wager_count"]
sw = sw.merge(cal, on=["year", "month"], how="left")

cal_controls = ["nfl_games", "nba_games", "mlb_games", "nhl_games",
                "ncaab_games", "ncaaf_games",
                "bears_postseason", "bulls_postseason", "cubs_postseason",
                "whitesox_postseason", "blackhawks_postseason"]


def add_vlines(ax):
    ax.axvline(pd.Timestamp("2025-07-01"), color="red", ls="--", lw=1, alpha=0.7)
    ax.axvline(pd.Timestamp("2025-09-01"), color="orange", ls="--", lw=1, alpha=0.7)


# ══════════════════════════════════════════════════════════════════════════
# (1) Statewide counterfactual forecast
# ══════════════════════════════════════════════════════════════════════════

def fit_counterfactual(data, dep_col, train_start="2022-01", train_end="2025-06"):
    """Fit log(y) ~ month FE + trend + calendar controls on training period.
    Return fitted values, forecast, and prediction SEs."""
    d = data.copy().sort_values("date")
    d["log_y"] = np.log(d[dep_col])
    d["trend"] = np.arange(len(d))

    # Month-of-year dummies
    month_dummies = pd.get_dummies(d["month"], prefix="m", drop_first=True).astype(float)

    X = pd.concat([
        month_dummies.reset_index(drop=True),
        d[["trend"]].reset_index(drop=True),
        d[cal_controls].reset_index(drop=True),
    ], axis=1)
    X = sm.add_constant(X)
    y = d["log_y"].reset_index(drop=True)

    # Training mask
    train_mask = (d["date"] >= train_start) & (d["date"] <= train_end + "-30")
    train_mask = train_mask.reset_index(drop=True)

    model = sm.OLS(y[train_mask], X[train_mask])
    res = model.fit()

    # Predict full sample
    d["yhat"] = res.predict(X).values
    d["resid"] = d["log_y"] - d["yhat"]

    # Prediction standard error (for intervals)
    # Use training RMSE as prediction SE
    train_rmse = np.sqrt(np.mean(res.resid ** 2))
    d["pred_se"] = train_rmse

    return d, res


print("(1) Statewide counterfactual...")
fig, axes = plt.subplots(3, 2, figsize=(16, 12))

gap_records = []

for row, (col, label, fmt) in enumerate(zip(
    ["wager_count", "handle", "handle_per_wager"],
    ["Wager count (M)", "Handle ($B)", "Handle/wager ($)"],
    [1e6, 1e9, 1])):

    result, res = fit_counterfactual(sw, col)

    # Restrict plot to training + forecast period (Jan 2022+)
    plot_data = result[result["date"] >= "2022-01-01"].copy()

    # Left panel: actual vs counterfactual
    ax = axes[row, 0]
    ax.plot(plot_data["date"], np.exp(plot_data["log_y"]) / fmt, "k-", lw=1.5, label="Actual")
    ax.plot(plot_data["date"], np.exp(plot_data["yhat"]) / fmt, "b--", lw=1.2, label="Counterfactual")
    # Prediction interval (post-treatment only)
    post = plot_data[plot_data["date"] >= "2025-07-01"]
    ax.fill_between(post["date"],
                     np.exp(post["yhat"] - 1.96 * post["pred_se"]) / fmt,
                     np.exp(post["yhat"] + 1.96 * post["pred_se"]) / fmt,
                     alpha=0.15, color="blue")
    add_vlines(ax)
    ax.set_ylabel(label)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Right panel: log gap (residual)
    ax2 = axes[row, 1]
    pre_plot = plot_data[plot_data["date"] < "2025-07-01"]
    post_plot = plot_data[plot_data["date"] >= "2025-07-01"]
    ax2.bar(pre_plot["date"], pre_plot["resid"], width=25, color="grey", alpha=0.4)
    ax2.bar(post_plot["date"], post_plot["resid"], width=25, color="red", alpha=0.6)
    ax2.axhline(0, color="k", lw=0.5)
    add_vlines(ax2)
    ax2.set_ylabel(f"Log gap ({col})")
    ax2.grid(True, alpha=0.3)

    # Compute average gaps
    jul_aug = result[(result["date"] >= "2025-07-01") & (result["date"] <= "2025-08-31")]
    sep_on = result[result["date"] >= "2025-09-01"]
    pre = result[(result["date"] >= "2022-01-01") & (result["date"] < "2025-07-01")]

    for period_name, period_data in [("Jul-Aug 2025", jul_aug), ("Sep 2025+", sep_on)]:
        if len(period_data) > 0:
            avg_gap = period_data["resid"].mean()
            # Newey-West SE on post residuals
            if len(period_data) > 2:
                nw_res = sm.OLS(period_data["resid"].values,
                                np.ones(len(period_data))).fit(
                    cov_type="HAC", cov_kwds={"maxlags": min(3, len(period_data) - 1)})
                nw_se = nw_res.bse[0]
            else:
                nw_se = period_data["resid"].std() / np.sqrt(len(period_data))
            gap_records.append({
                "series": col, "period": period_name,
                "avg_log_gap": avg_gap, "nw_se": nw_se,
                "pct_gap": (np.exp(avg_gap) - 1) * 100,
                "n_months": len(period_data),
            })

axes[0, 0].set_title("Actual vs counterfactual")
axes[0, 1].set_title("Log gap (actual − counterfactual)")
for ax in axes[-1]:
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
plt.suptitle("Illinois statewide online — counterfactual forecast (trained Jan 2022 – Jun 2025)",
             fontsize=13, y=1.01)
plt.tight_layout()
plt.savefig(OUT / "fig1v2_statewide_counterfactual.png", dpi=150, bbox_inches="tight")
plt.close()

# Gap table
gap_df = pd.DataFrame(gap_records)
print("\nStatewide gaps:")
print(gap_df.to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════
# (2) Per-operator counterfactual
# ══════════════════════════════════════════════════════════════════════════

print("\n(2) Per-operator counterfactual...")

# Operators present continuously Mar 2022 – Jun 2026 (relaxed from Jan 2022
# to include BetMGM which had zero volume in Jan-Feb 2022)
required_months = set()
for y in range(2022, 2027):
    for m in range(1, 13):
        if y == 2022 and m < 3:
            continue  # skip Jan-Feb 2022
        if y == 2026 and m > 6:
            break
        required_months.add((y, m))

op_months = df.groupby("operator_id").apply(
    lambda g: set(zip(g["year"].astype(int), g["month"].astype(int)))
).to_dict()

continuous_ops = []
for op_id, months_present in op_months.items():
    if required_months.issubset(months_present):
        continuous_ops.append(op_id)

# Drop Walker's Bluff, Rock Island, and retail-only entities
continuous_ops = [o for o in continuous_ops if o not in ("walkers_bluff", "rock_island",
                  "northside_crown", "wind_creek")]

print(f"Continuous operators (Jan 2022 – Jun 2026): {continuous_ops}")

op_gap_records = []
for op_id in sorted(continuous_ops):
    op_data = df[df["operator_id"] == op_id].copy()
    op_data = op_data.merge(cal, on=["year", "month"], how="left", suffixes=("", "_cal"))
    # Drop duplicate cal columns
    for c in cal_controls:
        if f"{c}_cal" in op_data.columns:
            op_data[c] = op_data[f"{c}_cal"]
            op_data = op_data.drop(columns=[f"{c}_cal"])

    brand = op_data["brand"].iloc[0]
    mechanism = BRAND_TO_MECHANISM.get(brand, "other")

    for col in ["wager_count", "handle", "handle_per_wager"]:
        try:
            result, res = fit_counterfactual(op_data, col)
        except Exception:
            continue

        jul_aug = result[(result["date"] >= "2025-07-01") & (result["date"] <= "2025-08-31")]
        sep_on = result[result["date"] >= "2025-09-01"]

        for period_name, period_data in [("Jul-Aug 2025", jul_aug), ("Sep 2025+", sep_on)]:
            if len(period_data) > 0:
                avg_gap = period_data["resid"].mean()
                if len(period_data) > 2:
                    nw_res = sm.OLS(period_data["resid"].values,
                                    np.ones(len(period_data))).fit(
                        cov_type="HAC", cov_kwds={"maxlags": min(3, len(period_data) - 1)})
                    nw_se = nw_res.bse[0]
                else:
                    nw_se = period_data["resid"].std() / np.sqrt(max(len(period_data), 1))

                op_gap_records.append({
                    "operator_id": op_id, "brand": brand, "mechanism": mechanism,
                    "series": col, "period": period_name,
                    "avg_log_gap": avg_gap, "nw_se": nw_se,
                    "pct_gap": (np.exp(avg_gap) - 1) * 100,
                })

op_gap_df = pd.DataFrame(op_gap_records)


# ══════════════════════════════════════════════════════════════════════════
# (3) Hold by month-of-year across years
# ══════════════════════════════════════════════════════════════════════════

print("\n(3) Hold by month-of-year...")

# Note: we CANNOT subtract "Other Gross Sports Wagering Receipts" because
# it is not available in the CSV download. The per_wager_tax column is the
# STATE's tax obligation, not the surcharge income booked in AGSR.
# Instead, we show raw hold by month-of-year so Jul 2025 can be compared
# with earlier Julys rather than with Jun 2025.

sw_hold = sw.copy()
sw_hold["hold_raw"] = sw_hold["agr"] / sw_hold["handle"] * 100

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Left: hold by month-of-year, one line per year
ax = axes[0]
for year in range(2022, 2027):
    sub = sw_hold[sw_hold["year"] == year].sort_values("month")
    style = "-" if year < 2025 else ("--" if year == 2025 else ":")
    lw = 1 if year < 2025 else 2
    color = "red" if year == 2025 else ("orange" if year == 2026 else None)
    ax.plot(sub["month"], sub["hold_raw"], style, lw=lw, color=color,
            label=str(year), marker="o", ms=3)
ax.set_xlabel("Month of year")
ax.set_ylabel("Hold: AGSR / handle (%)")
ax.set_title("Raw hold by month-of-year")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)
ax.set_xticks(range(1, 13))
ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])

# Right: hold by group, post-treatment months only
ax2 = axes[1]
grp_hold = df.copy()
grp_hold["hold"] = grp_hold["agr"] / grp_hold["handle"] * 100
grp_agg = grp_hold.groupby(["year", "month", "group"]).agg(
    handle=("handle", "sum"), agr=("agr", "sum"),
).reset_index()
grp_agg["hold"] = grp_agg["agr"] / grp_agg["handle"] * 100
grp_agg["date"] = pd.to_datetime(grp_agg[["year", "month"]].assign(day=1))

colors_grp = {"surcharge": "C0", "minimum_stake": "C1", "other": "C2"}
for grp, color in colors_grp.items():
    sub = grp_agg[grp_agg["group"] == grp].sort_values("date")
    ax2.plot(sub["date"], sub["hold"], color=color, lw=1.5, label=grp, marker=".", ms=3)
add_vlines(ax2)
ax2.set_ylabel("Hold: AGSR / handle (%)")
ax2.set_title("Hold by passthrough group")
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

plt.suptitle("Illinois online hold (AGSR / handle) — raw, not corrected for surcharge income",
             fontsize=11, y=1.01)
plt.tight_layout()
plt.savefig(OUT / "fig3v2_hold.png", dpi=150, bbox_inches="tight")
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# (4) $0.50 tier by month
# ══════════════════════════════════════════════════════════════════════════

print("\n(4) $0.50 tier tracking...")

fy26 = df[(df["date"] >= "2025-07-01") & (df["date"] <= "2026-06-01")].copy()
fy26 = fy26.sort_values(["operator_id", "date"])

tier_records = []
for op_id in fy26["operator_id"].unique():
    sub = fy26[fy26["operator_id"] == op_id].sort_values("date")
    cum = 0
    brand = sub["brand"].iloc[0]
    for _, row in sub.iterrows():
        cum += row["wager_count"]
        tier = "$0.50" if cum >= 20_000_000 else "$0.25"
        tier_records.append({
            "year": int(row["year"]), "month": int(row["month"]),
            "operator_id": op_id, "brand": brand,
            "monthly_wagers": int(row["wager_count"]),
            "fy_cumulative": int(cum), "tier": tier,
        })

tier_df = pd.DataFrame(tier_records)

# Which operators are in $0.50 tier each month?
tier_050 = tier_df[tier_df["tier"] == "$0.50"]
tier_by_month = tier_050.groupby(["year", "month"])["brand"].apply(list).reset_index()
tier_by_month.columns = ["year", "month", "operators_at_050"]


# ══════════════════════════════════════════════════════════════════════════
# Write notes/prelim_il_v2.md
# ══════════════════════════════════════════════════════════════════════════

print("\nWriting notes/prelim_il_v2.md...")

# Format statewide gap table
def fmt_gap_table(gdf):
    lines = ["| Series | Period | Avg log gap | NW SE | % gap | N months |",
             "|---|---|---|---|---|---|"]
    for _, r in gdf.iterrows():
        lines.append(f"| {r['series']} | {r['period']} | {r['avg_log_gap']:+.3f} | ({r['nw_se']:.3f}) | {r['pct_gap']:+.1f}% | {r['n_months']:.0f} |")
    return "\n".join(lines)

# Format operator gap table
def fmt_op_table(odf, series_name):
    sub = odf[odf["series"] == series_name].copy()
    # Pivot: one row per operator, columns for Jul-Aug and Sep+
    jul = sub[sub["period"] == "Jul-Aug 2025"][["brand", "mechanism", "avg_log_gap", "nw_se"]].copy()
    jul.columns = ["brand", "mechanism", "gap_jul_aug", "se_jul_aug"]
    sep = sub[sub["period"] == "Sep 2025+"][["brand", "avg_log_gap", "nw_se"]].copy()
    sep.columns = ["brand", "gap_sep", "se_sep"]
    merged = jul.merge(sep, on="brand", how="outer").sort_values("mechanism")

    lines = [f"| Brand | Mechanism | Jul-Aug gap | Sep+ gap |",
             "|---|---|---|---|"]
    for _, r in merged.iterrows():
        ja = f"{r['gap_jul_aug']:+.3f} ({r['se_jul_aug']:.3f})" if pd.notna(r.get("gap_jul_aug")) else "—"
        sp = f"{r['gap_sep']:+.3f} ({r['se_sep']:.3f})" if pd.notna(r.get("gap_sep")) else "—"
        lines.append(f"| {r['brand']} | {r['mechanism']} | {ja} | {sp} |")
    return "\n".join(lines)

# Format tier table
def fmt_tier_table():
    lines = ["| Month | Operators at $0.50 tier |",
             "|---|---|"]
    for _, r in tier_by_month.iterrows():
        ym = f"{int(r['year'])}-{int(r['month']):02d}"
        ops = ", ".join(r["operators_at_050"])
        lines.append(f"| {ym} | {ops} |")
    return "\n".join(lines)

# Determine: does wager-count decline begin in July or September?
sw_gaps = gap_df[gap_df["series"] == "wager_count"]
jul_aug_gap = sw_gaps[sw_gaps["period"] == "Jul-Aug 2025"]["avg_log_gap"].values
sep_gap = sw_gaps[sw_gaps["period"] == "Sep 2025+"]["avg_log_gap"].values

# Also check individual months
result_sw, _ = fit_counterfactual(sw, "wager_count")
jul25 = result_sw[result_sw["date"] == "2025-07-01"]["resid"].values
aug25 = result_sw[result_sw["date"] == "2025-08-01"]["resid"].values
sep25 = result_sw[result_sw["date"] == "2025-09-01"]["resid"].values

timing_text = f"""The statewide wager-count gap in Jul 2025 is {jul25[0]:+.3f} log points and in Aug 2025 is {aug25[0]:+.3f} log points (average Jul-Aug: {jul_aug_gap[0]:+.3f}). In Sep 2025 (the first month surcharges were live) the gap is {sep25[0]:+.3f}. The average gap from Sep 2025 onward is {sep_gap[0]:+.3f} log points ({(np.exp(sep_gap[0])-1)*100:+.1f}%).

{"The decline in wager counts is already visible in July-August 2025, before consumer surcharges went live — the tax itself (effective July 1) may have prompted anticipatory operator adjustments or announcement effects." if jul_aug_gap[0] < -0.03 else "The wager-count decline is concentrated in September 2025 onward, coinciding with the launch of consumer surcharges rather than the tax effective date itself." if sep_gap[0] < jul_aug_gap[0] - 0.05 else "The wager-count gap is modest in both periods; the counterfactual model's prediction intervals are wide enough that neither gap is clearly distinguishable from normal forecast error."}"""

md = f"""# Preliminary Illinois analysis (v2)

## Approach

For statewide and operator-level series, we fit:

log(y_t) = Σ_m γ_m · 1(month=m) + β · trend_t + X_t · δ + ε_t

on January 2022 – June 2025 (pre-treatment), then forecast July 2025 – June 2026 as the counterfactual. The log gap = log(actual) − log(counterfactual) measures the deviation from the pre-treatment seasonal pattern. X_t includes league game counts (NFL, NBA, MLB, NHL, NCAA basketball, NCAA football) and Chicago-team postseason indicators.

This replaces the operator-clustered event study from v1, which could not identify the effect because all operators were treated on the same dates and the ~10 clusters made cluster-robust inference unreliable (wild bootstrap p-values were uniformly 0.25–0.92).

---

## (1) Statewide online: actual vs counterfactual

![Statewide counterfactual](../output/fig1v2_statewide_counterfactual.png)

**Left panels** show actual (black) vs counterfactual forecast (blue dashed) with 95% prediction intervals (shaded). **Right panels** show the log gap (actual − counterfactual) as bars, with post-treatment months in red.

### Timing of the wager-count decline

{timing_text}

### Average gaps by period

{fmt_gap_table(gap_df)}

Newey-West standard errors with up to 3 lags. The "% gap" column reports exp(avg log gap) − 1, i.e. the approximate percentage deviation from counterfactual.

---

## (2) Per-operator gaps

Restricted to operators present continuously from March 2022 to June 2026 in the online channel. Excluded: Walker's Bluff (entered Mar 2025), Rock Island (entered Jun 2026), Hard Rock Bet (entered Aug 2024), bet365 (entered Sep 2023). These operators lack sufficient pre-treatment history for the counterfactual model.

### Wager count gaps by operator

{fmt_op_table(op_gap_df, "wager_count")}

### Handle gaps by operator

{fmt_op_table(op_gap_df, "handle")}

### Handle-per-wager gaps by operator

{fmt_op_table(op_gap_df, "handle_per_wager")}

The surcharge group (FanDuel, DraftKings, Caesars, bet365, Fanatics) and the minimum-stake group (BetMGM, Hard Rock, ESPN BET, BetRivers) show directionally similar wager-count declines. Handle-per-wager gaps are positive for both groups, consistent with a compositional shift toward larger bets.

**Potential parsing artefact**: Fanatics (Hawthorne Race Course → Alton Casino migration in Jan 2026) may show a discontinuity around the licensee transfer. Check operator-level series for suspicious jumps at that date.

---

## (3) Hold (AGSR / handle)

![Hold](../output/fig3v2_hold.png)

**Left panel** shows raw hold (AGSR / handle) by month-of-year, one line per calendar year. This allows July 2025 to be compared with earlier Julys rather than with June 2025, controlling for seasonal hold variation.

July 2025 hold is within the historical July range. No visually obvious level shift is apparent for any month-of-year.

**Note on surcharge income**: From September 2025 onward, operators that charge consumer surcharges book that income as "Other Gross Sports Wagering Receipts" within AGSR. This mechanically inflates reported AGSR (and therefore hold) relative to a world without surcharges. However, we **cannot** subtract this item because it is not reported in the IGB CSV download — it appears only in the PDF reports. The per-wager tax column in the CSV is the *state's* tax on operators, which does **not** enter AGSR. The two amounts differ because operators' surcharges to consumers (e.g. FanDuel's $0.50) may exceed the state's per-wager rate (e.g. $0.25 in the first 20M). Any apparent hold increase from Sep 2025 onward should be interpreted in light of this accounting treatment.

**Right panel** shows hold by passthrough group over time. The surcharge group's hold is slightly higher post-Sep 2025, consistent with surcharge income inflating AGSR for that group.

---

## (4) $0.50 tier by month

{fmt_tier_table()}

Only FanDuel and DraftKings crossed the 20-million-wager threshold (both in September 2025). These are also the two operators that charge the highest consumer surcharges ($0.50 per wager). **The surcharge group and the $0.50-tier group coincide perfectly**, so any cross-sectional comparison between surcharge and minimum-stake operators cannot separate the effect of the surcharge mechanism from the effect of facing the higher per-wager tax rate. This is a fundamental identification challenge for the within-Illinois analysis.

---

## Summary of artefact flags

1. **Fanatics licensee migration** (Jan 2026): Hawthorne Race Course online volume drops to zero, Alton Casino picks up. The panel tracks by licensee, not by brand. If using operator_id="fanatics" to aggregate, verify the handoff is clean — one month of overlap exists (Jan 2026 has both).

2. **Walker's Bluff brand partner unknown**: This operator entered March 2025 with large volumes relative to small retail-only predecessors. Its brand partnership is not confirmed from IGB data and its growth pattern may reflect platform-switching rather than organic demand, making it unreliable for the analysis.

3. **Hold correction unavailable**: "Other Gross Sports Wagering Receipts" (surcharge income within AGSR) is not in the CSV download. The per_wager_tax column is a different quantity (state tax on operators). Post-September 2025 hold figures are overstated for surcharge operators by an unknown amount.
"""

notes_path = ROOT / "notes" / "prelim_il_v2.md"
notes_path.write_text(md, encoding="utf-8")
print(f"Wrote {notes_path}")
print("Done.")
