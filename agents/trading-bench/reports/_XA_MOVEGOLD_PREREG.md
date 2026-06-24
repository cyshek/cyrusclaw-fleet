# PRE-REGISTRATION — Cross-Asset MOVE / Gold-Copper Regime Overlay

**Lane:** XA_MOVEGOLD (research / candidate-only scope)
**Written:** BEFORE any backtest run (pre-commit of rules, grid, bars, eval).
**Agent:** research subagent for Tessera (trading-bench).
**Scope guardrails:** read-only on live — NO `strategies/`, NO crontab, NO paper-clock, NO promote, NO edits to any protected/evaluator file (`runner/{runner,risk,backtest,backtest_xsec,broker_alpaca}.py`). Candidate code lives in `strategies_candidates/xa_movegold/` only.

---

## 0. Hypothesis (the NEW, untested orthogonal angle)

Every prior REJECTED macro/cross-asset overlay used either equity-derived inputs or growth/credit/curve ETF momentum:
- `macro_nowcast` (FP +0.501) — growth/credit/curve from ETF prices + SPY/TLT/GLD rotation.
- `dollar_leadlag` (FP +0.547) — DXY/UUP.
- VIX-overlay / VIXTERM / SKEW — **equity** vol.

**None tested BOND-MARKET VOLATILITY (`^MOVE`, the rates analog to VIX) or the Gold/Copper growth-vs-fear ratio.** Hypothesis: bond-market stress (`^MOVE`) and the commodity growth/fear ratio (GC=F/HG=F) carry regime information orthogonal to equity price/vol, and can time SPX long/flat (or to a risk-off asset) on a raw-return basis that survives the bench's closet-beta / relabel killers.

**Mission bar = BEAT SPX RAW RETURN on the HONEST traded path** (vs total-return BH on the identical window, net of the same costs). Gates suspended → do NOT reject on sub-1.0 Sharpe alone; but the raw-return beat must be real (not a BH artifact), orthogonal, additive, and a plateau (not a knife-edge argmax).

---

## 1. Data (verified fetchable this session via `runner.daily_bars_cache.get_daily`)

| Symbol | n | span | role |
|---|---|---|---|
| `^MOVE` | 5835 | 2002-11-12 → 2026-06-18 | ICE BofA MOVE (Treasury rate vol) — SIGNAL |
| `GC=F` | 6476 | 2000-08-30 → 2026-06-23 | gold front future — SIGNAL |
| `HG=F` | 6481 | 2000-08-30 → 2026-06-23 | copper front future — SIGNAL |
| `^VIX` | 9186 | 1990-01-02 → 2026-06-23 | equity vol — SIGNAL (for MOVE/VIX ratio) |
| `SPY` | 8406 | 1993-01-29 → 2026-06-23 | traded (deep, for OOS path) |
| `QQQ` | 6864 | 1999-03-10 → 2026-06-23 | traded (alt) |
| `TLT` | 6013 | 2002-07-30 → 2026-06-23 | risk-off asset |
| `GLD` | 5431 | 2004-11-18 → 2026-06-23 | risk-off asset |
| `^GSPC` | 14239 | 1970+ | reference only (NOT traded; we trade SPY total-return) |

All inputs are **market-priced => point-in-time by construction** (a close printed on date d was knowable EOD d; futures/index prints are not revised). No release-lag/revision surface, no lookahead from the data itself. `adjclose` used for the traded path (total-return compounding). Cache: `data_cache/yahoo/` (module-managed).

---

## 2. Signals (TEST BOTH SIGNS — contrarian vs trend — for each)

Let `z_W(x, d)` = trailing z-score of series `x` over the last `W` observations whose date `< d` (STRICT; see §4).

1. **MOVE level z-score regime.** `s1 = z_W(MOVE, d)`. High bond-vol (z > thr) ⇒ risk-OFF (flat / to risk-off asset); low ⇒ risk-ON.
2. **MOVE/VIX ratio.** `r = MOVE/VIX`; `s2 = z_W(r, d)`. Rates-fear vs equity-fear regime gate.
3. **Gold/Copper ratio.** `gc = GC/HG`; trend `s3 = z_W(gc, d)` (also tested as `mom_W = gc(d)/gc(d-W) - 1`). Rising GC/HG = growth fear ⇒ risk-OFF; falling ⇒ risk-ON.
4. **2-feature combine** (only if 1 OR 3 shows life): MOVE-calm AND GC/HG-falling ⇒ risk-ON; else flat.

**Both signs** = for each signal we test the stated economic direction AND its inverse (so we never assume direction). A "sign" winning only because we cherry-picked it is flagged in the plateau check.

### Grid (pre-committed)
- Trailing window `W ∈ {63, 126, 252}`
- Threshold `thr ∈ {0.5, 1.0, 1.5}` (in z units; for the binary regime gate)
- Sign ∈ {trend, contrarian}
- Signals 1, 2, 3 standalone; signal 4 = combine(MOVE z<thr AND GC/HG falling)
- Deploy targets: `{SPY}` single-name timing; `{QQQ}` single-name timing; `{SPY,TLT,GLD}` rotation (risk-on→SPY, risk-off→TLT or GLD)
- Exposure: BINARY (full/flat) primary. (Proportional noted as secondary if a binary cell shows life.)

This is a pre-committed sweep (3 signals × 3 W × 3 thr × 2 signs × deploy-target families). The full grid is reported; we flag any isolated argmax vs broad plateau.

---

## 3. Bars / eval (MIRROR the proven-honest `_macro_nowcast_driver.py` EXACTLY)

