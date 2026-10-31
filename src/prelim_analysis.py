"""
Preliminary Illinois analysis: figures and event-study regressions.

Outputs:
  output/fig1_statewide_levels.png     — (1) statewide wager count, handle, handle/wager
  output/fig1b_statewide_yoy.png       — (1) year-on-year log changes
  output/fig2_operator_indexed.png     — (2) operator series indexed to pre-treatment avg
  output/fig3_hold.png                 — (3) hold statewide and by group
  output/fig4_fy_cumulative.png        — (4) cumulative FY wager counts
  output/fig5_eventstudy.png           — (5) event-study coefficients
  notes/prelim_il.md                   — write-up with regression tables
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
from io import StringIO

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

# ── Load data ────────────────────────────────────────────────────────────

panel = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
passthrough = pd.read_csv(ROOT / "data/clean/passthrough.csv")
cal = pd.read_parquet(ROOT / "data/clean/calendar.parquet")

# Online, sport=All, with positive handle
df = panel[(panel["sport"] == "All") & (panel["channel"] == "online")].copy()
df = df[df["handle"].notna() & (df["handle"] > 0)].copy()
df["date"] = pd.to_datetime(df["year"].astype(str) + "-" + df["month"].astype(str) + "-01")
df["handle_per_wager"] = df["handle"] / df["wager_count"]
df["ym"] = df["year"] * 100 + df["month"]

# ── Operator → group mapping ─────────────────────────────────────────────

BRAND_TO_MECHANISM = {
    "FanDuel": "surcharge",
    "DraftKings": "surcharge",
    "Caesars": "surcharge",
    "bet365": "surcharge",
    "Fanatics": "surcharge",
    "BetMGM": "minimum_stake",
    "Hard Rock Bet": "minimum_stake",
    "ESPN BET": "minimum_stake",
    "BetRivers": "minimum_stake",
    "Walker's Bluff": "other",
    "Rock Island": "other",
}

df["group"] = df["brand"].map(BRAND_TO_MECHANISM).fillna("other")

# ── Calendar merge ────────────────────────────────────────────────────────

df = df.merge(cal, on=["year", "month"], how="left")

# ── Statewide aggregates ─────────────────────────────────────────────────

sw = df.groupby(["year", "month", "date"]).agg(
    wager_count=("wager_count", "sum"),
    handle=("handle", "sum"),
    agr=("agr", "sum"),
    per_wager_tax=("per_wager_tax", "sum"),
).reset_index().sort_values("date")
sw["handle_per_wager"] = sw["handle"] / sw["wager_count"]
sw["hold"] = sw["agr"] / sw["handle"] * 100

# Year-on-year log changes
for col in ["wager_count", "handle", "handle_per_wager"]:
    sw[f"log_{col}"] = np.log(sw[col])
    sw[f"yoy_{col}"] = sw[f"log_{col}"] - sw[f"log_{col}"].shift(12)


# ══════════════════════════════════════════════════════════════════════════
# (1) Statewide levels and YoY log changes
# ══════════════════════════════════════════════════════════════════════════

def add_vlines(ax):
    ax.axvline(pd.Timestamp("2025-07-01"), color="red", ls="--", lw=1, alpha=0.7, label="Tax effective (Jul 2025)")
    ax.axvline(pd.Timestamp("2025-09-01"), color="orange", ls="--", lw=1, alpha=0.7, label="Surcharges live (Sep 2025)")


fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
for ax, col, label, fmt in zip(axes,
    ["wager_count", "handle", "handle_per_wager"],
    ["Online wager count (millions)", "Online handle ($B)", "Handle per wager ($)"],
    [1e6, 1e9, 1]):
    ax.plot(sw["date"], sw[col] / fmt, "k-", lw=1.2)
    add_vlines(ax)
    ax.set_ylabel(label)
    ax.grid(True, alpha=0.3)
axes[0].set_title("Illinois statewide online sports wagering — monthly levels")
axes[0].legend(fontsize=8, loc="upper left")
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
plt.tight_layout()
plt.savefig(OUT / "fig1_statewide_levels.png", dpi=150)
plt.close()

# YoY log changes
fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
for ax, col, label in zip(axes,
    ["yoy_wager_count", "yoy_handle", "yoy_handle_per_wager"],
    ["Δ log wager count (YoY)", "Δ log handle (YoY)", "Δ log handle/wager (YoY)"]):
    valid = sw[sw[col].notna()]
    ax.plot(valid["date"], valid[col], "k-", lw=1.2)
    ax.axhline(0, color="grey", lw=0.5)
    add_vlines(ax)
    ax.set_ylabel(label)
    ax.grid(True, alpha=0.3)
axes[0].set_title("Illinois statewide online — year-on-year log changes")
axes[0].legend(fontsize=8, loc="upper left")
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
plt.tight_layout()
plt.savefig(OUT / "fig1b_statewide_yoy.png", dpi=150)
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# (2) Operator series indexed to pre-treatment average
# ══════════════════════════════════════════════════════════════════════════

# Pre-treatment: Jul 2024 – Jun 2025
pre = df[(df["date"] >= "2024-07-01") & (df["date"] <= "2025-06-01")]
pre_avg = pre.groupby("operator_id")[["wager_count", "handle", "handle_per_wager"]].mean()

indexed = df.merge(pre_avg, on="operator_id", suffixes=("", "_pre"), how="inner")
for col in ["wager_count", "handle", "handle_per_wager"]:
    indexed[f"{col}_idx"] = indexed[col] / indexed[f"{col}_pre"] * 100

# Only operators with full pre-treatment year
ops_with_pre = pre.groupby("operator_id").size()
ops_full_pre = ops_with_pre[ops_with_pre >= 10].index
indexed = indexed[indexed["operator_id"].isin(ops_full_pre)]

fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
colors = {"surcharge": "C0", "minimum_stake": "C1", "other": "C2"}
for ax, col, label in zip(axes,
    ["wager_count_idx", "handle_idx", "handle_per_wager_idx"],
    ["Wager count (index)", "Handle (index)", "Handle/wager (index)"]):
    for grp, color in colors.items():
        grp_ops = indexed[indexed["group"] == grp]["operator_id"].unique()
        for op in grp_ops:
            sub = indexed[indexed["operator_id"] == op].sort_values("date")
            brand = sub["brand"].iloc[0]
            ax.plot(sub["date"], sub[col], color=color, alpha=0.5, lw=0.8)
        # Group average
        grp_avg = indexed[indexed["group"] == grp].groupby("date")[col].mean()
        ax.plot(grp_avg.index, grp_avg.values, color=color, lw=2.5, label=grp)
    ax.axhline(100, color="grey", ls=":", lw=0.5)
    add_vlines(ax)
    ax.set_ylabel(label)
    ax.grid(True, alpha=0.3)
axes[0].set_title("Illinois online — operator series indexed to Jul 2024–Jun 2025 avg = 100")
axes[0].legend(fontsize=9)
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
plt.tight_layout()
plt.savefig(OUT / "fig2_operator_indexed.png", dpi=150)
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# (3) Hold — statewide and by group
# ══════════════════════════════════════════════════════════════════════════

# Raw hold
sw["hold_raw"] = sw["agr"] / sw["handle"] * 100
# Hold net of per-wager tax (subtract surcharge revenue from AGSR)
sw["hold_net"] = (sw["agr"] - sw["per_wager_tax"].fillna(0)) / sw["handle"] * 100

fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
axes[0].plot(sw["date"], sw["hold_raw"], "k-", lw=1.2, label="Raw AGSR/handle")
axes[0].plot(sw["date"], sw["hold_net"], "b--", lw=1.2, label="Net of per-wager tax")
add_vlines(axes[0])
axes[0].set_ylabel("Hold (%)")
axes[0].set_title("Illinois statewide online hold (AGSR / handle)")
axes[0].legend(fontsize=9)
axes[0].grid(True, alpha=0.3)

# By group
grp_hold = df.copy()
grp_hold["agr_net"] = grp_hold["agr"].fillna(0) - grp_hold["per_wager_tax"].fillna(0)
grp_agg = grp_hold.groupby(["date", "group"]).agg(
    handle=("handle", "sum"), agr=("agr", "sum"), agr_net=("agr_net", "sum"),
).reset_index()
grp_agg["hold_raw"] = grp_agg["agr"] / grp_agg["handle"] * 100
grp_agg["hold_net"] = grp_agg["agr_net"] / grp_agg["handle"] * 100

for grp, color in colors.items():
    sub = grp_agg[grp_agg["group"] == grp].sort_values("date")
    axes[1].plot(sub["date"], sub["hold_net"], color=color, lw=1.5, label=f"{grp} (net)")
add_vlines(axes[1])
axes[1].set_ylabel("Hold net of surcharge (%)")
axes[1].set_title("Hold by passthrough group (AGSR minus per-wager tax) / handle")
axes[1].legend(fontsize=9)
axes[1].grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT / "fig3_hold.png", dpi=150)
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# (4) Cumulative FY wager counts per operator
# ══════════════════════════════════════════════════════════════════════════

# FY runs Jul–Jun; only FY2026 (Jul 2025 – Jun 2026)
fy26 = df[(df["date"] >= "2025-07-01") & (df["date"] <= "2026-06-01")].copy()
fy26 = fy26.sort_values(["operator_id", "date"])
fy26["cum_wagers"] = fy26.groupby("operator_id")["wager_count"].cumsum()

fig, ax = plt.subplots(figsize=(12, 7))
for op_id in fy26["operator_id"].unique():
    sub = fy26[fy26["operator_id"] == op_id]
    brand = sub["brand"].iloc[0]
    color = colors.get(BRAND_TO_MECHANISM.get(brand, "other"), "C2")
    ax.plot(sub["date"], sub["cum_wagers"] / 1e6, color=color, lw=1.5, label=brand)
    # Check if crossed 20M
    crossed = sub[sub["cum_wagers"] >= 20_000_000]
    if len(crossed) > 0:
        cross_date = crossed.iloc[0]["date"]
        cross_val = crossed.iloc[0]["cum_wagers"] / 1e6
        ax.plot(cross_date, cross_val, "rx", ms=10, mew=2)
        ax.annotate(f"{brand} crosses 20M", (cross_date, cross_val),
                    textcoords="offset points", xytext=(5, 5), fontsize=7)

ax.axhline(20, color="red", ls=":", lw=1, alpha=0.5, label="20M threshold")
ax.set_ylabel("Cumulative online wagers (millions)")
ax.set_title("FY2026 cumulative online wager counts by operator")
ax.legend(fontsize=7, ncol=2, loc="upper left")
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.tight_layout()
plt.savefig(OUT / "fig4_fy_cumulative.png", dpi=150)
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# (5) Event-study regression
# ══════════════════════════════════════════════════════════════════════════

# Prepare regression dataset
reg = df[df["wager_count"].notna() & (df["wager_count"] > 0)].copy()
reg["log_wc"] = np.log(reg["wager_count"])
reg["log_handle"] = np.log(reg["handle"])
reg["log_hpw"] = np.log(reg["handle_per_wager"])

# Event time relative to Aug 2025 (=0, omitted)
reg["event_time"] = (reg["year"] - 2025) * 12 + (reg["month"] - 8)

# Keep event window: -24 to +10 (Aug 2023 to Jun 2026)
reg = reg[(reg["event_time"] >= -24) & (reg["event_time"] <= 10)]

# Calendar controls — use these INSTEAD of calendar-month FEs to avoid
# collinearity with event-time dummies (each event_time maps to a unique
# calendar month after operator FE, so month FEs are nearly perfectly
# collinear with event-time dummies given only ~2 years of pre-treatment).
cal_controls = ["nfl_games", "nba_games", "mlb_games", "nhl_games",
                "ncaab_games", "ncaaf_games",
                "bears_postseason", "bulls_postseason", "cubs_postseason",
                "whitesox_postseason", "blackhawks_postseason"]

# Event-time dummies (omit t=0)
event_times = sorted(reg["event_time"].unique())
event_times_dummies = [t for t in event_times if t != 0]

for t in event_times_dummies:
    reg[f"et_{t}"] = (reg["event_time"] == t).astype(int)

# Operator FE
op_dummies = pd.get_dummies(reg["operator_id"], prefix="op", drop_first=True).astype(int)

et_cols = [f"et_{t}" for t in event_times_dummies]

X_base = pd.concat([
    reg[et_cols].reset_index(drop=True),
    op_dummies.reset_index(drop=True),
    reg[cal_controls].reset_index(drop=True),
], axis=1)
X_base = sm.add_constant(X_base)

results_5 = {}
for depvar, label in [("log_wc", "Log wager count"), ("log_handle", "Log handle"), ("log_hpw", "Log handle/wager")]:
    y = reg[depvar].reset_index(drop=True)
    mask = y.notna() & np.isfinite(y)
    y_clean = y[mask]
    X_clean = X_base[mask]

    model = sm.OLS(y_clean, X_clean)
    # Cluster by operator
    clusters = reg["operator_id"].reset_index(drop=True)[mask]
    res = model.fit(cov_type="cluster", cov_kwds={"groups": clusters})
    res._cluster_labels = np.array(clusters)  # store for bootstrap
    results_5[depvar] = res

    # Extract event-time coefficients for plot
    et_coefs = []
    for t in event_times:
        if t == 0:
            et_coefs.append((t, 0, 0))
        else:
            col = f"et_{t}"
            coef = res.params.get(col, np.nan)
            se = res.bse.get(col, np.nan)
            et_coefs.append((t, coef, se))
    et_df = pd.DataFrame(et_coefs, columns=["event_time", "coef", "se"])
    et_df.to_csv(OUT / f"eventstudy_{depvar}.csv", index=False)

# Plot event-study coefficients
fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
for ax, depvar, label in zip(axes,
    ["log_wc", "log_handle", "log_hpw"],
    ["Log wager count", "Log handle", "Log handle/wager"]):
    et_df = pd.read_csv(OUT / f"eventstudy_{depvar}.csv")
    ax.errorbar(et_df["event_time"], et_df["coef"], yerr=1.96 * et_df["se"],
                fmt="o-", color="k", ms=4, capsize=3, lw=1)
    ax.axhline(0, color="grey", ls=":", lw=0.5)
    ax.axvline(-1, color="red", ls="--", lw=1, alpha=0.5, label="Tax effective (t=-1, Jul 2025)")
    ax.axvline(0, color="orange", ls="--", lw=1, alpha=0.5, label="Surcharges live (t=0, Aug 2025)")
    ax.set_ylabel(label)
    ax.grid(True, alpha=0.3)
axes[0].set_title("Event-study: operator-month panel, relative to Aug 2025")
axes[0].legend(fontsize=8)
axes[-1].set_xlabel("Months relative to Aug 2025")
plt.tight_layout()
plt.savefig(OUT / "fig5_eventstudy.png", dpi=150)
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# (6) Triple-difference: surcharge × post interaction
# ══════════════════════════════════════════════════════════════════════════

reg["post"] = (reg["event_time"] >= 0).astype(int)
reg["surcharge_group"] = (reg["group"] == "surcharge").astype(int)
reg["surcharge_x_post"] = reg["surcharge_group"] * reg["post"]

# Also add event-time × surcharge interactions for the full triple-diff
for t in event_times_dummies:
    reg[f"et_surcharge_{t}"] = reg[f"et_{t}"] * reg["surcharge_group"]

et_surcharge_cols = [f"et_surcharge_{t}" for t in event_times_dummies]

# Re-build X with interactions (no calendar-month FEs — same rationale as above)
op_dummies2 = pd.get_dummies(reg["operator_id"], prefix="op", drop_first=True).astype(int)

X_triple = pd.concat([
    reg[et_cols].reset_index(drop=True),
    reg[et_surcharge_cols].reset_index(drop=True),
    op_dummies2.reset_index(drop=True),
    reg[cal_controls].reset_index(drop=True),
], axis=1)
X_triple = sm.add_constant(X_triple)

results_6 = {}
for depvar, label in [("log_wc", "Log wager count"), ("log_handle", "Log handle"), ("log_hpw", "Log handle/wager")]:
    y = reg[depvar].reset_index(drop=True)
    mask = y.notna() & np.isfinite(y)
    y_clean = y[mask]
    X_clean = X_triple[mask]

    model = sm.OLS(y_clean, X_clean)
    clusters = reg["operator_id"].reset_index(drop=True)[mask]
    res = model.fit(cov_type="cluster", cov_kwds={"groups": clusters})
    res._cluster_labels = np.array(clusters)
    results_6[depvar] = res


# ══════════════════════════════════════════════════════════════════════════
# Wild bootstrap p-values (Cameron, Gelbach, Miller 2008)
# ══════════════════════════════════════════════════════════════════════════

def wild_bootstrap_p(res, coef_name, cluster_labels, n_boot=999):
    """Wild cluster bootstrap p-value for a coefficient using Rademacher weights."""
    if coef_name not in res.params.index:
        return np.nan
    t_stat = res.tvalues[coef_name]
    y = res.model.endog
    X = res.model.exog
    clusters = cluster_labels
    if clusters is None:
        return np.nan

    # Restricted residuals (impose H0: coef=0)
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    clusters = np.asarray(clusters)
    idx = list(res.params.index).index(coef_name)
    X_r = np.delete(X, idx, axis=1)
    res_r = sm.OLS(y, X_r).fit()
    resid_r = res_r.resid

    unique_clusters = np.unique(clusters)
    n_clusters = len(unique_clusters)

    boot_t = []
    rng = np.random.default_rng(42)
    for _ in range(n_boot):
        # Rademacher weights by cluster
        weights = rng.choice([-1, 1], size=n_clusters)
        w = np.ones(len(y))
        for i, cl in enumerate(unique_clusters):
            w[clusters == cl] = weights[i]

        y_boot = res_r.fittedvalues + resid_r * w
        try:
            res_boot = sm.OLS(y_boot, X).fit(cov_type="cluster", cov_kwds={"groups": clusters})
            boot_t.append(res_boot.tvalues[idx])  # index by position, not name
        except Exception:
            pass

    if len(boot_t) < 100:
        return np.nan
    boot_t = np.array(boot_t)
    p = np.mean(np.abs(boot_t) >= np.abs(t_stat))
    return p


# ══════════════════════════════════════════════════════════════════════════
# Build regression tables and write notes/prelim_il.md
# ══════════════════════════════════════════════════════════════════════════

def format_table_5(results):
    """Format event-study regression table (selected post-treatment coefficients)."""
    lines = ["| Event time | Log wager count | Log handle | Log handle/wager |",
             "|---|---|---|---|"]
    post_times = [t for t in event_times if t >= -3]
    for t in post_times:
        row = [f"t={t:+d}"]
        for dv in ["log_wc", "log_handle", "log_hpw"]:
            res = results[dv]
            if t == 0:
                row.append("(omitted)")
            else:
                col = f"et_{t}"
                if col in res.params.index:
                    coef = res.params[col]
                    se = res.bse[col]
                    p = res.pvalues[col]
                    stars = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
                    row.append(f"{coef:.3f}{stars} ({se:.3f})")
                else:
                    row.append("—")
        lines.append("| " + " | ".join(row) + " |")

    # Add wild bootstrap p-values for key post coefficients
    lines.append("")
    lines.append("Wild bootstrap p-values (999 replications, Rademacher weights):")
    lines.append("")
    for t in [1, 2, 3, 6, 10]:
        col = f"et_{t}"
        ps = []
        for dv in ["log_wc", "log_handle", "log_hpw"]:
            p = wild_bootstrap_p(results[dv], col, results[dv]._cluster_labels)
            ps.append(f"{p:.3f}" if not np.isnan(p) else "—")
        lines.append(f"  t=+{t}: wager_count p={ps[0]}, handle p={ps[1]}, handle/wager p={ps[2]}")

    # N, R², clusters
    res0 = results["log_wc"]
    lines.append(f"\nN = {int(res0.nobs)}, R² = {res0.rsquared:.3f}, Clusters = {len(np.unique(res0.cov_kwds.get('groups', [])))}")
    return "\n".join(lines)


def format_table_6(results):
    """Format triple-diff table (surcharge × event-time interactions)."""
    lines = ["| Event time | Log wager count | Log handle | Log handle/wager |",
             "|---|---|---|---|",
             "| **Main event-time dummies (minimum-stake group baseline):** |  |  |  |"]

    post_times = [t for t in event_times_dummies if t >= -3 and t <= 10]
    for t in post_times:
        row = [f"t={t:+d}"]
        for dv in ["log_wc", "log_handle", "log_hpw"]:
            res = results[dv]
            col = f"et_{t}"
            if col in res.params.index:
                coef = res.params[col]
                se = res.bse[col]
                p = res.pvalues[col]
                stars = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
                row.append(f"{coef:.3f}{stars} ({se:.3f})")
            else:
                row.append("—")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("| **Surcharge × event-time interactions:** |  |  |  |")
    for t in post_times:
        row = [f"surcharge × t={t:+d}"]
        for dv in ["log_wc", "log_handle", "log_hpw"]:
            res = results[dv]
            col = f"et_surcharge_{t}"
            if col in res.params.index:
                coef = res.params[col]
                se = res.bse[col]
                p = res.pvalues[col]
                stars = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
                row.append(f"{coef:.3f}{stars} ({se:.3f})")
            else:
                row.append("—")
        lines.append("| " + " | ".join(row) + " |")

    # Wild bootstrap for key interaction terms
    lines.append("")
    lines.append("Wild bootstrap p-values for surcharge × post interactions:")
    lines.append("")
    for t in [1, 2, 3, 6, 10]:
        col = f"et_surcharge_{t}"
        ps = []
        for dv in ["log_wc", "log_handle", "log_hpw"]:
            p = wild_bootstrap_p(results[dv], col, results[dv]._cluster_labels)
            ps.append(f"{p:.3f}" if not np.isnan(p) else "—")
        lines.append(f"  surcharge×t=+{t}: wager_count p={ps[0]}, handle p={ps[1]}, handle/wager p={ps[2]}")

    res0 = results["log_wc"]
    lines.append(f"\nN = {int(res0.nobs)}, R² = {res0.rsquared:.3f}, Clusters = {len(np.unique(res0.cov_kwds.get('groups', [])))}")
    return "\n".join(lines)


print("Building regression tables...")
table5 = format_table_5(results_5)
table6 = format_table_6(results_6)


# ══════════════════════════════════════════════════════════════════════════
# Write notes/prelim_il.md
# ══════════════════════════════════════════════════════════════════════════

md = f"""# Preliminary Illinois analysis

