# Natenberg — Batch 3B: Bull/Bear Spreads · Risk Considerations · Synthetics

> **Source-coverage note (read first).** The supplied batch file
> `batches/03b_verticals_synthetics.txt` (2,850 lines, pp. ~193–247) actually contains:
> tail of **Ch11** (calendar/diagonal spreads + volatility-spread summary tables), all of
> **Ch12 Bull & Bear Spreads** (incl. Vertical Spreads), and **Ch13 Risk Considerations**
> through the start of *Adjustments* (ends mid-sentence at "Which method is best?", p.247).
> **Ch14 Synthetics is NOT in this file** — it cuts off before that chapter. Grep for
> `synthet|conversion|reversal|iron|parity` over the whole file → **zero hits**.
> So the Synthetics section below is reconstructed from canonical Natenberg / put-call-parity
> theory and is **explicitly flagged `[NOT IN BATCH FILE]`**. The parity algebra is standard and
> correct, but it was not verifiable against this file's text. If a faithful Ch14 extract is needed,
> re-batch the source PDF — this file does not contain it. Everything in §1–§2 below IS verified
> against the file text; §3 is reconstructed.

---

## §1 — Vertical Spreads (bull/bear call & put spreads) — Ch12 *(verified)*

### 1.1 What a vertical spread is
- A **simple call or put spread**: buy one option, sell one option, **same type** (both calls OR
  both puts), **same expiration**, differing **only by exercise price**. Also called a **credit /
  debit spread** or **vertical spread** (name origin: exchange display boards once listed exercise
  prices *vertically*).
- The whole point vs. ratio/butterfly/calendar directional plays: a vertical is **directionally
  robust**. "Two options with different exercise prices but otherwise identical cannot have
  identical deltas," so the spread's delta sign **cannot invert** — if it starts bullish it stays
  bullish under all market conditions; if bearish, stays bearish. (Ratio/butterfly/calendar
  directional positions CAN flip sign as price/vol/time move — that's the contrast Ch12 builds.)

### 1.2 The master construction rule (Natenberg states it as an italicized law)
> **Buy the lower exercise price + sell the higher exercise price → BULLISH.
> Buy the higher exercise price + sell the lower exercise price → BEARISH.**
> *This is true regardless of whether the spread is made of calls or puts.* (Counterintuitive:
> people expect put spreads to behave oppositely to call spreads — they don't, on the
> direction axis.)

So the four flavors (file's exact examples, June 100/105):

| Strategy | Legs | Debit/Credit | Delta |
|---|---|---|---|
| **Bull call spread** | Buy June 100 call, Sell June 105 call | **Debit** (100c costs more) | + |
| **Bull put spread**  | Buy June 100 put,  Sell June 105 put  | **Credit** (105p costs more) | + |
| **Bear call spread** | Sell June 100 call, Buy June 105 call | **Credit** | − |
| **Bear put spread**  | Sell June 100 put,  Buy June 105 put  | **Debit**  | − |

- Bull **call** = debit; bull **put** = **credit**. Bear **call** = credit; bear **put** = debit.
  (Buying the lower strike is bullish either way; whether that nets debit or credit just depends on
  whether the lower strike is the more- or less-expensive option, which flips between calls and puts.)
- **Why both bull variants are bullish — two proofs the file gives:**
  1. *Delta:* 100c has greater +delta than 105c; 105p has greater −delta than 100p → sum is +delta either way.
  2. *P&L:* both spreads want underlying **above 105** at expiry (call spread expands to its max 5.00;
     put spread's short 105p you sold decays to make you keep the credit). Both want the rise ⇒ both bullish.

### 1.3 Payoff arithmetic (expiration)
- At expiration a vertical is worth between **0** (both legs OTM) and the **distance between strikes**
  (both legs ITM). 100/105 spread → trades 0–5.00; 95/105 spread → 0–10.00.
- **Bull call spread (debit D, strikes K_lo/K_hi):**
  - Max profit = `(K_hi − K_lo) − D`, reached at/above K_hi.
  - Max loss = `D` (the debit paid), at/below K_lo.
  - Breakeven = `K_lo + D`.
- **Bear put spread (debit D):** max profit `(K_hi − K_lo) − D` reached at/below K_lo;
  max loss `D` at/above K_hi; breakeven `K_hi − D`.
- **Credit verticals (bull put / bear call, credit C):** max profit = `C` (kept if it expires worthless),
  max loss = `(K_hi − K_lo) − C`, breakeven sits one credit inside the short strike. *Credit and debit
  versions across the same strikes/expiry are economically the same spread — they only differ by which
  legs you label long/short and by carry; max-profit + max-loss always sum to the strike width.*
- **Wider strikes ⇒ more directional + bigger max P&L.** "The greater the amount between exercise prices,
  the greater the delta of the spread": 95/110 bull > 95/105 bull > 95/100 bull. (Caveat: fails for very
  deep-ITM or very far-OTM spreads, where both deltas crowd 100 or 0 and widening barely moves total delta.)

### 1.4 THE key trade-selection rule (Natenberg's headline takeaway for verticals)
Given two same-direction verticals with the **same delta** (e.g. 95/100 vs 100/105 bull call, both Δ=20),
which to pick? Decided by **implied vol vs your estimate**, via the ATM option:

> **If implied vol is LOW → focus on BUYING the at-the-money option.
> If implied vol is HIGH → focus on SELLING the at-the-money option.**

Mechanism: among ITM/ATM/OTM options identical but for strike, the **ATM option is the most sensitive
in total points to a vol change** (Ch6 result). So if everything's underpriced (impl. vol low), the ATM
is the *most* underpriced → buy it → you're then forced to sell the OTM to make a bull spread (⇒ pick the
**100/105**, the higher/OTM-anchored spread). If everything's overpriced (impl. vol high), ATM is *most*
overpriced → sell it → forced to buy the ITM (⇒ pick **95/100**, the ITM-anchored spread). Same logic for
puts. Refinement: it's really the **at-the-FORWARD** option (esp. stock options w/ high rates + long
d>maturity, where the ATF strike sits well above spot), but "ATM" is a fine practical proxy.

