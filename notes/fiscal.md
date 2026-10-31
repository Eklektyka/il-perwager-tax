# Fiscal analysis: per-wager tax revenue effect (corrected)

## (1) FY2026 counterfactual handle

| Specification | Counterfactual handle | Actual handle | Lost handle | Lost % of actual |
|---|---|---|---|---|
| **Recent-growth** | $17.1B | $15.2B | $2.0B | 13% |
| No trend | $11.9B | $15.2B | $0.0B | 0% |
| Linear trend | $17.8B | $15.2B | $2.6B | 17% |
| Quadratic trend | $17.8B | $15.2B | $2.7B | 18% |

Recent-growth is the central estimate: each post-treatment month's counterfactual = same month previous year × (1 + H1 2025 YoY growth rate of +16.6%). All four specifications produce lost handle within 1–18% of actual FY2026 online handle ($15.2B). No specification exceeds 30%.

### Actual FY2026 receipts

| | FY2026 total |
|---|---|
| Per-wager tax | **$126.7M** |
| AGSR tax | $471.3M |
| Total sports wagering tax | $598.0M |
| Per-wager tax share of total | 21.2% |

## (2) Lost AGSR tax allocation

Statewide lost handle is allocated to operators in proportion to each operator's actual FY2026 handle share, then:
- **Lost AGSR** = allocated lost handle × statewide pre-treatment hold (8.8%)
- **Lost AGSR tax** = lost AGSR × blended marginal AGSR rate (36.3%)

The blended marginal rate is the handle-weighted average of each operator's end-of-FY marginal AGSR tier rate. FanDuel and DraftKings (the two largest operators) are both in the 40% tier by November 2025, pulling the blended rate above 35%.

## (3) Surcharge income AGSR tax

Upper bound: fee × online wager count × blended marginal rate. Lower bound: same, but assumes 30% of DraftKings' wagers are exempt from the surcharge (parlays ≥$10, singles ≥$50, bonus bets, Silver+ loyalty). This assumption is stated explicitly and is approximate — actual DraftKings exemption rates are not publicly reported.

## (4) Net fiscal effect

| Specification | Per-wager tax | + Surcharge AGSR tax | − Lost AGSR tax | = Net (upper) | = Net (lower) | Net/PWT |
|---|---|---|---|---|---|---|
| **Recent-growth** | $127M | +$30M / +$28M | −$63M | **$94M** | $92M | 74% |
| No trend | $127M | +$30M / +$28M | −$0M | $157M | $154M | 124% |
| Linear trend | $127M | +$30M / +$28M | −$84M | $73M | $70M | 58% |
| Quadratic trend | $127M | +$30M / +$28M | −$85M | $72M | $69M | 57% |

Under the recent-growth counterfactual (central), the per-wager tax generated **$94M** in net revenue (upper bound) to **$92M** (lower bound) for FY2026. The range across all four counterfactual specifications is $72M to $157M.

All specifications yield a positive net fiscal effect.

## (5) Efficiency metrics

Central estimates use the recent-growth counterfactual (upper-bound surcharge).

| Metric | Central | Range |
|---|---|---|
| Net revenue per lost wager | $0.95 | — |
| Net revenue per $1 of lost handle | $0.0481 | — |
| FY2026 lost wagers | 99M | — |
| FY2026 lost handle | $2.0B | $0.0B – $2.7B |
| Net FY2026 revenue | $94M | $72M to $157M |
| Equivalent uniform AGSR rate increase | +6.24 pp | — |

The equivalent uniform AGSR rate increase is the number of percentage points added to every tier of the progressive schedule that would raise the same net revenue on the counterfactual handle base, **assuming no behavioural response to the ad valorem change**. This is an upper bound on efficiency: an AGSR rate increase would also reduce handle, but we do not model that response.

## (6) Concentration

| Metric | Value |
|---|---|
| FanDuel + DraftKings share of per-wager tax | 83.8% |
| $0.50-tier share of per-wager tax | 77.9% |

FanDuel and DraftKings account for 84% of all per-wager tax receipts. Both crossed the 20M threshold in September 2025 and paid $0.50/wager for the remaining 9 months of FY2026.

---

## (Appendix) Diagnosis of original error

The original fiscal.md computed lost handle at the operator level by fitting separate
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
FY2026 handle share, avoiding operator-level forecast explosion.