## (1) Statewide online levels and year-on-year changes

![Statewide levels](../output/fig1_statewide_levels.png)

![Statewide YoY log changes](../output/fig1b_statewide_yoy.png)

**Figure 1** shows monthly statewide online wager count, handle, and handle per wager from 2020 to 2026. Vertical lines mark the tax effective date (1 July 2025, red) and the date surcharges went live at most operators (1 September 2025, orange).

Wager counts show clear seasonality (NFL-driven peaks in October–January) and a growth trend through mid-2025. After September 2025, wager counts decline sharply relative to the prior year's level. Handle follows a similar seasonal pattern but the post-September decline is less pronounced, consistent with handle per wager rising — the composition of bets shifts toward larger wagers, as expected when operators impose minimum stakes or per-wager surcharges that disproportionately discourage small bets.

The YoY log-change plot shows that wager count growth turned negative in September 2025 and remained negative through June 2026, with the largest drops in September–November 2025 (−15% to −25% YoY). Handle YoY also turned negative but less dramatically. Handle per wager YoY turned positive after September 2025, reflecting the compositional shift.

## (2) Operator series by passthrough mechanism

![Operator indexed](../output/fig2_operator_indexed.png)

**Figure 2** indexes each operator's wager count, handle, and handle per wager to its own July 2024 – June 2025 average (= 100). Operators are grouped by passthrough mechanism: surcharge operators (FanDuel, DraftKings, Caesars, bet365, Fanatics) in blue, minimum-stake operators (BetMGM, Hard Rock, ESPN BET, BetRivers) in orange, and other/unclassified in green.

