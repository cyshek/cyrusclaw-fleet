# RANKING RISK METRICS — L166 (Sortino + Calmar) + leaderboard de-pollution

**Date:** 2026-06-24 (PT)
**Item:** BACKLOG L166 — "Sortino + Calmar in ranking (currently total return + per-strategy P&L only)."
**Scope:** additive metric/display work; reuses existing FIFO daily-P&L series. Touched `runner/ranking.py`
(ad-hoc/weekly tool, not cron-wired) + new isolated module + tests. No strategy/GATE/risk-cap edits,
no live trades affected, killswitch untouched.

## What & why
The tournament leaderboard ranked only on raw total/realized P&L — no risk-adjustment, so a strategy
that made money via large swings looked identical in spirit to one that made it smoothly. L166 adds
two standard risk-adjusted measures:
- **Sortino** = (mean daily P&L − target) / **downside** deviation, ×√252. Punishes downside vol only.
- **Calmar** = annualized mean daily P&L / **max drawdown** of the cumulative curve.

Both need a per-period return *series*, which the codebase already produces:
`correlation.daily_pnl_series(strategy) -> {date: realized_pnl}` (same FIFO closed-leg logic used by
the correlation matrix). So this is a clean reuse, not a new equity-curve subsystem.

## Implementation
1. **`runner/risk_metrics.py`** (new, pure, no runner deps beyond types):
   - `sortino()`, `calmar()`, `max_drawdown()`, `downside_deviation()`, `compute_for_series()`.
   - √252 annualization (matches MEMORY.md "√252 Sharpe bug" convention).
   - **Equity curve starts at 0** → an opening losing day is a real drawdown (doesn't understate risk).
   - **Honest undefined handling (no fake infinities):** no losing day → downside dev 0 → Sortino `None`;
     monotone-up curve → maxDD 0 → Calmar `None`; <2 closed days → `None`.
2. **`runner/ranking.py`** (additive):
   - `_attach_risk_metrics(rows)` decorates each row with `sortino`/`calmar`/`max_drawdown_usd`/
     `n_closed_days` (best-effort; never raises — raw P&L stays intact on any failure).
   - `format_chat` now prints `| Sortino=…, Calmar=… (closed-days=N)`, with `n/a` for undefined,
     and a footnote explaining the `n/a` semantics.
   - New CLI flags: `--risk-sort` (rank by Sortino desc; undefined sink to bottom), `--all`.
   - The existing `rankings` table schema + `snapshot()` are **unchanged** (no migration risk).

## Bonus hardening — leaderboard was showing synthetic-row pollution
Rendering the live board surfaced the documented `tournament.db` contamination (MEMORY.md
"SYNTHETIC-ROW CONTAMINATION — ALWAYS filter"): the board listed `backstop_test` (−$120 synthetic),
`any`, `bp2`, and dead crypto/retired lanes — `ranking.py` had no universe filter.
Fix: `compute(include_all=False)` now reuses the **canonical** `edge_calibrator.LIVE_ROSTER` +
`EXCLUDE_STRATEGIES` (single source of truth — no list duplication, so no drift), restricting the
default board to the live 8-strategy book. `--all` restores the full forensic view.
Result: default board dropped from 18 rows → the 6 live strategies that have fills.

## Testing
- **18 new unit tests** in `tests/test_risk_metrics.py`: known-value Sortino/Calmar, √252 scaling,
  downside-deviation math, drawdown paths (incl. opening-loss case), all-positive/single-day/empty
  undefined cases, bundle counts. All pass.
- **Full suite: 721 passed, 1 skipped** (was 703+1; +18 new, nothing regressed).
- **Live render** verified (read-only, `--no-snapshot`): Sortino/Calmar compute for strategies with a
  losing day (e.g. `sma_crossover_qqq_regime` Sortino +0.06 / Calmar +0.54), `n/a` elsewhere; default
  board is clean (no synthetic rows), `--all` shows all 18.

## Files
- `runner/risk_metrics.py` (new), `tests/test_risk_metrics.py` (new), `runner/ranking.py` (additive edits).

## Notes
- `ranking.py` is not referenced by any cron/`*.sh` (only a comment in `correlation.py`), so this is
  zero-risk to automated Discord posting; it improves the ad-hoc/weekly leaderboard.
- Tooling gotcha re-confirmed: the `write`/`edit` tools mangle any tool-input line containing the
  sequence `:` + newline + spaces into a literal `\n`; created/patched these files via `exec`
  heredoc + single-line guards to avoid it.
