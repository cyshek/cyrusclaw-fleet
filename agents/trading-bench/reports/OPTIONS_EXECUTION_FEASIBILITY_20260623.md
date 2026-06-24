# OPTIONS AS AN EXECUTION/STRUCTURE VEHICLE — Paper-Trading Feasibility Memo
**Date:** 2026-06-23 · **Author:** trading-bench subagent (options-feasibility-memo) · **Authority:** RESEARCH ONLY — no orders placed, no spend, no signups
**Scope:** Can we PAPER-TRADE *defined-risk options structures* (execution/structure, NOT signal) on our existing Alpaca paper account, free, today? Options-as-a-signal is already tested DEAD/MARGINAL and is NOT re-litigated here (see `OPTIONS_SKEW_20260604T065259Z.md` → REJECT; `OPTIONS_FLOW_RESEARCH_20260614.md` → MARGINAL).

---

## 1. HEADLINE VERDICT — **CONDITIONAL GO (mechanics) → SHELF-WITH-TRIGGER (research priority)**

- **Execution is FULLY GO, confirmed LIVE:** our Alpaca *paper* account is `options_approved_level = 3` (verified via a read-only `account()` call today — covered calls, CSP, long calls/puts, AND **debit verticals as a single `mleg` order**). `options_buying_power ≈ $98.7k`. Order placement, multi-leg spreads, OCC chain enumeration, exercise/assignment are all supported on free Basic data.
- **The biggest blocker is NOT execution and NOT the $100 cap — it is DATA: deep history.** Alpaca free option bars start **2024-01-18** (~16 months, ZERO 2020/2022 stress overlap; established `OPTIONS_SKEW_…md` §1a). **No honest options backtest can clear our FP-continuous + beat-BH-on-traded-path bar on 16 months of single-regime bull data.** The only honest path is a **paper-FORWARD pilot** (collect-and-trade live), readable in ~9–18 months.
- **The $100-cap framing in the task brief is STALE:** `runner/risk.py` is `MAX_NOTIONAL = MAX_POSITION = $1000` (paper bump, Cyrus 2026-05-31), not $100. **A 1-wide defined-risk vertical (~$30–$120 max-loss) fits the live $1000 paper cap cleanly** — no cap raise needed for the pilot I recommend. (A single SPY/QQQ outright *does* breach $1000 and is correctly out.)
- **Net recommendation: SHELF the options-execution lane WITH A TRIGGER, do NOT pursue an engineering build now.** It's mechanically possible but mission-marginal: the most mission-aligned structure (deep-ITM LEAPS as synthetic leverage) needs ~6–18mo expiries our 16mo no-stress data can't validate, and the runner needs net-new options plumbing (~400–600 LOC) for an edge we can't pre-prove. Trigger to revive in §6.

---

## 2. EXECUTION FEASIBILITY (the core — new work)

### 2a. Does Alpaca PAPER support options ORDER PLACEMENT? **YES — and our account is already provisioned at the max free level (3).**

