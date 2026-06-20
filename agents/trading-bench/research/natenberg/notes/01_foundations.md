# Natenberg (2nd ed.) — Batch 1: FOUNDATIONS

**Source file:** `research/natenberg/batches/01_foundations.txt` (2907 lines, read end-to-end).
**Intended scope (per task):** Chapters 1–5.

> ⚠️ **EXTRACTION GAP — READ THIS FIRST.** The batch text file actually ends at the **end of Chapter 4 (page 51, "Expiration Profit and Loss")**. The lines that mention Chapter 5 ("Theoretical Pricing Models," "The Importance of Probability," "A Simple Approach," "The Black-Scholes Model") appear **only in the Table of Contents at the top of the file**, not as body text. **Chapter 5's actual content (pp. 52–68) is NOT in this batch file.** I have therefore fully covered Ch 1–4 below, and included a Ch 5 *placeholder* reconstructed from the TOC + the Preface's framing + standard Natenberg structure, clearly flagged as "(verify: not in extracted text)". If Ch 5 matters, re-extract it — most of its real machinery (volatility as a standard deviation, scaling vol for time, lognormal, the 5 inputs in depth) is developed in Ch 5–6 and should land in **Batch 2**.

---

## Chapter 1 — Financial Contracts

### Core concepts & precise definitions
- **Spot / cash transaction:** both parties agree on terms, then *immediately* exchange money for goods. Stock trading is treated as cash (despite a short T+settlement lag).
- **Forward contract:** terms agreed *now*, but the actual exchange of money-for-goods happens at a later **maturity / expiration date**. Because payment and delivery are deferred, the forward price generally differs from spot (interest, carry costs/benefits get priced in).
- **Futures contract:** a forward contract traded on an *organized exchange* with **standardized** specs (quantity, quality, delivery date/place, payment method). The exchange **guarantees contract integrity** (covers default).
- **Option contract:** gives **one party (the buyer) the right to make a decision later**; all *rights* lie with the buyer, all *obligations* with the seller.
  - **Call** = right to **buy** (take a long position) at a fixed price on/before a date.
  - **Put** = right to **sell** (take a short position) at a fixed price on/before a date.
  - **Premium** = the separately-negotiated payment the buyer makes; seller keeps it regardless of the buyer's later decision. (Analogy used throughout: insurance ≈ a put.)
- **Derivative:** a contract whose value is *derived from* an underlying asset (forwards, futures, options). A **swap** is also a derivative (exchange of cash flows; plain-vanilla = fixed-for-floating interest), but the book restricts itself to forwards/futures/options.

### Buying & selling mechanics
- In derivatives you can **sell first, buy later** — order of trades doesn't change the P&L. Profit if you (buy low → sell high) OR (sell high → buy low).
- **Opening trade** → creates an **open position**; **closing trade** reverses it.
- **Open interest** = number of exchange contracts traded but not yet closed. Long count = short count (one seller per buyer).
- **Long** = bought first (debit, you pay). **Short** = sold first (credit, you receive).
- Caution on terminology: with derivatives, "long the option" does NOT necessarily mean "want the underlying to rise." Book distinguishes **long/short contract position** (bought/sold) vs **long/short market position** (want underlying up/down).

### Notional (nominal) value
- **Physical commodity forward:** `notional = units_at_maturity × unit_price`. (1,000 units × $75 = $75,000.)
- **Financial future (no physical delivery, e.g. stock index):** `notional = index_price × point_value`. (825.00 × $200 = $165,000.)
- Exchange sets point value so notional is "reasonable for trading" — too high = too risky/illiquid; too low = transaction costs dominate.

### Settlement procedures (CRITICAL distinction)
- **Stock-type settlement:** full + immediate payment at trade; **all profits/losses are UNREALIZED (paper)** until the position is closed. To realize, you must trade out.
- **Futures-type settlement** (a.k.a. **margin and variation settlement**): no payment up front; instead each party posts an **initial margin** deposit (security against default), then **daily variation** cash is transferred between accounts as the price moves.
  - **Variation credit/debit** = daily cash from price fluctuation while open. `variation = (new_price − old_price) × position × contract_size`.
  - At maturity: final variation payment; margin returned. Worked example (Fig 1-2): a contract bought at 75 that settles at 90 — buyer "pays" 90 at delivery but already *received* 15 in variation along the way ⇒ net effective price = 75 (the agreed price). The two paths reconcile exactly.
