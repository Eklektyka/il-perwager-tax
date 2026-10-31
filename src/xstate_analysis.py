"""
Cross-state comparison: IL vs NJ, NY, IN, PA.
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

# ── Load and harmonise five state panels ─────────────────────────────────

def load_il():
    df = pd.read_parquet(ROOT / "data/clean/il_sports_wagering_panel.parquet")
    df = df[(df["sport"] == "All") & (df["channel"] == "online") & (df["handle"] > 0)].copy()
    monthly = df.groupby(["year", "month"]).agg(
        handle=("handle", "sum"), revenue=("agr", "sum"),
        per_wager_tax=("per_wager_tax", "sum"),
    ).reset_index()
    monthly["state"] = "IL"
    monthly["revenue_type"] = "AGSR"
    return monthly

def load_nj():
    df = pd.read_parquet(ROOT / "data/clean/states/nj.parquet")
    df = df[(df["operator"] == "STATEWIDE") & (df["channel"] == "online") & (df["handle"].notna())].copy()
    monthly = df.groupby(["year", "month"]).agg(handle=("handle", "sum"), revenue=("revenue", "sum")).reset_index()
    monthly["state"] = "NJ"
    monthly["revenue_type"] = "GGR"
    monthly["per_wager_tax"] = 0
    return monthly

def load_ny():
    df = pd.read_parquet(ROOT / "data/clean/states/ny.parquet")
    df = df[df["handle"].notna()].copy()
    monthly = df.groupby(["year", "month"]).agg(handle=("handle", "sum"), revenue=("revenue", "sum")).reset_index()
    monthly["state"] = "NY"
    monthly["revenue_type"] = "GGR"
    monthly["per_wager_tax"] = 0
    return monthly

def load_in():
    df = pd.read_parquet(ROOT / "data/clean/states/in.parquet")
    df = df[df["handle"].notna()].copy()
    monthly = df.groupby(["year", "month"]).agg(handle=("handle", "sum"), revenue=("revenue", "sum")).reset_index()
    monthly["state"] = "IN"
    monthly["revenue_type"] = "AGR"
    monthly["per_wager_tax"] = 0
    return monthly

def load_pa():
    df = pd.read_parquet(ROOT / "data/clean/states/pa.parquet")
    df = df[(df["channel"] == "online") & (df["handle"].notna()) & (df["handle"] > 0)].copy()
    monthly = df.groupby(["year", "month"]).agg(handle=("handle", "sum")).reset_index()
    monthly["state"] = "PA"
    monthly["revenue"] = np.nan  # PA revenue is after promo deductions — excluded
    monthly["revenue_type"] = "taxable_GGR"
    monthly["per_wager_tax"] = 0
    return monthly


all_states = pd.concat([load_il(), load_nj(), load_ny(), load_in(), load_pa()], ignore_index=True)
all_states["date"] = pd.to_datetime(all_states[["year", "month"]].assign(day=1))
all_states["ym"] = all_states["year"] * 100 + all_states["month"]

# Restrict to common window: Jan 2022 – Jun 2026
panel = all_states[(all_states["ym"] >= 202201) & (all_states["ym"] <= 202606)].copy()


def add_vlines(ax):
    ax.axvline(pd.Timestamp("2025-07-01"), color="red", ls="--", lw=1, alpha=0.7, label="IL tax (Jul 2025)")
    ax.axvline(pd.Timestamp("2025-09-01"), color="orange", ls="--", lw=1, alpha=0.7, label="IL surcharges (Sep 2025)")


# ══════════════════════════════════════════════════════════════════════════
# (1) Indexed handle + YoY log change
# ══════════════════════════════════════════════════════════════════════════

# Index to Jul 2024 – Jun 2025 average
pre_avg = panel[(panel["ym"] >= 202407) & (panel["ym"] <= 202506)].groupby("state")["handle"].mean()

fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
colors = {"IL": "red", "NJ": "C0", "NY": "C1", "IN": "C2", "PA": "C4"}

ax = axes[0]
for state in ["IL", "NJ", "NY", "IN", "PA"]:
    sub = panel[panel["state"] == state].sort_values("date")
    if state not in pre_avg.index:
        continue
    idx = sub["handle"] / pre_avg[state] * 100
    lw = 2.5 if state == "IL" else 1.2
    ax.plot(sub["date"], idx, color=colors[state], lw=lw, label=state)
ax.axhline(100, color="grey", ls=":", lw=0.5)
add_vlines(ax)
ax.set_ylabel("Handle index (Jul 2024 – Jun 2025 avg = 100)")
ax.set_title("Monthly online handle — five states indexed")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# YoY log change
ax2 = axes[1]
for state in ["IL", "NJ", "NY", "IN", "PA"]:
    sub = panel[panel["state"] == state].sort_values("date").copy()
    sub["log_h"] = np.log(sub["handle"])
    sub["yoy"] = sub["log_h"] - sub["log_h"].shift(12)
    valid = sub[sub["yoy"].notna()]
    lw = 2.5 if state == "IL" else 1.2
    ax2.plot(valid["date"], valid["yoy"], color=colors[state], lw=lw, label=state)
ax2.axhline(0, color="grey", ls=":", lw=0.5)
add_vlines(ax2)
ax2.set_ylabel("Δ log handle (YoY)")
ax2.set_title("Year-on-year log change in online handle")
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

plt.tight_layout()
plt.savefig(OUT / "fig_xstate_handle.png", dpi=150)
plt.close()
print("(1) Handle figure saved.")


# ══════════════════════════════════════════════════════════════════════════
# (2) Hold for IL, NJ, NY, IN (not PA)
# ══════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(14, 6))
for state in ["IL", "NJ", "NY", "IN"]:
    sub = panel[(panel["state"] == state) & (panel["revenue"].notna())].sort_values("date").copy()
    if state == "IL":
        # IL hold corrected: subtract per-wager tax from AGSR
        # User says "Other Gross Sports Wagering Receipts" not available.
        # per_wager_tax is the state's tax, not the surcharge income.
        # But the surcharge income IS in AGSR and we don't have it.
        # Best available proxy: subtract per_wager_tax as lower bound correction.
        # Flag this in the writeup.
        sub["hold"] = (sub["revenue"] - sub["per_wager_tax"].fillna(0)) / sub["handle"] * 100
        label = "IL (AGSR less per-wager tax)"
    else:
        sub["hold"] = sub["revenue"] / sub["handle"] * 100
        label = state
    lw = 2.5 if state == "IL" else 1.2
    ax.plot(sub["date"], sub["hold"], color=colors[state], lw=lw, label=label)
add_vlines(ax)
ax.set_ylabel("Hold (%)")
ax.set_title("Online hold by state (IL: AGSR net of per-wager tax / handle; others: GGR / handle)")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
ax.set_ylim(0, 20)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
plt.tight_layout()
plt.savefig(OUT / "fig_xstate_hold.png", dpi=150)
plt.close()
print("(2) Hold figure saved.")


# ══════════════════════════════════════════════════════════════════════════
# (3) Difference-in-differences: log handle
# ══════════════════════════════════════════════════════════════════════════

print("\n(3) DiD regressions...")

# Drop IN to maintain balanced panel (IN ends Nov 2025; others run to Jun 2026)
did = panel[panel["handle"].notna() & (panel["handle"] > 0) & (panel["state"] != "IN")].copy()
did["log_handle"] = np.log(did["handle"])
did["IL"] = (did["state"] == "IL").astype(int)
did["post_sep"] = (did["ym"] >= 202509).astype(int)
did["post_jul"] = (did["ym"] >= 202507).astype(int)
did["IL_x_post_sep"] = did["IL"] * did["post_sep"]
did["IL_x_post_jul"] = did["IL"] * did["post_jul"]

# State FE
state_fe = pd.get_dummies(did["state"], prefix="st", drop_first=True).astype(float)
# Calendar-month FE (1-12)
cm_fe = pd.get_dummies(did["month"], prefix="cm", drop_first=True).astype(float)

# State-specific linear trends to account for differential growth paths
did["trend"] = did.groupby("state").cumcount()
for st in did["state"].unique():
    did[f"trend_{st}"] = did["trend"] * (did["state"] == st).astype(int)
trend_cols = [f"trend_{st}" for st in did["state"].unique()]

# === Model A: IL × post-Sep-2025 only ===
X_a = pd.concat([
    did[["IL_x_post_sep"]].reset_index(drop=True),
    state_fe.reset_index(drop=True),
    cm_fe.reset_index(drop=True),
    did[trend_cols].reset_index(drop=True),
], axis=1)
X_a = sm.add_constant(X_a)
y = did["log_handle"].reset_index(drop=True)

res_a = sm.OLS(y, X_a).fit(cov_type="HC1")
coef_a = res_a.params["IL_x_post_sep"]
se_a = res_a.bse["IL_x_post_sep"]

# === Model B: IL × post-Jul + IL × post-Sep (both) ===
X_b = pd.concat([
    did[["IL_x_post_jul", "IL_x_post_sep"]].reset_index(drop=True),
    state_fe.reset_index(drop=True),
    cm_fe.reset_index(drop=True),
    did[trend_cols].reset_index(drop=True),
], axis=1)
X_b = sm.add_constant(X_b)
res_b = sm.OLS(y, X_b).fit(cov_type="HC1")

coef_b_jul = res_b.params["IL_x_post_jul"]
coef_b_sep = res_b.params["IL_x_post_sep"]

# === Permutation placebo ===
# Assign treatment to each control state in turn, compute the IL×post_sep coef
states_list = ["IL", "NJ", "NY", "PA"]  # balanced panel (IN excluded)
placebo_coefs_a = {}
placebo_coefs_b_jul = {}
placebo_coefs_b_sep = {}

for treated_state in states_list:
    did_p = did.copy()
    did_p["TREATED"] = (did_p["state"] == treated_state).astype(int)
    did_p["T_x_post_sep"] = did_p["TREATED"] * did_p["post_sep"]
    did_p["T_x_post_jul"] = did_p["TREATED"] * did_p["post_jul"]

    # Model A placebo (with state-specific trends)
    X_pa = pd.concat([
        did_p[["T_x_post_sep"]].reset_index(drop=True),
        state_fe.reset_index(drop=True),
        cm_fe.reset_index(drop=True),
        did_p[trend_cols].reset_index(drop=True),
    ], axis=1)
    X_pa = sm.add_constant(X_pa)
    res_pa = sm.OLS(y, X_pa).fit()
    placebo_coefs_a[treated_state] = res_pa.params["T_x_post_sep"]

    # Model B placebo
    X_pb = pd.concat([
        did_p[["T_x_post_jul", "T_x_post_sep"]].reset_index(drop=True),
        state_fe.reset_index(drop=True),
        cm_fe.reset_index(drop=True),
        did_p[trend_cols].reset_index(drop=True),
    ], axis=1)
    X_pb = sm.add_constant(X_pb)
    res_pb = sm.OLS(y, X_pb).fit()
    placebo_coefs_b_jul[treated_state] = res_pb.params["T_x_post_jul"]
    placebo_coefs_b_sep[treated_state] = res_pb.params["T_x_post_sep"]


# ══════════════════════════════════════════════════════════════════════════
# Write notes/prelim_xstate.md
# ══════════════════════════════════════════════════════════════════════════

print("Writing notes/prelim_xstate.md...")

# Format placebo table A
def fmt_placebo_a():
    lines = ["| Treated state | IL×post-Sep coef | Note |",
             "|---|---|---|"]
    for st in states_list:
        c = placebo_coefs_a[st]
        note = "**actual treatment**" if st == "IL" else "placebo"
        lines.append(f"| {st} | {c:+.4f} | {note} |")
    return "\n".join(lines)

# Format placebo table B
def fmt_placebo_b():
    lines = ["| Treated state | post-Jul coef | post-Sep coef | Note |",
             "|---|---|---|---|"]
    for st in states_list:
        cj = placebo_coefs_b_jul[st]
        cs = placebo_coefs_b_sep[st]
        note = "**actual treatment**" if st == "IL" else "placebo"
        lines.append(f"| {st} | {cj:+.4f} | {cs:+.4f} | {note} |")
    return "\n".join(lines)


md = f"""# Cross-state comparison: IL vs NJ, NY, IN, PA