Official docs (cited):
- **Options Trading** — https://docs.alpaca.markets/us/docs/options-trading — *"In the Paper environment, options trading capability will be enabled by default — there's nothing you need to do."* Defines the level ladder:
  - **Level 0** — disabled.
  - **Level 1** — sell covered call, sell cash-secured put (must own underlying / have BP).
  - **Level 2** — + buy call, buy put.
  - **Level 3** — + **buy call spread, buy put spread** (defined-risk debit verticals).
  - (No Level 4 / naked-short selling is offered in these docs — the platform's free retail ceiling is defined-risk.)
  - Level is read from the account model (`options_approved_level` / `options_trading_level` / `max_options_trading_level`); a user can *downgrade* via Account Configuration; live-account *upgrade* is a separate flow. Account-model refs: https://docs.alpaca.markets/reference/getaccount-1 and https://docs.alpaca.markets/reference/getaccountconfig-1
- **Order placement uses the SAME Orders API as equities** (https://docs.alpaca.markets/reference/postorder), with options validations: `qty` must be a whole number, **`notional` must NOT be populated (qty-only — no fractional/dollar sizing)**, `time_in_force` ∈ {day, gtc}, `extended_hours` false, `type` ∈ {market, limit, stop, stop_limit} (stop/stop_limit single-leg only). Order-payload examples: https://docs.alpaca.markets/us/docs/options-orders

**OUR SPECIFIC ACCOUNT (verified live today, read-only `account()` — no order placed):**
```
status                   = ACTIVE
options_approved_level   = 3
options_trading_level    = 3
options_buying_power     = 98748.61
buying_power             = 394994.45   (4x equity; equity ≈ 99,891)
cash                     = 98292.55
trading_blocked          = False
```
→ **API CAN do levels 0–3; OUR paper account IS provisioned at Level 3.** No live check pending for *capability* — it's confirmed. (A live check WOULD still be needed only to confirm a specific contract is `tradable` at order time and that BP suffices — but that's per-order hygiene, not a provisioning unknown. **No orders were or will be placed by this memo.**)

### 2b. Multi-leg / spreads, symbology, chain enumeration

- **Vertical spread = ONE order. CONFIRMED.** Set `order_class: "mleg"` and pass a `legs[]` array; each leg has `symbol`, `ratio_qty`, `side`, `position_intent` (`buy_to_open`/`sell_to_open`/`buy_to_close`/`sell_to_close`). Doc + working cURL for call spread, put spread, iron condor, and rolling: https://docs.alpaca.markets/us/docs/options-level-3-trading
  - **Defined-risk gate (Level-3 day-zero rule, quoted):** *"an MLeg order is accepted only if all its legs are covered within the same MLeg order… an MLeg order containing two short call legs would be rejected."* A debit vertical (long leg funds the short leg) **passes**; a naked short leg **fails**. This *is* the defined-risk guarantee enforced broker-side.
  - **MLeg with an equity leg is NOT supported** (quoted: *"MLeg orders that include an equity leg are not supported at this time"*). ⇒ A **PMCC / covered call cannot be submitted as one combined stock+option order** — you must hold/leg the stock separately and add the option as its own single-leg order. Relevant to §3.
  - `leg_ratio` must be in simplest form (GCD across legs = 1).
- **OCC symbology (confirmed from doc examples):** `ROOT + YYMMDD + {C|P} + strike×1000 zero-padded to 8 digits`. E.g. `AAPL250117C00190000` = AAPL, 2025-01-17, Call, $190.00. We construct these algorithmically (already prototyped in `OPTIONS_SKEW_…md` §1b).
- **Chain enumeration endpoint:** `GET /v2/options/contracts?underlying_symbols=SPY` (single contract: `/v2/options/contracts/{symbol_or_id}`). Defaults: `expiration_date_lte = next weekend`, `limit = 100`, `page_token` paging. Returns `symbol, strike_price, type, style, expiration_date, open_interest, close_price, tradable`, etc. **Known quirk (from `OPTIONS_SKEW_…md` §1b): it returns only CURRENTLY-listed contracts** — filtering by a *past* expiration returns 0; there is NO point-in-time historical-chain endpoint on the free tier. Fine for a *forward* pilot (we enumerate the live chain), fatal for a *historical* backtest.
- **Greeks/IV for live sizing:** option **snapshots** carry greeks + IV on free Basic via the Indicative feed (`OPTIONS_SKEW_…md`; `DATA_SCOUT_OPTIONS_VIX_20260608.md` §A). Option **bars** carry OHLCV only — IV must be inverted (BS bisection, already built in `strategies_candidates/options_skew/build_skew.py`).

**What `runner/broker_alpaca.py` (`AlpacaClient`) has vs. needs (READ-ONLY assessment — not adding now):**
Current methods: `account()`, `get_position(symbol)`, `latest_stock_price()`, `latest_crypto_price()`, `stock_bars()`, `crypto_bars()`, `submit_market_order(symbol, side, notional|qty, tif)`, `get_order()`, `close_position()`. Conceptually, an options pilot would need these ADDED (sketch only — NOT written, NOT wired):
  1. `list_option_contracts(underlying, exp_lte, exp_gte, strike_gte/lte, type)` → wraps `/v2/options/contracts` with paging. (~40 LOC)
  2. `option_snapshot(occ_symbols[])` → greeks/IV/quote for chosen strikes (sizing + marking). (~30 LOC)
  3. `submit_option_order(occ_symbol, side, qty, type, limit_price, tif, position_intent)` — single-leg; **must send `qty` NOT `notional`** (the existing `submit_market_order` is notional-first → cannot be reused as-is; this is the cleanest reason it needs a *new* method, not a tweak). (~40 LOC)
  4. `submit_mleg_order(legs[], qty, type, limit_price, tif)` — builds the `order_class:"mleg"` payload for the vertical. (~50 LOC)
  5. `exercise_position(symbol)` → `POST /v2/positions/{symbol}/exercise`; plus an NTA poller for assignment/expiry (no websocket — must poll `/v2/account/activities`). (~60 LOC)
**Crucially these are ADDITIVE — `broker_alpaca.py` is protected and UNCHANGED by this memo; the above is a conceptual gap list, not a diff.**

### 2c. The $100-cap-vs-×100-multiplier problem — RESOLVED (cap is actually $1000, and a 1-wide vertical fits)

**Correction of the brief's premise:** `runner/risk.py` enforces `MAX_NOTIONAL = MAX_POSITION = 1000.0` (paper bump, Cyrus 2026-05-31; the $100 is the *real-money* graduation start, explicitly NOT the paper sandbox). So the real question is "what defined-risk options structure fits a **$1000** notional cap," and the answer changes materially.

Concrete sizing (option multiplier = ×100/contract):
| Instrument | Notional / max-loss | Fits $1000 cap? | Fits old $100? |
|---|---|---|---|
| 1× SPY ATM put (~$5 premium) | ~$500 debit | ✅ (but big, single-name binary) | ❌ |
| 1× SPY/QQQ outright call/put (~$6–$12) | ~$600–$1,200 | ⚠️ borderline/over | ❌ |
| **1-wide SPY/QQQ debit vertical** (e.g. buy 600P / sell 599P) | **net debit ≈ $30–$120 max-loss** | ✅ **easily** | ✅ (tightest only) |
| 5-wide SPY vertical | ~$150–$350 max-loss | ✅ | ❌ |
| 1× far-OTM cheap single (~$0.30–$0.80) | ~$30–$80 | ✅ | ✅ (but ~lottery) |
| Deep-ITM LEAPS (the mission-aligned one, §3) | ~$3,000–$8,000+ /contract | ❌ **breaches $1000** | ❌ |

**The cap mechanics through the runner (important nuance):** `risk.check_trade` rejects when `notional_usd > max_notional`. But the runner's order path is **notional-first** for buys and Kelly-rewrites notional — options orders are **qty-only** (`notional` forbidden by Alpaca's options validation). So an options trade cannot flow through the *existing* buy path unchanged; the pilot must compute `max_loss_usd = net_debit × 100 × qty` and pass THAT as the `notional_usd` the risk-check sees (greeks-aware sizing), while the actual broker call sends `qty`. This is a real wiring seam, not a blocker — but it's why §6's effort estimate is non-trivial.

