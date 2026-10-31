# Illinois Per-Wager Tax

Empirical analysis of Illinois' July 2025 per-wager online sports betting tax.
Panel data from IGB monthly reports (152 files, 16 operators, Mar 2020–Jun 2026)
and a multi-state comparison panel.

**Status:** Closed — weak results. Directionally large effects but statistically
underpowered. See [CLOSURE.md](CLOSURE.md).

---

## Key findings

All numbers from [`notes/prelim_v4.md`](notes/prelim_v4.md) and
[`notes/results_outline.md`](notes/results_outline.md):

- Statewide wager count: −25.4% post-tax (recent-growth counterfactual)
- Statewide handle: −12.6%
- Handle per wager: +17.1% (shift toward fewer, larger bets)
- Cross-state DiD: −0.178 (HC1 SE 0.029); permutation p = 0.20
- FanDuel waiver DiD: −0.091 (p = 0.160)

All results directionally consistent but underpowered (~10 clusters).

## Data

Source: state gaming commission monthly reports (public records).

- Illinois: [IGB monthly reports](https://www.igb.illinois.gov/SportsReports.aspx)
- Parsed states: IL, NJ, PA, NY, IN, OH, MD, CO, TN, VA, MI
- Not parsed: IA, AZ, MA, KS, LA

Raw PDFs and parsed CSVs are not redistributed due to size (411 files).

## Structure

- [`src/`](src/) — parsing and analysis scripts (26 files)
- [`notes/`](notes/) — data log, preliminary results, event study
- [`output/`](output/) — figures only
- [`CLAUDE.md`](CLAUDE.md) — project documentation
- [`CLOSURE.md`](CLOSURE.md) — closure note

## License

Code: [MIT](LICENSE). Text and figures: [CC BY 4.0](LICENSE).
