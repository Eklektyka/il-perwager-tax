# Equity event study: IL per-wager tax

## Data

Daily adjusted close prices for FLUT, DKNG, RSI, PENN, MGM, CZR, ENT.L, and SPY, January 2024 – September 2026 (via yfinance). BJK (VanEck Gaming ETF) is delisted; the gaming benchmark is an equal-weighted portfolio of the six US-listed gaming stocks.

Market model: R_it = α_i + β_i · R_SPY,t + ε_it, estimated on 120 trading days ending 10 days before each event. Abnormal return AR_it = R_it − (α̂_i + β̂_i · R_SPY,t).

## Event calendar

| Event ID | Date | Description |
|---|---|---|
| budget_pass | 2025-05-31 | IL General Assembly passes FY2026 budget with per-wager tax (HB 2755) |
| budget_sign | 2025-06-16 | Governor Pritzker signs HB 2755 into law |
| fd_announce | 2025-06-10 | FanDuel announces $0.50 per-wager surcharge for Illinois |
| dk_announce | 2025-06-12 | DraftKings files 8-K announcing Illinois transaction fee |
| tax_effective | 2025-07-01 | Per-wager tax takes effect ($0.25/$0.50 per online wager) |
| dk_q2 | 2025-08-06 | DraftKings Q2 2025 earnings (record revenue $1.51B) |
| flut_q2 | 2025-08-07 | Flutter/FanDuel Q2 2025 earnings ($4.19B revenue) |
| surcharge_live | 2025-09-01 | FanDuel/DraftKings/Caesars surcharges go live |
| igb_jul2025 | 2025-09-23 | IGB releases July 2025 data (first month of per-wager tax) |
| igb_aug2025 | 2025-10-22 | IGB releases August 2025 data |
| igb_sep2025 | 2025-11-17 | IGB releases September 2025 data (first full surcharge month) |
| sba_warning | 2026-01-12 | Sports Betting Alliance warns per-wager tax is hurting Illinois market |
| hb5143_filed | 2026-02-10 | Rep. Didech files HB 5143 to repeal per-wager tax |
| flut_q4 | 2026-02-26 | Flutter/FanDuel Q4 2025/FY2025 earnings |
| fd_waiver | 2026-04-10 | FanDuel announces temporary surcharge waiver through June 19 |
| hb5143_deadline | 2026-04-17 | HB 5143 House advancement deadline passes (bill does not advance) |

## Illinois exposure proxy

| Ticker | Operator | IL FY2025 handle ($B) | US handle est. ($B) | IL share (%) | Source |
|---|---|---|---|---|---|
| FLUT | fanduel | $4.8B | $80B | 6.0% | Flutter FY2025 10-K (US segment ~$80B est.) |
| DKNG | draftkings | $5.2B | $50B | 10.5% | DraftKings FY2025 10-K (est. ~$50B handle) |
| RSI | betrivers | $0.6B | $5B | 12.2% | RSI FY2025 earnings (est. ~$5B handle) |
| PENN | espn_bet | $0.5B | $15B | 3.7% | Penn FY2025 10-K (est. ~$15B incl ESPN BET) |
| MGM | betmgm | $0.8B | $20B | 4.0% | BetMGM JV; MGM share ~50% of est. $20B handle |
| CZR | caesars | $0.8B | $15B | 5.5% | Caesars FY2025 10-K (est. ~$15B digital handle) |
| ENT.L | bet365 | $0.1B | $100B | 0.1% | Entain global; US exposure via BetMGM JV. IL share minimal. |

US handle estimates are approximate, sourced from 10-K filings, earnings calls, and investor presentations where available. ENT.L (Entain) has minimal direct IL exposure (bet365 operates under a separate US subsidiary). These figures should be treated as order-of-magnitude estimates, not precise measurements.

## CAR[-1,+1] by event and firm