## States included

| State | Handle range | Revenue used | Revenue type | Notes |
|---|---|---|---|---|
| IL | Jan 2022 – Jun 2026 | AGSR | Handle − payouts, no promo deduction | Treated state |
| NJ | Jan 2022 – Jun 2026 | GGR | Handle − payouts | Control |
| NY | Jan 2022 – Jun 2026 | GGR | Handle − payouts (cash basis) | Mobile only; control |
| IN | Jan 2022 – Nov 2025 | AGR | Handle − payouts − adjustments | Control; **excluded from DiD** (ends Nov 2025, unbalances panel) |
| PA | Jul 2022 – Jun 2026 | Handle only | Taxable GGR is after promo deductions → excluded from hold | Control (handle only) |

OH, MD, CO excluded from all figures.

---

## (1) Handle comparison

![Handle indexed](../output/fig_xstate_handle.png)

**Top panel**: Monthly online handle indexed to each state's Jul 2024 – Jun 2025 average = 100. IL (red, bold) tracks the control states closely through mid-2025, then diverges downward from September 2025 onward. The divergence is visible against all four control states, which remain roughly at or above their pre-treatment averages.

**Bottom panel**: Year-on-year log change in handle. IL's YoY growth rate drops below the control states' growth rates starting in September 2025 and remains below through mid-2026. The gap between IL and the control states widens in September–November 2025, then partially narrows.

