# Natenberg — Batch 3A: Intro to Spreading + Volatility Spreads (ch10–11)

> **Source coverage note:** This batch file (`03a_volspreads.txt`, 2737 lines) contains the
> tail of ch9 (risk measures II — theta/vega/gamma/lambda + the higher-order Greeks summary
> tables), **all of ch10 (Introduction to Spreading)**, and **ch11 (Volatility Spreads) up
> through the *Time Butterfly* section**. The file is **CUT OFF** at the header *"Effect of
> Changing Interest Rates and Dividends"* — its body is a single teaser sentence, nothing more.
>
> **Structures the task listed but that are NOT in this file** (they live in a later batch — flag for follow-up):
> **diagonal spreads**, "choosing an appropriate strategy," "making adjustments," and
> "submitting a spread order." All notes below on diagonals are inferred/standard, clearly marked.
> Everything else (straddle → time butterfly) IS fully covered by the source and noted from it.

Sign convention reminder (Natenberg): long premium/wants-movement = **+gamma / –theta / +vega**;
short premium/wants-stillness = **–gamma / +theta / –vega**. Theta is shown as negative when you
*own* decay-losing premium. "Long the spread" = paid a debit; "short the spread" = took a credit.

---

## Ch10 — Introduction to Spreading

### What a spread is & why traders spread
- **Spread = opposing positions in different but related instruments.** Most commonly the two legs
  move *opposite* to each other when conditions change; profit requires they change at **different
  rates** (if they moved identically the spread value would never change → no edge).
- Natenberg's thesis: **most successful option traders are spread traders.** A naked directional
  bet is better expressed in the *underlying* (if you're right on direction you're guaranteed paid).
  In options, even a correct directional call can lose because vol-change + time-decay + other
  forces move the price independently of direction.
- Probability-based pricing only pays off **in the long run**; over short horizons any single
  outcome can deviate. Spreading is "the primary method by which traders limit the short-term
  effects of *bad luck*" while still capturing theoretical edge.

### Spread families introduced (non-option, to build intuition)
- **Cash-and-carry arbitrage:** buy cash commodity, sell overpriced forward, carry to maturity.
  Forward value = cash + interest + storage/insurance. Worked ex: $700 cash, 6% rate, $5/mo carry →
  2-mo forward fair = $717; if market forward = $725, locked profit = +$8 = exact mispricing,
  independent of where the commodity goes. Note: reverse arb (sell cash, buy forward) usually
  impossible in commodities — can't borrow/short the physical.
- **Intramarket / calendar (futures):** long one futures month vs short another; value driven by
  cost-of-carry between months. Worked ex: 2-mo fair $717 vs 4-mo fair $734.17 → fair spread
  $17.17; if trading $20 it's $2.83 rich → sell the spread (buy near, sell far). Realize profit
  either by spread reverting **or** carrying to maturity.
- **Intermarket spread:** buy one market, sell a different but related one (10y vs 30y Treasury
  "NOB" — notes over bonds; gold/silver; corn/soybeans; S&P vs Dow). Less reliable relationship →
  more risk.
- **Ratio strategy:** unequal contract counts when products trade at a price *multiple* (ex:
  Commodity B ≈ 3× Commodity A → buy 3 A / sell 1 B for +30 credit when ratio is stretched to 3.25).
- **Multi-leg / crack & crush:** crack spread 3:2:1 = (2×gasoline + 1×heating oil – 3×crude);
  "buy the spread" = buy products / sell crude. Crush = soybeans vs soyoil + soymeal.

### Execution mechanics (matters for the paper-quant fill model)
- **Execute the HARDER (less liquid) leg first.** If you fill the easy leg first you risk being
  left naked when the hard leg won't fill at a good price → "legging risk."
- A spread quoted as one instrument has **one bid / one offer**, and the market-maker's
  spread-as-a-unit price is usually **tighter** than summing the individual leg bid-asks (he has
  less risk doing all legs at once). Worked ex: summing legs gives 9 bid / 16 ask, but the unit
  spread might quote 11 bid / 14 ask. **Executing the whole spread as one trade beats legging.**
- When exchanges require reporting individual leg prices, the **individual prices don't matter** as
  long as they sum to the agreed spread price (though exchanges frown on absurd prints).