| Event | FLUT | DKNG | RSI | PENN | MGM | CZR | GAMING_EW |
|---|---|---|---|---|---|---|---|
| budget_pass | -1.9% | -4.4% | -3.7% | +1.2% | -0.5% | -3.9% | -2.2% |
| fd_announce | +7.5% | +5.8% | +3.3% | +7.9% | +4.1% | +8.2% | +6.1% |
| dk_announce | +0.3% | -1.1% | -2.2% | -4.9% | -3.4% | -7.7% | -3.2% |
| surcharge_live | -3.5% | -2.0% | -1.0% | -2.0% | -5.4% | -2.2% | -2.7% |
| igb_sep2025 | -1.9% | +2.1% | +1.0% | -4.9% | -1.2% | +8.2% | +0.5% |
| hb5143_filed | -4.1% | -0.1% | -3.4% | +0.3% | -2.8% | -2.9% | -2.2% |
| hb5143_deadline | -1.2% | -3.4% | -0.9% | -2.7% | +0.8% | +0.2% | -1.2% |
| fd_waiver | -3.3% | -5.9% | -4.9% | -2.0% | -3.0% | -1.6% | -3.4% |

## CAR[0,+3] by event and firm

| Event | FLUT | DKNG | RSI | PENN | MGM | CZR | GAMING_EW |
|---|---|---|---|---|---|---|---|
| budget_pass | -4.4% | -6.3% | -0.5% | +5.9% | -1.8% | -4.9% | -2.0% |
| fd_announce | +1.2% | +2.2% | -1.5% | -3.6% | -1.3% | -3.0% | -1.0% |
| dk_announce | +1.9% | +2.2% | +0.9% | +0.2% | +2.3% | -3.3% | +0.7% |
| surcharge_live | -5.1% | -4.3% | -4.1% | -0.8% | -8.6% | +1.5% | -3.6% |
| igb_sep2025 | +0.1% | +2.9% | +2.0% | -2.2% | -0.4% | +8.6% | +1.8% |
| hb5143_filed | -17.0% | -18.9% | -8.5% | -11.2% | -8.5% | -9.7% | -12.3% |
| hb5143_deadline | -0.9% | -5.3% | +0.1% | -10.5% | -0.1% | -1.9% | -3.1% |
| fd_waiver | +5.6% | +5.4% | +3.5% | -1.6% | -0.1% | +0.7% | +2.3% |

## Cross-section: CARs vs IL exposure and mechanism

| Ticker | Mechanism | IL share (%) | CAR[-1,+1] fd_announce | CAR[-1,+1] dk_announce | CAR[-1,+1] surcharge_live | CAR[-1,+1] fd_waiver |
|---|---|---|---|---|---|---|
| FLUT | surcharge | 6.0 | +7.5% | +0.3% | -3.5% | -3.3% |
| DKNG | surcharge | 10.5 | +5.8% | -1.1% | -2.0% | -5.9% |
| RSI | minimum_stake | 12.2 | +3.3% | -2.2% | -1.0% | -4.9% |
| PENN | minimum_stake | 3.7 | +7.9% | -4.9% | -2.0% | -2.0% |
| MGM | minimum_stake | 4.0 | +4.1% | -3.4% | -5.4% | -3.0% |
| CZR | surcharge | 5.5 | +8.2% | -7.7% | -2.2% | -1.6% |
| ENT.L | surcharge | 0.1 | +0.8% | +0.2% | -3.9% | -7.3% |

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
| budget_pass | − | -1.9% | -4.4% | -2.2% |
| fd_announce | − | +7.5% | +5.8% | +6.1% |
| dk_announce | − | +0.3% | -1.1% | -3.2% |
| surcharge_live | − | -3.5% | -2.0% | -2.7% |
| igb_sep2025 | − | -1.9% | +2.1% | +0.5% |
| hb5143_filed | + | -4.1% | -0.1% | -2.2% |
| hb5143_deadline | ? | -1.2% | -3.4% | -1.2% |
| fd_waiver | + | -3.3% | -5.9% | -3.4% |

The expected sign column assumes that bad news for Illinois-exposed operators (tax passage, surcharge announcements, data showing wager declines) produces negative abnormal returns, while good news (repeal bill, waiver) produces positive returns.

