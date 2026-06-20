# Harness Integrity Audit — trading-bench (Tessera)

**UTC timestamp:** 20260531T190026Z
**Auditor:** measurement-integrity subagent (depth 1)
**Scope:** backtest.py, walk_forward.py, walk_forward_xsec.py, backtest_xsec.py, risk.py, correlation.py, bars_cache.py, GATE.md
**Mandate:** verify the harness lies in NEITHER direction (false-positive promotes OR false-negative rejects). Audit only — no runner-logic changes except a demonstrated measurement bug pinned by a test.
**Suite at audit start:** 226 passing (`pytest -q` → `226 passed in 7.04s`).
**Strategy promotions performed:** ZERO.

---

## TL;DR verdict

**Can we trust the bench's verdicts? → YES, WITH CAVEATS.**

The harness is structurally honest on the things that have actually bound past decisions (returns, cost application, lookahead, cache-floor discipline, trade-cap, zero-trade guard). But it carries **two real measurement defects, both of which bias toward UNDER-stating risk / OVER-stating quality** — i.e. toward false-positive promotes, the more dangerous direction:

- **FINDING 1 (most important): `max_drawdown_pct` measures the diluted 90%-cash portfolio NAV, not the deployed instrument.** A −50% instrument crash reports as **−5.0%** maxDD (reproduced below). Every drawdown-based gate clause is fooled. This is the *exact* leveraged-ETF bug class, and it is live in the gate.
- **FINDING 2: Sharpe annualization for `1Day` uses √365, not √252.** Daily bars are trading-days-only (verified ratio 0.719 ≈ 252/365), so daily Sharpe is **inflated ~20%** (√(365/252)=1.204×).

Neither has been *fixed* in this audit (Finding 1 needs a design decision on the right denominator; Finding 2 is a one-line fix but I am leaving runner logic untouched per mandate and recommending it loudly instead — see "Most important fix"). Both are documented with reproductions so the next decision-maker can act with eyes open.

**The prior leveraged-ETF and xsec rejections still STAND** (see final section) — neither was promoted, and both defects bias toward *promoting*, so a reject produced despite these defects is conservative and safe. The risk is entirely on the *promote* side going forward.

---

## Checklist results

### 1. Drawdown denominator — **FAIL (LOUD)** ⛔ — most important

**Claim under test:** is `max_drawdown_pct` computed on deployed-strategy NAV or diluted by idle cash, and is the diluted number the one gates use?

**Evidence (code):** `backtest.py` computes maxDD over `equity_curve`, where `equity = cash + qty*close` (line ~ "equity = cash + qty * close"). With $1000 starting cash and a $100-notional deployment, ~90% of equity is idle cash that never moves. The drawdown denominator is the full $1000 portfolio, not the $100 at risk.

`backtest_xsec.py` is identical: `equity = cash + Σ qty*px` then `dd = (e-peak)/peak`.

**Reproduction (synthetic, costs off):** strategy deploys $100 of $1000 into an instrument that falls 100→50 (−50%) then recovers:
```
Portfolio-NAV maxDD (reported): -5.0 %
equity curve: [1000, 990, 970, 950, 960, 980, 1000]
Instrument price drawdown: -50.00 %
```
The harness reports **−5.0%** for a **−50%** instrument move. 10× understatement — precisely the dilution factor ($100/$1000).

**Does a gate consume this?** YES, three places:
- `GATE.md` Bar A bullet **#5** post-cost MaxDD ≤30% (line 22) and bullet **#5(b)** "full-period max drawdown ≤ 2×MAX_NOTIONAL ($200) in absolute USD."
- `walk_forward.py` / `walk_forward_xsec.py` surface `max_dd_pct` into every per-window row and the markdown reports a human reads when deciding.

**Why this is worse than it looks for #5(b):** because #5(b) is an *absolute USD* bound ($200) measured on the diluted NAV, a strategy could lose **100% of its deployed $100** (a total instrument wipeout) and the portfolio NAV would drop only ~$100 — comfortably under the $200 cap. **The drawdown gate literally cannot detect a full blow-up of the deployed capital.** That is a false-negative-on-risk hole big enough to drive the leveraged-ETF candidate through.

**Note — the harness already has the right number, unused:** per-trade excursion (`closed_trades[].max_drawdown_pct`) IS computed against `avg_entry_price` (instrument-level, line "max_dd_from_entry = (trade_low_seen - avg_entry_price)/avg_entry_price"). It is correct and instrument-relative — but it is (a) per-closed-trade only (empty while a position is open, as in the repro), and (b) **never aggregated into any gate metric.** The honest denominator exists; it just isn't wired to the decision.

