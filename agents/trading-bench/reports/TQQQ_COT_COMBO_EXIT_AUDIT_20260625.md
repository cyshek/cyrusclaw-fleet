# TQQQ_COT_COMBO — Live Paper-Trading Exit Audit
**Date:** 2026-06-25 · **Auditor:** subagent (opus) · **Scope:** READ-ONLY forensics · **No files/trades/params/cron modified.**

---

## VERDICT: **(b) WORKING AS DESIGNED**

`tqqq_cot_combo` is a **vol-target + SMA-200-gated accumulator**, not a discrete entry/exit trader. The 10-buys / 0-sells streak is the strategy **ramping a single position from $0 to its full target weight**, throttled by the 4-trades/day risk cap. The exit logic is **present, correctly wired, and reachable** — it simply has not fired because the SMA-200 risk-gate has been **ON the entire window** (QQQ is **+12.65% above its 200-day SMA**). The −$43 is **mark-to-market drawdown on a fully-deployed position, well within tolerance — not a broken exit.**

**Recommendation: KEEP. No code change required.** (One optional hardening note in §7.)

---

## 1. How it decides — target-weight rebalancer, not buy/sell signals

`decide()` (strategies/tqqq_cot_combo/strategy.py) computes a **target weight** each tick and rebalances toward it:

```
final_weight = min(target_ann_vol / realized_vol_20d, w_max=1.0) * cot_scale
target_qty   = floor(final_weight * notional / price)
delta        = target_qty - current_qty
churn_thresh = max(1, floor(0.05 * target_qty))
```

It emits **buy / sell / close / hold**. There are **THREE distinct exit/de-risk paths**, all verified live:

| # | Exit path | Exact trigger (quoted) | Action emitted |
|---|-----------|------------------------|----------------|
| **A** | **SMA-200 gate OFF** | `gate_up = last_close > sma_val`; `if not gate_up: if current_qty>0: return Action("close", ...)` — QQQ closes **below** its 200-day SMA | `close` → runner sells **full** qty |
| **B** | **Vol-target downside trim** | `if delta < -threshold: return Action("sell", -delta sh)` — realized vol **rises** (or COT halves weight) so target_qty drops below holdings | `sell` (partial trim) |
| **C** | **Target collapses to 0** | `if target_qty <= 0: if current_qty>0: return Action("close", ...)` | `close` → full sell |

The COT overlay (`_get_cot_scale`) multiplies weight by **0.5 when ES AM-net is declining WoW** (3-day pub-lag enforced), which can *trigger path B* but cannot itself force a full exit.

---

## 2. Params (live vs backup)

| key | **live params.json** | backup (20260624T160502Z) |
|-----|------|--------|
| symbol / underlying | TQQQ / **QQQ** | TQQQ / QQQ |
| target_ann_vol | 0.40 | 0.40 |
| vol_window | 20 | 20 |
| w_max | 1.0 | 1.0 |
| cot_scale_bearish | 0.5 | 0.5 |
| **notional** | **160.0** | 1000.0 |
| sma_gate_window | **200** | 200 |

> ⚠️ **Note (not a bug, but flag-worthy):** live `notional` is **$160**, but the position was built to ~$1000 cost basis and the rankings row shows `turnover_usd=1000`. The 10 buys were placed under the **old $1000 notional**; params were trimmed to $160 at the 2026-06-24T16:05 backup timestamp. At $160 notional the target_qty is now ~2 shares, **far below the 12.7 held** — see §6, this actually makes an exit *more* imminent, not less.

---

## 3. Live trade history (tournament.db `trades`, strategy='tqqq_cot_combo')

All 10 rows are `side=buy`, `status=filled`. **Zero sells.** Confirmed.

| # | ts_utc | qty | px | QQQ close / SMA200 / gate |
|---|--------|-----|----|---------------------------|
| 46 | 06-15 13:30 | 1.21 | 82.75 | 721.31 / 625.36 / **ON** |
| 48 | 06-16 13:30 | 1.19 | 83.93 | 743.81 / 626.21 / **ON** |
| 50 | 06-17 13:30 | 1.23 | 81.35 | 729.87 / 626.98 / **ON** |
| 56 | 06-18 13:30 | 1.22 | 82.24 | 722.48 / 627.74 / **ON** |
| 61 | 06-22 13:30 | 1.19 | 84.22 | 739.82 / 628.61 / **ON** |
| 68 | 06-23 13:30 | 1.34 | 74.62 | 738.10 / 629.45 / **ON** |
| 69 | 06-24 13:30 | 1.35 | 74.31 | 713.58 / 630.14 / **ON** |
| 72 | 06-24 14:00 | 1.34 | 74.52 | 714.77 / 630.83 / **ON** |
| 73 | 06-24 14:30 | 1.33 | 74.97 | 715.05 / 630.84 / **ON** |
| 74 | 06-24 15:00 | 1.31 | 76.09 | 719.53 / 630.86 / **ON** |

**Net position:** 12.707 sh · **Cost basis:** $999.90 · **Avg entry:** $78.69
**Realized P&L:** $0.00 · **Unrealized (system-of-record rankings @ 06-25T00:00):** **−$43.05** · (at latest TQQQ 73.30 close: ≈ −$68; both are MTM noise on a 3x ETF.)