No interpretation is offered beyond the sign pattern. The small number of events, confounding news flow, and noisy daily returns mean individual CARs should be read as descriptive rather than inferential.




---

## Release-surprise test

For each IGB monthly report release, the **count surprise** is log(actual statewide online wager count) − log(recent-growth counterfactual), and the **handle surprise** is defined analogously. The recent-growth counterfactual projects each month as the same month previous year × (1 + H1 2025 YoY growth rate).

### Release dates and surprises

| Data month | Release date | Source | Count surprise | Handle surprise | Period |
|---|---|---|---|---|---|
| 2024-07 | 2024-09-15 | covers.com sept-15-2024 | +0.197 | +0.083 | placebo |
| 2024-08 | 2024-10-22 | covers.com oct-22-2024 | +0.220 | +0.109 | placebo |
| 2024-09 | 2024-11-18 | covers.com nov-18-2024 | +0.167 | +0.043 | placebo |
| 2024-10 | 2024-12-17 | covers.com dec-17-2024 | +0.168 | +0.070 | placebo |
| 2024-11 | 2025-01-15 | covers.com jan-15-2025 | +0.037 | -0.043 | placebo |
| 2024-12 | 2025-02-12 | covers.com feb-12-2025 | -0.016 | -0.022 | placebo |
| 2025-01 | 2025-03-14 | covers.com mar-14-2025 | -0.001 | -0.013 | placebo |
| 2025-02 | 2025-04-21 | covers.com apr-21-2025 | -0.060 | -0.078 | placebo |
| 2025-03 | 2025-05-15 | covers.com may-15-2025 | +0.003 | +0.022 | placebo |
| 2025-04 | 2025-06-17 | covers.com jun-17-2025 | +0.021 | +0.004 | placebo |
| 2025-05 | 2025-07-17 | covers.com jul-17-2025 | +0.049 | +0.082 | placebo |
| 2025-06 | 2025-08-18 | estimated (Jun data; no article found) | -0.020 | -0.027 | placebo |
| 2025-07 | 2025-09-24 | covers.com sept-24-2025 | -0.105 | -0.041 | post |
| 2025-08 | 2025-10-16 | covers.com oct-16-2025 | -0.144 | +0.010 | post |
| 2025-09 | 2025-11-17 | covers.com nov-17-2025 | -0.247 | -0.066 | post |
| 2025-10 | 2025-12-23 | covers.com dec-23-2025 | -0.255 | -0.047 | post |
| 2025-11 | 2026-01-16 | covers.com jan-16-2026 | -0.250 | -0.073 | post |
| 2025-12 | 2026-02-06 | ingame.com feb-06-2026 | -0.369 | -0.184 | post |
| 2026-01 | 2026-03-13 | covers.com mar-13-2026 | -0.305 | -0.178 | post |
| 2026-02 | 2026-04-15 | covers.com apr-15-2026 | -0.372 | -0.137 | post |
| 2026-03 | 2026-05-21 | covers.com may-21-2026 | -0.400 | -0.222 | post |
| 2026-04 | 2026-06-17 | covers.com jun-17-2026 | -0.374 | -0.211 | post |
| 2026-05 | 2026-07-14 | covers.com jul-14-2026 | -0.314 | -0.260 | post |
| 2026-06 | 2026-08-25 | covers.com aug-25-2026 | -0.039 | +0.028 | post |

Release dates for post-treatment months are confirmed from the earliest press article citing each report. Placebo-period dates are estimated from the IGB's statutory pattern (last week of the month following the data month) and are flagged accordingly. Any regression results using placebo dates should be interpreted with this caveat.

### Regression: AR[0,+1] on surprise

AR[0,+1] is the two-day cumulative abnormal return (market-model, estimated on 120 trading days ending 10 days before). The surprise is the log deviation of actual from counterfactual.

