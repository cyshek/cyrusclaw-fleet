# Tier 2 Design Doc — Daily LLM Regime Classifier

**Author:** Tessera (subagent design pass)
**Date:** 2026-05-30 17:07 UTC
**Status:** DRAFT — pending review by main / Cyrus before any implementation.
**Scope:** Pure design. No code in this doc; no code committed in this turn.
**Gate target:** `GATE.md` Bar C (LLM-decision strategy → live paper).

---

## 0. TL;DR

Build one Tier 2 strategy: **`regime_classifier_v1`** — a once-per-day, post-NYSE-close LLM call that ingests a fixed bundle of market-state features (SPY price/MA/return, VIX level + term, breadth, sector dispersion) and emits a strict-JSON verdict `{regime, confidence, rationale, allow_strategies}`. The verdict is written to a new `regime_decisions` table and consulted by `runner.runner.run()` as a **gate** in front of `module.decide()`. If `regime ∉ allow_strategies` for a given strategy → runner skips with reason `regime_block`. Fallback to `regime_uptrend()` on any LLM failure. Cost ceiling ≈ **$0.30/month** at gpt-4o-mini equivalent, far under the 30% gross-edge cap in Bar C.2.

This doc walks through Bar C criteria in §10 and flags open questions in §11.

---

## 1. Decision frequency — once per day, post-close

**Decision:** one call per trading day, scheduled at **17:30 ET** (after the 16:00 close + post-market settles + daily SPY bar from Alpaca is final). Verdict is valid for the *next* trading day's session and is consumed by every runner tick on that day.

**Why not more frequent:**

1. **Cost.** Per-tick LLM calls fail Bar C.2 instantly. `breakout_xlk` & friends tick `*/30 7-13 * * 1-5` PT = ~14 ticks/day × 5 strategies = 70 calls/day. At gpt-4o-mini-ish pricing (~$0.15/MTok in, $0.60/MTok out) and ~2k tokens/call, that's ~$0.20/day → ~$5/mo per strategy. With expected gross edge of single-digit basis points/trade and ≤4 trades/day cap, the cost ratio explodes.
2. **Determinism.** Bar C.3 requires a full determinism log per decision. One decision/day means the log is auditable in seconds; 70 decisions/day across 5 strategies means hundreds of rows/day to reconcile.
3. **Signal stability.** Regime is, by construction, a slow-moving feature. SPY's relationship to its 50d/200d MA changes meaningfully on a daily-bar cadence, not an intraday one. Re-running the classifier intraday introduces churn (regime flips on noise) without adding real information. The whole point of a regime *gate* is that it's stable enough that strategies don't flip in and out of "allowed" mid-day.
4. **Operational simplicity.** Daily cron = 1 row/day in `regime_decisions`. Replay/backtest is trivial. Intraday adds time-of-day axis to every analysis.

**Holiday/weekend handling:** classifier skips on weekends + NYSE holidays (already detectable via `runner/market_hours.py` `is_nyse_holiday`). On a skipped day, runner uses the most recent decision (TTL: 5 calendar days, beyond which we fall back to `regime_uptrend()` — see §8).

---

## 2. Inputs to the LLM

Feature bundle assembled in `runner/regime_features.py` (new module — design only here). All features come from the **previous trading day's close**, computed at decision time.

### 2.1 Features (numeric, all expressed as floats / structured dicts)

| # | Feature | Source | Notes |
|---|---|---|---|
| 1 | `spy_close` | Alpaca `stock_bars("SPY","1Day",1)` | Yesterday's close |
| 2 | `spy_sma_50` | Alpaca SPY 1Day(60) → `indicators.sma(...,50)` | Same series the code-baseline uses |
| 3 | `spy_sma_200` | Alpaca SPY 1Day(220) → `indicators.sma(...,200)` | Longer-trend context |
| 4 | `spy_return_5d`, `spy_return_20d` | `indicators.pct_change(...,5/20)` | Short + medium trend |
| 5 | `spy_dist_from_52w_high_pct` | Alpaca SPY 1Day(260) | Drawdown context |
| 6 | `vix_level` | **New API needed** — see §2.2 | Vol regime |
| 7 | `vix_term_slope` (VIX3M − VIX) / VIX | **New API needed** | Negative ⇒ stress (backwardation) |
| 8 | `breadth_adv_decl_5d_avg` (NYSE) | **New API needed** | <1.0 = bearish breadth |
| 9 | `sector_dispersion` (stdev of 1-day returns across 11 SPDR sector ETFs) | Alpaca `stock_bars` on XLK/XLF/XLE/XLI/XLY/XLP/XLV/XLU/XLB/XLRE/XLC | Fully derivable from Alpaca |
| 10 | `recent_regime_history` | Last 5 days' classifier outputs from `regime_decisions` | Self-reference for stability/hysteresis |