**Why so many small buys:** the **4-trades/day risk cap** (`risk.MAX_TRADES_PER_DAY=4`) chops the ramp-to-target into pieces. Decision log confirms: after hitting cur_qty=12 the strategy logs `skip_risk: already 4 trades today; cap 4` and then `hold: within threshold |delta|=1<=1`. **It has converged.** This is throttled accumulation, not runaway buying.

---

## 4. Exit reachability — PROVEN by direct simulation

I called the live `decide()` with the live params under synthetic QQQ paths:

```
[GATE ON  (QQQ>SMA), vol low, holding 12] -> action=SELL  -10sh   (path B: vol-target trim fires)
[GATE OFF (QQQ<SMA),          holding 12] -> action=CLOSE         (path A: full de-risk fires)
[GATE OFF (QQQ<SMA),          flat]       -> action=HOLD          (correct: stay flat)
```

And the **runner** (runner/runner.py L453-471) executes `close` as a **real broker sell**:
```python
if action.action == "close":
    held_qty = position_state[symbol]["qty"]
    order = client.submit_market_order(symbol, "sell", qty=held_qty)   # REAL downside sell
```
The runner also fetches **genuine QQQ daily closes from Alpaca** (L224-235) and passes them as `underlying.closes` — so live gating uses **real QQQ**, not the TQQQ proxy. Verified: strategy's logged `SMA200=630.86` matches independently-computed QQQ SMA-200 = **630.84** (Yahoo v8). **The exit is not dead code; it is armed and correctly plumbed end-to-end.**

---

## 5. Gate distance RIGHT NOW

| metric | value |
|--------|-------|
| QQQ last close (raw) | **710.62** |
| QQQ SMA-200 (raw) | **630.84** |
| Distance above gate | **+12.65%** (abs $79.78) |
| **QQQ drop needed to flip gate OFF → full CLOSE** | **−11.23%** (QQQ must close below 630.84) |

The gate is **firmly risk-ON**. That single fact explains every "no sell." A ~11% QQQ drawdown (≈ −33% in 3x TQQQ terms) would flip it and the strategy would **sell the entire position to cash** — exactly the "cash 93% of 2022" behavior in the strategy's validation memo.

---

## 6. Is it DEGENERATE (unbounded accumulation into a falling knife)? — NO

Two independent ceilings prevent unbounded accumulation:
1. **Vol-target weight cap:** `w_max=1.0` → max deployed = 1.0 × notional. It **cannot** buy past `notional/price` shares. With QQQ rising it stays pinned at w=1.0 and simply **holds** (as it does now: `hold |delta|=1<=1`).
2. **Position is self-limiting on the downside too:** when TQQQ falls, target_qty = floor(w×notional/price) actually *rises slightly* (lower price → more shares for same $), BUT the dominant downside control is the **SMA-200 gate**, which liquidates the whole book before a true bear market. TQQQ's own price can't drag the share-target unboundedly because notional is fixed.

Critically, with the **new $160 notional**, target_qty ≈ floor(1.0 × 160 / 73) ≈ **2 sh**, vs **12.7 held**. `delta = 2 − 12 = −10 < −threshold` → **the very next unthrottled tick will emit a `sell` (path B) to trim ~10 shares.** So an exit is not merely *reachable in theory* — it is **imminent under the current params** the moment the daily trade-cap and market-open allow it. (The accumulation we see is a relic of the pre-trim $1000 notional.)

There is **no hard stop-loss** (it's gate-based, not %-based), which is by design for a trend-following 3x sleeve — the SMA-200 gate *is* the stop. Not degenerate.

---

## 7. Bottom line + recommendation

- **Net position:** 12.707 TQQQ @ $78.69 avg · **Cost basis** $999.90 · **MTM** −$43.05 (rankings) / ≈ −$68 (spot)
- **Realized P&L:** $0.00 (correctly — nothing has sold because nothing *should* have)
- **Gate status:** **ON**, QQQ **+12.65%** over SMA-200; needs **−11.2%** QQQ to trigger a full CLOSE
- **Exit logic:** present, correctly wired, simulation-proven reachable on BOTH paths (vol-trim `sell` + gate `close`), and the runner executes real downside sells

**→ KEEP. Do not disable, do not mark broken, no stop needed.** This is a textbook SMA-gated vol-target accumulator behaving exactly to spec; the drawdown is ordinary MTM noise on a 3x ETF inside a risk-ON regime.

**Optional follow-ups (non-blocking, your call — not bugs):**
1. **Expect a ~10-share SELL imminently** now that notional was cut $1000→$160; if you do NOT want it to trim back to a ~$160 sleeve, revisit the notional. If you do, no action needed — let it rebalance.
2. The 4-trades/day cap makes the ramp look like "spam buying." Cosmetic only; consider raising the cap for this slow daily strategy if the noisy trade log bothers the tournament view.
3. Consider logging realized/unrealized MTM per-strategy to a positions table so future audits don't have to recompute from `trades` × spot.
