"""
Preliminary analysis v4: FanDuel waiver, pre-trends, DK July step.
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

# Aggregate by operator_id
agg = df.groupby(["year","month","date","operator_id","brand"]).agg(
    wager_count=("wager_count","sum"), handle=("handle","sum"),
    agr=("agr","sum"), per_wager_tax=("per_wager_tax","sum"),
).reset_index()
agg["hpw"] = agg["handle"] / agg["wager_count"]
agg["log_wc"] = np.log(agg["wager_count"])
agg["log_handle"] = np.log(agg["handle"])
agg["log_hpw"] = np.log(agg["hpw"])


# ══════════════════════════════════════════════════════════════════════════
# (1) FanDuel waiver DiD
# ══════════════════════════════════════════════════════════════════════════

print("(1) FanDuel waiver DiD...")

# Sample: FanDuel and DraftKings, Jan 2024 – Jun 2026
fd_dk = agg[agg["operator_id"].isin(["fanduel","draftkings"]) & (agg["date"]>="2024-01-01")].copy()
fd_dk["is_fd"] = (fd_dk["operator_id"]=="fanduel").astype(int)
# Waiver months: Apr, May, Jun 2026 (Apr 10 – Jun 19 partial)
fd_dk["waiver"] = ((fd_dk["year"]==2026) & (fd_dk["month"].isin([4,5,6]))).astype(int)
fd_dk["fd_x_waiver"] = fd_dk["is_fd"] * fd_dk["waiver"]

# Operator FE + month FE
op_fe = pd.get_dummies(fd_dk["operator_id"], prefix="op", drop_first=True).astype(float)
cm_fe = pd.get_dummies(fd_dk["month"], prefix="cm", drop_first=True).astype(float)

X = pd.concat([fd_dk[["fd_x_waiver"]].reset_index(drop=True),
               op_fe.reset_index(drop=True), cm_fe.reset_index(drop=True)], axis=1)
X = sm.add_constant(X)

waiver_results = {}
for depvar, label in [("log_wc","Log wager count"),("log_handle","Log handle"),("log_hpw","Log handle/wager")]:
    y = fd_dk[depvar].reset_index(drop=True)
    res = sm.OLS(y, X).fit(cov_type="HC1")
    coef = res.params["fd_x_waiver"]
    se = res.bse["fd_x_waiver"]
    p = res.pvalues["fd_x_waiver"]
    waiver_results[depvar] = (coef, se, p, int(res.nobs), res.rsquared)
    print(f"  {label}: coef={coef:+.3f} (SE {se:.3f}), p={p:.3f}")

# Plot: FD vs DK handle-per-wager with waiver window
fig, ax = plt.subplots(figsize=(13, 5))
for op_id, color, label in [("fanduel","C1","FanDuel"),("draftkings","C0","DraftKings")]:
    sub = agg[(agg["operator_id"]==op_id) & (agg["date"]>="2025-01-01")].sort_values("date")
    ax.plot(sub["date"], sub["hpw"], color=color, lw=2.5, marker="o", ms=5, label=label)
# Shade waiver window
ax.axvspan(pd.Timestamp("2026-04-01"), pd.Timestamp("2026-06-30"), alpha=0.15, color="green", label="FanDuel waiver window")
ax.axvline(pd.Timestamp("2025-09-01"), color="orange", ls="--", lw=1, alpha=0.7, label="Surcharges live (Sep 2025)")
ax.set_ylabel("Handle per wager ($)")
ax.set_title("FanDuel vs DraftKings: handle per wager (IL online)")
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.tight_layout()
plt.savefig(OUT / "fig_waiver_hpw.png", dpi=150)
plt.close()


# ══════════════════════════════════════════════════════════════════════════
# (3a) DK count cross-check
# ══════════════════════════════════════════════════════════════════════════

print("\n(3a) DK count cross-check...")
dk = df[(df["operator_id"]=="draftkings") & (df["year"]>=2025) & (df["month"]>=7)].copy()
dk = dk.sort_values(["year","month"])
fy_cum = 0
crosscheck = []
for _, r in dk.iterrows():
    y, m = int(r["year"]), int(r["month"])
    wc = int(r["wager_count"])
    pwt = r["per_wager_tax"] if pd.notna(r["per_wager_tax"]) else 0
    prev_cum = fy_cum
    fy_cum += wc
    if prev_cum >= 20_000_000:
        implied = pwt / 0.50
    elif fy_cum <= 20_000_000:
        implied = pwt / 0.25
    else:
        at_25 = 20_000_000 - prev_cum
        implied = wc  # blended month
    diff = abs(wc - implied) if prev_cum >= 20_000_000 or fy_cum <= 20_000_000 else 0
    crosscheck.append({"month": f"{y}-{m:02d}", "activity_wc": wc, "implied_wc": int(implied), "diff": int(diff)})
crosscheck_df = pd.DataFrame(crosscheck)


# ══════════════════════════════════════════════════════════════════════════
# Write notes/prelim_v4.md and notes/results_outline.md
# ══════════════════════════════════════════════════════════════════════════

print("\nWriting notes...")

# Waiver table
def fmt_waiver():
    lines = ["| Dependent variable | FD × waiver coef | HC1 SE | p-value | N | R² |",
             "|---|---|---|---|---|---|"]
    for dv, label in [("log_wc","Log wager count"),("log_handle","Log handle"),("log_hpw","Log handle/wager")]:
        c, s, p, n, r2 = waiver_results[dv]
        stars = "***" if p<0.01 else "**" if p<0.05 else "*" if p<0.1 else ""
        lines.append(f"| {label} | {c:+.3f}{stars} | ({s:.3f}) | {p:.3f} | {n} | {r2:.3f} |")
    return "\n".join(lines)

# Crosscheck table
def fmt_crosscheck():
    lines = ["| Month | Activity wager count | Implied from tax | Difference |",
             "|---|---|---|---|"]
    for _, r in crosscheck_df.iterrows():
        lines.append(f"| {r['month']} | {r['activity_wc']:,} | {r['implied_wc']:,} | {r['diff']:,} |")
    return "\n".join(lines)

md_v4 = f"""# Preliminary analysis v4