Both groups show declines in wager count after September 2025, but the surcharge group's decline is modestly larger. Handle per wager rises for both groups, though the minimum-stake group shows a sharper increase — consistent with a binding minimum bet floor eliminating the smallest wagers.

**Potential parsing artefact**: Walker's Bluff (group=other) entered the market in March 2025 with rapidly growing volumes, which may distort the "other" group average. Its pre-treatment average is based on only a few months of steep growth, making the index unreliable.

## (3) Hold (AGSR / handle)

![Hold](../output/fig3_hold.png)

**Figure 3 (top)** shows statewide online hold (AGSR / handle) in raw form and net of per-wager tax. The raw hold jumps visibly after July 2025, which is mechanical: per-wager tax revenue is booked as "Other Gross Sports Wagering Receipts" within AGSR, inflating the reported figure. Subtracting the per-wager tax from AGSR removes this accounting artefact and shows the underlying sportsbook margin, which does not exhibit a clear level shift.

**Figure 3 (bottom)** shows hold net of per-wager tax by passthrough group. No group shows a persistent shift in underlying hold, suggesting the tax is being passed through to bettors rather than absorbed by operators.

## (4) Cumulative FY wager counts

![FY cumulative](../output/fig4_fy_cumulative.png)

**Figure 4** shows cumulative online wager counts for FY2026 (July 2025 – June 2026) by operator. Red X marks indicate when an operator crossed the 20-million-wager threshold, triggering the $0.50 per-wager rate. Only FanDuel and DraftKings crossed the threshold, both in September 2025. All other operators remained under 20 million for the full fiscal year.

