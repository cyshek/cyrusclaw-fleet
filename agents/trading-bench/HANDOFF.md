# HANDOFF.md — trading-bench (Tessera)

_Fresh instance? Read this first, then `MEMORY.md`, then the last 2 days under `memory/`. Then read `BACKLOG.md` to see what's next._

_Last refreshed: 2026-06-14 ~16:00 UTC — 3 signal-class sprints completed (PEAD/options-flow/COT all MARGINAL OOS). TQQQ+COT combo backtest built + sensitivity validated (Sharpe plateau). tqqq_cot_combo paper runner live (11 strategies total). 613/613 tests green._

> **⚠️ MOST OF THIS PAGE PREDATES THE 2026-06-07 EXPLORE-FIRST MISSION (beat SPX raw return; all promotion gates SUSPENDED). Read the MEMORY.md CURRENT MISSION banner first — the gate/Bar framing below is HISTORICAL.**
>
> **🟢 NEWEST (2026-06-13 session 2): 6 of 7 backlog items done.** (1) Fill-reconcile on every tick. (2) Kelly sizing live. (3) FX lane — CLOSED (no beat, carry_proxy best at 0.3%/yr). (4) Loss postmortem loop live. (5) Polymarket scout — CONDITIONAL-GO (Cyrus needs Polymarket.us KYC; data/API ready). (6) Mutation parent diversification — 3 new archetypes (rsi_oversold_spy, volume_breakout_qqq, macd_momentum_iwm) walk-forward gated, live on cron, added to GATE_PASSING_PARENTS (now 7). Suite 475/475 green. Deferred: edge-calibration meta-model (#6, needs Kelly trade history to train on). One action needed from Cyrus: Polymarket.us signup.
>
> **🟢 NEWEST (2026-06-13): TQQQ VOL-TARGET SLEEVE PROMOTED TO LIVE PAPER — the project's first investable SPX-beating candidate.** The risk/sizing layer was the missing piece (confirmed by a YouTube research sprint: our record + failed bot-builders + Umar Ashraf all independently say the gap is risk-mgmt/sizing, not another signal). Vol-targeting the leveraged-trend lead (scale weight ∝ 1/trailing-20d-vol, target 25% ann vol, SMA-200 gate on QQQ, cap 1.0 = no added leverage) compresses maxDD from raw −56% to −34.8% (≈SPX −33.9%) while STILL beating SPX raw + Sharpe OOS net of realistic costs (+1,881% vs +587% full; OOS +354% vs +175%). **HONEST CAVEATS:** TQQQ-specific (UPRO/SPXL flip negative at realistic cost — don't generalize); leverage premium w/ working risk layer, not pure alpha. Built deployable adapter `strategies/leveraged_long_trend_paper/` (decide() mirrors `backtest_daily_voltarget.py` verbatim, lookahead-safe, fail-safe-to-flat if QQQ data absent). Patched runner.py + candidate_smoke.py to inject `market_state['underlying']` (QQQ closes) for strategies declaring `underlying` — gate now evaluates live (verified: gate=ON QQQ 721 vs SMA200 625, w=0.33, $326 buy). On crontab tick line; NOT in ALL/STOCK_STRATEGIES (event-backtest would mis-score a daily-continuous-weight strategy — documented). Suite 446 green; live runner logged real DB rows. Real money still needs explicit Cyrus approval + GATE bars. Reports: `reports/VOLTARGET_SLEEVE_VERDICT_20260613.md` + `reports/yt_research/SYNTHESIS_20260612.md`. Daily logs 2026-06-12.**
>
> **🟢 PRIOR (2026-06-09): three real lanes resolved, all clean NEGATIVES on the beat-SPX-raw bar — each leaves a keep-able crisis-diversifier sliver. (1) leveraged-long vol-target = WASH net of realistic cost (the 0.95%/yr 3x expense ratio flips the thin broad-cap OOS beat to a loss). (2) FX (no-leverage) = no beat; Trend+XSMom are a genuinely-uncorrelated crisis hedge (corr −0.16/−0.10, positive 2008+2020). (3) credit-stress (BAA10Y/NFCI/T10Y2Y regime gates) = no beat vs buy-and-hold-SPY-total-return (the JSON's "beats_spx_raw" is a price-vs-total-return artifact; closet-long at 0.76–0.85 corr), BUT real GFC-type decoupling (+8.1% in 2008 GFC while SPX −39.5% @ corr 0.05) — candidate only, `reports/CREDIT_STRESS_20260609.md`. Suite 446; protected md5s unchanged. THE PATTERN: every lane that can't be flat/short in a downturn loses the full-cycle raw-return race; the only repeatable value found so far is crisis-hedge sleeves, which need a multi-strategy ALLOCATOR to matter. Beat-SPX-raw bar UNMET. Next real levers: a continuous rolling-origin re-run of the crisis sleeves, parent-diversity for the mutation loop, or a fundamentally different (concentrated/long-biased-with-a-real-exit) archetype.**
>
> **🟡 PRIOR (2026-06-08): leveraged-long vol-target engine — a ROBUST RAW-RETURN SPX beat across multiple 3x sleeves (NOT a risk-adjusted-alpha play — corrected by survivorship cross-check).** `strategies_candidates/leveraged_long_trend/` (quarantine, NOT promoted). Mechanism: trend-gate a 3x ETF (hold while underlying > 200d SMA, else T-bill cash) + scale the sleeve by inverse-realized-vol. **WHAT SURVIVES (structural, reproduced on UPRO/SPXL/SOXL, every config):** the RAW-RETURN SPX beat — 1.5×-3.5× SPX raw on every sleeve; on broad-cap (UPRO/SPXL) vol-target also brings maxDD ≤ SPX (−27/−31% at target 0.20/0.25, down from binary −51%). **WHAT DID NOT survive (over-claim in my first report, now CORRECTED):** the Sharpe/risk-adjusted edge was LARGELY TQQQ-SPECIFIC (TQQQ vol-target Sharpe 0.859>SPX, but UPRO 0.746<0.802, SOXL 0.723<0.752 — only SPXL clears, as a window artifact); and "clean OOS" doesn't generalize (target 0.20 FAILS OOS on broad-cap; only 0.25 holds OOS, narrowly: UPRO OOS +186 vs SPX +175). **HONEST FRAME: a raw-return leverage-harvest w/ broad-cap drawdown-control, not alpha.** TQQQ reference (target 0.25): +2,026% vs SPX +587%, maxDD −34.5%. Survivorship REDUCED not eliminated (UPRO/SPXL/SOXL are also survivors). Reports: `reports/LEVERAGED_LONG_ENGINE_20260608.md` + `LEVERAGED_LONG_VOLTARGET_20260608.md` (w/ correction banner) + `LEVERAGED_LONG_SURVIVORSHIP_20260608.md`. Tests `tests/test_leveraged_long_trend{,_voltarget}.py` (11+14 green; suite **391/391**; protected md5s unchanged). **NEXT (re-prioritized): #1 = realistic execution-drag model** — off-TQQQ OOS margins are thin enough (+186 vs +175) that ~3000 rebal/yr turnover could erase them; if the broad-cap OOS beat dies under real costs, the family is a WASH. Then rolling walk-forward (UPRO 0.25), synthetic pre-2010, THEN a promotion talk framed as raw-return-harvest.

## Mission

Build trading-expert agents that perform profitable paper trades, eventually graduating to real $100 with explicit per-request Cyrus approval. The tournament/cull/mutate loop is the *mechanism* for finding edge; profitable strategies are the *goal*. See MEMORY.md "North star" for graduation criteria.

## Current state

**Live paper strategies (cron-driven):**
- **Stocks (11 on cron):** `breakout_xlk`, `sma_crossover_qqq`, `breakout_xlk_regime`, `sma_crossover_qqq_regime`, `sma_crossover_qqq_rth`, `breakout_xlk__mut_c382b1` (promoted 2026-06-11), `leveraged_long_trend_paper` (promoted 2026-06-13, TQQQ vol-target sleeve), `rsi_oversold_spy`, `volume_breakout_qqq`, `macd_momentum_iwm` (all 3 added 2026-06-13, walk-forward gated), **`tqqq_cot_combo`** (added 2026-06-14, TQQQ vol-target + COT AM-momentum overlay, OOS Sharpe 0.960, maxDD −32.9%). Cron line in user crontab; NYSE-session schedule (`*/30 7-13 * * 1-5`). All at $100 notional parity. Healthy.
- **`xsec_momentum_xa_38d2b2`: DEMOTED to candidate 2026-05-31 (main RULING 1).** Was promoted/cron'd 2026-05-31; demoted same day after √252 Sharpe correction (1.04→0.87, below 1.0 fast-track bar) + WF median Sharpe 0.17 fitness fail. Cron line removed, live dir → `.trash/`, candidate preserved in `strategies_candidates/`. Re-promotes only if it clears the corrected gate honestly. Record: `reports/DEMOTE_xsec_momentum_xa_38d2b2_20260531T190924Z.md`. **No live xsec strategy on cron now.**
- **Stocks (4 orphan, NOT on cron):** `buy_and_hold_spy`, `momentum_arkk`, `rsi_mean_revert_iwm`, `trend_follow_gld`. Discovered during 2026-05-30 crypto retirement audit. Decision pending: wire in OR retire. Flagged in BACKLOG.
- **Crypto: RETIRED 2026-05-30.** All 6 (`buy_and_hold_btc`, `sma_crossover_btc`, `rsi_mean_revert_eth`, `breakout_ltc`, `momentum_sol`, `trend_follow_doge`) archived to `strategies_retired/<name>/` with per-strategy RETIREMENT.md (full trade history + P&L + reason + resurrection instructions). Cron lines removed from user crontab.
- **Weekly leaderboard cron:** Saturday morning, posts to channel.
- **Nightly post-market review:** evening, posts anomalies.
- **Mutation cron: REMOVED (prior session).** The hourly/4h LLM-mutation loop was retired — it was costume-changing a 2-signal engine, not producing edge. (A weekly candidate-pile cull cron remains, to keep `strategies_candidates/` from re-piling.)

**Active candidates in `strategies_candidates/` (PAPER-CANDIDATES, NOT LIVE):**
- `xsec_momentum_236b86` — wave-3 sector-equity Jegadeesh-Titman 12-1. **REJECT** (Sharpe 0.30, floor-blocked).
- `xsec_lowvol_c3783c` — wave-3 sector-equity AHXZ low-vol. **REJECT-WITH-CAVEATS** (Sharpe 0.36).
- `xsec_sector_rot_b7a2f9` — wave-3 sector-equity Faber GTAA. **REJECT** (Sharpe -0.09).
- `xsec_momentum_xa_38d2b2` — wave-4 cross-asset 12-1. **FP Sharpe 1.13.** Blocked by K-invariant 19% in-position floor. **Promotion candidate IF Bar A bullet #5 amendment approved.**
- `xsec_lowvol_xa_38a206` — wave-4 cross-asset low-vol. FP Sharpe 0.97 K=3 / 0.76 K=2-regime. Blocked by 2022-Q3 chop window (genuine strategy-class gap).
- `xsec_sector_rot_xa_257225` — wave-4 cross-asset Faber GTAA. FP Sharpe 0.98 N=150. Blocked by WF median Sharpe horizon mismatch (Pattern #3 candidate).

**Bar A archetype track (Tier 1):**
- 7 archetypes triaged 2026-05-30 (`reports/ARCHETYPE_TRIAGE_20260530T170659Z.md`).
- Wave 2: 4 REJECTs (TSMOM SPY, MeanRev3D QQQ, Overnight SPY, PEAD).
- Wave 3 (sector-equity): 3 REJECTs (xsec momentum, lowvol, sector rotation).
- Wave 4 (cross-asset): 3 REJECT-WITH-CAVEATS but **all 3 cleared FP Sharpe ≥0.97**. Universe-class hypothesis CONFIRMED — wave-3 rejects were universe-class, not strategy-class.

**Bar C (Tier 2 / LLM-decision) track:**
- Infra shipped 2026-05-30: `runner/regime_classifier.py`, frozen prompt + schema, `llm_decisions` + `regime_decisions` DB tables, opt-in `regime_gate` in `runner.py`. Not yet consuming live.
- Eval methodology design doc shipped 2026-05-30: `reports/TIER2_BAR_C_EVAL_METHODOLOGY_20260530T190500Z.md`. Phase 1 (code fallback) + Phase 2 (one-time historical LLM replay, ~$9 OpenAI spend per backtest) + Phase 3 (weekly drift monitor). First proposed candidate: `regime_gated_xsec_momentum_xa`. Awaiting main review before spawning `regime_backtest_impl` subagent.

**Bar D (Tier 3 / peer agents):** ARCHIVED 2026-05-29 per Cyrus. Re-evaluate only after ≥2 strategies pass Bar E.

**Bar E (real money):** GATE.md current. 0 candidates eligible.

## Open with Cyrus (DO NOT auto-resolve)

1. **GATE.md Bar A bullet #5 amendment SHIPPED 2026-05-31** per Cyrus explicit ack. Promotion memo: `reports/PROMOTE_xsec_momentum_xa_38d2b2_20260531T015000Z.md`. No further Cyrus action needed unless monitoring flags an anomaly post-runner-wiring.
2. **Pattern #1 + Pattern #3 updates to `reports/PATTERNS.md`** are SHIPPED — main approved standalone. No Cyrus action needed.

## Open with main (technical, not personal)

1. **Tier 2 Bar C evaluator design doc** awaiting main review per `reports/TIER2_BAR_C_EVAL_METHODOLOGY_20260530T190500Z.md`. 4 decision points: phase split approval, first-candidate approval (`regime_gated_xsec_momentum_xa`), eval-cost budget (~$9-20 real OpenAI spend per Phase 2), spawn impl subagent.

## Active subagents

**None.** `runner_xsec_impl` completed (with a test-isolation bug Tessera fixed post-hoc); runner shipped. All weekend subagents done.

## Xsec promotion / paper-clock state (2026-05-31, current)

- **CLOCK IS LIVE.** Cron `5 14 * * 1-5` UTC (=07:05 PT) → `cron_tick.sh xsec_momentum_xa_38d2b2` → `tick.sh` → `runner.runner_xsec`. First real tick Monday 14:05 UTC.
- **Corrected FP Sharpe = 1.04** (NOT 1.13 — that was best-window; 2010 span was phantom, cache floor 2020-07-27). Promotion stands (1.04 ≥ 1.0 fast-track bar). Canonical: `reports/PROMOTION_RECORD_CORRECTION_20260531T024500Z.md`.
- **Promotion-survival condition is LIVE** (in the promotion memo): two-tier. Tier 1 = 4wk liveness (trades-as-designed + live cost ≤2× model + no >2% single-rebalance loss). Tier 2 = ≥12wk significance (≥15 round-trips + cost-aware realized Sharpe ≥0.80). Fail either → back to bench regardless of headline Sharpe.
- **PENDING main reply:** I relocated the ≥15-trade floor 4wk→12wk (monthly cadence can't deliver 15 trades in 4wk). Main may override. Default = relocation.
- **Harness guard:** `walk_forward_xsec` raises `ZeroTradesError` on all-zero-trade runs (warmup-starvation). Pin `--warmup-days ≥400` for 252d-lookback strategies. `--allow-zero-trades` to override.
- **Hard rule:** PATTERNS.md Pattern #4 — FP-Sharpe claims state real data span, never beyond 2020-07-27 cache floor.
- **GATE Bar A #5 clause (f) (2026-05-31):** absolute-return floor ≥8.0%/yr net-of-cost on deployed notional, co-primary with Sharpe ≥1.0. Catches Sharpe-gaming barbells. momentum_xa clears at 11.6%/yr (re-checked, promotion safe). Number pending Cyrus ack, live as operating bar.
- **Pattern #5 (2026-05-31):** cross-asset low-vol archetype CLOSED (high Sharpe / no return / owns cash-like leg). Barbell `xsec_lowvol_xa2_440761` filed defensive-sleeve-only, never alpha. No wave-6.

## Xsec live-runner status (2026-05-31)

- `runner/runner_xsec.py` (454 LOC) live; `tick.sh` dispatches `decide_xsec` strategies to it. 226/226 tests.
- ONE step from paper-trading: add cron line. Recommended `0 13 * * 1-5` PT, channel 1508503706545557656. Awaiting Cyrus go/hold.
- When cron lands → status-post on first rebalance fill → ≥4-week Bar B/C/E clock starts.

## Recent shipped infrastructure (2026-05-30 / 2026-05-31)

- **2026-05-31**: Basket-aware `MAX_TRADES_PER_DAY` cap. New `runner.risk.resolve_trades_per_day(params)`; strategies declare `xsec_basket_size: K` to lift cap to `max(4, 2*K)`. Fixes silent leg-truncation in xsec rebalances. 22 new tests, suite 182→204. All 6 wave-3/4 candidates backfilled with `xsec_basket_size`.
- `runner/backtest_xsec.py` (660 LOC) — cross-sectional multi-symbol harness (design A: wrapper-of-singletons + synced bar clock + `_clamp_basket` shared risk cap).
- `runner/walk_forward_xsec.py` (440 LOC) — xsec walk-forward mirror.
- `runner/candidate_smoke.py` — Bar A bullet #7 smoke evaluator (single-symbol + xsec modes).
- `runner/regime_classifier.py` (707 LOC) — first Tier 2 LLM-decision infra.
- `runner/prompts/regime_classifier_v1.{txt,schema.json}` — frozen prompt + JSON schema.
- DB tables: `llm_decisions` (append-only audit), `regime_decisions` (UPSERT hot-path).
- `runner/bars_cache.py` `_iso_date` intraday fix.
- `tick.sh --candidate <name>` mode for candidate smoke.
- GATE.md bullet #1 + #7 amendment shipped (cap=1, participation floor). History entry added.

## Hard rails (do not bypass)

- **CHANNEL-FIRST STATUS POSTING.** Cyrus's primary view = my Discord channel (`1508503706545557656`), NOT webchat-to-main or daily memory. Status-post on every meaningful state change.
- **DEFAULT TO ACTION on money/strategy delegations** — but NOT on gate amendments that promote candidates I designed. That audit shape requires explicit Cyrus eyeball.
- **Paper-only.** `broker_alpaca.py` refuses non-`paper-api.alpaca.markets` base URLs.
- **Risk caps** in `runner/risk.py`: `MAX_NOTIONAL=$100`, `MAX_POSITION=$100`, `MAX_TRADES_PER_DAY=4` per strategy.
- **Killswitch:** `STOP_TRADING` file → every runner no-ops.
- **Real money requires explicit per-request Cyrus approval.** Never standing.
- **LLM-generated strategy code → `strategies_candidates/`, NEVER directly to `strategies/`.** Manual promotion + smoke test required.
- **GATE.md changes need Cyrus or main sign-off + audit-entry in History.** Implicit-approval-to-proceed CONDITIONAL on amendment NOT promoting a self-designed candidate.
- **No promoting subagent reports as ground truth without disk verification.** Always check: candidate dir exists, report file exists, test suite still passes, protected-file md5s unchanged.
- **Pattern #2 single-data-point trap:** ≥2 within-class data points before bringing class-level framings to main or shipping as durable narrative. Exception: hard safety/correctness issues.

## Test suite & verification

- **226 tests passing** (was 182 at start of day 2026-05-31; +22 basket-aware trade-cap, +9 xsec live runner, +others incl. ZeroTradesError guard).
- Recent protected-runner-file md5s (post 2026-05-31 trade-cap fix):
  - `runner/risk.py` 2e471e04... (added `resolve_trades_per_day` + basket-cap docstring)
  - `runner/runner.py` 4be185e4... (1-line: passes `max_trades_per_day` through)
  - `runner/backtest.py` e1a64a4f... (added `max_trades_per_day` kwarg to `_bt_check_trade`)
  - `runner/backtest_xsec.py` d94e823b... (threads basket-aware cap into both inner check sites)
  - `runner/walk_forward_xsec.py` (no edits since creation 2026-05-30 17:47)
  - `runner/candidate_smoke.py` (no edits since xsec extension)

## Architecture footguns (preserved from prior HANDOFF)

- **Position attribution per-strategy** via `db.strategy_position()`. Two strategies can hold same symbol; closes use *strategy qty*, NEVER `/v2/positions/{sym}` DELETE.
- **Bar fetch:** explicit `start` + `sort=desc` then reverse for indicator math.
- **Notional buys:** Alpaca returns empty `qty` until filled; runner derives `qty = notional / fill_price`.
- **Order reconcile:** runner polls `get_order()` 3× post-submit.
- **Cron tick wrappers:** direct-shell (`cron_tick.sh`), NOT agentTurn. LLM hiccups must not block trade ticks.
- **Cron sessionKey routing:** scheduled jobs MUST set `sessionKey: "agent:trading-bench:discord:channel:1508503706545557656"` for delivery to route.
- **Alpaca crypto spread ~4% round-trip** is why crypto strategies all lose. Retired 2026-05-30.
- **`@dataclass` in importlib-loaded module:** must register in `sys.modules` BEFORE `exec_module()` or `dataclasses` crashes. (`runner/strategy_gen.py` handles this.)
- **`bars_cache._iso_date`:** intraday `end_dt` serializes full timestamp; midnight-UTC keeps YYYY-MM-DD form.
- **NYSE holidays:** `runner/market_hours.py` `NYSE_HOLIDAYS` + `NYSE_EARLY_CLOSE` cover 2024-2028. Extend before 2028.
- **MAX_TRADES_PER_DAY=4 shared-cap** is per-strategy; basket strategies with >4 legs need rebalance staggering. Flagged in BACKLOG (P2).

## Key files

- `GATE.md` — promotion bars (append-only with History section)
- `MEMORY.md` — durable principles, lessons, north star
- `BACKLOG.md` — prioritized todo / shipped log
- `memory/YYYY-MM-DD.md` — raw daily logs
- `reports/` — point-in-time artifacts (audits, design docs, backtests)
- `reports/PATTERNS.md` — institutional knowledge (positive lessons, separate from GATE)
- `runner/risk.py` — risk caps (single source of truth)
- `runner/walk_forward.py` — Tier 1 Bar A evaluator (8 NAMED_WINDOWS)
- `runner/walk_forward_xsec.py` — xsec Bar A evaluator
- `runner/candidate_smoke.py` — Bar A bullet #7 evaluator

## Communication

- **My Discord channel:** `1508503706545557656`. Status posts here via `message(action="send", channel="discord", target="...")`.
- **main:** `sessions_send(agentId="main", ...)` for design questions, escalations.
- **Cyrus:** in his Discord DM via main. I post to my channel; he reads.

## Next 24-hour priorities (in order)

1. Wait for Cyrus's response on GATE amendment + Tier 2 eval design.
2. If Cyrus approves amendment → ship GATE.md edit, write promotion memo for `xsec_momentum_xa_38d2b2`, promote to `strategies/`, wire cron line, start Bar B/C/E accumulation clock.
3. If Cyrus pushes back → revise per his direction.
4. While waiting: small backlog items (MAX_TRADES_PER_DAY shared-cap fix, orphan stocks decision, weekly MEMORY.md distillation cron).
5. If main approves Tier 2 eval design independently → spawn `regime_backtest_impl` subagent.

## Subagent count audit (end of weekend)

- Active: 0
- Total weekend runs: 8 (multi_symbol_harness, tier2_regime_classifier_impl, xsec_wf_plus_momentum, xsec_lowvol_backtest, xsec_sector_rot_backtest, xsec_momentum_xa_backtest, xsec_lowvol_xa_backtest, xsec_sector_rot_xa_backtest)
- Promotions: 0
- Files shipped: 3 new runner modules + 1 extended runner module + 1 extended DB + 6 candidate dirs + 8 backtest reports + 3 design docs (PATTERNS, GATE amendment draft, Tier 2 eval methodology)
- Test suite: 116 → 182 (+57%)