**Resolution:** the **minimum viable defined-risk instrument is a 1-wide SPY (or cheaper QQQ) debit vertical, max-loss ≈ $30–$120**, which fits the live $1000 paper cap with room to spare and is genuinely defined-risk (broker-enforced via the mleg "covered legs" rule). **No cap raise is required for the recommended pilot.** Outrights on SPY/QQQ and any LEAPS do NOT fit and are excluded under the cap.

---

## 3. WHAT STRUCTURE IS WORTH IT (tie to mission: BEAT SPX RAW RETURN)

Ranked, each with the honest objection:

1. **Deep-ITM LEAPS as capital-efficient synthetic leverage (replace the leveraged-ETF leverage).** *Rationale:* most mission-aligned — a ~0.80-delta LEAPS gives ~1.6–2x effective exposure with **defined risk (premium = max loss)** and **no daily-rebalance/volatility decay** that drags TQQQ/UPRO in chop. This attacks the exact mechanism (leverage + structure) our validated raw-return beats already win on. *Honest objection:* (a) **financing cost** is baked into the premium (you pay ~risk-free + borrow via extrinsic/theta) — it is NOT free leverage; over a long bull it can lag the ETF's compounding. (b) **A single LEAPS is ~$3k–$8k notional → breaches the $1000 cap**, so it cannot be piloted under current caps without a cap raise (parent/Cyrus call — flagged, not assumed). (c) **Liquidity/roll risk** on long-dated contracts; wide spreads tax every roll. (d) **16mo no-stress data cannot validate it** — LEAPS behavior in a 2020/2022 drawdown is exactly what's missing.
2. **Covered calls / PMCC on the TQQQ vol-target sleeve (income vs capped upside).** *Rationale:* harvests premium on an existing long. *Honest objection — and it's decisive against a raw-return mandate:* **capping upside directly HURTS a "beat SPX raw return" goal.** Our edge is uncapped right-tail leverage; selling calls truncates exactly the fat upside that wins. Income smooths the path but lowers the ceiling — wrong trade for THIS mandate. Also PMCC can't be one mleg (equity-leg + the stock-leg restriction), adding legging complexity. *Demote.*
3. **Cash-secured puts as a sleeve-entry mechanism.** *Rationale:* get paid to set a lower entry on a name we'd buy anyway. *Honest objection:* CSP on SPY/QQQ ties up ~$50k BP/contract (>>$1000 cap) and is really a *timing/entry* overlay — adjacent to the long/flat overlays we've closed SIX times at the same ceiling. Marginal, and cap-incompatible. *Demote.*
4. **Defined-risk put spreads as a tail hedge for the book.** *Rationale:* cheap, fits the cap, caps left-tail. *Honest objection:* **pure cost drag** — a standing long-put-spread bleeds premium every cycle and, on a raw-return mandate over a bull tape, mathematically lowers terminal wealth. Only justifiable if it lets us lever the core *more* (convexity budget), which we're not set up to exploit yet. *Hold as future combo, not standalone.*