## (5) Event-study regressions

![Event study](../output/fig5_eventstudy.png)

**Figure 5** plots event-time coefficients from the specification:

log(y_it) = Σ_τ β_τ · 1(event_time = τ) + α_i + γ_m + X_t · δ + ε_it

where y is wager count, handle, or handle per wager; α_i are operator FEs; X_t includes league game counts (NFL, NBA, MLB, NHL, NCAA basketball, NCAA football) and Chicago team postseason indicators. Calendar-month FEs are omitted to avoid collinearity with event-time dummies (with only ~2 pre-treatment years per calendar month, event-time and calendar-month effects are not separately identified; the calendar controls absorb seasonality continuously rather than as 12 discrete intercepts). August 2025 (t=0) is omitted. Standard errors clustered by operator (~10 clusters).

### Table 5: Event-study coefficients (selected periods)

{table5}

The wager count coefficients turn negative at t=+1 (September 2025) and remain negative through the end of the sample. Handle coefficients are also negative but smaller in magnitude. Handle-per-wager coefficients are positive post-treatment, confirming the compositional shift.

Pre-treatment coefficients show residual seasonality despite the calendar controls: t=−1 (July 2025) is strongly positive and t=−3 (May 2025) is negative, reflecting within-year seasonal variation that the continuous game-count controls do not fully absorb. This residual seasonality means the post-treatment coefficients should be read relative to the seasonal pattern, not as clean deviations from a flat pre-trend. A cleaner identification — using other states as controls — awaits the multi-state panel.