Corollary the file makes explicit:
- The **ITM-anchored** spread (95/100) is **always priced higher** than the OTM-anchored (100/105) at the
  same strikes/width, because it profits in *more* scenarios — it wins if the market merely **doesn't fall**
  (positive theta / negative gamma). The **OTM-anchored** spread (100/105) **needs the market to move up**
  (positive gamma / negative theta) but pays more when right and loses less when wrong *if* movement happens.
  → Estimate vol **> implied** (expect movement) ⇒ prefer the OTM/100-105 spread; estimate **< implied**
  (expect stagnation) ⇒ prefer the ITM/95-100 spread.

### 1.5 Greek profile of a (bull) vertical — Figs 12-8..12-13
- **Delta:** always same sign, never inverts; peaks between the strikes.
- **Gamma / Vega / Theta:** these are **NOT single-signed across spot** — they change sign depending on
  where spot is relative to the two strikes. Max |gamma|, |vega|, |theta| occur when spot is **just below
  the lower strike or just above the higher strike** (i.e., near the "kinks"), not at the dead center.
- A bull call spread bought as a **debit** is long the cheaper-movement structure: net it behaves like a
  capped long-premium directional bet near/below the strikes and a capped short-premium one above.
- **Why prefer a vertical to an outright underlying position?** *Limited risk.* 500 long deltas via 25
  bull spreads (Δ20 each) has **capped** downside vs. 5 long underlying contracts with **open-ended** risk.
  Reward is also capped — but you can be **right without being right on direction**: a correctly-vol-priced
  bull spread can profit even if the market fails to rise (sometimes even if it falls slightly). Outrights
  only pay if you nail direction.

### 1.6 Ch12 — what a quant should remember
- Vertical spread = the *clean directional primitive*: sign-stable delta, bounded P&L, simple BE math.
  For a paper-quant directional signal, prefer verticals over naked options (margin-for-error) and over
  ratio/fly/calendar directionals (which can flip delta sign on you — a silent regime risk).
- **Encode the ATM/forward rule as a vol-aware strike selector:** when `IV < σ_forecast`, buy the
  ATF-nearest option (build the OTM-anchored vertical); when `IV > σ_forecast`, sell the ATF-nearest
  (build the ITM-anchored vertical). This maximizes theoretical edge *for free* given a chosen delta.