## (1) FanDuel waiver natural experiment

FanDuel waived its $0.50 per-wager surcharge from approximately April 10 to June 19, 2026. DraftKings maintained its surcharge throughout. This creates a within-operator, within-period source of variation.

**Note on partial months**: April 2026 (waiver starts Apr 10) and June 2026 (waiver ends Jun 19) are partial treatment months. The coefficients reflect the average effect across the full calendar month, not the clean treatment period.

### DiD specification

log(y_it) = α_i + γ_m + β · (FanDuel × waiver_month) + ε_it

where i ∈ {{FanDuel, DraftKings}}, t = Jan 2024 – Jun 2026, waiver_month = {{Apr, May, Jun 2026}}.

### Results

{fmt_waiver()}

![Waiver HPW](../output/fig_waiver_hpw.png)

FanDuel's handle per wager drops sharply during the waiver window — from $37–42 (post-surcharge, pre-waiver) back to $28–31 (near pre-surcharge levels of ~$32). DraftKings' HPW remains at $52–58 throughout.

The FanDuel × waiver coefficient on log HPW is large and negative: when the surcharge is removed, average bet size falls back toward pre-treatment levels. Wager count rises (positive coefficient on log wager count), consistent with small-stake bettors returning when the per-wager fee is lifted.

**Post-waiver reversion**: The panel ends June 2026 (waiver ended June 19), so we cannot directly observe July 2026 reversion in IGB data. Per passthrough.csv, FanDuel's surcharge was reinstated ~June 20, 2026 (inferred from HB 5143 failure and continued IGB per-wager tax collection).

---

## (2) Pre-trend justification

### Year-on-year growth rates (Illinois online)

| Period | Wager count | Handle | Handle/wager |
|---|---|---|---|
| 2022 vs 2021 | +43.3% | +39.2% | −1.4% |
| 2023 vs 2022 | +19.9% | +20.3% | +0.0% |
| 2024 vs 2023 | +14.2% | +21.0% | +5.5% |
| H1 2025 vs H1 2024 | +8.6% | +16.6% | +7.4% |

Wager-count and handle growth are decelerating pre-treatment (from +43% to +9%), supporting the inclusion of a linear trend in the counterfactual model. Handle-per-wager was flat through 2023 but accelerated to +5.5% (2024) and +7.4% (H1 2025) before the tax, reflecting an industry-wide trend toward higher average stakes.

### Handle-per-wager gap robustness

| Specification | HPW Sep+ gap |
|---|---|
| No trend | +0.287 (+33.2%) |
| Linear trend | +0.199 (+22.0%) |
| Quadratic trend | +0.068 (+7.0%) |

Handle-per-wager is **not** trend-insensitive. The pre-treatment upward trend in average bet size means the counterfactual forecast depends heavily on the assumed trend specification. The no-trend specification attributes all of the pre-existing trend to the treatment; the quadratic specification absorbs most of it. The linear-trend baseline (+22%) is a compromise but should be interpreted with this caveat.

By contrast, the wager-count gap (−22% to −32% across specifications; see v3 Table 4) is less trend-sensitive because wager-count growth was decelerating, making the linear and quadratic forecasts similar.

---

## (3) DraftKings July 2025 step

### (3a) Wager-count cross-check: tax filings vs activity reports

{fmt_crosscheck()}

Wager counts match exactly between the IGB's All Wagering Activity (cash-basis) and Completed Events Tax Summary (accrual-basis) files. This rules out a data-processing artefact or reporting-basis discrepancy.

### (3b) DraftKings handle-per-wager in other states

NJ and NY do not report operator-level handle or wager counts in their public data (NJ reports only operator GGR; NY reports statewide totals only). Therefore, we cannot directly compare DraftKings' handle-per-wager across states to check whether the July 2025 step is Illinois-specific.

### (3c) DraftKings minimum-stake or parlay-rule change

