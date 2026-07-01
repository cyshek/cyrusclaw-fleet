# DAA (Keller/Keuning Defensive Asset Allocation) — PAPER TRACKER BUILD

**UTC:** 20260630T205632Z
**Builder:** trading-bench subagent (DAA paper tracker build)
**Pattern:** VERBATIM mirror of `runner/crash_sleeve_paper_tracker.py` (which mirrors
`runner/xa_tsmom_paper_tracker.py`). Reuses the validated `_daa_confirm.run_daa()` +
`_sigimprove_tests.run_sector_rotation()` directly — ZERO numeric logic re-derived.

---

## Build summary

A standalone, **READ-ONLY**, PAPER-ONLY daily forward clock for the Keller/Keuning DAA canary
strategy. NO live orders, NOT wired into the live roster, writes ONLY to a new side DB
`daa_paper.db`. Logs every trading day, three streams on one path:

- **DAA cascade book** (the VWO/BND canary 13612W de-risk strategy)
- **control** = our validated rotation sleeve `run_sector_rotation(["SPY","QQQ","GLD","TLT"], lookback_months=3, hold_top=2)`
- **SPX** (`^GSPC`)

Why: DAA's value is crash-INSURANCE (a breadth-momentum canary that cascades the book out of risk
and into bonds during stress) — exactly the de-risk our `allocator_blend` lacks. The confirm-or-kill
backtest verdict rests on a finite OOS window; this forward clock accumulates NEW regimes the
backtest could not fit — the honest way to earn (or falsify) confidence in the gate.

### Files delivered
| File | Purpose | md5 |
|---|---|---|
| `runner/daa_paper_tracker.py` | standalone daily paper tracker (snapshot/stats/staleness + CLI) | `1246379de9a4cc33efaa3c4a7479ccec` |
| `tests/test_daa_paper_tracker.py` | 27 offline/deterministic pins (tests-first, RED→GREEN) | `a96c49943a6f211796b5f9f6d2381983` |
| `scripts/daa_daily_track.sh` | cron wrapper (mirrors crash_sleeve_daily_track.sh) | `91cc5c3d4b001f8ab90365f416072890` |
| `daa_paper.db` | new side DB (1 row: inception 2026-06-30) | — |

### Mechanism (reused verbatim from `_daa_confirm.py`)
- **CANARY** = {VWO, BND}, **13612W** = (12·r1 + 4·r3 + 2·r6 + 1·r12)/4, rN = trailing ~21·N-day
  total return from prior month-end close (lookahead-safe). `_mom_13612w` **delegates** to
  `_daa_confirm._mom_13612w` (byte-identical, pinned by test).
- **RISK G12** = {SPY, IWM, QQQ, VGK, EWJ, VWO, VNQ, GSG, GLD, TLT, HYG, LQD}, EW top-6.
- **CASH/bond** = {SHY, IEF, LQD}, best single by 13612W.
- **Cascade:** both canaries > 0 → `risk_on` (100% top-6, w_def 0.0); exactly one > 0 → `half`
  (50% top-3 + 50% best bond, w_def 0.5); both ≤ 0 → `crash_off` (100% best bond, w_def 1.0).
  Undefined momentum treated as ≤0 (defensive), VERBATIM to the driver's `cmom is not None and cmom > 0.0`.
- **Cost:** 2bps one-way on turned-over fraction (`COST_BPS` inherited from `_daa_confirm`, handed
  straight to both engines — pinned by test).
- **Lookahead contract:** rank on prior month-end close (cal[mf-1]); held from month-first.
  Per-day signal readout decoded at the latest month-first using the prior month-end — a future
  price move cannot change today's decision (pinned by a future-spike lookahead test).

---

## DB schema (`daa_paper.db` → table `daily_snapshots`)
```
id                  INTEGER PK AUTOINCREMENT
date                TEXT UNIQUE        -- trading date marked (engine last close)
daa_equity          REAL               -- DAA cascade book equity (1.0 at inception)
control_equity      REAL               -- rotation-sleeve control equity (1.0 at inception)
spx_equity          REAL               -- SPX (^GSPC) equity (1.0 at inception)
regime              TEXT               -- risk_on / half / crash_off (current-month cascade state)
w_defensive         REAL               -- defensive (cash/bond bucket) fraction {0.0, 0.5, 1.0}
daa_daily_return    REAL               -- DAA book realized return ON date (close-to-close)
control_daily_return REAL              -- control realized return ON date
spx_daily_return    REAL               -- SPX realized return ON date
canary_vwo_13612w   REAL               -- VWO 13612W at current month's decision day (prior month-end)
canary_bnd_13612w   REAL               -- BND 13612W at current month's decision day
top_risk_assets     TEXT               -- JSON list of held risk legs (EW; [] if crash_off)
defensive_asset     TEXT               -- best single bond when defensive; NULL when risk_on
engine_full_sharpe  REAL               -- DAA full-period continuous-span Sharpe (drift check)
created_at          TEXT               -- when row was written (UTC ISO8601)
```