### Option spreads specifically
- A "position" in a spread need not be directional. In options you can build spreads on **any**
  Greek dimension: long-gamma vs short-gamma (sensitive to *realized* vol of underlying), long-vega
  vs short-vega (sensitive to *implied* vol), even long/short-rho (interest rates).
- The Ch8 dynamic-hedging examples ARE gamma spreads: option (has gamma) hedged with underlying
  (no gamma) → net position cares about **realized volatility, not direction**.
- Spreads can be **dynamic** (need periodic delta re-hedging) or **static** (set once, carried to
  expiry — done only when risk is well-defined and limited, e.g. butterflies/condors).
- **Three reasons options are spread so heavily:**
  1. **Capture relative mispricing** — and in options mispricing is usually expressed in
     **volatility** terms, not price. Ex: an 8.00 option (IV 26%) vs a 6.75 option (IV 28%) where
     model vol is 23% → the 6.75 one is *more* overpriced in vol terms even though it's "less"
     overpriced in dollars. **Lesson: always compare in IV, not price.**
  2. **Express a specific market view** with capped loss.
  3. **Control risk / widen margin for error** on model inputs.
- **Margin-for-error / sizing lesson (critical for a quant):** a 4×1 hedge with 0.50 edge/contract
  makes 2.00; scaling to 400×100 makes 200.00 — *but* if your 35% vol estimate is wrong and real
  vol prints 45%, that same 200.00 *profit flips to a 200.00 loss*. Don't size to max theoretical
  edge; size so you **survive an input error**. Spreading raises your breakeven-vol cushion
  (e.g. from a 5-pt to a 10-pt margin for error) and *that* is what lets a trader run big size.
- **Casino/roulette analogy:** the house edge (5%) is identical whether one player bets $2,000 on
  one number or 38 players bet $1,000 across all numbers — but **risk collapses** when bets are
  spread. The "perfect spread" (all 38 numbers covered) guarantees the edge with ~zero variance.
  Same edge, far less short-run ruin risk. **This is the entire rationale for spreading: keep the
  edge, kill the variance, stay in the game long enough for probabilities to pay.**

### Ch10 — what a quant should remember
- Spread P&L depends on legs changing at **different rates**, not on either leg's absolute move.
- **Compare option richness in IV, not dollars.** Dollar mispricing lies; vol mispricing is the
  real signal.
- **Sizing is a survival problem, not a max-edge problem.** Size to survive an input (vol) error;
  spreading buys margin-for-error which is what permits size.
- Microstructure: model **legging risk** (hard leg first) and the fact that a packaged spread fills
  *inside* the summed leg bid-asks. For a paper fill model, single-order multi-leg spreads should
  get a tighter effective spread than legging would.

---

## Ch11 — Volatility Spreads

**Definition:** a *volatility spread* hedges an option position with **other options** (rather than
the underlying), chosen so the package is **≈delta-neutral** but sensitive to (a) underlying price
moves, (b) implied-vol changes, and (c) time. Ch11 examines each structure's expiration value, then
its delta/gamma/theta/vega/rho profile.

---

### 1. Straddle
- **Construction:** one call + one put, **same strike, same expiry.** Long straddle = buy both;
  short = sell both. Usually done **1:1 at-the-money** (ATM call δ≈+50, put δ≈–50 → net ≈0).
- **Greeks / view:**
  - **Long straddle: +gamma / –theta / +vega.** Wants a BIG move *either direction* + rising IV.
    Direction-neutral, volatility-LONG.
  - **Short straddle: –gamma / +theta / –vega.** Wants the underlying to sit still + falling IV.
