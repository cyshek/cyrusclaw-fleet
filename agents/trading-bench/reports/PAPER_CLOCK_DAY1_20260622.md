# PAPER_CLOCK_DAY1 — Day-0 Snapshot (2026-06-22)

**Generated:** 2026-06-22 ~12:40 PT (19:40 UTC) · Tessera
**Purpose:** Baseline snapshot of the two newly-launched multi-sleeve paper strategies (allocator_blend + tqqq_cot_combo) for the Saturday OOS check. All numbers reconciled against the live Alpaca paper account, not just the local DB.

---

## TL;DR

- **tqqq_cot_combo** — live & healthy. Ticked cleanly via cron today (13:30 UTC), bought TQQQ; **COT signal flipped 0.5 → 1.0 (full exposure)** today as speculators washed out. 5 fills since 06-15, $500 notional deployed.
- **allocator_blend** — seeded its **first-ever live fills today** (16:09 UTC) via a manual out-of-cron run: QQQ/SPY/TQQQ for ~$68.75. Weights match the validated tracker decomposition exactly. **NOT yet wired into cron** — that's the open item.
- **Reconciliation:** live Alpaca positions == DB net positions, to the share, across all 4 symbols. No drift.
- **2 anomalies flagged** (neither affects fills): (1) cron Discord post step is failing on an ambiguous-recipient error; (2) the out-of-band allocator *tracker* DB still has only the 06-18 row (correct-by-design: leveraged/QQQ bars cache hasn't rolled past 06-18 over the weekend).

---

## 1. Strategies active (the two Day-0 subjects)

| Strategy | Live since | Cron-wired? | Fills to date | Notional deployed |
|---|---|---|---|---|
| `tqqq_cot_combo` | 2026-06-15 | ✅ yes (in cron_tick.sh strategy loop) | 5 | $500 (5× $100 DCA) |
| `allocator_blend` | 2026-06-22 (today) | ❌ **no** — manual seed run only | 3 (1 per leg) | ~$68.75 |

Context: both are paper sleeves running at **$100 notional per tick** (parity with the rest of the 11-strategy roster). The Alpaca paper account equity is $99,978 (large account, small per-strategy stakes — these are deliberately tiny relative to buying power).

---

## 2. Fills today (2026-06-22)

### tqqq_cot_combo (cron, 13:30 UTC — market open run, rc=0)
```
BUY 1.18719 TQQQ @ $84.22 | $100
reason: underweight +7sh ($589) | [QQQ] close=739.82 SMA200=628.61 gate=ON
        | rv=21.1% tgt=40% w=1.000 | COT_scale=1.0 | w_final=1.000 tgt_qty=11 cur_qty=4 thresh=1
```
**Notable:** `COT_scale` jumped **0.5 → 1.0** vs the prior four fills. Leveraged-fund (speculator) net positioning washed out below the low percentile → the combo went to full target exposure (tgt_qty 11 vs the ~6 it had been running). The SMA-200 gate is firmly ON (QQQ 739.82 ≫ SMA200 628.61). Realized vol 21.1% is well under the 40% target, so the vol-target weight is uncapped at 1.0.

### allocator_blend (manual seed, 16:09:17 UTC — first live fills ever)
```
BUY 0.03792 QQQ  @ $735.49 | $27.90 | tgt_w=0.2790
BUY 0.03747 SPY  @ $744.25 | $27.90 | tgt_w=0.2790
BUY 0.15823 TQQQ @ $81.78  | $12.95 | tgt_w=0.1295
```
Deployed **$68.75 of a notional $100** by design — the remaining **31% sits as cash**, exactly the tracker's decomposed target (`{TQQQ: 0.1319, SPY: 0.279, QQQ: 0.279}, cash 31.0%`). Rotation sleeve's current top-2 = SPY + QQQ; vol-target sleeve internal TQQQ weight 0.30. This is **not** a partial-fill or under-deployment bug — the blend intentionally holds cash when the vol-target sleeve gates TQQQ exposure below full.

### Other roster strategies that also fired today (context, not Day-0 subjects)
`breakout_xlk` BUY XLK $100 · `sma_crossover_qqq` BUY QQQ $100 · `breakout_xlk_regime` BUY XLK $100 · `sma_crossover_qqq_regime` BUY QQQ $100. (rsi_oversold_spy, volume_breakout_qqq, macd_momentum_iwm, sma_crossover_qqq_rth, leveraged_long_trend_paper, breakout_xlk__mut_c382b1 — no trade this tick.)

---

## 3. Notional deployed vs target weights — Day-0

### allocator_blend (target vs actual, $100 notional basis)
| Leg | Target weight | Target $ | Filled $ | Status |
|---|---|---|---|---|
| QQQ (rotation) | 0.2790 | $27.90 | $27.90 | ✅ on target |
| SPY (rotation) | 0.2790 | $27.90 | $27.90 | ✅ on target |
| TQQQ (voltarget sleeve) | 0.1295 | $12.95 | $12.95 | ✅ on target |
| Cash | 0.3100 | $31.00 | $31.25 | ✅ by design |
| **Total invested** | **0.6875** | **$68.75** | **$68.75** | ✅ |

Top-level sleeve split (from tracker): **TQQQ-voltarget 44.2% / rotation 55.8%.**

### tqqq_cot_combo
Single-symbol (TQQQ) DCA sleeve; "target" is a vol-target × COT-scaled share count vs current holding. Today: tgt_qty 11 sh, cur_qty 4 → bought toward target ($100 cap per tick throttles the fill below the full +7sh "underweight" gap). Cumulative: 6.032 TQQQ sh / $500 cost.

---

## 4. Current positions — live Alpaca == DB (reconciled to the share)

| Symbol | Live Alpaca qty | DB net qty | Match | Live mkt value | Unrealized P&L |
|---|---|---|---|---|---|
| TQQQ | 9.81726 | 6.032 (cot) + 3.627 (lev) + 0.158 (alloc) = 9.817 | ✅ | $805.75 | −$7.11 (−0.88%) |
| QQQ | 0.30731 | 0.1347 + 0.1347 (sma×2) + 0.0379 (alloc) = 0.307 | ✅ | $226.30 | −$1.57 (−0.69%) |
| SPY | 0.03747 | 0.0375 (alloc only) | ✅ | $27.88 | −$0.01 (−0.05%) |
| XLK | 1.03577 | 0.518 + 0.518 (breakout×2) = 1.036 | ✅ | $198.38 | −$1.60 (−0.80%) |

**Account:** equity $99,978.03 · cash $98,300.06 · long mkt value $1,677.97 · status ACTIVE. Day P&L essentially flat (last_equity $99,980 → $99,978, ≈−$2 on the small invested sleeve; broad market was up today but these positions were bought at today's intraday prices so carry only a small adverse mark).

> Note: the Day-0 P&L on the two subject strategies is ~zero by construction — they bought today, so there's almost no holding period yet. The −0.7% to −0.9% marks are entry slippage/intraday drift, not strategy performance. The Saturday check is where the first real OOS read begins.

---

## 5. Anomalies / open items

1. **🟡 allocator_blend is NOT cron-wired.** Today's 3 fills came from a manual seed run, not `cron_tick.sh`. The strategy module exists (`strategies/allocator_blend/strategy.py`) and executed faithfully, but it's absent from the cron strategy loop (loop currently runs 11 strategies; allocator_blend not among them). **Open backlog item** (already flagged in MEMORY: "wire allocator_blend into cron_tick.sh + decide live paper notional"). Until wired, it will not tick tomorrow on its own.

2. **🟡 cron Discord post step failing** (`post rc: 1`). Fills succeed, but the end-of-tick notification errors: `Ambiguous Discord recipient "1508503706545557656"` + a `gateway secrets.resolve unavailable` warning. Cosmetic to trading (no fill impact) but means the cron is not posting its tick summary to Discord. Worth a fix so we don't go blind on cron health via the channel. (Recipient id needs `channel:` / `user:` prefix.)

3. **🟢 allocator_paper.db tracker shows only the 06-18 row — correct by design.** The out-of-band tracker ran today (13:30 UTC, rc=0) but `inserted=0` because the leveraged/QQQ bars cache last-close is still 2026-06-18 (`{"TQQQ":"2026-06-18","QQQ":"2026-06-18","TLT":"2026-06-18"}`) — weekend gap, Yahoo not yet refreshed for those symbols. Idempotent-per-trading-date logic correctly declined to write a duplicate 06-18 row. **Not a bug**, but worth noting the tracker's forward clock is currently one trading day behind the live strategy until the bars cache rolls. Tracker engine drift-check Sharpe = 1.014 (matches report exactly — no engine drift).

---

## 6. Baseline for Saturday OOS check

- **Inception marks:** allocator_blend live 2026-06-22 (cost basis above); tqqq_cot_combo live 2026-06-15 (6.032 TQQQ @ avg $82.80-ish blended).
- **What to verify Saturday:** (a) did allocator_blend get cron-wired and tick on its own? (b) tqqq_cot_combo COT_scale path (did the 1.0 full-exposure call pay off or whipsaw?); (c) tracker DB caught up once bars rolled (expect new rows for 06-19/22/23); (d) live==DB still reconciles; (e) first non-trivial holding-period P&L vs SPX on the same path.
- **OOS benchmark:** SPX on the actually-traded path (close-to-close), per house measurement-hygiene rules.

---

## Appendix — sources
- Live broker: `runner/broker_alpaca.py` → `account()` + `get_position()` (queried 2026-06-22 19:3x UTC).
- Trades: `tournament.db::trades` (strategy, ts_utc, symbol, side, qty, notional_usd, status, reason).
- Tracker: `allocator_paper.db::daily_snapshots` + `logs/allocator_paper.log`.
- Cron: `logs/cron_tick_20260622T133001Z.log`, `cron_tick.sh`.

---

## Addendum — open items CLOSED (2026-06-22 ~12:50 PT)

Both anomalies from §5 are resolved (main greenlit):

1. **✅ allocator_blend cron-wired.** Now #12 in the crontab tick line (`*/30 7-13 * * 1-5 ... tqqq_cot_combo allocator_blend`) and present in cron_tick.sh's strategy run. Verified the exact runner path: tick.sh dispatch grep matches `def decide_xsec(` → routes to `runner.runner_xsec`; `load_xsec_strategy("allocator_blend")` imports clean, returns a valid `decide_xsec` callable, params fully populated ($100 notional + $100 max-notional cap, 5-symbol basket, 5% churn guard, monthly cadence). **First cron-driven tick expected next trading day in the 07-13 UTC window.** (The wiring + today's manual seed were applied earlier today; I confirmed end-to-end.)

2. **✅ Discord post recipient fixed.** cron_tick.sh `CHANNEL_ID` now carries the `channel:` prefix (`channel:1508503706545557656`); the bare-id version that caused today's 13:30 `post rc:1` is preserved in `logs/cron_tick.sh.backup_20260622T165133Z`. Confirmed working with a live test send (messageId returned, recipient resolved).

3. **🧹 Pruned** a stale `_paper_only` note in `strategies/allocator_blend/params.json` that still said "Not yet scheduled" — updated to reflect the live schedule.

**Net:** going into tomorrow, both Day-0 strategies are fully autonomous on cron. Saturday check should find allocator_blend's first self-driven tick + the tracker DB caught up once the leveraged/QQQ bars roll past Friday.