**RECOMMENDED FIX (design decision required — not applied here):** report a **deployed-capital / instrument-NAV drawdown** alongside the portfolio number, and make the gate consume the deployed one. Cleanest options:
- (A) Track a parallel "deployed-NAV" curve = (cash committed to the strategy + position MV) / peak-committed, OR simpler:
- (B) compute max peak-to-trough on the **position market-value series** (qty*close) over each open episode, and surface `max_instrument_dd_pct`. Gate on `max(portfolio_dd, instrument_dd)` or switch the #5(b) clause to instrument basis.
- Minimum viable: aggregate the existing per-trade `max_drawdown_pct` (already correct) into a `worst_trade_dd_pct` aggregate and add it to the gate.

This needs a one-line-of-judgment call on which denominator the gate should bind (Cyrus/main), so I am **flagging not fixing**, per "don't change runner logic except for a demonstrated bug I also pin with a test." This IS demonstrated, but the *fix* is a metric-definition/gate-policy change, not a bug-correction, so it belongs to the gate owner.

---

### 2. Sharpe/Sortino annualization + cadence — **FAIL** ⛔ (real, ~20% Sharpe inflation on daily)

**Evidence:** `backtest.py` `BARS_PER_YEAR["1Day"] = 365`; Sharpe = `(mean/std)*sqrt(bpy)`. So daily Sharpe is annualized with **√365 = 19.10**.

**But daily stock bars are trading-days-only.** Verified against cached SPY 1Day data:
```
span calendar days=57, bar count=41, ratio=0.719  (≈ 252/365 = 0.690)
```
The return series has ~252 points/yr, not 365. Correct annualization factor is **√252 = 15.87**. Using √365 inflates every daily Sharpe by **√(365/252) = 1.204×** — a flat ~20% overstatement.

