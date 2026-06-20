# YouTube Research Sprint — Synthesis & Recommendation

**Date:** 2026-06-12
**Author:** Tessera (trading-bench)
**Trigger:** Cyrus paused the wind-down decision and asked for thorough, open-minded YouTube research before ruling out the project. Sent 6 video links + asked specifically for a careful pass on **Umar Ashraf** (@UmarAshraf28), a discretionary trader he has followed since high school.
**Inputs:** `A1_BOTBUILD_VIDEOS_20260612T180302Z.md` (6 bot-build videos), `A2_UMAR_ASHRAF_20260612T181512Z.md` (8 Umar Ashraf videos, full transcripts read).

---

## TL;DR

Two clusters, two honest answers:

1. **The 6 "build an AI trading bot" videos** = all **plumbing, no alpha.** Every one is "how to wire an LLM into a trade loop." The only two that showed real money both **lost** (one bled to ~$0 on fees over 814 trades; one was −$19 in 30 days). Viral wins were unaudited or backtest-only. **They contain no edge we lack — but they validate the rails we already enforce** (dual-logging, caps-in-runner, no leverage), and they surface **2 cheap engineering upgrades worth stealing.**

2. **Umar Ashraf** = **the real deal, but his edge is genuinely discretionary** and does not reduce to a mechanical signal on the OHLCV data our bench uses. His durable advantage is **live order-flow/tape reading + context + intuition + execution discipline.** He says this himself, credibly and repeatedly. **The mechanizable part of him is his risk & money-management framework** — which is valuable, but it's a *money-management overlay*, not an alpha signal.

**Net effect on the wind-down decision:** This research did **not** find a new alpha signal. But it meaningfully *reframes* what we should be building — and it argues against winding down *just yet*, because the single highest-leverage thing we have never properly built is exactly the thing both clusters independently point at: **disciplined risk management and position sizing around the one real lead we already have.**

---

## Cluster 1 — The "AI bot build" videos (A1)

**What they are:** Build In Public ("OpenClaw bot in 2 days"), Ray Fu ("prediction market bots with Claude"), cryptoleon ("profitable OpenClaw bot"), Across The Rubicon ("automated AI crypto bot"), Sharbel A. ("self-healing bot that fixes its own losses"), Nate Herk ("I gave OpenClaw $10k to trade stocks").

**Honest findings:**
- **No alpha.** None demonstrates a tested, durable edge. The genre is automation tutorials, not strategy research.
- **Real money shown = real money lost.** Sharbel's live bot decayed to ~$0, almost entirely on fees, over 814 trades. Nate's $10k was −$19 over 30 days (and his bots were caught *fabricating* P&L in chat — which our dual-logging would also catch).
- **Strong validation of our design.** Caps enforced in the runner, dual-logging against the broker's record, and the no-leverage rail are exactly the things these videos either lacked (and blew up) or stumbled toward. We are not behind; we are ahead of this content.

**2 upgrades worth stealing** (both from Sharbel's clone of Karpathy's `autoresearch`, which is structurally *our* mutation loop):
- **(U1) Anti-lookahead / "too-good-to-be-true" reject filter** for mutants — auto-reject any backtested candidate whose Sharpe/return is implausibly high as presumptive look-ahead/overfit, on top of our train/test split. Cheap, high-value guard.
- **(U2) Fee/slippage realism + a churn penalty** in backtest *and* ranking — a metric like "fees as % of gross P&L" and/or a trades-per-day penalty, so a high-Sharpe-but-hyperactive mutant can't win on paper then bleed live (Sharbel's exact failure mode). *We already model costs, but we do not explicitly penalize churn in ranking.*
- Minor: a `MAX_OPEN_POSITIONS` cap (cheap), a structured per-loss postmortem note in the DB (turns the trade log into a learning signal).

---

## Cluster 2 — Umar Ashraf (A2)

**Who he is:** Established discretionary US day-trader since ~2013. Trades **SPY via 0DTE options** in size (also TSLA/AMZN/ES). Founder of TradeZella (trade-journaling SaaS) and Ashraf Capital. Substantive teacher, not a hype account.

**His theory of edge (told straight):** The market is an **auction**. Supply/demand zones and key levels tell you *where* to pay attention; they are **not** a signal by themselves. The trade is taken only when the **order flow** (DOM, Level 2, time & sales, footprint, Delta, absorption, exhaustion, unfinished auctions) confirms *who is winning the auction* at that level. He **explicitly rejects** mechanical pattern trading. His named setups (morning top reversal, opening-range drive, second-day play, continuation sell-off, midday reversal) are **contexts that "ignite interest," not triggers.** The actual trigger is discretionary tape reading + context synthesis + intuition built over ~10 years of screen time.

### The honest split

