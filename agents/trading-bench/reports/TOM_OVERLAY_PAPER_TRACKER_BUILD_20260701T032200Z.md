# TOM OVERLAY — PAPER TRACKER BUILD & LAUNCH

**Run:** 20260701T032200Z (local 2026-06-30 ~20:22 PDT) · **Agent:** trading-bench · **Mode:** paper-research forward clock (NO live orders, NO protected-file edits, side-DB only)
**Trigger:** Cyrus (2026-06-30 ~20:18 PDT) explicitly loosened the paper leverage rail — *"i don't think you need my approval for these. Even previous strategies you tested had leverage."* ETF-form leverage on paper is now the agent's call; the live book already runs TQQQ/UPRO/SOXL. This discharged the last gate on the TOM overlay (production-harness verdict was already GO-for-paper).

---

## What shipped

A daily forward PAPER CLOCK for the Turn-of-Month (TOM) leverage-concentration OVERLAY at the **recommended shelf config** from `reports/TOM_OVERLAY_PRODUCTION_HARNESS_20260630T050146Z.md` (GO-for-paper). READ-ONLY forward evidence; **NOT wired into the live roster**.

- **`runner/tom_overlay_paper_tracker.py`** (new, ~27 KB) — mirrors `runner/crash_sleeve_paper_tracker.py` verbatim in structure. Reuses `reports/_tom_overlay_harness.py` verified primitives DIRECTLY (`load`, `daily_returns`, `align_returns`, `tom_mask`, `overlay_etf`, `stats`) — **zero return-math reimplementation**. The harness file itself is byte-unchanged (md5 c1972269).
- **`scripts/tom_overlay_daily_track.sh`** (new, executable) — snapshot + staleness-guard wrapper, mirrors `crash_sleeve_daily_track.sh` / `daa_daily_track.sh`. Logs to `logs/tom_overlay_track.log`.
- **Cron:** `0 22 * * 1-5` (22:00 UTC Mon–Fri, staggered +5min after the 21:55 daa / 21:50 crash_sleeve / 21:45 gate-dashboard jobs — after US cash close + settle). Crontab backup `memory/crontab_backups/crontab_20260701T032243Z.bak` (30→32 lines, clean +2-line append, every other agent's job byte-identical; verified by diff).
- **`tests/test_tom_overlay_paper_tracker.py`** (new, 15 tests, all pass).
- DB: `tom_overlay_paper.db` (side DB, workspace root).

## Shelf config tracked (exactly what the clock marks)

```
Base exposure : 1.0x the index EVERY day (keep beta -- never go flat)
TOM window    : last pre=2 + first post=3 trading days of the month-turn
                (PURE calendar date mask, NO price lookahead; ~23.8% of days)
Tilt          : +0.5 EXTRA index exposure during the window (conservative start)
Tradeable form: rotate w = tilt/(k-1) = 0.25 of the book into a 3x ETF during TOM, back out after
                UPRO(3x) for the S&P book, TQQQ(3x) for the Nasdaq book
Cost          : 2bps one-way on every rotation into/out of the ETF
```

Two books tracked side by side, each vs its own **B&H 1x control** (the exact thing the overlay must beat on RAW RETURN — the headline claim), plus the SPX index:
- **SPX-book:** SPY base / UPRO 3x leg (conservative headline; +0.1pp DD in the harness).
- **NDX-book:** QQQ base / TQQQ 3x leg (bigger raw lift, bigger DD).

## Engine reproduction (first row, 2026-06-30)

Cross-checks against the validated production-harness numbers:
- SPX-book overlay full backtest Sharpe **0.900** (harness UPRO shelf 0.858 canary / 0.894 B&H band ✓), window 2009-06-25→2026-06-30 (UPRO inception floor ✓).
- NDX-book overlay full backtest Sharpe **0.990** (harness TQQQ 0.954/0.982 ✓), window 2010-02-11→2026-06-30 (TQQQ inception floor ✓).
- 2026-06-30 was a TOM day (last 2 of June) → tilt correctly ENGAGED; overlay beat B&H raw on both books (+0.35pp SPX, +0.81pp NDX) as the 3x tilt amplified an up-day.

## No-lookahead (the make-or-break)

The TOM window is a PURE function of the ordered calendar date axis (`tom_mask` takes only the date list; no price input). The decision for date D ("is D a TOM day?") is known before D opens. The ETF leg uses the ETF's OWN realized adjclose return on D (`align_returns` keys to the ETF's consecutive bars; a missing ETF bar falls back to pure 1x — never invents a return). The harness's +1-bar canary (shift mask to the WRONG day → Sharpe degrades) proved this is a calendar TIMING edge, not same-bar leakage. Tests pin the mask's price-independence + the canary-shift-later property.

## Honest caveats (carried from the harness verdict — why paper-track, not deploy)

1. Modern-ETF statistical significance is WEAK (Welch t ~1.1–1.5 on SPY/QQQ; only deep 1970s/1980s ^GSPC/^NDX history is properly significant).
2. The edge is leverage-amplified BETA-TIMING, not alpha with hedge value; the ETF-form DD cost is understated by a benign post-2009 OOS window (no 2000/2008 bear inside a TOM window).
3. This is a RAW-RETURN engine, not a Sharpe improver in leveraged form. The forward clock exists precisely to see whether the calendar tilt keeps paying its leverage cost going forward.

## Safety / rails

- **All 6 protected md5s unchanged** (runner 0f763975, risk e303317e, backtest 717c36e6, backtest_xsec d8927364, walk_forward_xsec 8c3df32c, safety_backstop bccefaba).
- No live orders, no live-roster change, no crontab churn beyond the +2-line append. Killswitch absent (live trading unaffected).
- Full suite **949 passed / 3 skipped** (+15 new tests, zero regressions).
- Idempotent on date; staleness guard (exit 3 if ≥2 trading days behind) so a silent-clock hole alarms.

## Read the clock

```
python3 runner/tom_overlay_paper_tracker.py            # snapshot + stats
python3 runner/tom_overlay_paper_tracker.py --stats    # forward stats since inception
python3 runner/tom_overlay_paper_tracker.py --check-staleness
```
The number to watch forward: per-book `overlay_vs_bh_pp` (does the calendar tilt add raw return over plain buy-&-hold on the path observed).
