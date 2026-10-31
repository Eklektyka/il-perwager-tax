# Illinois Per-Wager Tax — closed 2026-09-13

**Question:** What is the causal effect of Illinois' July 2025 per-wager tax
on online sports betting handle, wagers, hold, and handle-per-wager?

**What I expected:** Not recorded (no formal pre-registration). The
results_outline.md documents the planned paper structure: cross-state DiD with
wild cluster bootstrap, synthetic control, and within-operator FanDuel waiver
natural experiment.

**What I found:** Directionally large effects, statistically underpowered.

- Cross-state DiD (IL × post-Sep): −0.178 (HC1 SE 0.029). IL ranked most
  negative in permutation, but permutation p = 0.20.
  (`notes/results_outline.md` line 37)

- Statewide wager count gap Sep+: −25.4%.
  Statewide handle gap Sep+: −12.6%.
  HPW gap Sep+: +17.1%.
  (`notes/prelim_v4.md` lines 107–109)

- FanDuel waiver HPW drop: $37–42 → $28–31.
  (`notes/prelim_v4.md` line 25)

- Within-operator FanDuel waiver DiD: log handle/wager −0.091 (p = 0.160),
  N=60. (`notes/prelim_v4.md` lines 19–21)

**Why I stopped:** "Directionally consistent but underpowered with only
3 treatment months and 2 operators" (notes/prelim_v4.md line 27). Cross-state
analysis limited by 5 comparable states and permutation p = 0.20. Five
additional states (IA, AZ, MA, KS, LA) not yet parsed. Michigan data blocked.
Synthetic control not implemented.

**What it rules out:** Not recorded — the evidence is suggestive but the study
cannot reject the null. The effect sizes are large (−25% wager count, +17%
HPW) and directionally consistent with the tax causing a shift toward fewer,
larger bets. But the formal tests do not achieve significance at conventional
levels.

**What would reopen it:** Another state imposing a similar per-wager tax (for
a second treated unit), or Illinois accumulating 12+ months of post-tax data
with additional comparison states parsed. Neither is expected soon.