**Impact on past decisions:** the cross-asset wave-4 candidates are `1Day` cadence. Their headline "FP Sharpe 1.04 / 0.97 / 0.98" were computed with the inflated factor. **De-inflated, 1.04 → ~0.86, 0.98 → ~0.81, 0.97 → ~0.81.** The promoted `xsec_momentum_xa_38d2b2` (1.04) would drop to **~0.86 — BELOW the 1.0 fast-track bar.** ⚠️ This does NOT auto-unwind the promotion (it cleared on the then-recorded number and also clears the independent return-floor #5(f) at 11.6%/yr, which is unaffected by this bug), but **the Sharpe ≥1.0 leg of that promotion is suspect and should be re-derived on √252.** Flag to main.

**Why "no false negatives" is also touched:** the rejects blocked on *median per-window* Sharpe (e.g. momentum_xa median 0.49 vs 0.5 bar) used the same inflated factor — so the TRUE median Sharpe is even lower (~0.41). The rejects are therefore *more* justified, not less. Inflation only endangers the promote side.

**Crypto note:** crypto trades ~24/7/365, so √365 is approximately right for crypto `1Day` — but all crypto is retired, so this only matters for stocks, where it's wrong. A single global `BARS_PER_YEAR["1Day"]` can't be right for both; the correct fix keys off symbol class.

**RECOMMENDED FIX (one line, but runner logic — flagging not applying):** make the daily annualization factor symbol-class-aware: 252 for equities, 365 for crypto. Concretely, pass a `periods_per_year` into the Sharpe calc derived from `is_crypto`. Pin with a test asserting a known daily return series annualizes with √252 for a stock symbol. I did not apply it because it changes every historical Sharpe number in the repo and must be a deliberate, announced recalibration (it will move the gate), not a silent subagent edit.

---

### 3. Benchmark alignment — **PASS** ✅

**Evidence:** `walk_forward._benchmark_spy_return` and `walk_forward_xsec._bh_basket_return` both:
- fetch the benchmark over the **same `(end_dt, days)`** window as the strategy backtest (same date span — verified, same args threaded through),
- apply the **same CostModel** (buy at ask / sell at bid via `alpaca_stocks`),
- and **scale to the same cash base**: `ret = price_ret * (notional_usd / starting_cash)` (the explicit 0.1× amplifier).

The scaling comment is exactly right and load-bearing: without it a −17% SPY move would be compared against the strategy's diluted −1.7% equity move and the strategy would "win" on lower exposure alone. They got this one correct. Benchmark and strategy are apples-to-apples on **both** return and the cash-base denominator. **The dilution that breaks Finding 1 is correctly neutralized here** because both sides are diluted identically.

Caveat (minor): because the comparison is symmetric-diluted, "beats BH" is an honest *relative* signal, but the *absolute* return number a human reads is still the diluted 0.1× figure. That's fine as long as readers know it (HANDOFF/GATE #5(f) already pin "deployed notional" as the absolute-return denominator, which is the right antidote).

---

### 4. Lookahead / cache-floor honesty — **PASS, with one CAVEAT** ✅⚠️

**Lookahead — PASS.** At bar `i` the strategy sees `bars[:i+1]` and fills at `bars[i].close`. That is an **end-of-bar decision filled at the same bar's close** — both the decision input (close) and the fill price (close) are known at decision time. No off-by-one: the strategy cannot act on bar `i+1` data, and it does not fill at a price it couldn't have known. Xsec is identical (`bars[:cur+1]`, fill at `last_price = bars[cur].close`, and crucially **only if `has_bar_at_t`** so a stale-priced symbol can't fill). Regime SPY slice is also `t[:10] <= bar_date` — no same-day-future leak. ✅

**Cache floor — PASS as discipline, CAVEAT as enforcement.** The 2020-07-27 floor is a **data-coverage fact, not a code guard.** `bars_cache.get_bars` requests whatever date range it's asked for; Alpaca silently returns only the bars it has (pre-2020 portion contributes zero bars). Cache *filenames* reflect the *requested* range (e.g. `SPY_1Day_2004-07-03_...` exists), so a naive reader could believe a 2004 span is real when only post-2020 bars populate it. This is exactly the phantom-span trap PATTERNS.md Pattern #4 documents. **The protection is procedural (Pattern #4 hard rule: every claim states real span ≥ 2020-07-27) plus the `ZeroTradesError` guard, NOT a hard floor in code.** A future careless memo could still cite a phantom span if the author ignores Pattern #4.

**CAVEAT / optional hardening (not applied):** consider a cheap assertion in the walk-forward path that logs/warns when a window's earliest *returned* bar is later than the requested start by more than a tolerance (i.e. the feed truncated the window) — turns the procedural rule into an automatic tripwire. Low priority; Pattern #4 + ZeroTradesError already cover the incident that actually occurred.

---

### 5. Cost-model realism — **PASS** ✅

**Evidence:**
- Defaults are **non-zero**: single-symbol WF uses `CostModel.for_symbol` (2bps one-way stocks / 200bps crypto); xsec WF uses `CostModel.alpaca_stocks()` (2bps). Zero-cost is reachable **only** via explicit `--no-costs` / `CostModel(0,0)` — no silent zero-cost default path.
- Costs are applied **per round trip in both harnesses.** Buys fill at `close*(1+spread/1e4)` and pay `fee_on(notional)`; sells/closes fill at `close*(1-spread/1e4)` and pay `fee_on(proceeds)`. Verified at both the single-symbol fill sites and the xsec close/buy sites (`cm.buy_fill_price`/`cm.sell_fill_price` + `cm.fee_on` present in both, plus `total_costs_usd` accumulation).
- **Modeled round-trip cost for a typical stock trade:** 2bps one-way spread × 2 sides = **4bps = $0.04 on a $100 notional** (fees 0 for Alpaca commission-free equities). Crypto would be 200bps×2 = 4% round-trip = $4.00/$100 — which is exactly why crypto was retired. Both numbers match the documented venue assumptions.

No zero-cost sneak path. The cost model is conservative-to-realistic for liquid US ETFs.

---

### 6. Trade-cap truncation (basket) — **PASS** ✅

**Evidence:** `backtest_xsec.backtest_xsec` computes `max_trades_per_day = risk_mod.resolve_trades_per_day(params)` once (line 354) and threads it into **both** inner `_bt_check_trade` sites — the close loop (line 613) and the buy loop (line 706). `walk_forward_xsec` calls `backtest_xsec` with the same `params`, so the basket-aware cap propagates to the WF path. The 2026-05-30 fix holds in walk_forward_xsec, not just backtest_xsec. ✅

**Reproductions:**
- K=5 declared (`xsec_basket_size:5` → cap `max(4,10)=10`): all 5 legs open same tick, `n_buys=5`, zero skips. Not truncated. ✅
- 5 legs, all same day/tick, **no** declaration (legacy cap 4): 4 fill, **5th correctly skipped** (`"already 4 trades today; cap 4"`). ✅
- Subtle benign behavior worth noting: when bars span multiple days, an undeclared-basket leg skipped on day 1 by the cap **defers and fills on day 2** (still flat, fresh quota) rather than being dropped — so it's not a *permanent* silent drop, just a one-day deferral. The `xsec_basket_size` declaration removes even the deferral. Not a bias source for declared baskets.

33 cap/basket/zero-trade tests pass. No silent leg-dropping for properly-declared baskets.

---

### 7. Zero-trade / warmup starvation — **PASS** ✅

**Evidence:** `walk_forward_xsec` raises `ZeroTradesError` when `n_windows_with_data > 0 and total_trades == 0 and not allow_zero_trades` (guard block present, well-commented, tied to the 2026-05-31 momentum_xa correction). `test_zero_trades_guard_raises_by_default` (tests/test_walk_forward_xsec.py:318) pins it. A warmup-starved 252d-lookback strategy that silently does nothing now **errors loudly** instead of reporting phantom +0.00% as a pass. The override (`--allow-zero-trades`) is explicit and documented as "do not cite its numbers."

**Caveat (scope):** this guard lives in `walk_forward_xsec` only. The single-symbol `walk_forward` has **no equivalent all-zero-trades guard** — a warmup-starved single-symbol slow-lookback strategy could still report +0.00% across windows silently. No single-symbol slow-lookback candidate has hit this yet, but it's an asymmetry worth closing if single-symbol 252d-lookback archetypes get added. Low priority; flagged.

---

## Summary table

| # | Item | Verdict | Direction of bias if wrong |
|---|------|---------|----------------------------|
| 1 | Drawdown denominator | **FAIL** ⛔ | understates risk → false-positive promote |
| 2 | Sharpe annualization (√365 vs √252) | **FAIL** ⛔ | inflates Sharpe ~20% → false-positive promote |
| 3 | Benchmark alignment | PASS ✅ | — |
| 4 | Lookahead / cache floor | PASS ✅ (+caveat: floor is procedural, not code-enforced) | — |
| 5 | Cost-model realism | PASS ✅ | — |
| 6 | Trade-cap truncation (basket) | PASS ✅ | — |
| 7 | Zero-trade / warmup guard | PASS ✅ (+caveat: single-symbol WF lacks the guard) | — |

---

## Final verdict

**(a) Can we trust the bench's verdicts? → YES, WITH CAVEATS.**
Every *reject* the bench has produced is trustworthy and conservative — both open defects bias toward *over*-stating quality, so a strategy rejected despite them is safely rejected. The caution is entirely on the **promote** side: the drawdown gate cannot see instrument-level blow-ups, and daily Sharpe is ~20% inflated. Until Findings 1 & 2 are fixed, treat every Sharpe-≥1.0 and drawdown-based promote as provisional and re-derive on corrected metrics.

**(b) Single most important fix:** **Finding 1 — make the gate's drawdown metric measure the deployed instrument, not the 90%-cash portfolio NAV.** It is the same class of bug as the leveraged-ETF incident that triggered this audit, it is live in GATE Bar A #5(b), and in its current absolute-USD form it cannot even detect a 100% loss of deployed capital. Wire the (already-correct) per-trade instrument-relative drawdown into an aggregate gate metric, or add a deployed-NAV drawdown curve. (Runner/metric change — needs gate-owner sign-off, hence flagged not applied.)

**(c) Do prior rejections still stand?**
- **Leveraged-ETF candidate: REJECT STILL STANDS — and is now better-justified.** It was rejected for instrument-NAV drawdown ~−65% that the portfolio metric hid as −9.6%. This audit confirms the portfolio metric is the unreliable one; the human override that caught it was correct, and Finding 1 is the systematic version of that catch. No reason to revisit.
- **xsec rejections (236b86, lowvol c3783c, sector_rot b7a2f9, lowvol_xa, sector_rot_xa) STILL STAND.** They were blocked on Sharpe/in-position/return-floor criteria. The Sharpe-annualization bug (Finding 2) makes their TRUE Sharpes *lower* than recorded, so the rejects are *more* justified, not less. None flips to a promote.
- **`xsec_momentum_xa_38d2b2` (the one live promotion): FLAG — re-derive its Sharpe on √252.** Recorded FP Sharpe 1.04 → ~0.86 de-inflated, which is below the 1.0 fast-track bar. It independently clears the #5(f) return floor (11.6%/yr, unaffected by this bug), and it was promoted on the then-current recorded number, so this is **not an emergency unwind** — but the Sharpe leg of that promotion is now suspect and should be recomputed and re-ratified by main on corrected annualization before the 4-week liveness clock is trusted as a pass.

**Suite count:** 226 passing, unchanged (no code modified in this audit).

---

## Appendix — what I did NOT change and why

Per mandate I made **zero code edits**. Findings 1 and 2 are demonstrated measurement defects, but:
- Finding 1's *fix* is a metric-definition + gate-policy decision (which denominator binds the gate), not a mechanical bug-correction — it belongs to the gate owner (Cyrus/main).
- Finding 2's *fix* (√252 for equities) is a one-line change that **moves every historical Sharpe in the repo and will move the gate** — it must be a deliberate, announced recalibration with re-ratification of the momentum_xa promotion, not a silent subagent edit.

Both are pinned here with reproductions so they can be fixed correctly and with a test, by the owner, in a follow-up. Recommended follow-up: a `harness_metric_fix` task that (1) adds instrument-NAV drawdown + gates on it, (2) makes daily annualization symbol-class-aware, (3) adds the pinning tests, (4) re-derives the wave-4 Sharpes and re-ratifies/​unwinds the momentum_xa promotion accordingly, keeping the suite green.