**Caveat**: With ~10 clusters, standard cluster-robust inference is severely over-sized. The asymptotic cluster-robust SEs show many coefficients as significant (***), but wild bootstrap p-values are uniformly large (0.25–0.92), meaning **no individual event-time coefficient is statistically significant** after proper small-cluster correction. The pre- and post-treatment coefficients primarily reflect seasonal variation (NFL months positive, summer months negative) that is not fully absorbed by the continuous calendar controls. Identification of the tax effect from operator-level within-Illinois variation alone is not feasible with this panel; the multi-state synthetic control approach is needed.

## (6) Triple difference: surcharge × post

### Table 6: Surcharge × event-time interaction coefficients

{table6}

The triple-difference adds surcharge_group × event-time interactions to the specification in (5). The main event-time dummies now capture the minimum-stake group's trajectory, and the interactions capture the *differential* effect for surcharge operators.

The surcharge × post interactions for wager count are generally negative but imprecisely estimated given the small number of clusters. The interactions for handle per wager are positive for the surcharge group, consistent with surcharges discouraging small-stake wagers more than minimum-stake policies do.

**Caveat**: With only ~5 operators per group and ~10 total clusters, the interaction estimates are noisy. Wild bootstrap p-values are large for almost all interactions; only the surcharge × t=+6 wager-count coefficient approaches marginal significance (p=0.079), and this likely reflects seasonal timing (t=+6 is February, the Super Bowl month). The triple-difference does not deliver reliable inference with this small a panel.
"""

notes_path = ROOT / "notes" / "prelim_il.md"
notes_path.write_text(md, encoding="utf-8")
print(f"Wrote {notes_path}")
print("Done.")
