# Illinois Tax

Empirical research paper on Illinois' per-wager online sports betting tax.
Formerly `il-perwager-tax`.

## Policy background

- **Per-wager tax** (effective 1 July 2025): $0.25 per wager on the first 20 million wagers per fiscal year, $0.50 per wager thereafter. Applies to online sports wagers only.
- **Progressive AGR tax** (effective 1 July 2024): 20–40% tax on adjusted gross revenue, graduated by AGR bracket. This replaced the prior flat 15% rate.
- Both taxes apply simultaneously; the per-wager tax is layered on top of the AGR tax.

## Research question

What is the effect of the per-wager tax on monthly handle, adjusted gross revenue (AGR), hold percentage, and wager counts, by operator? The paper uses operator-level monthly panel data to estimate the tax's impact relative to the pre-treatment period under the AGR-only regime.

## Outcomes of interest

- Monthly handle (total dollars wagered)
- Adjusted gross revenue (AGR)
- Hold percentage (AGR / handle)
- Wager counts (where reported)
- All outcomes by operator and month

## Project conventions

- **Language:** Python. Package management via `uv`.
- **Raw data:** `data/raw/` — downloaded source files go here and are **never modified or deleted**. Treat as immutable.
- **Cleaned data:** `data/clean/` — cleaned/parsed outputs stored as Parquet files.
- **Scripts:** `src/` — one script per data source. Every script must be idempotent and re-runnable (i.e., running it twice produces the same output without side effects).
- **Data log:** `notes/data_log.md` — every source URL, download date, and any parsing quirk must be recorded here. This is the audit trail.
- **No invented numbers.** If a value cannot be reliably parsed from the source, leave it as null/NaN and log the issue in `notes/data_log.md`. Never impute, estimate, or fabricate data.

## Directory structure

```
il-perwager-tax/
  CLAUDE.md
  data/
    raw/          # immutable downloaded files
    clean/        # parquet outputs
  src/            # one script per source
  notes/
    data_log.md   # source URLs, download dates, parsing notes
```