**❌ Irreducibly discretionary (cannot mechanize on our data):** his actual entry trigger is live order-flow microstructure (footprint/Delta/DOM — data we don't even ingest), interpreted contextually with no fixed threshold, plus intuition, plus the discipline to *not trade* when he can't read the tape, plus execution under live P&L pressure. **There is no faithfully-backtestable "Umar Ashraf strategy."** An OHLCV reconstruction (failed-breakout-on-volume + opening-range + time-filter) would be a *pale proxy* that strips out the exact information he decides on, and would almost certainly underperform him. Presenting such a proxy as "his method, tested" would be dishonest.

**✅ Mechanizable (his risk & money-management framework — the part he says matters most):**
- **Fixed-fractional sizing:** risk **1–2% of account per trade**; **size = dollar-risk ÷ distance-to-stop**; keep risk constant until consistently profitable for ~a year.
- **≥2R trade selection** + the expectancy math: at avg **2R you're profitable at a 50% win rate**; ~40% still works with good R. "You don't need to be right all the time."
- **Anti-ego streak sizing:** never up-size right after a big win or loss; after 2 losers don't up-size, after 3 step away.
- **Structural stops** (placed where the thesis is invalidated, never an arbitrary dollar figure) + **R-based exits.**
- **Journal/measure by R, not P&L;** track process metrics (win-rate, R, plan-accuracy, loss-cutting) over monthly P&L — especially early.
- His own post-mortems: losing trades usually had the *right setup* and lost to **fear / late entry / tilt / revenge / not honoring the stop.** By his account, the alpha is in **execution and risk discipline, not the signal.**

**Verdict:** If the question is *"does Umar give us a testable alpha signal?"* — **no, honestly.** If it's *"is there anything here worth taking?"* — **yes: his risk/sizing/process discipline**, which belongs in our bench as a **portfolio-level money-management module**, not as a strategy. His real lesson for a quant bench is almost an *anti-lesson*: a large, durable retail edge can be **discretionary execution**, and the highest-leverage code we could write is **not a new entry signal but better risk management and sizing around the signals we already have.**

---

## The convergence (why this matters for the wind-down call)

Three independent things now point at the **same** conclusion:

1. **Our own 19-day record:** ~66 lanes tried; the *only* thing that ever cleared the "beat SPX raw" bar is **leveraged-trend (TQQQ / SMA-200)** — and it's a *leverage premium*, not alpha, held back by an uninvestable −56% drawdown.
2. **A1 (bot-build):** the bots that traded actively *died on costs/churn and poor risk control*, not on bad signals.
3. **A2 (Umar):** the most-respected discretionary trader in this set says, in his own words, that the durable edge is **risk management, sizing, and execution discipline** — not the signal.

All three say: **the missing piece is not another entry signal — it's the risk/sizing layer.** And that is *exactly* the build that turns our one real lead (leveraged-trend) from a paper curiosity into something potentially investable: a **volatility-targeting + position-sizing sleeve** that compresses the −56% drawdown toward something holdable.

In other words, the research didn't hand us a new horse — it handed us a *saddle*, and we already have the horse.

---

## Recommendation

**Do NOT wind down yet. Run one focused, finite experiment**, now better-justified than before:

**Build a risk-management / position-sizing sleeve and apply it to the leveraged-trend lead.** Concretely:
- **Volatility targeting:** scale exposure inversely to realized volatility (target a fixed annualized vol, e.g. ~15–20%), instead of always-100% in TQQQ.
- **Fixed-fractional / structural-stop sizing** (the Umar-mechanizable part): size by a fixed risk fraction with a structural stop; test flat-risk vs. streak-reactive sizing for drawdown/risk-of-ruin.
- **Measure honestly:** does the sleeve compress max drawdown toward SPX's range (~−34% or better) **while still beating SPX on raw return**, out-of-sample? That is a clean **go/no-go**.

**Also adopt the 2 cheap engineering upgrades (U1, U2)** regardless of the above — they harden the mutation loop and the ranking against the precise failure mode (overfit + churn) that killed the bots in A1.

**If the sleeve works:** we have a genuine paper→real candidate to put in front of Cyrus, with the drawdown problem actually addressed — and a money-management layer that improves everything else we run.
**If it doesn't:** then we will have honestly exhausted the one real lead with the one missing ingredient, and I'll give Cyrus a clean, evidence-based recommendation to wind the *return-engine* ambition down and keep only what has standalone value (the harness + the honesty discipline). Either way it's a real verdict, not idling.

**What this research explicitly did NOT find:** a new mechanical alpha signal, from either cluster. I'm not going to dress up an OHLCV proxy of Umar's tape-reading as "his strategy" — that would be exactly the kind of narrative-fallacy self-deception the bench exists to prevent.