- `from runner.backtest_xsec import backtest_xsec`
- `from runner.backtest import CostModel` → `CostModel.alpaca_stocks()` (spread_bps=2 one-way, fee_bps=0; round-trip ≈ 4 bps)
- `from runner.walk_forward import NAMED_WINDOWS` (the canonical 8-window panel)
- `from runner.fp_sharpe import fp_continuous_sharpe` → headline number
- `NOTIONAL=1000`, `START_CASH=1000`
- Single-name timing ({SPY} or {QQQ}) via the xsec idle-cash mechanism AND a {SPY,TLT,GLD} rotation, both through `backtest_xsec`.
- Benchmark = **BH-SPY total-return on the identical traded path**, net of the same CostModel. Report `beats_BH` wins / 8.

### KNOWN HARNESS CONSTRAINT (stated up front, not a leak)
`backtest_xsec` fetches the **traded** symbols' bars via `bars_cache.get_bars` (Alpaca IEX), which only reaches back to ~2018-11 (SPY) / ~2020-07 (QQQ/TLT/GLD). So the 8-window NAMED_WINDOWS panel (2022→2026) is the deepest the *standard harness* can go — identical to what `macro_nowcast` faced. **The SIGNAL** (`^MOVE`/GC/HG/`^VIX`) is read via `daily_bars_cache` (deep to 2002), so the signal is never starved; only the traded panel is Alpaca-bounded.

### DEEP OOS (the real train/test split — uses `daily_bars_cache` adjclose for BOTH signal and traded path)
Because the Alpaca panel cannot reach pre-2018, the frozen OOS split is run as a **self-contained long/flat vector backtest on SPY `adjclose` total-return**, 2003→2026, applying the **identical** `CostModel.alpaca_stocks()` round-trip cost (2 bps each side) on every regime flip. Frozen split: **train ≤ 2018-12-31, test ≥ 2019-01-01.** Report full-period AND test-only raw-return-vs-BH and continuous Sharpe. **OOS (test ≥ 2019) is what counts.** This is cost-honest and PIT-honest (adjclose, strict-prior signal), just not routed through the Alpaca-bounded xsec harness — which is a stated, deliberate choice to get genuine OOS rather than an in-sample-only panel.

---

## 4. STRICT anti-lookahead (pre-committed enforcement)

At a SPY/QQQ bar dated `d`, the signal may read ONLY `^MOVE`/GC/HG/`^VIX` closes dated **`< d`** (STRICTLY before d). Enforced via `daily_bars_cache.asof_strict(sym, d)` (asserts bar_date < d) in the xsec path, and via an explicit `date < d` slice in the deep-OOS vector path. **We chose STRICT `< d` (not `<= d`)** — the more conservative option — so even though index prints are EOD-knowable, no same-day close can inform a same-day fill. Traded fills occur at the traded bar's close on `d` (harness contract) / at `adjclose(d)` in the deep path; signal uses only `< d` data. This is leak-free by construction.

---

## 5. KILLER DIAGNOSTICS (the whole point — run all four, report numbers honestly)

**(a) RELABEL CHECK.** `corr(signal series, SPY trailing return)` AND `corr(signal, SPY trailing realized vol)`. `|r| > ~0.5` ⇒ disguised price/vol relabel ⇒ say so.

**(b) CLOSET-BETA CHECK (the FINRA failure mode).** `corr(daily exposure fraction, daily excess return)` and avg deployed-capital fraction. If exposure correlates ~+0.9 with excess return and we only "win" by staying ~fully invested, it's closet-beta with no timing edge. Report `corr(exposure, excess_ret)` and whether ANY config beats BH with deployed-fraction **< ~70–90%**.

**(c) ORTHOGONALITY-TO-WHAT-WE-RUN.** `corr(this signal's risk-on/off state, SMA-200-gate state on QQQ)` and `corr` to a 20d-realized-vol-target exposure on TQQQ. If it just reproduces SMA-200 / vol-target (already live in `leveraged_long_trend_paper` + `tqqq_cot_combo`), it adds nothing — quantify it.

**(d) KNIFE vs PLATEAU.** Show the full sweep grid; flag if the only good cell is an isolated argmax (overfit) vs a broad, sign-stable plateau.

---

## 6. Verdict rubric (pre-committed; honest negative = SUCCESS)

**PROMOTE-candidate** ONLY if ALL hold:
1. Beats SPX raw on the traded path **OOS** (test ≥ 2019 in the deep split; and ≥ bench on the 8-window panel), net of costs.
2. Survives (a) relabel — composite `|r|` to SPY-return AND SPY-vol both not ~price/vol.
3. Survives (b) closet-beta — beats BH with deployed fraction materially < ~full, and `corr(exposure, excess_ret)` not ~+0.9-and-nothing-else.
4. Survives (c) orthogonality — not a re-skin of SMA-200 / vol-target.
5. Is a (d) plateau, not a knife-edge argmax.

Otherwise **CLOSE** it with the single decisive killer number stated.

**The macro_nowcast trap to avoid:** vs `^GSPC` price-only a marginal overlay can look like a beat; vs total-return BH-SPY on the same path it loses. ALWAYS compare to total-return BH on the identical traded path.

---

## 7. Deliverables (committed)
- this prereg (written first) → `reports/_XA_MOVEGOLD_PREREG.md`
- full report → `reports/XA_MOVEGOLD_LANE_<UTCSTAMP>.md`
- throwaway driver → `reports/_xa_movegold_driver.py` + results JSON `reports/_xa_movegold_results.json`
- candidate (if created) → `strategies_candidates/xa_movegold/` ONLY
- protected-file md5 before+after (5 files) — report unchanged.

*Pre-registration complete. No backtest has been run at the time of writing this file.*