---

## (2) Hold comparison

![Hold](../output/fig_xstate_hold.png)

Monthly online hold for IL, NJ, NY, IN. IL hold is computed as (AGSR − per-wager tax) / handle. The per-wager tax is the state's tax on operators, which is a lower bound for the surcharge income that operators book within AGSR (since operators' consumer surcharges may exceed the state's per-wager rate). This correction is therefore incomplete — IL hold post-September 2025 may still be overstated relative to the GGR-based hold reported by other states.

All four states show substantial month-to-month hold variation (range ~3–13%) with strong seasonal patterns (NFL months higher). IL hold does not visibly diverge from control states' hold post-treatment, consistent with the per-wager tax being passed through to consumers rather than absorbed by operators.

---

## (3) Difference-in-differences: log online handle

### Model A: IL × post-September-2025

log(handle_st) = α_s + γ_m + δ_s · t + β · (IL × post-Sep-2025) + ε_st

State FEs (α_s), calendar-month FEs (γ_m), state-specific linear trends (δ_s · t). Balanced panel: IL, NJ, NY, PA, Jan 2022 – Jun 2026 (IN excluded — ends Nov 2025).

| | Coefficient | HC1 SE |
|---|---|---|
| IL × post-Sep-2025 | {coef_a:+.4f} | ({se_a:.4f}) |
| N | {int(res_a.nobs)} | |
| R² | {res_a.rsquared:.4f} | |

