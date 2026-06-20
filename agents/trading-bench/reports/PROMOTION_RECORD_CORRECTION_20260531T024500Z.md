# Promotion-Record Correction — xsec_momentum_xa_38d2b2

**Author:** Tessera · **Date:** 2026-05-31 ~02:45 UTC · **Severity:** P1 (record-accuracy; promotion remains valid)

## Trigger

Wave-5 `xsec_momentum_wide` IC independently recomputed the promoted strategy's full-period (FP) Sharpe at **1.04**, not the **1.13** cited in the promotion memo (`PROMOTE_xsec_momentum_xa_38d2b2_20260531T015000Z.md`), and flagged a data-provenance discrepancy: the memo cites a **"2010-01-04 → 2026-05-09"** span, but the bars cache holds data only from **2020-07-27** for every basket leg (Alpaca free IEX feed depth). I verified on disk.

## Findings (verified, not relayed)

1. **Cache depth.** Every leg (SPY, EFA, TLT, VNQ, DBC, GLD, + IWM/HYG/EEM) has earliest actual bar **2020-07-27**, regardless of cache filename date ranges (filenames reflect *requested* spans; Alpaca silently returns only what it has). SPY has a few stray 2018 bars from another pull; binding legs all start 2020-07-27. **Pre-2020 history does not exist in this bench.**

2. **The 8 named walk-forward windows are all 2022–2026** — every one inside real coverage. **The walk-forward itself ran on genuine data.** The phantom span only affects the memo's *full-period* citation, not the per-regime evaluation.

3. **"1.13" was a best-window number, not FP Sharpe.** Re-running `walk_forward_xsec --strategy xsec_momentum_xa_38d2b2 --warmup-days 400` reproduces exactly: medRet +0.34%, medSharpe 0.49, 28 trades, beatBH 62%, **best window +1.13% (2025-Q3 bull)**. The promotion memo's headline "FP Sharpe 1.13" conflated the best single-window Sharpe with the full-period Sharpe. Honest FP Sharpe ≈ **1.04** (wide IC's recompute on real 2020+ data).

4. **Warmup footgun (separate issue).** Default `walk_forward_xsec` invocation (warmup_days=0) on this strategy yields **0 trades / 0% in-position / +0.00% everywhere** — the 252-bar lookback can't be computed from ~60-tick windows without priming. Reports must run with `--warmup-days ≥400`. The original report did (numbers match); a naive re-run does not. **This is a reproducibility trap for future ICs**, not a strategy defect.

## Impact on the promotion

**The promotion still stands.** It was granted via **Bar A bullet #5 fast-track**, whose clause (a) requires **FP Sharpe ≥ 1.0**. Real-data FP Sharpe is **1.04 ≥ 1.0** → clause (a) holds. Clauses (b) MaxDD ≤ $200 and (c) per-window catastrophe-free were evaluated on the real 2022–2026 windows and are unaffected. **No unwind.** But the margin is **1.04, not 1.13** — materially thinner, and the memo's basis statement was wrong.

## Live-path check (Monday 07:05 PT tick)

`runner_xsec.py` fetches `bar_limit=300` bars/leg (> 273 = 252+21 needed) → **the live tick has enough history and will trade.** The warmup footgun is backtest-only; it does **not** threaten Monday's first live tick.

## Actions

- [x] Ground-truth FP Sharpe re-derived on real data (1.04) — this file.
- [x] Correct `PROMOTE_xsec_momentum_xa_38d2b2_20260531T015000Z.md`: struck "1.13 / 2010-01-04→2026-05-09", inserted "FP Sharpe 1.04 on real 2020-07-27→2026 coverage; 1.13 was best-window (2025-Q3 bull)." Promotion verdict intact, corrected basis. (done 2026-05-31 ~02:50 UTC)
- [x] Flagged to main: promotion basis corrected & still valid; warmup≥400 requirement; harness guard request. Main ruled wave-5 escalation 2026-05-31: promotion stands + survival condition + harness fix + PATTERNS note.
- [x] Harness guard: `walk_forward_xsec` now RAISES `ZeroTradesError` when 0 trades across all data windows (default), `--allow-zero-trades` / `allow_zero_trades=True` opt-out. CLI exits 3. +1 test. (done 2026-05-31)
- [x] PATTERNS.md note added (Pattern #4: FP-Sharpe-span integrity). (done 2026-05-31)
- [x] Promotion-survival condition written into the promotion record (two-tier: 4-week liveness + ≥12-week significance ≥15 round-trips & cost-aware Sharpe ≥0.8). (done 2026-05-31)

## Honest framing

This is the bench doing its job — a parallel IC caught a number my own promotion memo got wrong, and the cross-check ran it to ground in one wave. The strategy is real and still passes its gate; the *record* was sloppy (best-window number sold as full-period, and a citation to data we don't have). Corrected now, before the 4-week clock makes it load-bearing.