- Two equal-delta verticals are **not** equal-edge: edge ranking flips with IV. Always compare
  `theoretical value − market price` (= edge), never just price or delta.
- Width is your directional gain knob (P&L max = strike width; delta scales with width) — until deep
  ITM/far OTM, where it saturates.
- Credit vs debit framing is cosmetic: same strikes/expiry ⇒ `max_profit + max_loss = strike_width`;
  carry/early-exercise aside, choose the leg labeling that's cheapest to execute / best for margin.

---

## §2 — Risk Considerations — Ch13 *(verified, through p.247)*

### 2.1 The five risks (Natenberg's taxonomy)
- **Delta (directional):** market goes one way vs another. Delta-neutral removes *initial* bias but not
  all directional risk (only within a limited range).
- **Gamma (curvature):** risk of a **large move, either direction**. *Positive gamma has no "gamma risk"*
  (a move helps it); **negative gamma** is the danger — a big move bleeds theoretical edge fast.
- **Theta (time decay):** the mirror of gamma. **+gamma ⇒ −theta** and **−gamma ⇒ +theta**, always paired.
  A −theta trader must ask: how long can pass before the edge evaporates?
- **Vega (volatility):** risk the vol input is wrong (⇒ wrong probability distribution) AND/OR that implied
  vol shifts. Every nonzero-vega position carries it. Ask: how far can vol move against me before the
  profit's gone?
- **Rho (interest-rate):** +rho helped by rising rates, −rho hurt. **Usually the least important** input /
  risk measure (except special situations).
- **Any spread with nonzero gamma OR vega has volatility risk.**

### 2.2 Theoretical edge is necessary but NOT sufficient
- **Edge** = average profit *if your view is right*. But you can inflate edge arbitrarily just by trading
  **bigger size** (5× the size = 5× the edge). So edge alone can't rank strategies. The discipline Ch13
  teaches: **normalize all candidate spreads to roughly equal theoretical edge, then compare their RISK.**
- Worked example (May options, all overpriced ⇒ want −vega): three ~equal-edge spreads —
  **Spread 1** short straddle (4:3), **Spread 2** call ratio spread (sell more than buy),
  **Spread 3** long put butterfly. Sized to ~+6.0 edge each, then judged on the risk graphs.

### 2.3 How vol risk dominates — the lessons from the risk graphs (Figs 13-4, 13-5)
- **Price-move graph (13-4):** short straddle = **unlimited loss both ways**; ratio spread = unlimited
  **upside** risk but flattens (small profit) on the downside; long butterfly = **limited both ways**.
- **Vol graph (13-5)** & the concept of **breakeven (implied) volatility** — the vol at which the position
  shows zero P&L. Approx BEs: straddle ~21%, ratio ~23%, butterfly ~21.5%. *Naively the ratio looks safest
  (highest BE vol).* BUT push vol higher (30–40%) and the ratio bleeds **as fast as the straddle**, while
  the butterfly **flattens** (limited loss). → **first-order risk metrics (gamma, vega at current spot/vol)
  mislead for large moves; you must look at the whole curve, because the Greeks themselves change as
  conditions change.**
- **Volga (vega-of-vol, dVega/dVol) is the deciding 2nd-order term here:**
  - Straddle: **volga ≈ 0** → vega ~constant (ATM vega is flat in vol).
  - Ratio spread: **negative volga** → as vol rises, vega gets *more* negative (loss accelerates); as vol
    falls, vega gets *less* negative (profit decelerates). Vol changes work **against** it both ways.
  - Long butterfly: **positive volga** → vol changes work **for** it (loss decelerates as vol rises, profit
    accelerates as vol falls). ⇒ on the **implied-vol-shock** axis the butterfly is best despite a worse
    headline BE vol. ITM/OTM-wing options gain vega as vol rises, which is what creates the positive volga.