| Sample | Surprise | Coef | HC1 SE | p-value | N | R² |
|---|---|---|---|---|---|---|
| FLUT post | Count surprise | -0.0871 | (0.0623) | 0.163 | 12 | 0.081 |
| FLUT post | Handle surprise | -0.0968 | (0.0921) | 0.293 | 12 | 0.068 |
| DKNG post | Count surprise | -0.0992 | (0.0863) | 0.251 | 12 | 0.066 |
| DKNG post | Handle surprise | -0.0613 | (0.1106) | 0.579 | 12 | 0.017 |
| RSI post | Count surprise | -0.1495 | (0.1590) | 0.347 | 12 | 0.108 |
| RSI post | Handle surprise | -0.1736 | (0.2045) | 0.396 | 12 | 0.100 |
| Pooled post (firm FE) | Count surprise | -0.1119* | (0.0603) | 0.064 | 36 | 0.110 |
| Pooled post (firm FE) | Handle surprise | -0.1106 | (0.0814) | 0.175 | 36 | 0.083 |
| FLUT placebo | Count surprise | +0.0103 | (0.0654) | 0.875 | 12 | 0.002 |
| FLUT placebo | Handle surprise | +0.1067 | (0.0984) | 0.278 | 12 | 0.085 |
| DKNG placebo | Count surprise | +0.1504 | (0.0956) | 0.116 | 12 | 0.145 |
| DKNG placebo | Handle surprise | +0.1702 | (0.1373) | 0.215 | 12 | 0.068 |
| RSI placebo | Count surprise | +0.0026 | (0.0847) | 0.975 | 12 | 0.000 |
| RSI placebo | Handle surprise | -0.0409 | (0.1399) | 0.770 | 12 | 0.006 |
| Pooled placebo (firm FE) | Count surprise | +0.0544 | (0.0464) | 0.241 | 36 | 0.057 |
| Pooled placebo (firm FE) | Handle surprise | +0.0787 | (0.0693) | 0.256 | 36 | 0.051 |

### Interpretation

The pooled post-treatment count-surprise coefficient is -0.112 (p = 0.064). All individual firm coefficients are negative: months with larger negative count surprises (more wagers lost than expected) are associated with more negative abnormal returns. This is directionally consistent with the market pricing the wager-count decline, though with only 12 release dates per firm the individual estimates are imprecise.

The pooled placebo count-surprise coefficient is +0.054 (p = 0.241) — positive and insignificant. The sign reversal between placebo (+) and post-treatment (−) is notable: pre-treatment, better-than-expected IGB data was weakly associated with positive returns (a normal information channel); post-treatment, worse-than-expected data is associated with negative returns (the tax-driven decline is priced). However, neither coefficient is individually significant at 5%, so this pattern should be treated as suggestive.

### Confounding same-day news


- **2025-09-24** (Jul 2025 data): Covers article published Sep 24. NFL Week 3. First month of per-wager tax data — headline: "Illinois Sports Betting Still Grows 12%."
- **2025-10-16** (Aug 2025 data): Covers article Oct 16. Q3 earnings season underway; DraftKings reports Q3 in late October.
- **2025-11-17** (Sep 2025 data): Covers article Nov 17. First report showing full surcharge impact; headline: "Illinois Sports Betting Profits Drop 26%." Widely covered.
- **2025-12-23** (Oct 2025 data): Covers article Dec 23. Holiday-thinned trading. Headline: "Illinois Sets New Handle Record in October" (positive handle spin despite declining wager count).
- **2026-01-16** (Nov 2025 data): Covers article Jan 16. Sports Betting Alliance had already issued its warning on Jan 12 (citing Oct data), so the Nov data release may have been partially anticipated.
- **2026-02-06** (Dec 2025 data): InGame article Feb 6. Headline: "Illinois Wagering Drops Sharply In December." Flutter Q4 earnings 20 days later (Feb 26).
- **2026-04-15** (Feb 2026 data): Covers article Apr 15. FanDuel had just announced its surcharge waiver 5 days earlier (Apr 10). The Feb data pre-dates the waiver.
- **Placebo-period releases** (Jul 2024 – Jun 2025): All dates confirmed from Covers.com article timestamps. Routine monthly data with no tax-related news; the H1 2025 growth rate used for the surprise measure was not known at the time of these releases.