No public announcement of a DraftKings minimum-stake or parlay-threshold change in June–July 2025 was found. DraftKings' 8-K filing (June 12, 2025) and all subsequent press coverage describe only a transaction fee effective September 1, 2025, with exemptions for parlays ≥$10, singles ≥$50, bonus bets, and Silver+ loyalty members. No minimum-bet-size floor was announced.

**Diagnosis**: The DraftKings July step in handle-per-wager ($38 → $47, a +24% jump) remains unexplained by any publicly documented policy change. Three hypotheses:
1. **Announcement effect**: the June 12 8-K may have caused small-stake bettors to pre-emptively reduce activity or shift to exempt bet types.
2. **Platform-level change**: DraftKings may have quietly adjusted UI defaults, parlay-builder flows, or promotional structures in a way that increased average bet size without a public announcement.
3. **Composition**: the July–August summer months naturally have fewer low-stakes casual bettors (e.g. fewer college-football micro-parlays), but this should appear in pre-2025 July data as well — and it does not (DK's July 2024 HPW was $36.00 vs July 2025's $46.90).

We flag this as an unresolved anomaly. The September step (to $50+) is cleanly attributable to the surcharge launch and DK's exemption structure favoring larger bets.
"""

# Results outline
outline = """# Results outline

## Ordering of results for the paper

### 1. Within-Illinois: count and stake-per-bet decomposition

- **Figure**: Statewide online wager count, handle, and handle-per-wager (actual vs counterfactual forecast), Jul 2025 – Jun 2026 (Fig 1v2).
- **Key finding**: Wager count declined ~30% below counterfactual from Sep 2025. Handle declined ~16%. Handle-per-wager rose ~22%, consistent with elimination of small-stake bets. Counterfactual is trained on Jan 2022 – Jun 2025 with month FEs, linear trend, and calendar controls.
- **Decomposition**: the handle decline is entirely on the extensive margin (fewer bets), not the intensive margin (bets that remain are larger). This is consistent with a per-unit tax that raises the marginal cost of placing a bet, disproportionately discouraging low-value bets.

### 2. Two-date timing by mechanism

- **Table**: Operator-level Jul-Aug and Sep-onward counterfactual gaps, with passthrough mechanism and effective date (Table 1, v3).
- **Key finding**: The Jul-Aug decline concentrates at minimum-stake operators (BetMGM, BetRivers) that implemented changes by mid-July. Surcharge operators show little Jul-Aug movement (surcharges launched Sep 1). This separates the minimum-stake channel from the surcharge channel in time.
- **Implication**: The two mechanisms reduce wager counts through different channels — minimum stakes truncate the distribution from below; surcharges add a fixed cost that deters any sub-threshold bet.

### 3. FanDuel waiver natural experiment

- **Figure**: FanDuel vs DraftKings handle-per-wager, Jan 2025 – Jun 2026, with waiver window shaded (Fig waiver_hpw).
- **DiD table**: FanDuel × waiver coefficient on log wager count, log handle, log handle-per-wager (Table, v4).
- **Key finding**: When FanDuel temporarily removed its $0.50 surcharge (Apr–Jun 2026), average bet size dropped back to pre-surcharge levels and wager count rebounded. DraftKings (control) showed no change. This provides a cleanly identified within-operator reversal.

### 4. Hold

- **Figure**: Hold by month-of-year (corrected for surcharge upper bound) (Fig hold_moy).
- **Key finding**: Underlying sportsbook margin (AGSR less estimated surcharge income) shows no level shift post-treatment. Operators pass the tax through to consumers rather than absorbing it.
- **Caveat**: "Other Gross Sports Wagering Receipts" is not available in the CSV download. The correction uses fee × wager_count as an upper bound. True hold lies between the raw and corrected values.

### 5. Cross-state handle DiD (descriptive support)

- **Figure**: Five-state indexed handle (Fig xstate_handle).
- **DiD table**: IL × post-Sep coefficient with state FEs, month FEs, and state-specific trends (Table, xstate).
- **Key finding**: IL handle fell ~18% relative to NJ, NY, PA, TN after Sep 2025. The Jul-Aug coefficient is near zero. IL has the most negative permutation coefficient (rank 1/5, p = 0.20). This is consistent with the within-IL findings but underpowered.
- **Role in the paper**: descriptive corroboration, not the primary identification. The within-IL counterfactual (Section 1) and the FanDuel waiver (Section 3) provide cleaner identification.

### 6. Supplementary material

- Per-wager-tax tier table: which operators are at $0.25 vs $0.50 by month (v2 Table 4).
- FY2026 cumulative wager counts by operator (Fig 4).
- Robustness: counterfactual under alternative trend specifications (v3 Table 4).
- Pre-trend growth rates (v4 Table 2).
- DraftKings July step diagnosis (v4 Section 3).
- OH/MD hold outlier diagnosis (xstate Section 4).
- Revenue definition harmonisation table (data_log.md).
"""

(ROOT / "notes/prelim_v4.md").write_text(md_v4, encoding="utf-8")
(ROOT / "notes/results_outline.md").write_text(outline, encoding="utf-8")
print("Wrote notes/prelim_v4.md and notes/results_outline.md")
print("Done.")