- **Expiration P&L:** V-shape (long) / inverted-V tent (short). Long = limited risk (debit paid),
  **unlimited profit both directions**; short = limited profit (credit), **unlimited loss both ways**.
  Breakevens = strike ± total premium (not numerically given in text, but that's the parity shape).
- **Natenberg's caution:** new traders love long straddles ("limited risk, unlimited profit both
  ways") but if the move doesn't come, even a *limited* loss hurts; you must weigh the *likelihood*
  of outcomes (← why you need a pricing model), not just whether risk is capped.
- **Ratio straddle variant:** can be built ITM/OTM. Ex: underlying 100, Sep-95 call δ=75, Sep-95
  put δ=–25 → 1:1 gives +50 net = a **bull straddle**. To stay delta-neutral, buy **3 puts per 1
  call** (3×–25 = –75 vs +75) → still same strike so still a "straddle," but unequal legs = **ratio
  straddle**.

### 2. Strangle
- **Construction:** long call + long put (or short both), **same expiry, DIFFERENT strikes.** 1:1,
  strikes chosen so call & put deltas are ~equal (delta-neutral). **Convention: a strangle =
  OUT-of-the-money options** (e.g. 90/110 strangle on a 100 underlying = 90 put + 110 call). An
  ITM-options version is a **"guts."**
- **Greeks / view:** same signs as straddle —
  - **Long strangle: +gamma / –theta / +vega** (wants big move + rising IV; cheaper than straddle,
    needs a *bigger* move to pay).
  - **Short strangle: –gamma / +theta / –vega** (wants stillness + falling IV; wider profit zone
    than short straddle but still unlimited tail risk).
  - ⚠️ **(verify: source text Fig 11-4 caption prints "Short strangle: +gamma/–theta/+vega" — this
    is a TYPO in the book/OCR. A short strangle is unambiguously –gamma/+theta/–vega; the body text
    and Fig 11-9 confirm short strangles sit with the short-premium family.)**
- **Expiration P&L:** flat-bottomed valley (long) between the strikes / flat-topped plateau (short).
  Long = limited risk, unlimited profit beyond either strike; short = capped credit, unlimited
  double-tail loss. Same open-ended profile as straddle but with a dead zone between strikes.

### 3. Butterfly
- **Construction:** **three** equally-spaced strikes, **all same type** (all calls OR all puts),
  same expiry. Ratio is **always 1 × 2 × 1.** **Long butterfly = buy the wings (outer strikes),
  sell 2× the body (inner strike).** Short = reverse. Ex long: +1 Mar-90c / –2 Mar-100c / +1 Mar-110c.
  Wings = outer strikes; body = inner strike.
- **Expiration value (the key table):** worth **0** if underlying finishes at/outside either wing;
  worth its **maximum = the distance between strikes** (10.00 in the 90/100/110 example) when
  underlying lands exactly on the body strike at expiry. Always **0 ≤ value ≤ strike-spacing.**
  Because it can never be <0, a long butterfly always *costs* a debit (pay between 0 and 10).
- **Greeks / view:**
  - **Long butterfly: –gamma / +theta / –vega** → behaves like a **short straddle** but with
    **strictly capped loss.** Wants underlying to pin the body strike + falling IV.
  - **Short butterfly: +gamma / –theta / +vega** → behaves like a **long straddle** with capped
    profit. Wants a move away from body + rising IV.
- **Max profit / loss / breakevens:** long fly max profit = (strike-spacing – debit paid) at the
  body; max loss = debit paid (occurs outside the wings); breakevens = lower wing + debit and upper
  wing – debit (parity geometry — text gives the 0-to-spacing bound and the "pay 1–8" pricing logic
  rather than an explicit BE formula).
- **Pricing intuition:** fair price ≈ probability of pinning the body. High pin-probability → pay
  up to ~8 (of a 10 max); low probability / fat tails → pay only 1–2 (likely to lose it all).
- **Call fly = put fly** (same strikes/expiry) **for European options** — identical desired outcome,
  identical value; if they differ in price it's an arb (buy cheap fly, sell rich fly). **Caveat:
  NOT guaranteed for American options** (early-exercise possibility breaks the equivalence unless
  you can be certain of carrying to expiry).
- **Sizing lesson:** because risk is capped, butterflies trade in **much bigger size** than
  straddles — "300 butterflies (300×600×300) can be less risky than 100 straddles." **Size ≠ risk
  in options; risk depends on the *structure*, not just the contract count.**

### 4. Condor
- **Construction:** **four** strikes, **all same type**, same expiry, ratio **1×1×1×1.** Two inner
  strikes = body, two outer = wings. Inner spacing can be anything, but the **two lowest** strikes
  must be equally spaced as the **two highest**. **Long condor = buy the 2 outer wings, sell the 2
  inner body** strikes. Ex long: +1 Mar-90c / –1 Mar-95c / –1 Mar-105c / +1 Mar-110c.
- **Greeks / view:** **a condor is to a strangle what a butterfly is to a straddle** — a
  range-bound, capped version.
  - **Long condor: –gamma / +theta / –vega** → like a **short strangle** with capped loss; wants
    underlying to finish *between the two inner strikes* (where it's worth max) + falling IV.
  - **Short condor: +gamma / –theta / +vega** → like a **long strangle** with capped profit.
- **Expiration value:** **0 ≤ value ≤ (spacing between the two higher OR two lower strikes).** Max
  value when underlying finishes anywhere between the two inner strikes (a flat-topped max region,
  vs the butterfly's single-point peak); worthless outside the outer wings.
- **Delta-neutral** when underlying is **midway between the two inner strikes.** Call condor = put
  condor for European options.

> **Symmetric-family summary (Fig 11-9), executed delta-neutral → no directional preference:**
> **Long straddle / long strangle / short butterfly / short condor → +gamma/–theta/+vega** (want
> movement + rising IV). **Short straddle / short strangle / long butterfly / long condor →
> –gamma/+theta/–vega** (want stillness + falling IV). *(Butterflies & condors = "wingspreads.")*

---

### 5. Ratio Spread (a.k.a. backspread / frontspread)
- **Construction:** buy & sell **unequal** numbers of options, **same type, same expiry**, usually
  **delta-neutral.** Two flavors:
  - **Buy more than sell ("backspread"):** ex +3 Oct-105c (δ25) / –1 Oct-95c (δ75), underlying 100.
    Net δ = 3×25 – 75 = 0.
  - **Sell more than buy ("frontspread"):** ex +1 Oct-95c / –3 Oct-105c.
- **Greeks / view:** a ratio spread lets you be vol-long/short **AND** lean directional:
  - **Buy more than sell: +gamma / –theta / +vega.** Wants a move + rising IV, but with a
    **directional preference** toward the side with extra long options (calls → prefers UP, profit
    *unlimited* upside; puts → prefers DOWN, unlimited downside). Worked call ex (3×105c / –1×95c):
    at 80 → +3.00, at 100 → –2.00, at 120 → +23.00. Profits on a big move *either* way but **much
    bigger up**; loses if it sits at the strike.
  - **Sell more than buy: –gamma / +theta / –vega.** Acts like a **short straddle but with limited
    risk on ONE side** (sell more calls → like short straddle with limited *downside* risk; sell
    more puts → limited *upside* risk). The naked extra short options carry the unlimited tail on
    the other side.
- **Credit/debit rule (important):** under a standard model, a **delta-neutral ratio spread where
  you buy more than you sell should always be established for a CREDIT** — and it *must* be a credit
  for the structure to profit (since it goes to 0 if the underlying collapses the wrong way).
  Conversely, "sell more than buy" caps the *downside* (calls) or *upside* (puts) because value
  can't drop below 0.
- **Expiration P&L:** non-symmetric. Buy-more: worthless on a big adverse move (calls→big down,
  puts→big up), unlimited gain on the favored side. Common ratios: **2:1** (most common), also 3:1,
  4:1, 3:2.
- **⚠️ (verify:** Fig 11-18 column header prints *"Call ratio spread (sell more than **sell**)"* —
  OCR typo; should read *"sell more than **buy**."* The Greek signs in that column
  (–gamma/+theta/–vega) are correct.**)**

### 6. Christmas Tree (a.k.a. ladder)
- **Construction:** the strangle-analog of a ratio spread (3 strikes, same type, same expiry,
  usually delta-neutral).
  - **Call Christmas tree:** buy(sell) a call at a **lower** strike, sell(buy) **one call each at
    two higher** strikes. Ex long: +1 Oct-90c / –1 Oct-95c / –1 Oct-105c.
  - **Put Christmas tree:** buy(sell) a put at a **higher** strike, sell(buy) **one put each at two
    lower** strikes.
  - **Long Christmas tree** = 1 bought / 2 sold → acts like a **short strangle with limited risk on
    one side.** **Short Christmas tree** = 1 sold / 2 bought → like a **long strangle with limited
    profit on one side.**
- **Greeks / view:** mimic strangles/straddles —
  - more bought than sold → **+gamma / –theta / +vega** (wants move + rising IV);
  - more sold than bought → **–gamma / +theta / –vega** (wants stillness + falling IV).
- **Expiration P&L:** non-symmetric (Figs 11-14→11-17), capped on one side via the structure, naked
  tail on the other.

---

### 7. Calendar Spread (time spread / horizontal spread)
- **Construction:** opposing positions in two options, **same type, same strike, DIFFERENT
  expiries.** **Long calendar = buy the LONG-term option, sell the SHORT-term** (a debit → "long").
  Short calendar = buy near, sell far (a credit). Usually 1:1, usually **ATM** (deltas ≈50 → ≈delta
  neutral). Can be ratio'd for directional lean.
- **The two defining behaviors (ATM long calendar):**
  1. **Gains value as time passes with no underlying move** — because the **short-term option
     decays faster** than the long-term one (Ch8 fact: ATM theta *increases* as expiry nears).
     Worked ex (Jun vs Apr 100c, underlying flat at 100, 20% vol): spread 1.34 → 1.69 (after 1 mo)
     → 3.26 (Apr expires worthless, Jun still worth 3.26).
  2. **Gains value if IMPLIED vol RISES, loses if IV falls** — because the **long-term option has a
     bigger vega.** Worked ex: at 10% vol spread = 0.67; at 30% vol spread = 2.02.
- **Greeks / view (long calendar): –gamma / +vega** (and **+theta**). **This is the structure's
  unique twist:** unlike all the symmetric spreads, **realized vol and implied vol pull in OPPOSITE
  directions.** A long calendar **wants the underlying to sit still (–gamma) BUT wants IV to rise
  (+vega)** — two seemingly contradictory wishes. Short calendar = **+gamma / –vega** (wants a big
  move and/or falling IV).
- **Expiration / move behavior:** value is maximized when **both** options stay ATM (max time
  value). A large move *either way* pushes the near option deep ITM/OTM **and eventually the
  long-term one too**, so the spread **collapses toward 0** on a big move (Fig 11-20 ex: spread
  worth 1.34 at 100, but 0.09 at 80 and 0.27 at 120). So a long calendar has a tent-like peaked
  payoff around the strike, **negative gamma.**
- **Why "still market + rising IV" actually happens:** pending known-date news (e.g. CEO statement
  in a week) keeps the stock quiet *now* while pumping IV → calendars widen. If the news turns out
  irrelevant, IV collapses → calendars narrow. **This is the canonical calendar trade: own the
  event via a calendar.**
- **Futures wrinkle (matters for futures options):** in **stock** options every expiry shares ONE
  underlying (GE options → GE stock), so no inter-month basis risk. In **futures** options
  different expiries can have **different underlying futures** (a Mar/Jun calendar = Mar future vs
  Jun future), which can move independently (esp. commodities, supply/demand). To isolate pure
  vol exposure, **hedge the calendar with an offsetting futures spread**: buy 10 Jun calls (+500δ)/
  sell 10 Mar calls (–500δ) → buy 5 Mar futures / sell 5 Jun futures to flatten each month's delta.

### 8. Time Butterfly (time fly)
- **Construction:** same strike, **same type (all calls or all puts), THREE different expiries**,
  with ~equal time spacing between them. Outer expiries = wings, inner expiry = body, ratio
  **1 × 2 × 1.** Ex: +1 May-100c / –2 Jun-100c / +1 Jul-100c. (Contrast: a *traditional* butterfly
  varies the **strike**; a time butterfly varies the **expiry**.)
- **Decomposition:** a time fly = simultaneously **buying one calendar spread and selling another**
  that share a common month. The May/Jun/Jul-100c fly = (sell May/Jun calendar) + (buy Jun/Jul
  calendar). **Long time butterfly = buy the body / sell the wings** → because the *short-term*
  calendar is worth *more* than the long-term one, buying-body/selling-wings nets a **DEBIT**
  (= "long"). **This sign flips vs a strike butterfly:** in a strike fly, buy-wings/sell-body = debit;
  in a time fly, buy-**wings**/sell-body = **credit**. Easy to get backwards — note it.
- **Greeks / view (long time fly): –gamma / +theta / +vega** → "characteristics similar to a long
  CALENDAR spread." Value collapses as underlying moves away from the strike (–gamma ⟹ +theta), and
  falls as IV declines (+vega). So like the calendar, it **wants the underlying near the strike but
  wants IV up** — the same realized-vs-implied tension.
  - ⚠️ **(verify / caveat from footnote 7:** the long-time-fly = debit claim assumes **equal IV
    across all three expiries.** If the IV term-structure differs across months, a long time
    butterfly can actually be a **credit**.)**

---

### 9. Diagonal Spread — ⚠️ NOT IN THIS BATCH FILE (inferred / standard)
> **The source file is cut off before diagonals are taught** (it ends at the *"Effect of Changing
> Interest Rates and Dividends"* header). The following is standard Natenberg/textbook treatment,
> **not extracted from this file** — re-verify against the next batch when it's available.
- **Construction:** like a calendar but the two legs have **BOTH different expiries AND different
  strikes** (same type). Effectively "a calendar spread tilted on the strike axis" — the diagonal
  on the option grid (rows = strikes, columns = expiries). Long diagonal usually = buy the
  longer-dated option, sell the shorter-dated, at a different strike.
- **Greeks / view:** inherits the calendar's **+vega / +theta / –gamma** (when long the back month)
  **plus** a directional/delta tilt from the strike offset — so it's a calendar with a built-in
  bullish or bearish lean. Net delta is non-zero unless deliberately balanced.
- **Use:** express "quiet-then-event" *and* a directional bias at once; or roll a covered-call-style
  position out and up/down in time.
- **(verify: full construction, P&L shape, max profit/loss, and Natenberg's adjustment notes — all
  pending the later batch that actually contains the diagonal-spread, choosing-strategy,
  adjustments, and order-submission sections.)**

---

### Effect of Changing Interest Rates & Dividends — ⚠️ CUT OFF
- The file ends at this header with only the teaser: *"What about changes in interest rates and, in
  the case of stocks, dividends?"* **No content follows.** Flag for the next batch. (Standard
  expectation: rho exposure mainly bites long-dated and deep-ITM legs; calendars/diagonals carry
  net rho because the two expiries discount differently; stock dividends shift put/call parity and
  thus the relative value of call-vs-put versions of the same structure and early-exercise risk on
  American calls — but **none of this is sourced from this file**.)

---

## Paper-quant context — options-approval / multi-leg notes (Alpaca paper account)

*Mapping these structures to broker approval tiers — relevant before we ever wire any of this into a
runner. Alpaca paper supports multi-leg options; approval levels still gate what's submittable.*

- **Defined-risk, multi-leg, NO naked short:** long butterfly, short butterfly, long condor, short
  condor, long calendar, long diagonal, long straddle, long strangle, long Christmas tree (the
  "buy-more" ratio). These are typically the **highest tier reachable on a paper/retail account**
  that still has capped risk. **Butterflies & condors are fully defined-risk** → safest to model.
- **Naked / undefined-risk short legs (need the top options-approval level + margin):**
  **short straddle, short strangle** (unlimited double-tail), **ratio frontspreads** (sell more than
  buy → naked extra shorts), **short calendar** as a strategy line, and any **long Christmas tree**
  (1 bought / 2 sold leaves a naked short option). On a real account these require Level 4 /
  "naked/uncovered" approval; on Alpaca **paper** they're simulatable but should be flagged as
  **not deployable to a live account without explicit per-request Cyrus approval** (live-money rule).
- **All multi-leg structures require multi-leg options entitlement** on the account; single-leg-only
  approval can't submit them. For a paper fill model: prefer **packaged multi-leg orders** (tighter
  effective spread, no legging risk) over legging — per Ch10's execution lesson.
- **Practical quant default:** start any volatility-spread experiment with **defined-risk wingspreads
  (butterfly/condor) or long calendars** — capped loss, no margin-call tail, cleanest to backtest
  and to reason about under an imperfect vol estimate.

---

## Ch11 — what a quant should remember
- **Every volatility spread reduces to a point in (gamma, theta, vega) sign-space.** Memorize the
  two clusters: **long-premium = +γ/–θ/+vega** (straddle, strangle, short fly, short condor, short
  Christmas tree, buy-more ratio); **short-premium = –γ/+θ/–vega** (their mirrors). Everything else
  is just *where* the payoff is capped and *which* direction it leans.
- **Capped-risk structures (fly, condor) let you run far bigger size for the same risk** as the
  open-ended ones (straddle, strangle). **Size ≠ risk** — risk is a property of the *structure*.
- **Calendars & time flies break the symmetry:** they are **–gamma but +vega** — they want the
  underlying *still* yet want *implied* vol *up*. This is the canonical "own the known-date event"
  trade (quiet spot + rising IV → calendar widens). The opposite (realized vol up / IV down)
  collapses them. **Always separate realized-vol exposure (gamma) from implied-vol exposure (vega) —
  the calendar is the structure where they diverge.**
- **Wingspreads are bounded: 0 ≤ value ≤ strike-spacing** (fly) or **≤ inner/outer spacing**
  (condor). That bound *is* your max profit/loss arithmetic and makes them ideal defined-risk
  backtest candidates.
- **European call-fly = put-fly (and call-condor = put-condor); NOT guaranteed for American** — an
  early-exercise-aware engine must price the call and put versions separately.
- **Futures-options calendars carry inter-month basis risk** (different underlying futures per
  expiry) — neutralize with an offsetting futures spread if you want pure vol exposure. Irrelevant
  for single-underlying equity options.
- **Delta-neutral buy-more ratio spreads should price as a credit** under a standard model — a quick
  sanity check on any ratio you build.

---

## Batch 3A — top lessons
1. **A spread profits from legs changing at *different rates*, not from either leg's direction.**
   If both legs moved identically the spread value would be constant.
2. **In options, mispricing is a volatility statement, not a dollar statement.** Compare candidate
   trades in **implied vol**, never in premium dollars — the cheaper-looking option can be the
   richer one in vol terms.
3. **Spreading keeps the edge but kills the variance** (roulette analogy: same 5% house edge,
   dramatically lower ruin risk when bets are spread). The point of spreading is to *survive long
   enough* for probabilities to pay.
4. **Size to survive an input error, not to maximize theoretical edge.** A vol estimate off by 10
   points can flip a scaled-up "profit" into an equal loss. Spreading buys margin-for-error, and
   that margin is what actually permits size.
5. **Collapse every structure to (gamma, theta, vega) signs.** Long-premium family wants
   movement + rising IV (+γ/–θ/+vega); short-premium family wants stillness + falling IV
   (–γ/+θ/–vega). Payoff cap and directional lean are the only other variables.
6. **Defined-risk wingspreads (butterfly 1×2×1, condor 1×1×1×1) are the quant's friend:** bounded
   0-to-spacing value, capped loss, big-size-with-small-risk, clean to backtest, no naked tail.
7. **Calendars/time-flies are the exception that separates realized vol from implied vol** —
   –gamma but +vega. Use them to be long IV / long an event while staying neutral on spot. Big
   realized moves or an IV crush destroy them.
8. **Execution: package multi-leg orders (tighter than summed bid-asks, no legging risk); if you
   must leg, do the illiquid leg first.** For a paper fill model, a packaged spread should fill
   *inside* the sum of leg spreads.
9. **Approval mapping:** flies/condors/long-calendars/long-diagonals = defined-risk, top retail
   tier OK; short straddles/strangles, frontspreads (sell-more ratios), and long Christmas trees
   carry **naked** legs → top approval + margin, and on Alpaca **paper** they're simulatable but
   **never live-deployable without explicit per-request Cyrus sign-off.**
10. **⚠️ Coverage gap:** this batch file is **truncated mid-ch11** — diagonal spreads, "choosing an
    appropriate strategy," "making adjustments," "submitting a spread order," and the interest-rate/
    dividend effects are **NOT in this file**. Diagonal notes above are inferred/standard and marked
    `(verify)`; pick these up from the next batch.