### 2.4 Why risk control matters at all (the survival argument)
- "+$7,000 half the time, −$5,000 half the time" → +$1,000 EV. But if your **first** trade loses $5,000 and
  you only had $3,000, you're **out of business** before the EV can show up. Good/bad luck only evens out
  over long horizons, so **no trader should run a strategy where short-term bad luck ends the career.**
  Every trader is his own risk/finance officer; steady cash flow > wild swings.

### 2.5 Practical considerations (execution reality)
- The theoretically-best spread (Spread 3, the butterfly) is a **three-legged** spread → harder to fill,
  wider effective bid-ask, **leg-in risk** if done piecemeal, and **liquidity-capped** (needed 100×200×100
  size to match the edge of the two-legged spreads — may not exist in the book). When the best spread is
  impractical, between a **short straddle** and a **ratio spread** of equal edge, the **ratio spread wins
  cleanly** — bigger margin for error on *both* gamma (price) and vega (vol) risk.
- Hard-won rule new traders miss: **straddles and strangles are the riskiest of all spreads — buy OR sell.**
  Buying isn't "safe because risk is limited": bleeding a little every day as the market sits still hurts
  just as much as one violent move against a short straddle. They offer the **least margin for error**.

### 2.6 How much margin for error?
- **No universal number** — depends on the market's vol behavior and the trader's experience. 5 vol points
  may be huge in one market, nothing in another.
- **Better framing: let margin-for-error set the SIZE.** Same spread at IV 23% vs your 25% forecast
  (2-pt cushion) → trade **small** (e.g. 20×10). Same spread at IV 18% (7-pt cushion, and you think 18% is
  extremely rare) → trade **large** (e.g. 100×50). *Size should scale with how much can go wrong before the
  trade turns against you*, not the other way round.

### 2.7 Dividends & interest (stock-option-specific carry risk)
- When **all options expire together**, rate/dividend risk is **small** — a rate/div change shifts the
  **one** forward price all options share, so straddles/strangles/ratios/butterflies barely move.
- **Calendar spreads are the exposure**, because the two expirations use **two different forward prices**
  that respond unequally (the longer-dated forward is more rate-sensitive). Sign conventions (from Ch11/Ch7,
  reused here):
  - **Calls & puts react oppositely** to rates and to dividends. **Rising rates / falling divs → calls up,
    puts down. Falling rates / rising divs → calls down, puts up.** Effect is larger on the long-dated leg.
  - Long **call calendar** (stock): **+rho**, **negative dividend sensitivity** (value falls as divs rise).
  - Long **put calendar** (stock): **−rho**, **positive dividend sensitivity** (value rises as divs rise).
  - A no-dividend stock's call calendar is always worth > 0 (≥ carry on the stock between expiries) —
    *unless* stock can't be borrowed, forcing early exercise of the long leg (the **short-squeeze** trap).
- Measure: total **rho** for rate risk; for dividends there's no Greek but a model can compute a dividend
  sensitivity per option / per spread (Fig 13-14). Generally **small vs gamma/vega risk**, but it matters
  for large positions or when a rate/dividend change is genuinely likely.

