# Data Log

## Source: Illinois Gaming Board — Sports Wagering Monthly Reports

- **URL**: https://igbapps.illinois.gov/SportsReports_AEM.aspx (embedded in https://igb.illinois.gov/sports-wagering/sports-reports.html)
- **Download date**: 2026-09-09
- **Description**: Monthly sports wagering data from March 2020 through June 2026. Two report types downloaded per month as CSV:
  1. **All Wagering Activity Detail** (`{YYYY-MM}_activity.csv`): wager counts and handle by sport level × channel × operator. Columns: Sport Level, Location Type, Licensee, Tier 1 Wagers, Tier 1 Handle, Tier 2 Wagers, Tier 2 Handle.
  2. **Completed Events Tax Summary** (`{YYYY-MM}_tax.csv`): AGR, taxes, and per-wager tax by channel × operator. Columns: Location Type, Licensee, State AGR, State Tax, Cook County AGR, Cook County Tax, Sports Wager Tax, Expired Tickets, Total Payment.

### Layout versions

**Single layout throughout** (March 2020 – June 2026). The CSV column structure is identical in every monthly file for each report type. No layout changes detected.

### Parsing notes

- **Line endings**: Files use `\r\r\n` (double carriage return). Python's text-mode read handles this by splitting into extra blank lines; parser filters them out.
- **Activity CSV structure**: Sport-level rows (Professional, College, Motor Race, Other Event) have 7 columns. A bottom section without a Sport Level column (6 columns) contains a residual "Other" category with small wager counts; tagged as sport="Other" in the panel.
- **"Total" rows**: Each sport section and the bottom section include "Total" Location Type rows that sum In-Person + Online. These are excluded from the panel (only retail/online channel rows are kept). The "All" sport rows in the panel are computed by summing across all sport-level rows per channel × operator.
- **Tax basis**: Tax Summary uses **completed events (accrual) basis** — it counts wagers on events that completed in the reporting month, not wagers placed in that month. The Activity report uses **cash basis** — wagers placed in the month. For monthly wager counts, the two bases produce the same totals in practice.
- **Sports Wager Tax column**: Present in all months but zero before July 2025 (pre-enactment). From July 2025 onward, only Online Wagering rows have non-zero values (the per-wager tax applies to online wagers only). In-Person rows remain $0.
- **Tier 1 vs Tier 2**: The activity CSV splits wagers into Tier 1 and Tier 2. These correspond to different wager types (single-game vs parlay/in-play, per IGB classification). The panel sums them into a single wager_count and handle.
- **"Other Gross Sports Wagering Receipts"**: This line item appears in the PDF versions of the monthly reports from July 2025 onward. The CSV Tax Summary does not include a separate line for it — the surcharge revenue is captured in the "Sports Wager Tax" column instead.
- **Operator count**: Varies over time as new licensees enter the market. 16 distinct licensee names appear across the full period.

### Earliest month with wager counts

**March 2020** — wager counts (Tier 1 Wagers, Tier 2 Wagers) are published in the Activity Detail CSV for every month from the start.

### Validation discrepancies

- **July 2025 per-wager tax**: IGB reports $4,737,108; user-provided benchmark was ~$5,200,000. The IGB figure equals exactly $0.25 × 18,948,431 online wagers. The $5.2M figure may originate from a news article or include adjustments not in the IGB CSV.
- **July 2025 AGR**: IGB reports $89,527,082; benchmark was ~$89,700,000. Difference is <0.2%, likely a rounding difference in the benchmark source.

## Source: Sports calendar (constructed)

