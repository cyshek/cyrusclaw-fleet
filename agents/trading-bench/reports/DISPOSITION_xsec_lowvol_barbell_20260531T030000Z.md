# Disposition — xsec low-vol cross-asset barbell (`xsec_lowvol_xa2_440761`)

**Decided:** 2026-05-31 by main (wave-5 low-vol IC ruling), executed by Tessera.
**Status:** NOT PROMOTED. Filed as DEFENSIVE / capital-preservation sleeve only. **Never labeled alpha.**

## What it is

Wave-5 variant of the wave-4 low-vol cross-asset archetype. Single highest-leverage change from the rejected parent (`xsec_lowvol_xa_38a206`): swap **TLT (20y+ Treasury) → SHY (1-3y Treasury)**, keep equal-weight at the tightest cut **K=2** on universe `[SPY, EFA, SHY, VNQ, DBC, GLD]`, N=60.

Backtest: `reports/BACKTEST_XSEC_LOWVOL_XA2_20260531T023858Z.md`.

## Why it is NOT promoted (main's ruling, 3 points)

1. **It's denominator-gaming, not alpha.** At K=2 on a 6-asset basket, **SHY is held 100% of months** — the strategy is structurally "always park 50% in 1-3y Treasuries, rotate the other 50% into the lowest-vol risk asset." The FP Sharpe 1.23 (the *highest* of all wave-4/5 cross-asset candidates) is high mainly because half the book is a near-cash anchor that mechanically halves portfolio volatility. The real return is **~0.75%/yr on bench equity / ~7.5%/yr on deployed notional** — modest. High Sharpe + low return = the classic "60/40 with the 40 in T-bills looks great on Sharpe in a calm decade" illusion.

2. **It fails the new Bar A #5 clause (f) absolute-return floor** (≥8%/yr-on-deployed): 7.5%/yr < 8%/yr. This candidate is, in fact, the calibration point that *motivated* clause (f) — it's the canonical example of a strategy that clears Sharpe but doesn't make enough money. It would be self-contradictory to promote the very strategy the floor was written to reject.

3. **Keep on file as a DEFENSIVE / capital-preservation sleeve ONLY.** It is a real, defensible *portfolio* — a 50/50 cash-anchor + low-vol-risk rotation with a contained max drawdown (~-$14, ~1.4% of $1000 equity). If the tournament ever wants a low-volatility ballast sleeve (e.g. to dampen aggregate book drawdown), this is a candidate for that role. **It must never be labeled or evaluated as an alpha/edge strategy.** Its job, if ever deployed, is to not lose money — not to make it.

## Where it lives

- Candidate code preserved at `strategies_candidates/xsec_lowvol_xa2_440761/` (audit trail).
- NOT copied to `strategies/`. NOT on cron. No paper clock.
- This memo is the disposition record. If a defensive-sleeve mandate ever opens, start here.

## Archetype-level conclusion

The **cross-asset low-vol archetype is CLOSED** (no wave-6). See PATTERNS.md Pattern #5: vol-ranking across asset classes mechanically owns the most cash-like leg → high Sharpe, no return. Dead end, do not re-run. The low-vol anomaly is an *intra-asset-class* effect (low-vol stocks beat high-vol stocks within equities); applied across asset classes it degenerates into a duration/cash-likeness sort, which is not an alpha sort.
