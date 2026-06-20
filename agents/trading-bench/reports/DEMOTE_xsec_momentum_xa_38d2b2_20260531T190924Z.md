# DEMOTION RECORD — `xsec_momentum_xa_38d2b2`

**Date:** 2026-05-31 ~19:09 UTC
**Action:** Live-paper → candidate (back to `strategies_candidates/`). Cron clock stopped.
**Authority:** main RULING 1 (2026-05-31), explicit GO. Audit (verified memo + √252 fix + GATE.md) found sound.

---

## What changed mechanically

1. **Cron line removed.** `5 14 * * 1-5 … cron_tick.sh xsec_momentum_xa_38d2b2` deleted from user crontab (backup saved to `/tmp/crontab_backup_*.txt`). The live paper-trading clock — which was exactly one tick old (first real tick would have been Monday 14:05 UTC; no fills had occurred yet) — is stopped. Demotion cost is effectively zero.
2. **Live strategy dir removed** from `strategies/` → moved to `.trash/xsec_momentum_xa_38d2b2_demoted_<ts>/`. Source files (`params.json`, `strategy.py`) are **byte-identical** to the preserved candidate copy in `strategies_candidates/xsec_momentum_xa_38d2b2/`; only `__pycache__` differed. No source lost.
3. **Candidate copy preserved** at `strategies_candidates/xsec_momentum_xa_38d2b2/` (was always kept for audit per Bar A #5 promotion protocol). The strategy can re-promote if it clears the corrected gate honestly.

## Why — the demotion reason (for the audit trail)

The promotion was made on a **Sharpe figure that the √252 annualization-fix audit revised downward**, and on a walk-forward (WF) fitness profile that does not actually clear the bar:

- **Full-period Sharpe re-derived: 1.04 → 0.87** after the √252 correction was applied consistently across both backtests. **0.87 is below the 1.0 fast-track bar (Bar A #5 clause (a)).** The promotion had stood on 1.04 ≥ 1.0; post-correction it no longer clears clause (a).
- **WF median Sharpe 0.17 fails the fitness gate.** The headline full-period number was carried by a minority of strong windows; the median window does not demonstrate edge.

**The principle (main's framing, adopted):** keeping it live on the **absolute-return floor (clause (f), 11.6%/yr) alone** would be retroactively justifying a promotion against a Sharpe criterion (clause (a)) it no longer meets. That is precisely the goalpost-moving this audit discipline exists to prevent. "This is not a fire-drill" (the correction is small, the clock is one tick old, no money at risk) does **not** translate to "keep the promotion." A clean demotion is the honest move: re-derive, fail the corrected gate, demote, document, and let it re-promote only if it clears the corrected ruler on its own merits.

## Numbers of record

| Metric | Pre-audit (promotion basis) | Post-√252-correction (binding) |
|---|---|---|
| Full-period Sharpe | 1.04 | **0.87** (FAIL clause (a) ≥1.0) |
| WF median Sharpe | — | **0.17** (FAIL fitness gate) |
| Annualized return (deployed) | 11.6%/yr | 11.6%/yr (clause (f) PASS — but not sufficient alone) |

## Re-promotion path

`xsec_momentum_xa_38d2b2` is **not killed** — it is back on the bench as a candidate. It re-promotes only if it clears the **corrected** Bar A gate honestly:
- Sharpe ≥ 1.0 full-period (clause (a)) computed with the √252 annualization fix, AND
- WF fitness (median Sharpe) clears the gate, AND
- absolute-return floor ≥ 8%/yr-on-deployed (clause (f)) — already clears at 11.6%, AND
- the rest of Bar A #5 (b)/(c) and #2/#4/#6/#7.

If a future re-derivation on more data lifts the honest Sharpe back over 1.0 with a passing WF profile, it re-promotes — through the front door, not the return-floor side door.

## Cross-references

- Promotion memo (now superseded as a live justification): `reports/PROMOTE_xsec_momentum_xa_38d2b2_20260531T015000Z.md`
- Promotion-record correction (√252 + cache-floor span fix): `reports/PROMOTION_RECORD_CORRECTION_20260531T024500Z.md`
- GATE.md Bar A #5 (fast-track) — the gate it must re-clear.