- **Output**: `data/clean/calendar.parquet`
- **Build date**: 2026-09-09
- **Description**: Monthly calendar table 2019-01 through 2026-12 (96 rows). League-wide game counts (regular + postseason) for NFL, NBA, MLB, NHL, NCAA basketball (men's D1), NCAA football (FBS). Playoff/postseason indicators, Super Bowl / March Madness / World Series month flags, and Chicago team postseason appearances (Bears, Bulls, Cubs, White Sox, Blackhawks).
- **Method**: Constructed from structural knowledge of league schedules and season formats. Game counts are approximate league-wide totals based on standard monthly distributions (e.g., NFL ~48 games/month for 4-week months). COVID-affected seasons (2019-20, 2020-21) adjusted for suspensions, bubbles, and shortened seasons.
- **Parsing quirks**:
  - COVID Apr-Jun 2020: zero games across all leagues (total sports shutdown).
  - NBA 2019-20 bubble: games in Jul-Oct 2020. NHL 2019-20 bubble: Aug-Sep 2020.
  - NBA 2020-21: started Dec 2020, 72-game season. NHL 2020-21: started Jan 2021, 56-game season.
  - NCAA basketball 2019-20: tournament cancelled (March Madness=0 for 2020).
  - NCAA football 2020: reduced schedules, some conferences delayed start.
  - Game counts are league-wide totals, not exact to the game — suitable for seasonal controls in regressions, not for precise game-level analysis.

## Source: Operator passthrough policies (constructed)

- **Output**: `data/clean/passthrough.csv`
- **Build date**: 2026-09-09
- **Description**: 14 rows covering surcharge and minimum-stake policies for 11 Illinois online operators in response to the per-wager tax (effective July 1, 2025). Each row records operator, effective date, mechanism (surcharge vs minimum_stake), amount, exemptions, and a primary source URL.
- **Sources**: Operator press releases (Flutter/FanDuel, DraftKings 8-K), trade press (SBC Americas, Legal Sports Report, Covers, Gaming America, InGame). All URLs recorded in source_url column.
- **Parsing quirks**:
  - Fanatics: exact effective date never publicly confirmed ("fall 2025" only).
  - Hard Rock Bet: exact date approximate (~July 15-16, 2025).
  - theScore: sources disagree — LSR lists $1 minimum, theScore help center describes $0.25 surcharge. May have both.
  - FanDuel reinstatement (2026-06-20): inferred from waiver expiry + HB5143 failure + continued IGB tax collection. No direct announcement found.

## Source: Multi-state panel — Ohio Casino Control Commission

- **Output**: `data/clean/states/oh.parquet`
- **Build date**: 2026-09-09
- **Raw files**: `data/raw/states/oh/2024_Sports.xlsx`, `2025_Sports.xlsx`, `2026_Sports.xlsx`
- **URL pattern**: `https://dam.assets.ohio.gov/raw/upload/casinocontrol.ohio.gov/revenue-reports/{YYYY}/Sports/{YYYY}_Sports_Gaming_Revenue_Report.xlsx`
- **Coverage**: Jan 2024 – Aug 2025 + Jan 2026 (2023 xlsx not found; launched Jan 2023)
- **Fields**: operator, channel (online/retail), Total Gross Receipts (handle), Revenue (GGR), Taxable Revenue
- **Revenue definition**: **GGR** = Handle − Payouts − Voids. Promotional credits are disclosed but NOT deductible from taxable revenue in Ohio (R.C. §5753.01). Taxable Revenue ≥ GGR for profitable operators; floored at $0 for unprofitable ones.
- **Operator detail**: Yes — ~15 online + ~15 retail proprietors per month, named as "CASINO NAME - BRAND" (e.g., "BELTERRA PARK - FANDUEL", "HOLLYWOOD TOLEDO - DRAFTKINGS")
- **Wager counts**: No — Ohio does not publish wager/bet counts

## Source: Multi-state panel — Maryland Lottery and Gaming

- **Output**: `data/clean/states/md.parquet`
- **Build date**: 2026-09-09
- **Raw files**: `data/raw/states/md/*.xlsx` (52 files)
- **URL**: https://www.mdgaming.com/maryland-sports-wagering/revenue-reports/
- **Coverage**: Feb 2022 – Jul 2026 (Dec 2021 has different format, not parsed; Jan/Apr/Jun 2022 xlsx not published)
- **Fields**: operator, channel (retail/online), Handle, Prizes Paid, Hold%, Promotional Play, Taxable Win, Contributions to State
- **Revenue definition**: Reports both **GGR** (Handle − Prizes Paid) and **AGR/Taxable Win** (GGR − Promos − Other Deductions). "Taxable Win" is the tax base. Tax rate: 15% of Taxable Win for mobile, varies for retail.
- **Operator detail**: Yes — ~12 retail + ~15 mobile licensees per month
- **Wager counts**: No
- **Bonus**: "Bets By Sport" sheet available Nov 2022+ with handle/hold by sport category

## Multi-state panel: Revenue definition harmonisation

| State | Metric reported | Definition | Promo deductible? | Tax base |
|-------|----------------|------------|-------------------|----------|
| IL | AGSR (Adjusted Gross Sports Wagering Receipts) | Handle − Winnings Paid (230 ILCS 45/25-10) | **No** — promos not deductible for sports wagering | AGSR |
| OH | Revenue / Taxable Revenue | Handle − Payouts − Voids | No (disclosed only) | Taxable Revenue (≥0) |
| MD | Taxable Win | Handle − Prizes − Promos − Other | Yes | Taxable Win |
| NJ | Win | Handle − Payouts | Varies by operator agreement | GGR |
| PA | Gross Sports Wagering Revenue | Handle − Payouts | Partial (subject to cap) | Taxable revenue |
| MI | GGR | Handle − Payouts | Yes (deductible) | Adjusted GGR |
| NY | GGR / Net Revenue | Handle − Payouts − Prior-period adj | Promo credits disclosed | GGR |
| IN | AGR | Handle − Payouts − Excise − Adj | Yes | AGR |
| IA | GGR | Handle − Payouts | Partial | GGR |
| CO | Net Proceeds | Handle − Payouts − Limited deductions | Limited | Net Proceeds |
| TN | AGI | Unique: tax at 1.85% of handle (not revenue) | N/A (handle-based) | Handle × 1.85% |
| VA | AGR | Handle − Payouts − Fed excise − Adj | Yes | AGR |
| AZ | AGEWR | Handle − Payouts − Adj | Yes | AGEWR |
| MA | TSWR | Handle − Payouts − Promos | Yes | TSWR |
| KS | AGR | Handle − Payouts − Adj | Yes | AGR |
| LA | GGR | Handle − Payouts | Unknown | GGR |

**Key**: "Revenue" in the panel uses each state's primary reported metric. The `revenue_type` column distinguishes GGR from AGR. For cross-state comparison, use handle and hold% (revenue/handle) as the most comparable metrics.

## Multi-state panel: Wager count availability

**States that publish wager/bet counts**: Only **Illinois** publishes monthly wager counts (Tier 1 + Tier 2 wager counts in the All Wagering Activity Detail CSV). No other state among the 15 studied publishes monthly wager counts in its regular reports.

Some states (MD, CO) publish handle broken down by sport, and a few include number of events or number of active accounts, but none report the total number of individual bets placed.

## Source: Virginia Lottery — Monthly Sports Betting Reports

- **URL pattern**: `https://rga.lis.virginia.gov/Published/{YYYY}/RD{NNN}/PDF`
- **Download date**: 2026-09-12 to 2026-09-13
- **Raw files**: `data/raw/states/va/*.pdf` (53 files, 110–232 KB each)
- **Coverage**: Mar 2022 – Jul 2026; missing Sep 2025 only
- **Source**: Virginia General Assembly Reports to the General Assembly (RGA) system. Virginia Lottery files a monthly sports betting report plus a separate Lottery Monthly Report. The sports betting report is always filed one RD number after the Lottery Monthly Report in the same batch submission.
- **RD number mapping** (confirmed for months found during download session):
  - 2022-01: RD155/2022; 2022-03: RD210/2022; 2022-05: RD328/2022; 2022-07: RD427/2022; 2022-09: RD603/2022; 2022-10: RD796/2022; 2022-12: RD90/2023
  - 2023-01: RD137/2023; 2023-02: RD170/2023; 2023-03: RD221/2023; 2023-04: RD249/2023; 2023-06: RD370/2023; 2023-08: RD477/2023; 2023-09: RD571/2023; 2023-10: RD700/2023; 2023-11: RD23/2024
  - 2024-01: RD178/2024; 2024-02: RD226/2024; 2024-03: RD248/2024; 2024-05: RD340/2024; 2024-06: RD417/2024; 2024-11: RD5/2025
  - 2025-04: RD283/2025; 2025-05: RD390/2025; 2025-07: RD487/2025; 2025-08: RD578/2025; 2025-09: **NOT FOUND** (see quirks); 2025-10: RD926/2025; 2025-11: RD1049/2025; 2025-12: RD220/2026
  - 2026-01: RD267/2026; 2026-02: RD289/2026; 2026-03: RD325/2026; 2026-04: RD353/2026; 2026-05: RD458/2026; 2026-06: **NOT FOUND** (likely not yet filed as of 2026-09-09); 2026-07: RD532/2026
- **Parsing quirks**:
  - RD numbers are assigned sequentially by submission date, NOT by report content date. Late-filed reports have higher RD numbers but cover earlier months.
  - Several months were filed very late (Oct 2025 = Dec 1, 2025; Nov 2025 = Dec 15, 2025; Dec 2025 = Jan 2026 year).
  - Nov 2022 (RD880/2022) and Dec 2022 (RD90/2023): Dec was filed in 2023 legislative year.
  - Nov 2023 (RD23/2024): filed in 2024 legislative year.
  - Nov 2024 (RD5/2025): filed in 2025 legislative year.
  - **Sep 2025 sports betting report**: searched exhaustively through all 2025 RDs (up to RD1052) and all 2026 RDs (up to ~RD549). Report not found — either never filed as a standalone report or buried in an unusual location. Pari-mutuel Sep 2025 report is at RD629/2025 but the sports betting companion was not filed at RD630. Leave 2025-09 as null/missing in panel.
  - **Jun 2026 sports betting report**: Lottery Monthly Jun 2026 = RD495/2026, but Sports Betting Jun 2026 not found adjacent. As of 2026-09-09, likely not yet filed. Check again later.

## Multi-state panel: Collection status

| State | Raw files | Format | Parsed? | Notes |
|-------|----------|--------|---------|-------|
| IL | 152 CSVs | CSV | ✅ Yes | Full panel Mar 2020 – Jun 2026. Operator-level. |
| NJ | 67 PDFs | PDF | ✅ Yes | Jan 2021 – Jun 2026 (66 months, no gaps). Statewide + operator GGR (2025+). |
| PA | 8 xlsx | Excel | ✅ Yes | Jul 2019 – Jul 2026 (85 months). Operator-level. |
| NY | 1 xlsx | Excel | ✅ Yes | Jan 2022 – Jul 2026 (55 months). Statewide GGR. |
| IN | 72 xlsx | Excel | ✅ Yes | Oct 2019 – Nov 2025 (72 months). Operator-level AGR. Missing 2025-07, 2025-09. |
| OH | 3 xlsx + 1 PDF | Mixed | ✅ Yes | Jan 2023 – Jan 2026 (33 months). Operator-level. Missing Sep–Dec 2025. |
| MD | 52 xlsx | Excel | ✅ Yes | Nov 2022 – Jun 2026 (43 months). Operator-level GGR + Taxable Win. Missing 2026-02. |
| CO | 134 PDFs | PDF | ✅ Yes | Jul 2020 – Jul 2026 (71 months). Statewide net proceeds. Missing 2024-06, 2025-07. |
| TN | 67 PDFs | PDF | ✅ Yes | Jan 2021 – Jul 2026 (67 months). Statewide handle only (online-only state). |
| VA | 53 PDFs | PDF | ✅ Yes | Feb 2022 – Jul 2026 (48 months). Statewide AGR. Missing Sep 2025, some early months. |
| MI | 1 xlsx | Excel | ✅ Yes | Jan 2023 – Dec 2024 (24 months). Operator-level. michigan.gov blocks curl; only 2024 file via Wayback. |
| IA | 0 | — | ❌ Not started | irgc.iowa.gov — monthly news releases |
| AZ | 0 | — | ❌ Not started | gaming.az.gov — monthly PDFs |
| MA | 0 | — | ❌ Not started | massgaming.com — interactive PDF reports |
| KS | 0 | — | ❌ Not started | krgc.kansas.gov — PDF reports |
| LA | 0 | — | ❌ Not started | lgcb.dps.louisiana.gov — statewide aggregate only |