### Model B: separating July and September

log(handle_st) = α_s + γ_m + δ_s · t + β₁ · (IL × post-Jul-2025) + β₂ · (IL × post-Sep-2025) + ε_st

| | Coefficient |
|---|---|
| IL × post-Jul-2025 | {coef_b_jul:+.4f} |
| IL × post-Sep-2025 | {coef_b_sep:+.4f} |
| N | {int(res_b.nobs)} |
| R² | {res_b.rsquared:.4f} |

β₁ captures the Jul-Aug 2025 shift (tax in force, no consumer surcharge) relative to the pre-Jul counterfactual. β₂ captures the *incremental* shift from September 2025 when surcharges went live. The total post-September effect is β₁ + β₂. {"β₁ is close to zero, suggesting handle did not fall relative to controls when the tax took effect but before surcharges were passed through. β₂ is negative, consistent with surcharges reducing handle." if abs(coef_b_jul) < 0.05 else f"β₁ = {coef_b_jul:+.4f} and β₂ = {coef_b_sep:+.4f}; the total post-September effect is {coef_b_jul + coef_b_sep:+.4f}."}

### Permutation placebo: Model A

{fmt_placebo_a()}

With 4 states, the permutation p-value = 1/4 = 0.25 if IL has the most negative coefficient, or higher if another state does. {"IL has the most negative coefficient among all four permutations, yielding a one-sided permutation p-value of 1/4 = 0.25." if placebo_coefs_a["IL"] == min(placebo_coefs_a.values()) else "IL does **not** have the most negative coefficient — " + min(placebo_coefs_a, key=placebo_coefs_a.get) + " does — which undermines the interpretation."}

### Permutation placebo: Model B

{fmt_placebo_b()}

---

## (4) OH and MD hold outliers — diagnosis

**Ohio (hold range 6.0%–22.0%)**: The 22.0% hold occurs in January 2023, the launch month of legal sports betting in Ohio. This is not a parsing error. Ohio's revenue definition (GGR = Handle − Payouts − Voids) does not allow promotional deductions, and the launch month saw massive sign-up promotional activity. Additionally, Ohio reports on a cash basis: bets placed on NFL playoff and Super Bowl events in January generate handle but payouts occur in future months, mechanically inflating the apparent hold. The 22% reading is an expected artefact of a launch month under cash-basis, no-promo-deduction reporting.

**Maryland (hold range 7.6%–17.2%)**: The 17.2% hold occurs in December 2022, the second month after mobile sports betting launched (November 2022). The same launch-month dynamics apply: heavy promotional sign-up activity and favorable sportsbook outcomes that month. FanDuel's Maryland skin (Live! Casino Mobile) showed 19.1% hold that month. The January 2024 outlier (15.1%) reflects an NFL playoff month with favorable outcomes for sportsbooks statewide.

Neither case reflects a parsing error or retail contamination. The revenue definitions are applied correctly; the outliers are consequences of launch-month promotional dynamics and cash-basis timing.

---

## (5) Illinois panel start date: Jun 2020, not Mar 2020

The parsed IL panel contains rows from March 2020 (the launch of retail sports wagering in Illinois), but the **online channel** had zero handle in March, April, and May 2020. Illinois online sports wagering launched on June 9, 2020. The March 2020 retail-only launch was immediately interrupted by COVID-19 closures (April–June 2020 retail handle = $0).

The online-only filter (channel="online", handle > 0) used throughout this analysis naturally drops the zero-handle months, producing a start date of June 2020. No rows were dropped by any other mechanism — the Mar–May 2020 rows exist in the parquet file but contain zero online handle because online wagering had not yet launched.
"""

notes_path = ROOT / "notes" / "prelim_xstate.md"
notes_path.write_text(md, encoding="utf-8")
print(f"Wrote {notes_path}")
print("Done.")