---

## First-row verification (inception 2026-06-30)

Live run logged exactly ONE row. **The canary engaged correctly today:**

| field | value |
|---|---|
| date | **2026-06-30** |
| regime | **risk_on** (both canaries positive) |
| w_defensive | **0.0** |
| canary_vwo_13612w | **0.2656** |
| canary_bnd_13612w | **0.0141** |
| top_risk_assets | **["QQQ", "IWM", "SPY", "EWJ", "GSG", "VWO"]** (EW top-6) |
| defensive_asset | **None** (risk_on, no bond) |
| daa_equity / control_equity / spx_equity | **1.0 / 1.0 / 1.0** (normalized inception) |
| daa/control/spx daily_return | **0.0 / 0.0 / 0.0** (inception zeroed — no prior logged close) |
| engine_full_sharpe (DAA, drift check) | **0.839** |
| backtest window | 2007-04-11 → 2026-06-30 (4836 days) |

**FIRST-ROW INVARIANT satisfied:** equities start at 1.0, the three daily returns are 0.0 on the
inception row, yet regime + both canary scores + held assets ARE persisted so a future session can
verify engagement. **Idempotency confirmed:** a second same-day run inserted 0 rows (rows_logged
stayed 1). **Staleness guard:** `--check-staleness` → `trading_days_behind: 0, stale: false`
(rc 0), current with the latest closed SPX bar.

---

## Test suite

- **New tracker tests:** `tests/test_daa_paper_tracker.py` → **27 passed** (≥12 required).
  Coverage: schema (2), canary regime cascade incl. verbatim cross-check vs `_daa_confirm` (6),
  13612W correctness incl. byte-identical delegation + closed-form value + insufficient-history (3),
  lookahead-safe ranking incl. future-spike leak test + strictly-earlier decision month (4),
  first-row invariant risk_on + crash_off (2), idempotency (1), 3-stream equity compounding (1),
  cost-bps constant (1), forward stats incl. defensive/crash_off rates (2), staleness guard (5).
- **RED→GREEN proof:** with the module stashed, collection fails (`ModuleNotFoundError`); restored → 27 pass.
- **FULL SUITE (regression):** **934 passed, 3 skipped** — baseline 907/3 + exactly **+27** new
  tests, **zero regressions**.

---

## Hard rails — verified

**6 protected files UNCHANGED** (md5, re-verified post-suite):
```
0f763975  runner/runner.py
e303317e  runner/risk.py
717c36e6  runner/backtest.py
d8927364  runner/backtest_xsec.py
8c3df32c  runner/walk_forward_xsec.py
bccefaba  runner/safety_backstop.py
```

- `_daa_confirm.py` was **imported only** (never written by this build); the exact 13612W +
  cascade math is reused, not re-derived.
- No touch to `_allocator_blend_tests.py`, `allocator_paper_tracker.py`, `strategies/`, crontab,
  `tournament.db`, or any live `.db`. The tracker writes ONLY to its own new `daa_paper.db`.
- NOT wired into the live roster (no crontab entry — confirmed `crontab -l | grep daa` empty).
- Editor literal-`\n` injection hit one block (`_spx_trading_dates`); fixed on file bytes with
  `perl -i -pe 's/\\n/\n/g'` (only the one broken line carried the token), then `py_compile` clean.

---

## Run

```bash
python3 runner/daa_paper_tracker.py                    # snapshot + print stats (idempotent)
python3 runner/daa_paper_tracker.py --stats            # forward stats since inception
python3 runner/daa_paper_tracker.py --check-staleness  # staleness JSON; exit 3 if >=2 days behind
bash scripts/daa_daily_track.sh                        # cron wrapper (logs to logs/daa_track.log)
```

Suggested cron slot (NOT installed — main's call): 21:55 UTC, staggered clear of the
21:30/21:35/21:45/21:50 heavy engine + tracker jobs.
