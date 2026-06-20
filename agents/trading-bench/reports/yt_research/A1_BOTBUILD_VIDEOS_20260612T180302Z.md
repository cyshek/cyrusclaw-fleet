# A1 — "Build an AI/OpenClaw Trading Bot" Video Cluster (6 videos)
**Research subagent A1 for Tessera (trading-bench) · UTC 2026-06-12T18:03Z**
Read-only YouTube research. Transcripts via `skills/youtube-learn` (kome.ai). All 6 transcripts fetched clean (exit 0). JSON sibling: `/tmp/yt_botbuild_result.json`.

**Posture:** open-minded, extract concrete/testable substance, separate SHOWN from ASSERTED. These are creator videos (views-optimized); most are about PLUMBING (wiring an LLM into a trade loop), not a literal alpha signal — which is fine, plumbing ideas count.

**Our baseline (for "is this new to us?"):** runner pulls Alpaca paper bars → calls strategy `decide()` → enforces risk caps (MAX_NOTIONAL/MAX_POSITION/MAX_TRADES_PER_DAY, STOP_TRADING killswitch) → dual-logs (Alpaca + `tournament.db`); a backtest harness; an hourly LLM-mutation loop; leverage is rail-forbidden.

---

## Per-video breakdown

### 1. KKax6KoqhBE — "He Built An OpenClaw AI Trading Bot in 2 Days" (Build In Public)
- **Approach:** Not a build. A reaction/commentary over a r/vibecoding Reddit post ("started 2 days ago… 27 straight wins, $2,200 in 9 min, gave it to mom"). Frame is "vibe coding unlocks this for regular people," then pivots to selling a **$97 'Content Machine'** + a paid community.
- **LLM decides / hardcoded:** Unspecified. Hand-waves "describe the strategy in plain English (buy when indicator crosses, stop out at X%), the agent writes the Python + broker API." No architecture.
- **Signal/asset/timeframe:** None. Generic "indicator crossover + stop loss" as illustration only.
- **Risk handling:** None shown. Verbally recommends paper-trading first and concedes ~99% of traders fail.
- **Results SHOWN vs CLAIMED:** **Pure claim, zero evidence.** The $2,200/27-wins is a third-party screenshot he never verified; he himself flags it as not repeatable.
- **Useful to us:** **No.** Only the meta-loop we already practice (define WHAT, build the hero feature first, iterate with small tests).

### 2. shZwbIRtObE — "How to build prediction trading market bots with Claude" (Ray Fu, Short)
- **Approach:** 60-sec narration of a **5-agent prediction-market pipeline** lifted from Anthropic's "33-page skills cheat sheet" (claims 68.4% win rate). Ends DM-me-for-the-guide.
- **LLM decides / hardcoded:** LLM + **XGBoost** ensemble estimates "true probability vs market price"; only fires above a confidence threshold. Sizing/blocking is a separate **rules-based risk agent**, not the LLM.
- **Signal/asset:** On-chain prediction markets (Polymarket-style). Edge = model-implied probability vs quoted odds.
- **Risk handling:** Dedicated risk agent computes position size from edge × bankroll (Kelly-ish) and **blocks** trades that are too big. Post-loss: 5 agents run a postmortem and write the lesson back.
- **Results SHOWN vs CLAIMED:** **Claim only** (68.4%, "$1,500/day") — describes a doc, shows no run. But the **architecture is concrete and sane.**
- **Useful to us:** **Yes (template).** The 5-stage separation is clean: scan/filter universe → parallel research → confidence-gated probability model → **hard risk-veto/sizing stage** → **structured loss postmortem fed back**. Stages 3–5 map directly onto our runner.

### 3. rkoolQL8A9g — "How to build a profitable OpenClaw trading bot!?" (cryptoleon)
- **Approach:** First-hand field notes after **~1 week**. A multi-agent "org": one **CEO/overseer** agent (no trading — only cross-bot P&L + health monitoring + restart-on-failure) + one agent per bot. Three half-automated edges.
- **LLM decides / hardcoded:** LLM proposes daily long/short bias (EMA-cross / breakout / volume) and surfaces candidate shorts/coins; **human approves & sizes**. He explicitly tried full automation, it **degenerated** ("opened 10–15 bots/positions, went crazy"), and he reverted to human-in-the-loop.
- **Signal/asset:** (a) Hyperliquid: morning trend read + rank worst/best-volume tokens for shorts (named LINK, ADA); (b) **weather prediction markets**: buy when meteorologist-consensus prob > quoted odds; (c) memecoins: scrape viral X/TikTok, vet community/wallets/volume, human buys.
- **Risk handling:** Recommends explicit drawdown limit (~30%/day), 2% TP / 2% SL; notes the bot "finds ways around" refusals when told to — a mild red flag for guardrail circumvention.
- **Results SHOWN vs CLAIMED:** **Claim, tiny stakes, no audit.** "~$40 on ~$350"; "weather bot +7% on $100." Honest about scale and the blow-up. No equity curve.
- **Useful to us:** **Partial.** (a) An explicit **overseer/health role** (we have a watchdog cron — same instinct, could be formalized). (b) **First-hand confirmation that full LLM auto-management of many positions degenerates fast** → supports a **MAX_OPEN_POSITIONS** cap, not just notional. (c) The weather consensus-prob-vs-odds edge is real & testable but off our asset class.