### 2.8 "What is a good spread?" + efficiency
- **Definition (the chapter's thesis):** *"A good spread is not necessarily the one that shows the greatest
  profit when things go well; it may be the one that shows the LEAST loss when things go badly."* Winning
  trades take care of themselves; **the losing trades that don't give back all your winners are what keep
  you in business.** A spread that passed *every* risk test would have so little edge it's not worth doing —
  the goal is a **reasonable margin for error**, not zero risk.
- **Efficiency = |gamma / theta|**, a quick risk-reward ratio when **all options expire together** (so
  gamma & theta are the dominant risks):
  - **+gamma / −theta** position: want |gamma/theta| **large** (much potential move-profit per unit of
    time-decay risk).
  - **−gamma / +theta** position: want |gamma/theta| **small** (little move-risk per unit of decay-reward).
  - Worked: Spread1 959, Spread2 1212, Spread3 925 → for these (−gamma/+theta) we want it small ⇒ **Spread3
    best**, consistent with the full risk analysis. **Caveat:** efficiency ignores **vega**, so it's only
    valid single-expiry; multi-expiry (calendar/diagonal) spreads need full vega analysis too.

### 2.9 Adjustments (chapter cuts off here, p.247)
- Deciding **how** to adjust matters as much as **when** (Ch11 covered "when"). An adjustment that cuts
  delta risk can **silently add** gamma/theta/vega risk — trading one risk for another.
- **Adjusting with the UNDERLYING is risk-neutral:** the underlying has gamma = theta = vega = 0, so
  buying/selling underlying changes **only delta**, leaving every other Greek untouched. **Adjusting with
  options changes all the Greeks at once** (every option carries gamma/theta/vega too) — a thing new traders
  forget. *(File ends mid-example: short 95/105 strangle drifts to +280 delta; the three rebalance choices —
  sell underlying / sell calls / buy puts — are posed but the comparison is cut off by the batch boundary.)*

### 2.10 Ch13 — what a quant should remember
- **Backtest/optimizer discipline:** never rank strategies by raw edge or P&L — **edge scales with size.**
  Hold edge (or capital-at-risk) roughly constant, then compare **risk curves over the full domain** of
  price and vol, not point Greeks. The "best at current spot/vol" can be the worst after a big move.
- **Model second-order vol risk (volga):** two positions with the same vega can diverge wildly under a vol
  shock. Negative-volga structures (ratio spreads, short strangles in a sense) accelerate losses as vol
  rises; positive-volga structures (long butterflies/condors, long wings) self-cap. For a paper book that
  may face vol regime shifts, prefer **positive-volga** tail protection.
- **Define breakeven implied volatility** for every vol position as a first-class risk number — the IV at
  which P&L = 0 — and stress beyond it (don't assume vol "stops" at the nearby BE).
- **Position sizing IS the risk control:** size ∝ margin-for-error. A thin-cushion edge ⇒ small size; a
  fat-cushion rare-vol edge ⇒ large size. Encode a `size = f(cushion)` map rather than a fixed lot.
- **Survival / ruin constraint dominates EV:** a positive-EV strategy that can blow the account on an early
  drawdown is unacceptable. Cap per-trade and aggregate loss so bad luck can't end the program.
- **Execution frictions are real costs:** 3-legged spreads (flies/condors) cost more in bid-ask + leg-in
  risk + liquidity caps than 2-legged ones — fold transaction cost and fill feasibility into selection, not
  just theory.
- **Efficiency = |gamma/theta|** is a fast single-expiry screen; add vega/volga whenever expiries differ.
- **Rebalance with the underlying when you only want to fix delta** (Greek-neutral hedge); use options only
  when you intend to reshape gamma/vega too.
- **Rule of thumb to hardcode:** straddles/strangles are the lowest-margin-for-error structures — flag them
  as high-risk regardless of long/short.

---

## §3 — Synthetics (Ch14) — `[NOT IN BATCH FILE — reconstructed from put-call parity theory]`

> ⚠️ **This entire section is NOT present in `03b_verticals_synthetics.txt`** (file ends at Ch13 p.247).
> The relationships below are **standard put-call parity / synthetics** and are algebraically correct, but
> they could **not** be verified against this batch's text. Re-batch the source if a faithful Ch14 extract
> is required. I'm including this so the note covers the brief's intended scope, clearly fenced.

### 3.1 Put-call parity — the one identity everything derives from
For **European** options, same strike **K** and expiry **T**, underlying forward price **F** (= S grown at
carry; for a stock S·e^{rT} minus dividends, for a future just F), discount factor for premium settlement:

```
C − P  =  PV( F − K )        (European, same K & T)
```

i.e. **(long call + short put) at the same strike/expiry ≡ a long forward struck at K**, whose value is the
discounted (F − K). Equivalently, the classic stock form:

```
C − P  =  S − K·e^{−rT}   (+ adjustments for dividends)   ⇒   C + K·e^{−rT}  =  P + S
```

Everything below is just this identity re-arranged. **(verify against source PDF: exact discounting/
dividend convention Natenberg uses — he typically frames it via the forward price F so carry is baked in.)**

### 3.2 Synthetic underlying
- **Synthetic LONG underlying = long call + short put**, *same strike, same expiry.*
  - Δ ≈ +100 (call Δ + |put Δ| at a shared strike sum to ~100). Gamma/vega/theta ≈ 0 (they cancel) →
    it behaves like the underlying, not like an option.
- **Synthetic SHORT underlying = short call + long put**, same strike/expiry. Δ ≈ −100.
- Intuition: at expiry, `long call − short put` (same K) pays `S_T − K` for **all** S_T (above K the call
  pays S_T−K; below K the short put costs K−S_T, i.e. −(K−S_T) = S_T−K) → a straight-line forward payoff.

### 3.3 Synthetic individual options (rearrangements of 3.1)
- **Synthetic long call  = long underlying + long put** (same K/T). *(a "married put"/protective put has the
  payoff shape of a long call.)*
- **Synthetic short call = short underlying + short put.**
- **Synthetic long put   = short underlying + long call.**
- **Synthetic short put  = long underlying + short call** *(= a covered call has the payoff of a short put).*
- Each real option and its synthetic twin have **matching deltas and matching expiration payoffs**; any price
  gap between them is an arbitrage (subject to carry/borrow/early-exercise frictions).

### 3.4 Conversion & Reversal (locking the parity arbitrage)
These are the **three-legged arbitrage packages** that monetize a violation of 3.1. All same strike & expiry:
- **Conversion = long underlying + short call + long put** (i.e., **long underlying + synthetic short
  underlying**). Net ≈ delta-0, gamma/vega/theta-0. You're **short the synthetic** against **long the real**
  underlying. Profits when the call is **rich** relative to the put (synthetic underlying trades **above**
  the real one). Locked P&L ≈ `(C − P) − (F − K)` discounted — a fixed number set at trade time, driven by
  carry (rates/dividends/borrow).
- **Reversal (reverse conversion) = short underlying + long call + short put** (**short real underlying +
  synthetic long underlying**). The mirror: profits when the put is **rich** / synthetic trades **below** the
  real underlying.
- Because both are carry trades, their value hinges on **interest rates, dividends, and stock-borrow** — the
  same inputs §2.7 flagged. A reversal needs to **borrow/short the stock**; if it can't be borrowed, the
  arbitrage breaks (the short-squeeze risk again).

### 3.5 Iron butterfly & iron condor (and why they equal their non-iron twins)
An **"iron"** spread is a butterfly/condor built from **BOTH calls and puts** (a short/long straddle or
strangle financed by a wider strangle), rather than all-calls or all-puts. The common **(long) iron** =
the **credit** structure (you *receive* premium, want price to sit at the body):

- **(Long) Iron Butterfly** = **short ATM straddle + long protective strangle**
  e.g. *sell 100 call, sell 100 put, buy 105 call, buy 95 put.* Credit received; max profit if it pins the
  100 body; risk capped by the wings. Δ≈0, **−gamma / +theta / −vega** (short-premium).
- **(Long) Iron Condor** = **short strangle + long wider strangle**
  e.g. *sell 100 call, sell 95 put, buy 105 call, buy 90 put.* Credit; profits in the body **range** between
  the short strikes; capped risk. Same short-premium Greek signature.
- **Why an iron fly/condor ≡ the ordinary (all-call or all-put) fly/condor at the same strikes:** apply
  put-call parity strike-by-strike. Swapping a call for the synthetic-equivalent put (or vice-versa) at any
  strike only shifts the package by a **fixed conversion/reversal amount** (a carry constant). So an iron
  butterfly and a plain butterfly on the same strikes share the **identical expiration payoff diagram** and
  identical Greeks; they differ only by a fixed cash amount (the debit-vs-credit framing), explained by carry.
  Concretely: the all-call long butterfly *(buy 95c, sell 2×100c, buy 105c)* and the iron butterfly
  *(buy 95p, sell 100p, sell 100c, buy 105c)* both want the 100 body, both are −gamma/+theta with capped
  risk both sides, and land on the same payoff up to a constant. **(verify: vendors differ on whether "long
  iron butterfly" denotes the credit body-seeking trade or its debit inverse; confirm Natenberg's sign/label
  convention against the source — but the parity-equivalence claim itself holds regardless of the label.)**

### 3.6 Ch14 — what a quant should remember
- **Put-call parity is the master constraint:** `C − P = PV(F − K)` (same K/T, European). Every synthetic,
  conversion, reversal, and iron-vs-plain equivalence is just this identity rearranged — memorize the one
  line and derive the rest.
- **Synthetic long underlying = +call −put (same strike/expiry)**; synthetic short = −call +put. Synthetic
  options: long call = +underlying +put; long put = −underlying +call; short put = +underlying −call
  (covered call); short call = −underlying −put.
- **Conversion (+stock −call +put) and reversal (−stock +call −put)** are delta-0, carry-driven arbitrage
  packages — their P&L is fixed at inception and set by **rates, dividends, and borrow**, not by spot
  movement. Treat any persistent gap between an option and its synthetic as a pricing/borrow signal, net of
  carry and early-exercise (American options break clean parity → parity becomes an inequality band).
- **Iron fly/condor ≡ plain fly/condor** on the same strikes, up to a fixed carry constant — so a backtester
  should **dedupe** them (don't treat iron and non-iron as independent strategies) and pick whichever has the
  **better fills / margin / assignment profile**, since the risk is identical.
- For execution: building a position **synthetically** (or hedging with the synthetic) is a tool to capture
  better bid-ask, manage borrow, or sidestep an illiquid leg — same risk, different microstructure cost.

---

## Batch 3B — top lessons (cross-chapter, for the paper-quant)

1. **Vertical spreads are the clean directional building block.** Sign-stable delta (never inverts), bounded
   P&L (`max_profit + max_loss = strike_width`), trivial breakevens. Prefer them over naked options (margin
   for error) and over ratio/butterfly/calendar "directional" plays whose delta sign can silently flip with
   price/vol/time.
2. **The ATM/at-the-forward vol rule is free edge:** IV **low → buy** the at-the-forward option (⇒ build the
   OTM-anchored vertical); IV **high → sell** it (⇒ ITM-anchored vertical). The ATF option is the most
   vol-sensitive in total points, so this maximizes theoretical edge for a chosen delta. Equal-delta
   verticals are **not** equal-edge — the ranking flips with IV.
3. **Theoretical edge is necessary but never sufficient** — edge scales linearly with size, so you can fake
   any edge. **Normalize edge, then compare full risk curves** over the whole price×vol domain. Point Greeks
   at current spot/vol mislead for large moves because the Greeks themselves move.
4. **Model second-order vol risk (volga).** Same-vega positions diverge under a vol shock: negative-volga
   (ratio spreads, short strangles) **accelerate** losses as vol rises; positive-volga (long
   butterflies/condors, long wings) **self-cap**. Define a **breakeven implied vol** for every vol position
   and stress *beyond* it.
5. **Survival > EV. Size ∝ margin-for-error.** Thin cushion ⇒ small size; rare fat-cushion edge ⇒ large size.
   A positive-EV strategy that can blow the account on an early drawdown is disqualified. "A good spread
   shows the **least loss when things go badly**," not the most profit when things go well.
6. **Carry risk lives in calendars / synthetics, not single-expiry spreads.** Same-expiry positions share one
   forward, so rate/dividend moves nearly cancel. Calendars use two forwards (long leg more rate-sensitive):
   long **call** calendar = +rho/−div-sensitivity; long **put** calendar = −rho/+div-sensitivity. Borrow can
   force early exercise (short-squeeze).
7. **Put-call parity unifies it all:** `C − P = PV(F − K)`. Synthetics, conversions/reversals, and the
   iron-vs-plain butterfly/condor equivalence are one identity rearranged. **Dedupe iron and non-iron**
   structures in any strategy search — identical risk, choose on fills/margin/assignment. *(Synthetics block
   reconstructed — not in this batch file; verify labels/discounting against the source PDF.)*
8. **Rebalance with the underlying for a pure delta fix** (Greek-neutral: underlying has 0 gamma/theta/vega);
   use options only when you deliberately want to reshape gamma/vega. **Efficiency = |gamma/theta|** is a fast
   single-expiry risk-reward screen; add vega/volga whenever expiries differ.
9. **Straddles & strangles are the lowest-margin-for-error structures — long OR short.** Flag them high-risk
   on principle; bleeding daily on a long straddle that never moves hurts as much as a violent move against a
   short one.