- **Margin ≠ Variation.** Margin still *belongs to the trader* and can earn interest. Variation is realized cash that itself earns/loses interest.
- **North American options are ALL settled stock-type** — even options *on futures*. ⚠️ This creates a real **cash-flow trap**: if you hedge a futures position (futures-type, variation = real cash out) with an option (stock-type, gains are paper), a "perfectly hedged" position can still have a surprise variation cash drain. Outside North America, option settlement usually *matches* the underlying's settlement, avoiding this.

### Market integrity / clearing
- On a trade, the buyer–seller link is *broken* and replaced by two links to the **exchange/clearinghouse**: exchange is buyer-to-every-seller and seller-to-every-buyer; it guarantees both payment and delivery.
- Three-tier guarantee: **individual trader → clearing firm → clearinghouse**. Clearing firms collect margin, may net long/short across their traders (reducing deposit), and can demand *more* margin than the clearinghouse. No US clearinghouse has ever failed.
- (Footnote: a professional's equity-options margin requirement is sometimes called a **haircut**.)

### Practical takeaways
- Know the settlement type of *every* leg of a position — the stock-vs-futures settlement mismatch on US futures options is a classic blow-up source even when "net P&L = 0."
- Variation can force an early liquidation if you don't keep enough cash to fund it. Hold cash for margin **and** for adverse variation.

### 🧠 What a quant should remember (Ch 1)
- Forward/futures price ≠ spot; the difference is *carry*, not a market view.
- US options = stock-type settlement always ⇒ option gains are unrealized; budget cash for hedge variation.
- Open interest balance (longs = shorts) is a structural identity, useful sanity check on positioning data.
- Clearing nets positions → margin modeling should account for portfolio netting, not gross legs.

---

## Chapter 2 — Forward Pricing

### The master identity
```
forward price = current cash price + costs of buying now − benefits of buying now
```
This is the spine of the whole chapter; every instrument just plugs in its specific carry costs/benefits.

### Worked example (Jerry's land — the canonical intuition)
Inputs: cash price $100,000; rate 8%/yr; property tax $2,000 due in 9 months; oil revenue $500/month received end-of-month.
- **Costs of buying now:**
  - Interest on price: `8% × 100,000 = 8,000`.
  - Tax + interest on financing the tax for its remaining 3 months: `2,000 + (2,000 × 8% × 3/12) = 2,040`.
  - Total cost = `8,000 + 2,040 = 10,040`.
- **Benefits of buying now:**
  - Oil revenue: `12 × 500 = 6,000`.
  - Interest earned on each month's oil revenue: `(500×8%×11/12)+(500×8%×10/12)+…+(500×8%×1/12) = 220`.
  - Total benefit = `6,220`.
- **Fair 1-yr forward = 100,000 + 10,040 − 6,220 = 103,820.**
- **Basis = cash − forward = 100,000 − 103,820 = −3,820.** Usually negative (carry costs > benefits); turns positive only if benefits (e.g. high oil yield) exceed costs.

### Carry table (costs vs benefits to "buying now")
| Instrument | Costs of buying now | Benefits of buying now |
|---|---|---|
| Physical commodity | interest on price, storage, insurance | **convenience yield** |
| Stock | interest on price | dividends + interest on dividends |
| Bonds/notes | interest on price | coupons + interest on coupons |
| Foreign currency | interest on borrowed **domestic** currency | interest earned on **foreign** currency |

### Formulas by instrument

**Physical commodity** (`C`=commodity price, `t`=time, `r`=rate, `s`=annual storage/unit, `i`=annual insurance/unit):
```
F = C × (1 + r×t) + (s×t) + (i×t)
```
- **Contango / "normal":** long-dated futures > short-dated (carry positive).
- **Backwardation:** cash > futures — looks impossible since carry costs are positive, but a **convenience yield** (value of having the physical *now*, e.g. to keep a factory running) can drive cash above futures.
- Solve for cash given F: `C = [F − (s+i)×t] / (1 + r×t)`.
  - Worked: F=77.40, r=8%, s=3.00, i=0.60, t=3/12 → `C = [77.40 − 3.60×0.25] / 1.02 = 76.50/1.02 = 75.00`. If observed cash = 76.25, implied **convenience yield = 1.25**.

**Stock** (full version, with per-dividend interest):
```
F = S + (S×r×t) − Σ[ dₙ × (1 + rₙ×tₙ) ]
  = [S × (1 + r×t)] − Σ[ dₙ × (1 + rₙ×tₙ) ]
```
where `dᵢ` = each dividend before maturity, `tᵢ` = time from that dividend to maturity, `rᵢ` = forward rate from dividend date to maturity.
- Worked: S=67, t=8/12, r=6%, semiannual div 0.33, next div in 1 month ⇒ t₁=7/12, t₂=1/12, r₁=6.20%, r₂=6.50%:
  `F = 67×(1+0.06×8/12) − 0.33×(1+0.062×7/12) − 0.33×(1+0.065×1/12) = 69.68 − 0.3419 − 0.3318 = 69.0063`.
- **Simplified stock forward** (aggregate dividends `D`, ignore interest on them):
```
F = [S × (1 + r×t)] − D
```
  → `67×(1+0.06×8/12) − 2×0.33 = 69.02`.

**Bonds/notes** (treat coupons like dividends; `B`=bond price, `cᵢ`=coupon):
```
F = B + (B×r×t) − Σ[ cₙ × (1 + rₙ×tₙ) ]
  = [B × (1 + r×t)] − Σ[ cₙ × (1 + rₙ×tₙ) ]
```
- Worked: B=109.76, t=10/12, r=8%, semiannual coupon 5.25, next coupon in 2 months ⇒ t₁=8/12, t₂=2/12, r₁=8.20%, r₂=8.50%:
  `F = 109.76×(1+0.08×10/12) − 5.25×(1+0.082×8/12) − 5.25×(1+0.085×2/12) = 117.0773 − 5.5370 − 5.3244 = 106.2159`.

**Foreign currency** — must keep units consistent. Express spot as `S = C_d / C_f` (domestic units per 1 foreign unit). With domestic rate `r_d`, foreign rate `r_f`:
```
F = [C_d × (1 + r_d×t)] / [C_f × (1 + r_f×t)]
  = S × (1 + r_d×t) / (1 + r_f×t)
```
- Worked: €1 = $1.50 (so S=1.50), r$=6%, r€=4%, 6 months: `F = 1.50 × (1+0.06×0.5)/(1+0.04×0.5) = 1.50×1.03/1.02 = 1.5147`. (This is **covered interest parity**.)

**Forward rate notation** (used in the stock/bond per-dividend discounting):
- `1×5` = a 4-month rate starting in 1 month; `3×9` = a 6-month rate starting in 3 months; `4×12` = an 8-month rate starting in 4 months.
- An **FRA (forward-rate agreement)** locks borrowing/lending for a fixed future period (a `3×9` FRA = borrow 6 months, starting 3 months out).

### Options forward price (key bridge)
- For **both** stock and futures options, the option's value depends on the **forward price of the underlying**.
- **A futures contract IS a forward contract ⇒ the forward price of a future = the futures price itself.** (3-mo future @75 ⇒ 3-mo forward = 75.) This is why futures options need *no extra forward calc* — convenient for modeling.

### Arbitrage
- **Definition used:** buying & selling the same/closely-related instruments in different markets to exploit an apparent mispricing. (Pure "riskless profit" is debatable — something can usually go wrong.)
- **Cash-and-carry arbitrage:** buy cash, sell future, carry to maturity.
  - Worked (stock): S=67, t=8/12, r=6%, D=0.66 ⇒ fair forward 69.02. If forward trades at 69.50, sell forward + buy stock. Cash-flow ledger: `−2.68 (interest) − 67.00 (stock) + 0.66 (div) + 69.50 (forward recv) = +0.48` profit. Stock/futures price moves *don't* change this (both legs locked).
- **Implied values** (invert the forward formula `F = S(1+r×t) − D`):
  - Implied spot: `S = (F + D) / (1 + r×t)`.
  - Implied interest rate: `r = ([(F+D)/S] − 1) / t`.
  - Implied dividend: `D = [S×(1+r×t)] − F`.
  - Worked: F=69.50, D=0.66, S=67, t=8/12 → implied `r = ([(69.50+0.66)/67]−1)/(8/12) = 0.0707 (7.07%)`. Implied `D = 67×(1+0.06×8/12) − 69.50 = 0.18` (≈ two 0.09 payments).
  - **Concept:** if you believe the contract is fairly priced, the implied value = the market's consensus estimate of the unknown input. (This is the same logic that later gives **implied volatility**.)

### Dividends — process & dates
- **Declared date:** company announces amount + pay date; *dividend risk is eliminated* until next one.
- **Record date:** must own stock (officially, i.e. settled) to receive the dividend. US stock settlement = **T+3**.
- **Ex-dividend date (ex-date):** first day trading *without* rights to the dividend = **2 business days before record date**; last day to buy *with* the dividend = 3 business days before record date. On ex-date, quotes drop by the dividend amount; if the stock would otherwise be unchanged it opens *lower by the dividend*.
- **Payable date:** when the dividend is actually paid to record-date holders.
- Estimation: stable payers (US quarterly) → assume continuation of recent amount. Interest-on-dividends is usually ignored *unless* the pay date is near the derivative's maturity, where a small date error can move value meaningfully.

### Short sales
- To short stock you must **borrow** it first. Proceeds are held by the lender as collateral; the lender pays you interest on the proceeds — but only **part** of the full rate. The shorter also **owes** any dividends that accrue.
- **Short-stock rebate** = the (reduced) rate the shorter receives. Hard-to-borrow → low/zero rebate; **short-stock squeeze** if borrow dries up.
- Rate definitions:
  - `r_l` = **long rate** (ordinary borrow/lend), `r_s` = **short rate** (on short-sale proceeds).
  - **Borrowing cost:** `r_l − r_s = r_bc`.
- Effect on arbitrage: shorting the stock to capture a *too-cheap* forward only earns `r_s`, not `r_l`, which lowers the fair forward.
  - Worked: with r=4% (short rate) instead of 6%: `F = 67×(1+0.04×8/12) − 0.66 = 68.13`. If forward trades at 68.75, a *long-stock holder* profits (69.02 − 68.75 = 0.27) but a *short-seller* loses (68.13 − 68.75 = −0.62). ⇒ **No-arbitrage band:** a non-owner can only profit if forward < 68.13 or > 69.02; in between, no arb.
- **Options use the long rate `r_l`** for the cash flow from buying/selling — an option isn't a deliverable security, you never "borrow" it to sell it.

### Practical takeaways
- Every forward price is just spot grown at the cost of carry minus the yield of carry. Memorize `F = S(1+r×t) − (income)` and adapt.
- Real desks face **two rates** (borrow > lend; long > short). No-arbitrage prices become a *band*, not a point — wide enough to swallow naive "free" arb.
- Implied-input thinking (implied r, implied D, and later implied vol) is the single most reusable trick in the book.

### 🧠 What a quant should remember (Ch 2)
- `F = S(1 + r×t) − dividends/coupons (+ storage/insurance for commodities)`; FX uses the *ratio* of growth factors (covered interest parity).
- Futures forward price = the futures price → futures options skip the carry step.
- The forward price, not spot, is the correct "center" for pricing options — this seeds the idea (Ch 6) that **forward = mean of the terminal distribution**.
- Borrow/lend and long/short-rate asymmetries turn single arbitrage prices into no-arb *bands*; build that spread into any fair-value/edge calc.
- Convenience yield is the unobservable plug for commodities — back it out from cash↔futures, analogous to backing out implied vol.

---

## Chapter 3 — Contract Specifications & Option Terminology

### The five identifying attributes of an exchange option
1. **Underlying** — the security/commodity to be bought/sold. Stock options: typically **100 shares** (a *round lot*; <100 = *odd lot*). Futures options: **1 futures contract**, usually the futures month matching the option's expiration. **Serial options** (no matching futures month) → underlying = nearest futures beyond expiration. **Midcurve options** = short-term options on long-dated futures (1-/2-/5-year midcurve).
2. **Expiration date / expiry** — last day to decide. Stock & index options: **3rd Friday** of the month (Thursday if Good Friday lands on it). **Last trading day** is what matters operationally.
   - **AM (a.m.) expiration:** value set from the **opening** price (common for cash-settled stock *index* options — introduced to fix expiration-Friday order-imbalance/price-distortion problems).
   - **PM expiration:** value set from the **closing** price on last trading day (individual stock options).
   - Physical-commodity futures options often expire *days/weeks before* the futures matures (often the prior month: March future → Feb option, etc.).
3. **Exercise / strike price** — price at which the underlying changes hands on exercise. Exchange sets strikes at regular intervals bracketing spot; adds more as price moves; can add intermediate strikes (52½, 57½…).
4. **Type** — call or put.
5. **Exercise style** —
   - **European:** exercisable **only at expiration** (decision on last business day).
   - **American:** exercisable **any business day** before expiration.
   - Geography is irrelevant to the name. Rule of thumb: **options on futures & on individual stocks tend to be American; index options tend to be European.**

### Exercise & assignment
- Buyer **exercises** (submits exercise notice); a seller is **assigned** (chosen essentially **randomly** among open short holders — no one is more/less likely).
- Direction cheat-sheet:
  - Exercise a **call** → you **buy** at strike.
  - Assigned a **call** → you **sell** at strike.
  - Exercise a **put** → you **sell** at strike.
  - Assigned a **put** → you **buy** at strike.
- **Three settlement-into outcomes** when exercised:
  1. **Physical underlying** (stock options always): call → pay `strike × shares`, receive shares; put → receive `strike × shares`, deliver shares. **Cash flow at exercise depends only on the strike**, not on the current stock price (the price/premium drive P&L, not the exercise cash flow).
  2. **Futures position:** become long (call exercise/put assignment) or short (put exercise/call assignment) a future *at the strike*, immediately subject to futures-type margin + variation. Variation credit/debit = `(future_price − strike) × point_value × contracts` with the appropriate sign.
     - e.g. future @85, exercise an 80 call → long 1 future @80, post $3,000 margin, receive `(85−80)×$1,000 = $5,000` variation.
  3. **Cash settlement** (index contracts): no position; account credited/debited `(underlying − strike) × point_value × contracts` (sign per call/put), using end-of-day index value.

### Automatic exercise
- To prevent in-the-money options expiring worthless by oversight, exchanges **auto-exercise** ITM options at expiration above a **threshold** (e.g. 0.05). Below threshold → must file an exercise notice; above threshold but unwanted → file a **"do not exercise"** notice. Thresholds can differ for **retail vs professional** (e.g. 0.05 vs 0.02) due to cost structures.

### Option margining
- **Buyer's risk ≤ premium paid** → margin never exceeds that.
- **Positions with unlimited risk** (e.g. naked short options) → **risk-based** margin over an array of price + speed-of-move scenarios. US systems: **OCC** (stock/index options) and **SPAN** (Standard Portfolio Analysis of Risk, CME — dominant on futures). Both scan a grid of underlying price moves × volatility/speed to set a "reasonable" margin. No single closed-form margin for complex option positions.

### Option price components — intrinsic value & time value (the core decomposition)
- **Premium = Intrinsic Value + Time Value, always** (either part can be 0).
- **Intrinsic value** = the immediately-capturable buy-low/sell-high amount, floored at 0. With `S` = underlying spot, `X` = strike:
```
Call intrinsic value = max(0, S − X)
Put  intrinsic value = max(0, X − S)
```
  - Intrinsic value is **independent of expiration date** (a March 70 call and a Sept 70 call have the same intrinsic value at a given S).
  - Worked: underlying 435, 400 call intrinsic = 35; underlying 62, 70 put intrinsic = 8.
- **Time value** (a.k.a. **time premium / extrinsic value**) = premium − intrinsic value. It's the extra traders pay for the **protective (insurance) characteristic** of the option vs an outright underlying position.
  - Worked: 400 call @50 with underlying 435 → intrinsic 35, time value 15 (35+15=50). 70 put @11 with stock 62 → intrinsic 8, time value 3.
- **Parity:** an option trading at *exactly* intrinsic value (zero time value) is **"trading at parity."**
- A **European** option *can* have **negative time value** ⇒ can trade **below parity** (developed in Ch 16, early exercise). American options effectively can't, since you could exercise.

### Moneyness — in / at / out of the money
- **In-the-money (ITM):** positive intrinsic value. Call ITM ⇔ `X < S`; Put ITM ⇔ `X > S`. (Same-strike call and put are always on opposite sides — if the call is ITM the put is OTM, and vice versa.)
- **Out-of-the-money (OTM):** no intrinsic value → premium is *pure time value*. Call OTM ⇔ `X > S`; Put OTM ⇔ `X < S`.
- **At-the-money (ATM):** strictly `X = S`. Technically ATM options are *also* OTM (no intrinsic value), but traders separate them because **ATM options have special, desirable characteristics and are the most actively traded** (this matters a lot later — max gamma/theta/vega cluster near ATM). For exchange options, "ATM" colloquially = the strike *closest* to spot.

### Practical takeaways
- Cash flow *at exercise* depends only on the strike; the *price you paid* determines P&L. Don't conflate the two.
- Assignment is random and can hit any open short — never assume you're "safe" from early assignment on a short American option that's ITM.
- ATM is where the action (and the most time value, and the most sensitivity) lives. When the book later builds Greeks, ATM is the reference point.

### 🧠 What a quant should remember (Ch 3)
- `Call IV = max(0, S−X)`, `Put IV = max(0, X−S)`; `Premium = IV + TV`; TV is the model's real output (everything beyond intrinsic).
- European options can carry **negative time value / sub-parity** prices — don't clamp them to ≥ parity in code; that's a real (deep-ITM, cost-of-carry) effect.
- American vs European + settlement style (physical/futures/cash) materially change pricing & early-exercise logic; tag every contract with both.
- ATM strike ≈ where vega/gamma/theta peak → the natural anchor for vol estimation and risk.

---

## Chapter 4 — Expiration Profit and Loss (Parity Graphs)

### Core idea
- **At expiration, an option is worth exactly its intrinsic value** — the one moment everyone agrees on price. OTM → 0; ITM → `|S − X|`. Each point the underlying moves further ITM adds 1 point of value (1-for-1).
- This makes expiration the clean base case for understanding any position before time value / volatility complicate things.

### Parity graphs ("hockey sticks")
A **parity graph** plots position value at expiration vs underlying price (parity = intrinsic value). The four basic ones:
- **Long call:** 0 below strike; **slope +1** above strike (kink at strike).
- **Short call:** 0 below strike; **slope −1** above (value goes negative).
- **Long put:** **slope −1** below strike; 0 above.
- **Short put:** **slope +1** below strike; 0 above.

**The fundamental asymmetry:** option **buyers** = limited risk (≤ premium) + unlimited profit; option **sellers** = limited profit (≤ premium) + unlimited risk. So why sell? → Because the *likelihood* of the bad tail can be low and the premium high enough; **probability** is what justifies selling (the whole point of the pricing-model chapters). (Footnote caveat: for puts the underlying can't go below 0, so put profit/risk isn't *literally* unlimited — but treated as such in practice.)

### Slope = the expiration analog of delta
```
slope = (change in position value) / (change in underlying price)
```
| Position | Slope |
|---|---|
| Long/short any OTM option | 0 |
| Long ITM call | +1 |
| Short ITM call | −1 |
| Long ITM put | −1 |
| Short ITM put | +1 |
| Long underlying | +1 (constant, all prices) |
| Short underlying | −1 (constant, all prices) |

**Building combined positions: add the slopes of the legs over each price interval.** The key difference between options and the underlying: the underlying's slope is *constant* (±1 everywhere), whereas an option's parity graph **always bends at its strike** (the insurance feature).

### Worked combinations (synthetic-equivalence preview)
- **Long call + long put, same strike** (a straddle): slope −1 below strike, +1 above → V-shape; profits on a *big move either direction*, indifferent to direction. (Magnitude play, not direction.)
- **Long 2 calls + short 1 underlying, same strike:** slope −1 below (0 − 1), +1 above (+2 − 1) → **identical graph to the long straddle.** ⇒ *The same payoff can be built multiple ways* (foreshadows **synthetics**, Ch 14). Underlying's position on the price axis is irrelevant to the slope.
- **Long call + short put, same strike:** slope +1 below (0 + 1) and +1 above (+1 + 0) → **constant +1 = synthetic long underlying.** (This is the seed of **put-call parity**.)

### Procedure for any complex position
1. Determine slope below the lowest strike, between each pair of strikes, and above the highest strike (sum the leg slopes per interval).
2. The parity graph is just those line segments connected.
- Book's complex example (−4 underlying; mixed 65/70/75/80 calls & puts) builds a slope table per interval (e.g. −3 below 65, +2 between 65–70, 0 between 70–75, −3 between 75–80, −1 above 80) → reveals unlimited profit on the downside and unlimited loss on the upside. (For positions with offsetting buys/sells across strikes, the graph may have **no y-axis anchor** — shape is still informative.)

### From parity graph → Expiration P&L graph
- **P&L graph = parity graph shifted by net premium**: **down by net debit** (you paid) or **up by net credit** (you received).
- **Breakeven** = price where the shifted graph crosses 0.
  - **Long 100 call @3.50:** below 100 lose 3.50 (flat); above 100 slope +1; **breakeven = 100 + 3.50 = 103.50**.
  - **Short 95 put @2.25:** above 95 keep +2.25 (flat); below 95 slope +1 (losing); **breakeven = 95 − 2.25 = 92.75**.
- **Relative value of strikes:** lower-strike **calls** are worth more (buy cheaper); higher-strike **puts** are worth more (sell higher).

### Computing P&L at an arbitrary price using slopes (the practical trick)
Pick a convenient point (usually a strike), compute total P&L there from the contract ledger, then walk to any other price using interval slopes: `P&L_end = P&L_start + slope × (price_end − price_start)`.
- Worked (mixed call/put/underlying position): P&L at 95 = −3.00; slope 95–105 = +1 → P&L at 105 = −3.00 + 10 = +7.00; slope above 105 = −2. Breakevens: `95 + 3.00/1 = 98.00` and `105 + 7.00/2 = 108.50`.
- Worked (the complex parity position): given P&L = +2.10 at 62.00, walk interval-by-interval to 81.50 → ends at **−13.40 loss**; three breakevens at 62.70, 68.45, ≈76.03. Demonstrates that once you know slopes + one P&L point, the *entire* payoff is determined.

### Practical takeaways
- Expiration payoff = **piecewise-linear**; fully described by (a) slopes between strikes and (b) one known P&L point. This is exactly how to code a payoff diagram.
- Breakeven = strike ± (premium / |slope|). For a simple long option: strike + premium (call) / strike − premium (put).
- Multiple constructions give identical payoffs → hunt for the *cheapest* way to express a view (synthetics/arbitrage edge).
- The buyer/seller risk asymmetry is *resolved by probability* — selling options is rational when premium > probability-weighted expected payout. That's the bridge into pricing models.

### 🧠 What a quant should remember (Ch 4)
- At expiry, value = intrinsic; payoff is piecewise-linear with slopes ∈ {sum of ±1 per leg}.
- **Slope at expiration = the limiting delta** (0 for OTM, ±1 for ITM, ±1 for underlying); composing positions = summing slopes per interval.
- **Synthetic identities fall straight out of slope addition:** long call + short put (same strike) = long underlying (put-call parity); long call + long put = straddle = long 2 calls + short underlying.
- P&L graph = parity graph shifted by net premium; breakeven = where it crosses 0 = strike ± premium/|slope|.
- Selling options (capped profit, big risk) is justified only by probability — model the distribution, then compare premium to expected payout.

---

## Chapter 5 — Theoretical Pricing Models *(PLACEHOLDER — body text NOT in this batch file; see top-of-note warning)*

> ⚠️ **Everything in this section is reconstructed from the Table of Contents + the book's stated approach, NOT from extracted body text.** Treat as a stub to be replaced when Ch 5 is properly extracted (likely lands in Batch 2 alongside Ch 6 Volatility, where the same machinery is developed in depth). Flagged throughout with (verify: ...).

The TOC lists Chapter 5 sections as: **The Importance of Probability (p.53)**, **A Simple Approach (p.57)**, **The Black-Scholes Model (p.61)**.

### What Ch 5 is expected to establish (verify against real text)
- **The Importance of Probability** — (verify) extends Ch 4's punchline: an option's *theoretical value* is the **probability-weighted average of its expiration payoffs**, discounted to present value. Fair value = expected intrinsic value at expiration. This is why a seller with capped profit/unbounded risk can still have edge: if the bad outcomes are improbable enough, expected payout < premium.
- **A Simple Approach** — (verify) Natenberg's intuitive, pre-Black-Scholes build: assume a simple (e.g. discrete/uniform or coin-flip-style) distribution of terminal underlying prices around the **forward price as the mean** (connecting to Ch 2), compute the expected payoff of a call/put, and show how the answer depends on how *spread out* the distribution is — i.e., **volatility** — motivating Ch 6. Likely demonstrates that a wider terminal distribution → more time value, and that the center of the distribution is the **forward**, not spot.
- **The Black-Scholes Model** — (verify) introduces the closed-form for European options. The canonical form a quant should expect (standard BSM, not guaranteed to match the book's exact notation):
  - Non-dividend stock call: `C = S·N(d1) − X·e^(−r·t)·N(d2)`; put `P = X·e^(−r·t)·N(−d2) − S·N(−d1)`.
  - `d1 = [ln(S/X) + (r + σ²/2)·t] / (σ·√t)`, `d2 = d1 − σ·√t`.
  - `N(·)` = cumulative standard normal; `σ` = annualized volatility; `t` = time in years.
  - Natenberg typically frames BSM in **forward terms** (Black-76 style for futures options): `C = e^(−r·t)·[F·N(d1) − X·N(d2)]`, `d1 = [ln(F/X) + (σ²/2)·t]/(σ√t)`. (verify which form the chapter uses.)
- **The five inputs to a theoretical pricing model** (this is the famous list the task asked for; Natenberg states it around here — verify exact page):
  1. **Underlying / forward price** (S or F)
  2. **Exercise (strike) price** (X)
  3. **Time to expiration** (t)
  4. **Interest rate** (r) — (for stock, dividends are effectively a 6th input / adjustment)
  5. **Volatility** (σ) — the *only* input not directly observable → the trader's edge and the focus of the whole book.
  - Of these, strike & time are fixed by the contract; underlying & rate are observable; **volatility must be estimated/forecast** → this is the central problem for a vol-trading quant.

### 🧠 What a quant should remember (Ch 5) — provisional
- Theoretical value = **PV of probability-weighted expiration payoff**; the model is just a disciplined way to compute that expectation.
- The terminal distribution is **centered on the forward price** (Ch 2 → Ch 5 → Ch 6 chain).
- **Five inputs**: forward/underlying, strike, time, rate, volatility (+ dividends for stock). **Volatility is the only unobservable** — everything competitive in options trading reduces to estimating/forecasting it.
- Re-extract Ch 5 before relying on any exact formula here.

---

## Batch 1 — Top 10 durable lessons

1. **Forward price is spot grown at carry:** `F = S·(1 + r·t) − income (+ storage/insurance)`; FX = `S·(1+r_d·t)/(1+r_f·t)`. The forward — not spot — is the correct center for option pricing (the terminal distribution is centered on the **forward**). For futures options, the futures price *is* the forward, so no extra carry step.
2. **Premium = Intrinsic + Time value, always.** `Call IV = max(0, S−X)`, `Put IV = max(0, X−S)`. Intrinsic is mechanical; **time value is the entire output of a pricing model** and is what volatility drives.
3. **At expiration, value = intrinsic; payoff is piecewise-linear.** Any position is fully described by its **slopes between strikes** + one known P&L point. Slope at expiry is the limiting delta (0 OTM, ±1 ITM). This is the recipe for any payoff diagram in code.
4. **Synthetics fall out of slope addition.** Long call + short put (same strike) = long underlying (→ **put-call parity**); long call + long put = straddle = long 2 calls + short underlying. The same payoff has multiple constructions → always seek the cheapest expression and watch for arbitrage.
5. **Implied-input thinking is the master tool.** Invert the fair-value formula to back out the unobservable: implied spot, implied rate, implied dividend — and, the big one later, **implied volatility**. If a price is fair, its implied value = the market's consensus estimate.
6. **Volatility is the only one of the five pricing inputs that isn't observable** (inputs: underlying/forward, strike, time, rate, vol [+ dividends]). All competitive edge in options trading is about **estimating/forecasting σ** — directly relevant to the tournament: prioritize a defensible vol estimate over everything else.
7. **Real markets have two rates, not one** (borrow > lend; long rate `r_l` > short rate `r_s`, with `r_l − r_s = r_bc`). This converts single no-arbitrage prices into no-arbitrage **bands**. Options always use the long rate `r_l` (an option isn't borrowed to be sold).
8. **Settlement type is a real risk, not a footnote.** Stock-type = gains unrealized until close; futures-type = daily margin + variation (real cash). **US options are always stock-type even on futures** → a "perfectly hedged" futures+option position can still bleed variation cash. Always budget cash for adverse variation.
9. **The buyer/seller asymmetry (capped vs unbounded) is resolved by probability.** Selling options is rational precisely when premium > probability-weighted expected payout. Never reason about payoff tails without weighting by likelihood — that's the entire justification for the pricing-model machinery.
10. **ATM is the center of gravity.** ATM options carry the most time value, are the most actively traded, and (per later chapters) are where gamma/theta/vega peak — making the ATM strike the natural anchor for vol estimation and risk management. Convenience yield (commodities) and dividends (stock) are the unobservable plugs to back out from the cash↔forward relationship.

---
*Note generated from a full end-to-end read of `01_foundations.txt` (2907 lines). Chapters 1–4 are from extracted body text; Chapter 5 is a flagged placeholder — its real content was absent from this batch file and should be re-extracted.*