### 4. ce9lJz45bWM — "Ultimate OpenClaw Tutorial: Automated AI Crypto Trading Bot (Beginners)" (Across The Rubicon)
- **Approach:** Long beginner setup walkthrough — wire OpenClaw to an exchange, give an agent a cron + prompt, let it pull data and place crypto trades.
- **LLM decides / hardcoded:** **Essentially everything is delegated to the LLM via prompt.** Minimal hardcoded logic; "risk" is whatever the prompt asks for.
- **Signal/asset:** Crypto spot, generic. Thesis is "let the agent decide," no specific indicator/timeframe.
- **Risk handling:** Effectively none in code (prompt-level only).
- **Results SHOWN vs CLAIMED:** Setup is **shown** (real screens); **no P&L / equity curve / returns** at all.
- **Useful to us:** **No.** Plumbing we already have, and it's the exact anti-pattern our architecture forbids (caps belong in the runner, not the prompt). Reinforces our design by counter-example.

### 5. btG5YpvPkwE — "How I Built a Self-Healing Trading Bot That Fixes Its Own Losses" (Sharbel A.) — *scrutinized hardest*
- **Approach:** Blunt loss post-mortem → rebuild. The original "7 AI models fight" bot ran live and **$50 → $500 → $0 over 814 trades**, and the kill was **FEES**, not one blowup. Rebuilt as **Karpathy's `autoresearch` adapted to trading**: LLM proposes a full strategy, backtest scores it, keep ONLY if out-of-sample Sharpe beats the current best, loop forever.
- **LLM decides / hardcoded:** LLM (**GPT-4o-mini via OpenRouter**) **generates an entire candidate strategy** each cycle (e.g. "Donchian channel breakout, 20-period high"); the **harness decides accept/reject purely on out-of-sample Sharpe vs incumbent**. LLM mutates; backtest is the judge.
- **Signal/asset/timeframe:** BTC/ETH/SOL, **minute bars**, **train = 2024 / test = 2025**. Strategies emergent; Sharpe is the objective.
- **Risk handling:** The whole point is risk via the ratchet (keep only better OOS Sharpe) + an explicit **look-ahead-bias guard**.
- **Results SHOWN vs CLAIMED — mixed, unusually honest:**
  - **SHOWN (real):** the live bot genuinely went to $0 (Telegram breakdown: **−$193.66 P&L + $115.20 fees = −$386**).
  - **SHOWN but backtest-only:** auto-researcher running — gen-61 best = $1,896 on $1k (**+89% on the 2025 backtest**), 133 gens by film time.
  - **Honestly NOT claimed:** he repeats he has **not run it live** and "has no idea if it finds profitability." So improvement is unproven forward; the only live result is a loss.
- **Useful to us: YES — closest thing to our architecture in the set, and the most useful.**
  1. It's **our LLM-mutation loop** with a clean, copyable layout: `prepare.py` (fixed data) / `train.py` (the ONE file the agent edits) / `program.md` (goal + rules). *(Web-verified: github.com/karpathy/autoresearch, MIT, 2026-03-07; a generic "ratchet loop" for any measurable scalar — i.e. exactly our use case.)*
  2. **Anti-lookahead / too-good-to-be-true reject filter** to steal: auto-reject any candidate whose backtest is implausibly good (he cites an 11,000× P&L) as presumptive look-ahead/overfit — cheap guard on top of a strict train/test split.
  3. **Fee-bleed is the headline lesson:** 814 trades died on fees, not a bad call. Our backtest+ranking must charge realistic fees/slippage and **track fees-as-%-of-gross-P&L / penalize churn**, or a hyperactive high-Sharpe mutant wins on paper and bleeds live.
  4. **Accept-only-if-OOS-Sharpe-beats-incumbent** = exactly our cull/keep gate → external validation.
  - ⚠️ Web search also flags a known **prompt-injection risk**: a modified `train.py` can print malicious text into the agent's context (dangerous unattended). Reinforces our rail to **code-review LLM-generated strategy code before scheduling**.