### 2.2 Data sources

**Already have via Alpaca:**
- SPY daily bars (#1–5)
- Sector SPDR daily bars (#9)

**Not in Alpaca — choices for VIX (#6, #7) and breadth (#8):**

- **Yahoo Finance via `yfinance`** — `^VIX`, `^VIX3M`, advance/decline approximations from index components. Free, no key, but unofficial / can break. Honest assessment: this is what every retail project uses, and it does break ~monthly.
- **CBOE delayed data** — free for 15-min delayed; needs a small scraper.
- **Polygon.io free tier** — 5 calls/min ample for daily; has VIX. Requires API key, free tier exists.
- **Skip VIX entirely for v1.** Derive a vol proxy from SPY itself: `spy_realized_vol_20d` (stdev of daily returns) and `spy_atr_14` from SPY bars. Lossy vs implied vol but **zero new dependencies** and lets us ship v1 honestly without an external surface to fail.

**Recommendation for v1:** ship with the **SPY-derived vol proxy** path; defer VIX + breadth integration to v2 once we've proven the gating shape works end-to-end. Bar C is unforgiving about new failure modes — adding two flaky APIs at v1 makes the determinism story worse, not better.

**Sector dispersion (#9)** is derivable from Alpaca alone — keep in v1.

### 2.3 Prompt shape

System prompt is **frozen at deployment** (Bar C.4). Pseudo-structure:

```
SYSTEM: You are a market regime classifier. Output ONLY a JSON object
        conforming to the schema in §3. No prose, no markdown fences.
        Allowed regimes: RISK_ON, RISK_OFF, CHOP.
        Conservative bias: when uncertain, prefer CHOP or RISK_OFF.
USER:   <features JSON blob, ~30 keys, ~800 tokens>
```

Prompt body and feature schema are versioned via SHA-256 (`prompt_hash`) — see §4.

---

## 3. Output schema

Strict JSON, validated against a schema before persistence. Invalid → fallback path (§8).

```json
{
  "regime": "RISK_ON" | "RISK_OFF" | "CHOP",
  "confidence": <float in [0.0, 1.0]>,
  "rationale": "<string, <= 200 chars>",
  "allow_strategies": ["breakout_xlk", "sma_crossover_qqq", ...]
}
```

Validation rules:
- `regime` must be one of the three literals.
- `confidence` must be a float in [0,1].
- `rationale` ≤ 200 chars; truncated if longer (logged as a warning, decision NOT rejected for length alone — that's brittleness, not safety).
- `allow_strategies` must be a subset of the **whitelisted strategy names** passed in the prompt context. Names outside the whitelist → drop with warning. Empty list is legal and means "block everything today."

**Why these three regimes (not more):** Bar C punishes flakiness. Three coarse buckets force the classifier to commit and make backtest evaluation tractable (each window cleanly falls in one bucket). A 5-bucket version (`STRONG_BULL/MILD_BULL/CHOP/MILD_BEAR/STRONG_BEAR`) can come after we have data showing 3 buckets is too coarse.

**Mapping default:**
- `RISK_ON` → all trend/breakout strategies allowed (current 5 stock strategies + future trend mutants).
- `CHOP` → only mean-revert strategies allowed (none today; this regime currently means "skip all" until we ship a mean-reverter that passes Bar A).
- `RISK_OFF` → block all long-only strategies. (We have no shorts.)

Final allow list is **`set(llm_allow_strategies) ∩ regime_default_allow`** — i.e., LLM can be more conservative than the default but cannot expand it. This is a safety rail against hallucinated strategy names or over-aggressive output.

---

## 4. Determinism log

New table `regime_decisions` in `tournament.db` (added to `runner/db.py` schema next to `decisions` at line 43):

```sql
CREATE TABLE IF NOT EXISTS regime_decisions (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  decision_ts     TEXT NOT NULL,         -- ISO8601 UTC
  trading_date    TEXT NOT NULL,         -- YYYY-MM-DD the decision is FOR
  model           TEXT NOT NULL,         -- e.g. "openai/gpt-4o-mini"
  model_version   TEXT,                  -- provider-reported version string if available
  temperature     REAL NOT NULL,         -- always 0.0 for live; logged anyway
  seed            INTEGER,               -- if provider supports
  prompt_hash     TEXT NOT NULL,         -- SHA-256 of (system_prompt || schema || feature_keys_sorted)
  inputs_json     TEXT NOT NULL,         -- the feature bundle, verbatim
  response_raw    TEXT NOT NULL,         -- raw model output, pre-parse
  response_parsed TEXT,                  -- normalized JSON; NULL if invalid
  regime          TEXT,                  -- denormalized for fast queries
  confidence      REAL,
  allow_strategies TEXT,                 -- JSON array
  fallback_used   INTEGER NOT NULL DEFAULT 0,  -- 1 if we fell back to code regime
  fallback_reason TEXT,
  cost_usd        REAL,                  -- token-based estimate
  latency_ms      INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_regime_decisions_tradingdate
  ON regime_decisions(trading_date);
```

Unique index enforces "one canonical decision per trading day." Re-runs (e.g. cron retry) UPSERT.

**Replayability:** given `(prompt_hash, inputs_json, model, temperature, seed)`, the LLM call is reproducible to the limit the provider allows. We don't promise bit-identical replay (providers don't guarantee that even with temperature=0); we promise full audit trail of what was sent and what came back. That meets Bar C.3.

---

## 5. Cost model

**Token budget per call (rough):**
- System + schema + frozen instructions: ~400 tok in
- Feature payload (~30 numeric keys + 5-day history): ~500 tok in
- Output (strict JSON, no rationale prose beyond 200 chars): ~150 tok out
- **Total: ~1,050 tok/call, of which ~900 in, ~150 out**

**At gpt-4o-mini-ish prices (illustrative — actual prices verify at deploy time):**
- $0.15/MTok input, $0.60/MTok output
- Per call: 900 × 0.15e-6 + 150 × 0.60e-6 = $0.000135 + $0.00009 ≈ **$0.000225/call**
- ~21 trading days/month × $0.000225 ≈ **$0.0047/month**

**Even at GPT-4o full pricing (~$5/MTok in, $15/MTok out):**
- Per call ≈ 900 × 5e-6 + 150 × 15e-6 = $0.0045 + $0.00225 ≈ $0.00675/call
- ~21 days × $0.00675 ≈ **$0.142/month**

**Bar C.2 check:** strategy declares `decisions_per_year = 252`, `cost_per_decision_usd ≈ $0.001` (conservative mini) or `≈ $0.01` (full GPT-4o). Annual cost ≤ ~$2.50. The classifier doesn't "gross-edge" by itself — it gates other strategies. Cost is applied to **the gated portfolio's gross PnL**, distributed across allowed strategies in backtest. With ~5 strategies sharing a $2.50/yr gate cost, that's $0.50/strategy/yr — utterly negligible vs even a single losing trade.

**Verdict: passes Bar C.2 with 3+ orders of magnitude headroom.**

---

## 6. Integration with `runner/runner.py`

### 6.1 New module: `runner/regime_classifier.py`

Two public functions:

```
get_today_regime(trading_date) -> RegimeDecision | None
  - Looks up regime_decisions WHERE trading_date == today.
  - Returns the parsed decision, or None if no row.
  - Caches in-process for the tick lifetime.

classify_and_log(now_utc) -> RegimeDecision
  - Builds features, calls LLM, validates, persists row.
  - Used by the daily cron only; not called per-tick.
```

### 6.2 Runner shim

In `runner/runner.py::run()`, immediately **after** the market-closed gate (around line 126, before `position_state` is built), insert:

```
regime_decision = regime_classifier.get_today_regime(today_et)
if regime_decision is None:
    # No fresh decision (cron missed, brand-new system, weekend follow-on).
    # Fall back to code-based regime_uptrend via SPY closes that we
    # already fetch below — but compute it upstream so we can gate.
    regime_decision = _code_fallback_regime(client)  # uses regime_uptrend()
elif regime_decision.is_stale(max_age_days=5):
    regime_decision = _code_fallback_regime(client)

if strategy_name not in regime_decision.allow_strategies:
    db.log_decision(strategy_name, "skip_regime_block",
                    symbol=symbol,
                    reason=f"regime={regime_decision.regime} "
                           f"blocks strategy; "
                           f"source={regime_decision.source}")
    db.log_run(strategy_name, "ok", elapsed_ms, detail="skip_regime_block")
    return 0
# else: proceed to existing decide() pipeline
```

**Crypto handling:** crypto strategies have no SPY-based regime today. Two options:
- (a) Regime classifier doesn't apply — crypto strategies bypass the gate (default behavior — `regime_decision = always_allow` for crypto symbols).
- (b) Add a crypto-specific feature bundle later (BTC trend + funding rates).

For v1, **(a)** — keep scope tight.

### 6.3 Daily cron

New entry, scheduled at `30 17 * * 1-5` ET (i.e., `30 14 * * 1-5` PT during PDT, adjusted via TZ in cron):

```
TZ=America/New_York
30 17 * * 1-5  $WORKSPACE/cron_regime.sh
```

`cron_regime.sh` (shell wrapper analogous to `cron_tick.sh`) calls `python3 -m runner.regime_classifier --classify`, then posts a one-line summary to channel via `openclaw message send` (e.g., `🟢 RISK_ON / conf 0.78 — allows: breakout_xlk, sma_crossover_qqq, ...`).

---

## 7. Backtest path

### 7.1 Offline replay infrastructure

New module `runner/regime_backtest.py`:
- Iterate every trading day in the walk-forward window.
- For each day, reconstruct the feature bundle from **historical bars only** (no look-ahead — features must use data through prior-day close).
- Call a **cheap** LLM (gpt-4o-mini or Claude 3.5 Haiku) with the frozen prompt.
- Persist into a parallel `regime_decisions_backtest` table (or use `regime_decisions` with a `run_id` discriminator — schema decision below).
- Replay each gated strategy through `runner/backtest.py`, with `regime_decisions` consulted to skip blocked days.

### 7.2 Why cheap model for backtest

8 walk-forward windows × ~90 days each ≈ 720 LLM calls per backtest run. At mini pricing this is ~$0.16/run; at full GPT-4o it'd be ~$5/run. Across iteration (likely 10–20 runs as we tune the feature set), the difference is $3 vs $100. Bar C.2 doesn't require the *live* and *backtest* models to match, only that the live cost is modeled. We tune with the cheap model and **freeze the live model** (which may be the same mini, or upgraded once) before deployment.

**Caveat / honesty:** if the cheap model produces materially different regime calls than the live model would, the backtest results don't predict live behavior. Mitigation: before promote, run a **calibration set** of ~50 days through *both* models and compare regime agreement. If <70% agreement, the cheaper model is unfit and we re-backtest on the expensive one.

### 7.3 Acceptance criteria coupling to Bar A

Strategy is the **gated portfolio**, not the classifier in isolation. The walk-forward run computes per-strategy metrics with the gate applied. Bar A criteria (positive median return per regime window, ≥30 trades, max DD ≤30%) apply to the **gated outputs**. If gating makes a strategy trade <30 times in the window, that's a real failure — the gate may be too restrictive.

---

## 8. Failure modes & fallbacks

| Failure | Detection | Fallback |
|---|---|---|
| LLM returns invalid JSON | `json.loads` raises | Persist row with `response_parsed=NULL`, `fallback_used=1`, `fallback_reason="invalid_json"`. Runner sees no parsed decision → uses code regime. |
| LLM API timeout / network error | `requests` timeout / 5xx | Same as above — no row written for the timeout, cron retries once with 30s delay; on second failure, write a `fallback_used=1` row and stop. |
| Hallucinated regime (e.g., `"BULLISH"` instead of `"RISK_ON"`) | Schema validation fails | Treated as invalid JSON path. |
| Hallucinated strategy name in `allow_strategies` | Whitelist intersection in §3 | Drop silently; if intersection is empty, treat as "no strategies allowed today." |
| Hallucinated confidence > 1 or < 0 | Range check | Clamp + log warning; do NOT reject decision on this alone. |
| Stale decision (cron missed for >5 days) | TTL check at runner | Code-fallback `regime_uptrend()` (line 84 in `strategies/_lib/indicators.py`). |
| Provider returns 200 + empty body | Empty-string check | Invalid JSON path. |
| Two cron runs same day | UNIQUE INDEX on `trading_date` | UPSERT — last writer wins; both logged. |
| Killswitch active (`STOP_TRADING`) | Existing runner check | Classifier cron also checks killswitch and skips; runner already short-circuits regardless. |

**Default-safe principle:** every fallback either (a) uses the code-based `regime_uptrend()` we already trust, or (b) errs on RISK_OFF (= block trading). Never "fail open into RISK_ON."

**Explicit:** if **both** the LLM path and the SPY data fetch fail simultaneously, runner blocks trading for that tick (logs `skip_regime_unknown`). Trading-bench is paper; missing a session is cheaper than trading blind.

---

## 9. Prompt freeze & versioning

Per Bar C.4: prompt is frozen at deployment. Mechanism:

1. The frozen prompt + feature schema live in `strategies/regime_classifier_v1/prompt.txt` and `prompt_schema.json`.
2. `prompt_hash` = SHA-256 of `(prompt.txt || canonicalize(prompt_schema.json))`.
3. Strategy folder's `params.json` declares `expected_prompt_hash`. Classifier asserts equality at load time; mismatch → refuse to run + log error + block trading (default-RISK_OFF).
4. Any prompt change = **new strategy folder** `regime_classifier_v2/`, fresh walk-forward + Bar C gate from zero. Old strategy can stay live while v2 backtest runs.

---

## 10. Bar C walkthrough

Quoting Bar C from `GATE.md` and showing satisfaction:

> **C.1. All of Bar A.**

Bar A criteria are evaluated against the **gated portfolio** in §7.3. Walk-forward across all 8 named regime windows is a hard requirement; we cannot waive this. **Status: must be demonstrated empirically post-implementation — design does not pre-satisfy this; backtest does.** Honest flag: if the classifier's allow-list shrinks trade count below 30 in any window, that's a Bar A failure even if returns are positive.

> **C.2. Per-decision cost modeled. ... If LLM cost ≥ 30% of gross edge, strategy is rejected.**

§5: ~$0.0047–$0.14/month live cost vs an expected gross edge in dollars (gated portfolio of 5 strategies trading on ~$100 notional). Even at GPT-4o-full pricing the cost is <1% of a single losing trade. **Satisfied with massive headroom.**

> **C.3. Determinism log.** `{prompt_hash, model_version, seed, response, decision}` to a `llm_decisions` table.

§4: full schema. Bar C says `llm_decisions`; we propose `regime_decisions` for clarity (specific to this strategy type) — flag for review. Either name is fine; the *content* matches the spec. **Satisfied.**

> **C.4. Prompt is frozen at deployment.**

§9: SHA-256 pinned hash + `expected_prompt_hash` in `params.json` + assert at load time. **Satisfied.**

> **C.5. Preferred archetypes (low decision frequency): once-daily regime classifier, weekly position sizer, end-of-day risk-on/risk-off filter.**

This *is* a once-daily regime classifier. **Satisfied.**

**Net Bar C status:** design satisfies C.2–C.5 by construction. C.1 is empirical and depends on backtest results — design cannot pre-prove it. If C.1 fails, the strategy stays in `strategies_candidates/` and we iterate (different feature set, different regime granularity, different gating mapping) before re-gate.

---

## 11. Open questions for Tessera / main / Cyrus

1. **VIX + breadth path.** v1 ship with SPY-derived vol proxy only (no external API), OR pay the API-flakiness cost of yfinance/Polygon up front? My recommendation: SPY-only for v1, add VIX in v2. **Want main's call.**
2. **Live model choice.** gpt-4o-mini is the default cost-sensible pick. Sonnet 4.7 (what we use elsewhere) is ~10× more expensive but stronger at structured-JSON adherence and instruction following. At the volumes here even Sonnet is <$0.50/month. **Recommend Sonnet 4.7 for live, mini for backtest, with calibration check** (§7.2). Confirm?
3. **Confidence threshold.** Should low-confidence (`confidence < 0.5`) decisions auto-defer to the code fallback regardless of regime value? Reduces LLM hallucination blast radius at the cost of using the LLM less. Default-off in v1?
4. **CHOP mapping when we have no mean-reverters.** Today, CHOP = block all. Is that the right default, or should CHOP fall back to "allow all" since we have no positive evidence to block? My instinct: block all. Mean-revert is the natural CHOP play; until we have one, sitting on hands is fine. **Confirm.**
5. **`regime_decisions` vs `llm_decisions` table name.** Bar C.3 says `llm_decisions`. I think the spec'd name was generic and we should name per-strategy-type for clarity (`regime_decisions` now, `position_sizer_decisions` next). Want explicit OK to use the more specific name or stick with the generic.
6. **Cron timing edge case.** If the classifier cron fails at 17:30 ET and we don't notice until next morning's tick, the runner falls back to code regime for the whole day. Should we add an early-morning re-attempt at 08:00 ET (1.5h before NYSE open) as a backup? Adds redundancy at near-zero cost.
7. **Whitelist source.** Should `allow_strategies` be drawn from a) all `strategies/` folders dynamically, b) a hand-maintained allowlist in `params.json`, or c) a hybrid (dynamic but with veto)? My instinct: (b) for v1 — minimizes the chance the LLM ever sees a strategy name that surprises us.
8. **Bar A.4 (trade count ≥ 30) interaction.** If gating cuts a strategy's trade count below 30 in the backtest, do we (a) fail the strategy under Bar A, (b) consider the *combined gated portfolio* as the unit and count its trades, or (c) extend the backtest window? Material methodological choice — needs main's call.

---

## Appendix A — File touch list (for the implementation pass, NOT this turn)

- `runner/regime_classifier.py` — NEW. Public: `get_today_regime`, `classify_and_log`.
- `runner/regime_features.py` — NEW. Feature builder; pure functions.
- `runner/regime_backtest.py` — NEW. Offline replay across walk-forward windows.
- `runner/db.py` — schema add: `regime_decisions` table near line 43; helpers `save_regime_decision`, `get_regime_decision_for_date`.
- `runner/runner.py` — shim inserted near line 126 (after market-closed gate, before `build_position_state`).
- `strategies/regime_classifier_v1/{params.json, prompt.txt, prompt_schema.json, __init__.py}` — strategy folder. Note: this is a *gate*, not a tradeable strategy; `strategy.py` may be a stub or absent depending on whether the framework lets us register a non-trading strategy. **Open question item 9 (newly surfaced).**
- `cron_regime.sh` — NEW shell wrapper, parallels `cron_tick.sh`.
- `tests/test_regime_classifier.py` — NEW. Schema validation, fallback paths, prompt-hash assert, cost-model arithmetic, deterministic-log round-trip.

## Appendix B — What this doc does NOT decide

- The exact prompt text (deferred to implementation pass; will be reviewed for freeze).
- The exact feature numerical thresholds the LLM is told about (we send raw numbers, not bucketed).
- Whether we'll ever auto-promote a v2 classifier (no — Bar C.4 explicitly requires re-gate).
- Tier 3 peer-agent ownership of regime classifier (out of scope; Bar D).

---

**End of design doc.** Ready for review.