**The ONE I'd pilot first (given the $1000 cap, defined-risk, and "no cap raise"): a 1-wide SPY/QQQ DEBIT VERTICAL as the smallest honest learning vehicle for the LEAPS thesis** — it is the cheapest structure that (a) fits the cap, (b) is broker-enforced defined-risk, (c) exercises the *entire* options plumbing (chain enum → greeks sizing → mleg submit → expiry/assignment handling) end-to-end, so the forward pilot DE-RISKS the eventual LEAPS build without needing a cap raise. **Honest caveat:** a 1-wide vertical is NOT itself a raw-return edge (it's a low-delta directional nibble); its value here is **infrastructure validation + forward data collection**, explicitly framed as such, not as an alpha claim. If/when a cap raise to ~$5k for ONE options sleeve is approved, the LEAPS synthetic-leverage pilot (candidate #1) becomes the real mission-aligned experiment.

---

## 4. BACKTEST FEASIBILITY — **NO honest historical backtest clears the bar. Paper-forward is the only path.**

- **Data reality (established, not re-scouted):** Alpaca free option bars start **2024-01-18** — *"Currently we only offer historical option data since February 2024"* (https://docs.alpaca.markets/us/docs/historical-option-data; floor pinned to 2024-01-18 in `OPTIONS_SKEW_…md` §1a). ~16 months, **overwhelmingly one regime** (SPY +~74% near-monotonic bull over the span), **zero overlap** with 2020 COVID / 2022 bear. Deep history (ORATS / OptionMetrics / CBOE DataShop) is **PAID and not approved** (`SCOUT_options_20260605.md`, `DATA_SCOUT_OPTIONS_VIX_20260608.md`).
- **Can ANY honest options backtest clear FP-continuous + beat-BH-on-traded-path on this?** **No.** `OPTIONS_SKEW_…md` already demonstrated the trap empirically on this exact window: the only "winning" variants were **bull-beta artifacts** (buy-every-dip in a tape where every dip V-recovered), and the thesis-consistent variant went **negative in the single bear sub-window**. A 16-month single-regime backtest cannot distinguish edge from beta, and **I will not pretend it can.** Modeled-premium backtests (price the structure off VIX-as-IV + a skew bump, per `DATA_SCOUT_OPTIONS_VIX_20260608.md` Track-1) can test *signal* logic deeper, but they cannot validate **execution mechanics** (real fills, assignment, roll slippage) — which is the whole point of THIS memo.
- **Therefore the only honest path is a PAPER-FORWARD pilot** (collect live chains + trade the structure live; build our own history going forward):
  - **What it looks like:** enumerate the live SPY/QQQ chain daily → open the defined-risk structure per a fixed, pre-registered rule → mark P&L from snapshot mids daily → hold to a fixed exit/expiry → log every fill, greek, and assignment. No historical backtest gate; the experiment IS the data collection.
  - **Readable horizon:** a directional 1-wide vertical run weekly gives ~40–50 independent round-trips/year → **statistically readable signal in ~9–12 months**, a *trustworthy* read (spanning at least one non-bull stretch) in ~**12–18 months**. A LEAPS pilot is even slower (annual-ish holds) → ~18mo+ to read. This is the honest cost of having no deep history.

---

## 5. MINIMAL PAPER PILOT SPEC (for the CONDITIONAL-GO path; tiny, defined-risk, no cap raise)

> Provided because mechanics are GO. Recommended ONLY if the lane is un-shelved (see §6 trigger). Kept deliberately minimal.

- **Instrument:** 1-wide **SPY** debit vertical (switch to QQQ if SPY 1-wide net debit ever exceeds the cap). Standard monthly expiry, **30–45 DTE** at entry.
- **Structure (directional, low-delta, defined-risk):** bull call debit spread — `buy_to_open` the ~0.35–0.45-delta call, `sell_to_open` the next $1 strike up, submitted as ONE `order_class:"mleg"` order (covered legs → Level-3 compliant).
- **Sizing under the $1000 cap:** `qty = 1`; `max_loss = net_debit × 100` (≈ $30–$80 typical). Risk-check sees `notional_usd = max_loss` (NOT premium×anything else) → always ≪ $1000. **No cap raise requested.** (Document, separately, that the *LEAPS* successor would need a one-sleeve cap raise to ~$5k — a **parent/Cyrus decision, explicitly NOT assumed here**.)
- **Entry rule (pre-registered, NOT a discovered signal — this is an execution pilot):** open one new vertical every Monday the market is open, IF no open position for the sleeve. Fixed cadence so the pilot measures *structure mechanics + drift*, not a timing edge.
- **Exit rule:** close (mleg `*_to_close`) at the earlier of (a) +50% of max profit, (b) −60% of max loss, or (c) 7 DTE (avoid gamma/assignment). Let nothing ride into expiry in v1 to keep assignment edge-cases out of the first run.
- **P&L marking:** daily from option **snapshot** mid (greeks feed); realized on close-fill. Benchmark each round-trip's path-return vs holding the equivalent SPY notional over the same window (the raw-return yardstick).
- **Success looks like:** (i) plumbing works end-to-end with zero protected-file regressions; (ii) ≥40 clean round-trips logged; (iii) **risk-adjusted path-return ≥ BH-SPY over the traded windows** with assignment/roll slippage fully accounted — i.e. structure adds something net of frictions. Anything less = the structure is cost drag, kill it.
- **Kill criteria:** any uncovered-leg rejection that implies a defined-risk breach; cumulative slippage > modeled by >2×; or path-return < BH-SPY after 6 months → STOP, write the post-mortem, shelve.

---

## 6. COST / EFFORT / FINAL VERDICT

**Engineering to wire options into the runner (net-new, additive; protected files would need a *future* approved change — none made here):**
- Broker methods (§2b items 1–5): chain enum, snapshot/greeks, single-leg qty order, mleg order, exercise + NTA assignment poller — **~220–280 LOC**.
- Sizing seam: greeks-aware `max_loss`→`notional_usd` translation so qty-only options orders pass the existing `risk.check_trade` (the runner buy path is notional-first; options forbid `notional`) — **~60–100 LOC** plus a small runner branch (a *future* protected change, gated on approval).
- A non-wired pilot strategy under `strategies_candidates/options_pilot/` (chain pick + structure builder + driver) — **~120–180 LOC**.
- **Total ≈ 400–600 LOC, MEDIUM complexity.** The hard parts are not the happy-path order — they're the lifecycle edge cases below.

**Exercise / assignment / settlement edge cases that are REAL and must be named** (from https://docs.alpaca.markets/us/docs/options-trading + the non-trade-activities doc):
1. **Auto-exercise of ITM at expiry:** Alpaca auto-exercises any contract ITM by ≥ $0.01 at expiry unless a Do-Not-Exercise is filed (DNE requires emailing support — not API). A vertical left to expire ITM can auto-exercise the long leg into **100 shares of SPY (~$60k)** — instantly blowing the $1000 cap and the paper sizing model. **Mitigation in v1: always close at ≥7 DTE; never hold to expiry.**
2. **Early assignment on the short leg:** American-style; the short leg can be assigned before expiry (esp. around dividends), leaving a stock position + a now-unhedged long. Must be detected by **polling NTAs** (`/v2/account/activities`) — *"assignments are not delivered through websocket events."* The runner has no NTA poller today.
3. **BP-insufficiency sell-out:** if an ITM position can't be afforded at exercise, *"Alpaca will sell-out the position within 1 hour before expiry"* — an uncontrolled close the strategy didn't choose. Another reason to exit early.
4. **Attribution drift:** our per-strategy attribution (`db.strategy_position`) walks `buy/sell` trade rows; an exercise/assignment arrives as an **NTA, not a fill** → it would NOT be captured and would silently desync the books. This is the single biggest plumbing risk and needs explicit handling before any forward pilot trades.
5. **Multiplier in every accounting path:** premium, P&L, cost-basis, and the cap-check all carry the ×100; a single missed multiplier mis-sizes by 100×. The `max_loss = net_debit × 100 × qty` convention must be threaded everywhere.

**FINAL RECOMMENDATION — SHELF WITH A TRIGGER (do not build now).**
- **Why not "pursue now":** mechanics are GO, but (a) the most mission-aligned structure (LEAPS synthetic leverage) **breaches the $1000 cap** and needs a Cyrus cap-raise + the slowest forward read (~18mo); (b) the cap-compatible pilot (1-wide vertical) is **infra-validation, not alpha** — honest, but it doesn't itself beat SPX; (c) **no historical backtest can pre-prove any of it** on 16mo no-stress data, so we'd spend ~400–600 LOC + months of forward paper time on an unproven, mission-marginal edge while validated raw-return work (TQQQ vol-target sleeve, sector rotation, allocator blend) has clearer compounding upside.
- **What would flip it to GO/build (the TRIGGER — revive if ANY fires):**
  1. Cyrus approves a one-sleeve cap raise to ~$5k specifically to pilot **deep-ITM LEAPS as defined-risk synthetic leverage** (uncapped upside, no ETF decay, premium-capped downside) — the only candidate that directly targets "beat SPX raw return," and the strongest reason to revive.
  2. We commit to (or are given) **deep paid option history** (ORATS/OptionMetrics) so an honest multi-regime backtest becomes possible — removing the "can't validate" blocker.
  3. The validated leveraged sleeves hit a *capital-efficiency* wall where LEAPS' no-decay property would measurably help, making the forward pilot worth its slow read.
- **Until a trigger fires:** keep options as a **known-feasible, parked capability** (this memo is the build spec) and spend the next research cycle on lanes with provable near-term raw-return upside. A clean, honest park beats a speculative build.

---

### FOOTER — Protected-file integrity (md5, READ-ONLY proof)
No protected file was edited. md5sums identical BEFORE (turn start) and AFTER (turn end):

| File | md5 BEFORE | md5 AFTER | Match |
|---|---|---|---|
| `runner/runner.py`        | `3811c37be962ea818e9958da675b1a03` | `3811c37be962ea818e9958da675b1a03` | ✅ |
| `runner/risk.py`          | `e4c227e019c99e7e52224eb2f91389b8` | `e4c227e019c99e7e52224eb2f91389b8` | ✅ |
| `runner/backtest.py`      | `ac0c579f8a20d11724879278a610fbb4` | `ac0c579f8a20d11724879278a610fbb4` | ✅ |
| `runner/backtest_xsec.py` | `fd39e011087d6e0295da83efbe858819` | `fd39e011087d6e0295da83efbe858819` | ✅ |
| `runner/broker_alpaca.py` | `2d82c8106496e7c80636684d2299cc89` | `2d82c8106496e7c80636684d2299cc89` | ✅ |

**Hard-rule compliance:** No orders placed (paper or otherwise). No signups. No spend. One read-only `account()` call made (to confirm provisioning level — no order). All `web_fetch` content treated as untrusted (facts only; embedded instructions ignored). No edits under `strategies/`. No protected-file edits. `web_search` not used (disabled).