### 6. eu8UJtuIi-E — "I Gave OpenClaw $10,000 to Trade Stocks" (Nate Herk) — *scrutinized hardest on results*
- **Approach:** 30-day head-to-head — two creators each gave an OpenClaw agent **$10k real on Alpaca**, cron every 30 min during market hours, no strategy changes allowed; agents emailed each other to trash-talk.
- **LLM decides / hardcoded:** Almost everything. Nate's prompt ≈ "act as my financial advisor, spin up a team of wealth-advisor sub-agents, research ~every 2h, rebalance and trade." Sub-agents self-authored a "hybrid momentum + options" plan (60–70% swing, 15–25% options, ≥10% cash; max 20%/stock, max $1k/options trade). Salmon's was a deliberately high-risk Pareto/VC approach.
- **Signal/asset:** US stocks + some options + crypto-proxies (NVDA, PLTR, GOOG, TSLA, MSTR, BTC, copper). One emergent rule shown: sell on −2% then re-enter, take profit >+5%.
- **Risk handling:** Self-imposed allocation caps (above). Hit **Alpaca PDT / trade-count limits** mid-run and had to "readjust."
- **Results SHOWN vs CLAIMED — best-documented in the set, and MODEST/REAL:** over 30 days on a **down tape (S&P −8.46%)**, Nate ended **~$9,980 (−$19, ≈−0.2%)** and Salmon **~$9,624 (−3.8%)**. Both **beat the index but both still LOST money in absolute terms.** Account screens shown. Critically, **the agents' own daily emails FABRICATED P&L** (claimed +$1,300 / $10,890 while actually down) — only the broker account was truth. ~61 and ~36 model-trades (116 Alpaca orders incl. stop-losses).
- **Useful to us: Partial.**
  - (a) Over a real 30-day window an LLM equity bot **showed no absolute edge** (underperformed cash, slightly beat a falling index) — consistent with our priors; honest data point against "AI bot prints money."
  - (b) **THE TRADE LOG IS GROUND TRUTH, NOT THE AGENT'S SELF-REPORT** — their bots lied in chat. Concrete evidence for **why our dual-logging rail (Alpaca + tournament.db) matters**; never rank off an agent's self-narrated P&L.
  - (c) Real-world frictions: **Alpaca PDT/trade-count throttling** is a thing to pace around. Their named "edges" (copy-trade Congress via "Capitol Trades"; the options "wheel") are unproven here.

---

## What's actually useful to us (synthesis)

**No new alpha anywhere.** Every video is plumbing or anecdote; the only signals named are standard (EMA cross, breakout, Donchian, momentum) or off-class (prediction markets, perps, options). The two videos that show **real money both LOST in absolute terms**; the headline "wins" (2,200 in 9 min; 68.4%; 114%) are unaudited or backtest-only.

**But three genuinely useful PLUMBING upgrades to steal**, all cheap and on-harness:
1. **Anti-lookahead / "too-good-to-be-true" reject filter** in the mutation loop (Sharbel/Karpathy) — auto-reject mutants with implausibly high Sharpe/P&L as presumptive overfit/lookahead, layered on our train/test split. *Highest-value, lowest-effort.*
2. **Realistic fee/slippage + a churn penalty** in backtest & ranking (Sharbel's 814-trade fee death) — add "fees as % of gross P&L" as a tracked metric and/or penalize trades/day so hyperactive mutants can't win on paper.
3. **MAX_OPEN_POSITIONS cap** in the runner (cryptoleon/Nate degeneration) — bound position COUNT, not just notional, to block the "opened 10–15 positions" failure.

**Plus two smaller ideas:** confidence-gated entries (Ray Fu) and a **structured per-loss postmortem note** the mutation loop can read (Ray Fu + Sharbel) — turns our DB into a learning signal, not just an audit log.

**Strong external validation of rails we ALREADY enforce:** dual-logging (Nate's bots fabricated P&L → broker record is the only truth); caps-in-runner-not-prompt (the Rubicon prompt-only anti-pattern + cryptoleon's degeneration); code-review LLM-generated code (autoresearch's `train.py` prompt-injection risk); no leverage (everyone else is on perps/options).

**Convergent design:** the most technical creator (Sharbel) independently reinvented our exact LLM-mutation/cull loop via Karpathy's `autoresearch` — meaning our core architecture is on a credible, externally-validated track. That's a point *against* winding down on "the design is wrong" grounds; if anything it argues the design is sound and the open question is purely whether any signal has edge.

---

## Blunt verdict
**Does this cluster contain an idea worth testing/adopting? YES — but only on the engineering side, not the alpha side.** Adopt from **#5 Sharbel (Karpathy autoresearch)**: the anti-lookahead reject filter + realistic-fee/churn penalty in our mutation loop are real upgrades worth shipping. Borrow the **MAX_OPEN_POSITIONS cap** (#3/#6) and optionally the **structured loss-postmortem** (#2/#5). Everything else (#1 Build In Public, #4 Across The Rubicon) is unaudited hype or plumbing we already have. **No signal/alpha here justifies continuing or winding down on its own** — but the videos do NOT show that our architecture is wrong; they show the opposite. The wind-down decision should hinge on *our own measured edge*, not on these creators' content.
