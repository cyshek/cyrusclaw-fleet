# Batch 4 — Option Arbitrage, Early Exercise (Natenberg, *Option Volatility & Pricing*)

> **Scope / sourcing note (important).** The input file
> `batches/04_arbitrage_exercise_hedging.txt` (3,594 lines) actually contains the **tail of Ch. 13 (Risk Considerations)**, **Ch. 14 (Synthetics)**, **Ch. 15 (Option Arbitrage)**, and **Ch. 16 (Early Exercise of American Options)** — book pages ~248–321.
> The **"Hedging with Options" chapter (the Ch. 17 material in the task brief — protective puts, covered calls, collars/fences) is NOT in this file.** Grep for `hedging|protective put|covered call|collar|fence|chapter 17` returns zero hits; the file stops at p.321 mid-book.
> Sections 1–3 below are sourced **directly and fully from the file**. Section 4 (Hedging with options) is a **short, correct standalone treatment NOT drawn from this batch** — included so the note still serves its purpose, but explicitly flagged. If a real Natenberg hedging chapter exists, it's in a different batch file and should be re-extracted.
> Garbled OCR bits flagged inline as **(verify: …)**.

Notation used throughout: `C`=call price, `P`=put price, `S`=underlying stock price, `F`=underlying futures price (or stock forward price), `X`=exercise/strike price, `r`=annual interest rate, `t`=time to expiration in years, `D`=expected dividends.

---

## 0. Foundation from the file: Synthetics (Ch. 14) — the engine behind all arbitrage

Every arbitrage relationship below is just *synthetics priced fairly*. A call and put with the **same strike and same expiration** can be combined with the underlying to replicate any of the six basic contracts. **All options must share strike + expiry.**

**Synthetic underlying:**
- `synthetic long underlying ≈ long call + short put`
- `synthetic short underlying ≈ short call + long put`

At expiration the synthetic long *always* buys the underlying at `X` (exercise the call if above `X`, get assigned on the put if below). Hence its delta ≈ +100 (synthetic short ≈ −100). **The absolute values of a call delta and its companion put delta sum to ≈100.** Because the synthetic underlying has zero gamma/vega, **companion call and put have identical gamma and identical vega** — so a volatility trader is indifferent between a call and its companion put (convert one to the other by trading the underlying). Theta is *not* generally equal between companions: the difference is the **cost of carry** (interest on stock, or stock-type settlement carry on the options). Only when there's no carry on either leg (futures options, futures-type settlement) do companion thetas match.

**The four synthetic options** (single option hedged with underlying = synthetic *companion* option):
- `synthetic long call ≈ long underlying + long put`
- `synthetic short call ≈ short underlying + short put`
- `synthetic long put ≈ short underlying + long call`
- `synthetic short put ≈ long underlying + short call`

Mnemonic from the book: *"Trade one option and hedge it with the underlying → you now hold, synthetically, the companion option."* (Buy call + sell underlying = synthetic long put; etc.)

Synthetics also reveal equivalences used later: a **bull call spread = bull put spread** (underlying legs cancel); call/put **butterflies are identical** (one is the synthetic of the other); an **iron butterfly = traditional butterfly** done for a credit (sell straddle / buy strangle ≈ buy the outside-strike butterfly); same for **iron condor = condor**. Key value identity: *butterfly value + iron-butterfly value = (present value of) the amount between strikes* (interest-rate-discounted under stock-type settlement).

---

## 1. Option Arbitrage (Ch. 15) — getting the relationships EXACTLY right

The whole chapter is one idea: **put-call parity**. A call, a put (same strike/expiry), and the underlying are price-locked. Know any two prices → the third is determined. Mispricing → a (near-)riskless arbitrage that everyone rushes to do, snapping prices back in seconds.

### 1.1 Conversion and Reversal/Reverse-conversion — exact construction

A **conversion** = buy the underlying in the cash/futures market + sell it synthetically in the options market:

```
Conversion  = long underlying + short call + long put
            = long underlying + synthetic short underlying
Reversal    = short underlying + long call + short put     (a.k.a. reverse conversion)
            = short underlying + synthetic long underlying
```
(call & put always same strike, same expiry). It's a classic arbitrage: buy and sell the *same* (synthetic) underlying in two different markets to capture a mispricing.

- Do a **conversion** when the **synthetic (combo) is too expensive** relative to the underlying (sell the rich synthetic, buy the cheap underlying).
- Do a **reversal** when the **synthetic is too cheap** (buy the cheap synthetic, sell the rich underlying).

The synthetic leg (long call + short put, or short call + long put) is called a **combo**.

### 1.2 The no-arbitrage parity each enforces (the derivation, exactly)

Carry a stock conversion (sell call, buy put, buy stock) to expiration and tally cash flows.
**Credits:** call premium `C`; interest earned on it `C·r·t`; dividends `D`; exercise price `X` received when stock is sold at expiry (exercise put or get assigned on call).
**Debits:** put premium `P`; interest cost to fund it `P·r·t`; stock price `S`; interest cost to fund stock `S·r·t`.

Arbitrage-free ⇒ credits = debits:
```
C + C·r·t + D + X  =  P + P·r·t + S + S·r·t
```
Solve for the combo `C − P`:
```
(C − P)(1 + r·t) = S(1 + r·t) − D − X
```
Recognize `S(1 + r·t) − D = F` (the **forward price** of the stock). So:
```
            F − X
  C − P  =  ────────       ◄ PUT-CALL PARITY (simple-interest form)
           1 + r·t
```
**In words:** the call−put price difference (the combo) equals the **present value of (forward price − strike)**. Names traders use: combo value, the synthetic relationship, the "conversion market."

**Continuous-compounding form:** `C − P = (F − X)·e^(−r·t)`.

### 1.3 How interest & dividends enter — the three settlement cases

1. **Options on futures, futures-type settlement** (most non-US futures exchanges): no money changes hands on trade → effective rate 0; futures pay no dividend. Parity collapses to the cleanest form:
   ```
   C − P = F − X
   ```
   *Worked:* Dec 100 call = 5.25, Dec 100 put = 1.50 ⇒ `C−P = 3.75` ⇒ futures must = 103.75. If futures = 104.00, `3.75 ≠ 4.00`; everyone buys the cheap synthetic (buy call/sell put) and sells the futures → arb profit 0.25 until call rises / put falls / futures falls back to restore `C−P=F−X`. (Eurex Euro-bund table in book confirms parity holds at every strike.)

2. **Options on futures, stock-type settlement** (most US futures exchanges): discount by interest:
   ```
   C − P = (F − X)/(1 + r·t)
   ```
   *Worked:* 6 mo, r=6%, Dec 100 call=4.90, futures=97.25 ⇒ `C−P = (97.25−100)/(1+0.03) ≈ −2.67` ⇒ `P = 4.90 + 2.67 = 7.57`.

3. **Options on stock** (the extra step is computing the forward first):
   ```
   F = S(1 + r·t) − D ;   then   C − P = (F − X)/(1 + r·t)
   ```
   *Worked:* 6 mo, r=4%, 65 call=8.00, S=68.50, D=0.45 ⇒ `F = 68.50·1.02 − 0.45 = 69.42` ⇒ `C−P = (69.42−65)/1.02 ≈ 4.33` ⇒ `P = 8.00 − 4.33 = 3.67`.

**Fast open-outcry approximation for stock options** (avoids the division):
```
C − P  ≈  S − X + X·r·t − D
```
i.e. *stock − strike + interest-on-strike − expected dividends*. Same example: `68.50 − 65 + 65·0.04·0.5 − 0.45 = 4.35` (off by 0.02 vs 4.33). Errors grow with high rates, big dividends, or long maturities.

**Implied interest / implied dividend.** Parity has 3 unknowns hiding in {r, D}. If observed prices don't fit, solve for the *implied* input:
- Implied rate: `r = (C − P − S + X + D)/X / t`.
- Implied dividend: `D = S − C + P − X + X·r·t`.
A market price implying a *lower-than-expected dividend* is a warning the company may **cut the dividend** before expiry.

### 1.4 Locked (limit) futures markets — a practical use of parity

If a futures market is locked at its daily limit (no one will trade), but options still trade, you can **trade futures synthetically**: buy call+sell put (= buy futures) or sell call+buy put (= sell futures). The implied futures price is `F = C − P + X`. The book's table of strikes all imply F≈133.2–133.3 even though the futures is locked limit-up at 131.75 — telling you where futures *would* trade.

### 1.5 "Locking in a profit" — what it actually means here

A conversion/reversal **locks the mispricing as a known terminal P&L**: you've bought and sold the *same* economic underlying at two different effective prices, so the gap is captured regardless of where the underlying finishes. Example: sell Dec 100 call @5.00, buy Dec 100 put @3.00, buy stock — you've synthetically sold the underlying at 102.00 while owning it; if parity said the combo was worth less, the difference is yours at expiry. The profit is realized at the **opening** trade (the edge), not the closing trade. **But "locked" ≠ "riskless"** — see §1.7.

### 1.6 Boxes, Rolls, Time boxes — eliminating the underlying leg

A conversion/reversal still **holds a real underlying position** → carries interest/dividend/settlement risk. Replace that underlying leg with *another synthetic* and the underlying cancels:

**BOX** = conversion at one strike + reversal at another strike (same expiry). Underlying legs cancel, leaving two synthetics at different strikes:
```
Long 90/100 box  =  +1 Jun 90 call / −1 Jun 90 put   (synthetic long @90)
                    −1 Jun 100 call / +1 Jun 100 put  (synthetic short @100)
```
- **Long the box** = synthetically long at the lower strike, short at the higher strike.
- At expiration the box is worth **exactly the distance between strikes** (`Xh − Xl`): you buy at the low strike and sell at the high strike no matter what.
- **Value today** (stock-type settlement) = present value of that distance:
  ```
  Box value = (Xh − Xl)/(1 + r·t)      [futures-type settlement: = (Xh − Xl), undiscounted]
  ```
  *Worked:* 90/100 box, 3 mo, r=8% ⇒ `10/(1+0.02) ≈ 9.80`.
- **A box is pure lending/borrowing** (when European + cash-settled = no early-exercise, no pin risk): *buying* the box = lending money to expiry; *selling* the box = borrowing. Selling the 3-mo 90/100 box for 9.80 ≈ borrowing at 8%; selling it cheaper (9.70) = borrowing at a higher implied rate (~12%). A firm short of cash can raise it by selling boxes (at a cost, due to bid-ask + margin + fees).
- **Decomposition:** a box = a **bull (call) vertical + a bear (put) vertical**; their prices must sum to the box value. If 90/100 box=9.80 and the 90/100 call spread=6.00, the 90/100 put spread must be `9.80 − 6.00 = 3.80`. (Trade around that to capture edge.)

**ROLL** (a.k.a. *jelly roll* in common trader usage — **(verify:** the book here calls it simply a "roll"; "jelly roll" is the standard street name for this exact long-synthetic-one-month / short-synthetic-another-month structure**)**) = conversion in one month + reversal in another month, **same strike**. Only works where the underlying is identical across months (i.e. **stock options** — the same stock underlies all expiries; *not* futures options, where June futures ≠ August futures, so the underlying legs don't cancel and it isn't a true roll).
```
Roll  =  +1 Jun 90 call / −1 Jun 90 put   (synthetic long, near month)
         −1 Aug 90 call / +1 Aug 90 put   (synthetic short, far month)
```
- **Value** = difference of the two combos `(Cl − Pl) − (Cs − Ps)`. Excluding dividends, that's the **difference between the discounted strikes** across the two expiries:
  ```
  Roll = X/(1 + rs·ts) − X/(1 + rl·tl) − D
  ```
  (subscripts s/l = short/long expiry; D = dividends paid *between* expirations). *Worked:* 90 roll, 2 mo & 4 mo, r=6%, D=0.40 ⇒ `90/1.01 − 90/1.02 − 0.40 = 89.11 − 88.24 − 0.40 = 0.47`.
- **Carry approximation:** roll ≈ cost of carrying the strike from one expiry to the other, less dividends: `X·r·t − D` (t = time *between* expiries). Here `90·0.06·(2/12) − 0.40 = 0.90 − 0.40 = 0.50` (off by 0.03).
- **Decomposition:** roll = **long call calendar − short put calendar** (i.e. buy call calendar, sell put calendar). Difference of the two calendars = roll value. (Contrast: box = *sum* of two verticals; roll = *difference* of two calendars.)
- **Sign:** because interest usually > dividends between expiries, a **long roll** (buy far synthetic, sell near) usually costs money (positive value) → the call calendar is richer than the put calendar. If **dividends > interest**, the roll flips negative and the put calendar is richer.
- Rolls with same expiries but different strikes differ by **interest on the strike difference**: `Roll(80) ≈ Roll(90) − (90−80)·r·t`.
- A roll only removes underlying risk **up to the near expiry** (where you exchange the stock); it stays sensitive to interest & dividends — more so the wider the gap between expiries.

**TIME BOX / diagonal roll** = synthetics at **different strikes AND different months**:
```
+1 Jun 90 call / −1 Jun 90 put ;  −1 Aug 100 call / +1 Aug 100 put
```
- Value = `Xs/(1 + rs·ts) − Xl/(1 + rl·tl) − D`. *Worked:* `90/1.01 − 100/1.02 − 0.40 = −9.33` (negative = you pay 9.33 to put it on).
- = combination of a **box and a roll**: `time box = long-term box − lower-strike roll = short-term box − higher-strike roll`. Decomposes into two **diagonal spreads**.

### 1.7 Arbitrage RISK — "few strategies are truly riskless"

Natenberg's explicit warning: conversions/reversals are *low*-risk, **not no-risk**.
- **Execution (leg) risk:** you rarely get all three legs at good prices simultaneously; you leg in and the last leg may move against you before you complete the arb.
- **Pin risk:** if the underlying finishes **exactly at the strike** at expiration, you don't know (until the next day's assignment notice) whether your short option gets exercised → you may wake up unexpectedly long/short the underlying, magnified because conversions/reversals are done in size. Mitigation: **reduce size into expiration** when price is near the strike; or **cross with a trader holding the opposite (reversal vs conversion) position at even money**. Pin risk **vanishes for cash-settled options** (e.g. index options) — no underlying position results.
- **Settlement risk:** only when the two legs settle differently (e.g. **stock-type** options vs **futures-type** underlying futures). Unrealized option P&L vs immediately-cash-settled futures variation creates an interest mismatch. Consequence: a "delta-neutral" conversion on futures is actually **slightly long deltas** — the synthetic-futures delta is `100/(1 + r·t)`, not 100 — because you prefer the futures to rise (cash inflow you earn interest on). Larger with higher rates / more time. In size this is real directional risk. (Hedgers call the analogous adjustment **tailing**.)
- **Interest & dividend risk** (stock conversions/reversals): a conversion (long stock, funded by borrowing ≈ X) has **negative rho** (wants rates to fall) and **positive dividend risk** (helped by a dividend hike). A reversal is the mirror: **positive rho** (wants rates to rise), **negative dividend risk**. In a conversion both the call-rho and put-rho positions carry the *same* sign (you buy one option, sell the other).
- **Removing the underlying leg** to kill these risks: replace it with a **deep ITM option** (delta≈100) → a **three-way** (e.g. short call / long put / long deep-ITM call). But if the market approaches the deep-ITM strike, that option stops acting like the underlying and the hedge degrades. The cleaner removal is the **box** (replace underlying with a *second synthetic*) — lowest risk of all.

**Summary of arbitrage relationships (book Fig. 15-3), simple-interest:**
| Relationship | Formula |
|---|---|
| Put-call parity (futures) | `C − P = (F − X)/(1 + r·t)` |
| Put-call parity (stock) | `C − P = S − X/(1 + r·t) − D`  ≈ `S − X + X·r·t − D` |
| Box value | `(Xh − Xl)/(1 + r·t)` ; long box = long bull-call-spread + long bear-put-spread |
| Roll (stock) | `X/(1+rs·ts) − X/(1+rl·tl) − D` ; long roll = long call calendar + short put calendar |
| Time box | `Xs/(1+rs·ts) − Xl/(1+rl·tl) − D` = long-term box − lower-strike roll |

---

## 2. Early Exercise of American Options (Ch. 16)

Three questions the chapter answers: **(1) when might early exercise be desirable, (2) is there an optimal moment, (3) how much extra is an American option worth vs European.**

**Core principle:** early exercise is only worthwhile if there's an advantage to holding the *underlying* rather than the *option* — and that advantage is either **dividends** (stock you'd own pays them) or **positive cash flow you can earn interest on**. **No dividends + no interest effect ⇒ early exercise has zero value ⇒ American = European.** This is exactly the case for **futures options under futures-type settlement** (no carry on either leg): American ≈ European, early exercise pointless.

### 2.1 Arbitrage boundaries (the scaffolding)

- **An American option must never trade below intrinsic value** — else buy it, hedge with the underlying, exercise immediately for a riskless profit. So `American call ≥ max(0, S−X)`, `American put ≥ max(0, X−S)`.
- **European lower boundaries** come from parity (set the other option to its floor of 0):
  - Call: `C ≥ (F − X)/(1 + r·t)` → for stock: `C ≥ S − X/(1+r·t) − D`.
  - Put: `P ≥ (X − F)/(1 + r·t)` → for stock: `P ≥ X/(1+r·t) − S + D`.
  - **A European option CAN be worth less than intrinsic value** (it's only the *present value* of intrinsic). E.g. futures 1167, 6mo, r=4%, stock-type settlement: 1100 call floor = `(1167−1100)/1.02 = 65.69` though intrinsic = 67.00. When an option sits below intrinsic, it **rises toward intrinsic as time passes → positive theta.**
- Since you can always *decline* to exercise, an American option's floor is the **max of intrinsic and the European floor**:
  ```
  American call ≥ max[0, S − X, (F − X)/(1 + r·t)]
  American put  ≥ max[0, X − S, (X − F)/(1 + r·t)]
  ```
- **Upper boundaries:** `American put ≤ X`, `European put ≤ X/(1+r·t)`; `European call ≤ F/(1+r·t)` → stock: `European call ≤ S − D`, `American call ≤ S`.

### 2.2 Early exercise of an American CALL on stock — driven by DIVIDENDS

Decompose: `Call value = intrinsic + volatility value + interest value − dividend value`.
(Volatility & interest *add*; dividend *subtracts* — owning the call means you forgo the dividend.)

**Early-exercise condition:**
```
Dividend value  >  volatility value + interest value
```
When the dividend you'd capture exceeds the volatility + interest value you'd surrender, the call's "hold" value drops below intrinsic → exercise to grab intrinsic now (exercise call + sell stock).

Estimating the three pieces (no model needed):
- **dividend value** = total dividend expected over the option's life.
- **interest value** ≈ cost of carrying the strike to expiry = `X·r·t` (if exercised you pay X; that's the carry you'd incur).
- **volatility value** ≈ price of the **companion OTM put** (same strike/expiry — its vega = the call's vega, so its premium proxies the call's protective value).

*Worked:* S=100, 1 mo, r=6%, dividend 0.75 in 15 days; 90 put = 0.20. Interest = `90·0.06·(1/12) = 0.45`.
Criterion: `0.75 > 0.20 + 0.45 = 0.65` ✓ → the 90 call **is** an early-exercise candidate; exercising now beats holding to expiry by 0.10 (its European value has dipped below intrinsic).

**Optimal MOMENT for a call (sharp result):** exercising any day costs you a day of volatility value *and* a day of interest, and gains you **nothing until the dividend is actually paid**. Therefore the *only* day it can ever be optimal to exercise an American stock call early is **the day before the stock goes ex-dividend.** Corollary: **a non-dividend-paying stock's American call should never be exercised early — American call = European call.** (The lifetime condition `dividend > vol + interest` must hold, *and* it must still hold over the very next day, which only happens right at ex-div.)

### 2.3 Early exercise of an American PUT on stock — driven by INTEREST (carrying cost)

Decompose: `Put value = intrinsic + volatility value − interest value + dividend value`.
(Volatility & dividend *add*; **interest subtracts** — exercising the put hands you the strike `X` in cash early, on which you earn interest, so a put's *time* value is eroded by interest.)

**Early-exercise condition:**
```
Interest value  >  volatility value + dividend value
```
The interest you'd earn on the strike outweighs the volatility + dividend value you'd give up → exercise the put now to collect `X` and start earning interest.

Pieces:
- **interest value** = interest earnable on the strike to expiry = `X·r·t`.
- **dividend value** = total expected dividend over the option's life (owning the put = you'd rather the stock *not* go ex-div, so a dividend you'd avoid by exercising late argues *against* early exercise).
- **volatility value** ≈ price of the **companion OTM call**.

*Worked:* S=100, 2 mo, r=6%, D=0.40; 120 call = 0.55. Interest = `120·0.06·(1/6) = 1.20`. Criterion: `1.20 > 0.55 + 0.40 = 0.95` ✓ → the 120 put is an early-exercise candidate (beats holding by 0.25).

**Optimal MOMENT for a put (different from calls!):** a put can be optimally exercised **any time** during its life, *not* only near ex-div — early exercise is best whenever interest earnable exceeds the combined volatility + dividend value. But you won't want to forfeit a pending dividend, so the **most common day to exercise a put early is the ex-dividend day itself** (exercise *after* capturing nothing you'd lose). Two refinements:
  - **Blackout period:** for a put, define `blackout days = dividend / (X · r / 365)` = the window *before* ex-div during which the interest you could earn by exercising can't possibly offset the dividend you'd lose. In the example `0.40 / 0.02 = 20` days: with <20 days to the dividend, **never** exercise the put. With, say, 30 days to the dividend, exercising now earns `30·0.02 = 0.60 > 0.40` dividend → exercise is sensible (provided vol value over those 30 days < 0.20).

### 2.4 Short-stock effect on early exercise

Lowering the relevant interest rate makes **calls more** likely to be exercised early (less interest forgone) and **puts less** likely (less interest earned). A **short stock position carries a reduced rate** (borrow cost). So a trader already **short stock is more likely to exercise a call early** (it covers the short), and a trader with **no stock is less likely to exercise a put early** (it would *create* a short). Ties to Natenberg's standing rule: *avoid a short stock position when possible.*

### 2.5 Early exercise of options on FUTURES

- **Futures-type settlement:** exercising produces a variation credit = intrinsic, but the disappearing option is debited by ≈ its value → cancels → **no cash flow → no early-exercise advantage. American = European.**
- **Stock-type settlement (US futures options):** no cash flows when the option vanishes, but the futures variation credit = intrinsic **can earn interest.** Condition simplifies to:
  ```
  Interest value > volatility value      where interest = (F−X)·r·t [calls] or (X−F)·r·t [puts]
  ```
  *Worked:* F=100, 3 mo, r=8%; 80 call, companion 80 put = 0.15. Interest = `(100−80)·0.08·0.25 = 0.40 > 0.15` ✓ candidate. But is it an *immediate* candidate? One day's interest = `20·0.08/365 = 0.0044`; the 80 put's **theta** (one day's volatility decay, from a pricing model — implied vol 24.68% → θ = −0.0046) slightly exceeds it, so **not yet** — exercise becomes optimal in ~4 days when θ falls below the daily interest. (The book notes the term **fugit** for the number of days until an option becomes an immediate early-exercise candidate.) Holding longer keeps the **positive gamma** (protective value if the future plunges through the strike) — that protective value *is* the companion option's theta.

### 2.6 Exercise vs SELL the option

A third choice beyond hold/exercise: **sell the option and replace it with the underlying** (economically identical to exercising). If the option trades *above* intrinsic, selling+replacing beats exercising. **In practice it's usually not viable**: an option deep enough ITM to warrant early exercise is illiquid with a wide bid-ask, so any sale realizes ≈ intrinsic anyway.

### 2.7 Protecting the forgone protective value

Exercising forfeits the strike's downside (call) / upside (put) protection. Exercising a 90 call = synthetically **selling the 90 put** — and the gain shows you're effectively selling it at a better-than-market price (in the example, selling the 90 put at 0.30 vs market 0.20). To keep the protection, **buy the companion OTM option** at the same time you exercise (exercise 90 call + buy 90 put @0.20 → same protection as the call, 0.10 cheaper). Whether to do so depends on whether implied vol makes that companion cheap or rich.

### 2.8 Pricing American options & the EARLY-EXERCISE PREMIUM

- `American value ≥ European value` always (strict unless r=0 and no dividends). The gap is the **early-exercise premium**.
- Black-Scholes is **European-only**. Early stopgaps: **pseudo-American call** = max of [BS call expiring the day before ex-div] vs [BS call to normal expiry on price-minus-dividend]; for puts/futures options, floor BS values at parity. Neither is truly accurate.
- First real American model: **Cox-Ross-Rubinstein (1979), the binomial model** — an iterative loop; more steps → closer to true value; intuitive, standard teaching tool; preferred for **dividend-paying stocks** (handles the lump-sum dividend). **Barone-Adesi-Whaley (1987), the quadratic model** — converges far faster but treats all cash flows as continuously-accruing interest, so it's weaker on lump-sum dividends.
- Both models also tell you **when** early exercise is optimal: precisely when the option's **theoretical value = parity and its delta = exactly 100.**
- **Behavior of the premium:** it **grows as the option goes deeper ITM** (early exercise more likely). It is **larger at LOWER volatility** (high vol = you won't surrender vol value, so American≈European; low vol = exercise more likely → bigger premium). For the example 90 call (dividend 1.00 in 4 wks), deep ITM the premium → `1.00 − (90·0.06·22/365) ≈ 0.67` (dividend minus carry on buying stock the day before ex-div). For a 110 put it → `110·0.06·21/365 ≈ 0.38` (interest on strike for the 3 weeks after the dividend). **Stock options:** the premium *plateaus* at that limit. **Futures options (stock-type settlement):** the premium has **no plateau — it keeps growing with intrinsic**, since it equals interest on intrinsic `(F−X)·r·t`.
- **American deltas can sum to MORE than 100.** A European companion call+put delta sums to ≈100; but an ITM American option's delta reaches 100 faster while the OTM companion still has delta → synthetic delta (call_Δ − put_Δ) can exceed 100. Consequence: conversions, reversals, **boxes, and rolls that are delta-neutral under European assumptions are NOT exactly delta-neutral with American options** — small per-unit, but dangerous in size.
- **Box value example with American options:** a 100/110 box (24 days, r=6%, div 0.60 in 9 days) has European value `10/(1+0.06·24/365) ≈ 9.96`; depending on which legs get exercised early the value ranges from ≈9.99 (both calls or both puts exercised) up to ≈**10.57** (both the 100 call *and* 110 put exercised — stock near 105, low vol). The American box is worth *more* and is path/exercise-dependent.
- **Model accuracy caveat:** garbage in, garbage out — wrong volatility/rate/underlying inputs swamp any European-vs-American modeling gain. In **futures-type-settlement** markets a European model fully suffices; even in stock-type futures options the early-exercise premium is tiny (option price small vs futures), relevant only for very deep ITM.

### 2.9 Early-exercise STRATEGIES (exploiting others' mistakes)

Early exercise is a *right*; some holders fail to exercise when they should. Professionals (low transaction costs) can harvest that error:
- **Dividend play:** just before ex-div, **sell deep-ITM calls + buy stock 1:1**. If assigned (as you should be) → break even. If *not* assigned → you keep the stock, collect the dividend → profit ≈ the dividend. Likelihood of escaping assignment rises with **high open interest** and an **unsophisticated market** (common in option trading's early days; rare now).
- **Interest play:** sell stock + sell deep-ITM American puts that *should* be exercised. If not exercised → earn interest on the strike proceeds; if exercised → break even. (Futures-option analogue exists under stock-type settlement, but you earn interest only on intrinsic, not the full strike → less lucrative.)
- **Spread version:** trade deep-ITM **call/put spreads** that should be worth exactly the strike difference. A market maker may quote an *identical* 5.00 bid and ask on an 85/90 call spread that should be worth 5.00 because whichever side fills, he exercises the appropriate leg and is set up for the dividend play — giving up the bid-ask edge for the chance the short option goes unexercised.

### 2.10 Early-exercise RISK (being on the receiving end)

Early assignment is just one of many risks; rarely a true surprise. **Test:** *"If I owned this option, would I rationally exercise it now?"* If yes → expect assignment, keep capital for the possible cash squeeze (deep-ITM short options assigned early can force a liquidation, which always loses). If no, and you're *still* assigned → it's a **gift** (someone abandoned interest/volatility value to you).

---

## 3. Practical takeaways (from the file: arbitrage + early exercise)

1. **Always ask: can I do part of this strategy synthetically and cheaper?** Even when no arbitrage exists, bid-ask spreads sometimes let you build a straddle/butterfly synthetically a few cents better (book: synthetic straddle saving 0.05; iron-butterfly being 0.05 better than the call/put butterfly). Over a career, the pennies compound.
2. **Put-call parity is the master check.** Three contracts, two prices → the third is pinned. A price that doesn't fit isn't necessarily arbitrage — first suspect your **interest or dividend assumption** (compute the implied rate / implied dividend; an implied dividend below expectation can foreshadow a dividend cut).
3. **"Riskless" arb isn't.** Budget for execution/leg risk, pin risk, settlement (carry-mismatch) risk, and interest/dividend risk. Size discipline near expiry kills pin risk; cash-settled products have none.
4. **Conversions/reversals on futures are not exactly delta-neutral** — synthetic-futures delta = `100/(1+r·t)`. In size, that's real directional exposure from the interest on variation. (Hedger analogue: *tailing*.)
5. **Boxes = interest-rate instruments.** Treat buying/selling a European cash-settled box as lending/borrowing; back out the implied rate before quoting. Box = bull vertical + bear vertical; price the missing leg off the box.
6. **Rolls (jelly rolls) = a dividend-vs-interest bet across expiries**, decomposing into call-calendar minus put-calendar. Usually positive (interest > dividends); flips sign if dividends dominate. Only valid where the underlying is identical across months (stock options).
7. **American call early exercise is a once-a-year event: the day before ex-div, and only if the dividend beats vol+interest.** No dividend ⇒ never exercise a call early.
8. **American put early exercise is interest-driven and can happen any day**, but respect the **blackout window** before ex-div (`dividend / daily-interest-on-strike` days) where it's never optimal.
9. **When you do exercise, consider buying the companion OTM option** to retain the protection you're giving up — if implied vol makes it cheap.
10. **Don't fear early assignment; pre-screen it** with the "would I exercise this?" test, and keep enough capital to absorb a cash squeeze on short deep-ITM options.

---

## 4. Hedging with options — protective put / covered call / collar (fence)

> ⚠️ **NOT FROM THIS BATCH FILE.** The hedging chapter the task brief expected (Natenberg Ch. "Hedging with Options") is **absent** from `04_arbitrage_exercise_hedging.txt` — the file ends at p.321 (end of Early Exercise). The following is a **concise, standard, self-contained** treatment so the note still serves its stated purpose. Re-extract the real chapter from the correct source batch if exact Natenberg wording/numbers are needed; **(verify against book).** Synthetic identities below are, however, directly consistent with this file's §0 synthetics.

All three structures hedge a **long underlying** position (mirror them for a short).

### 4.1 Protective put (a.k.a. married put) = portfolio insurance
- **Construction:** long underlying + **long an OTM put** (strike `Xp < S`).
- **Cost:** pay the put premium (a debit); this is the insurance cost / drag.
- **Payoff:** downside is **capped** — below `Xp` losses stop (floor = `Xp − premium − S0`); upside stays **unlimited** minus the premium. By §0, *long underlying + long put = synthetic long call* → a protective put has the payoff *shape* of owning the call at `Xp`.
- **Greeks:** adds **positive gamma, positive vega, negative theta** (you bought an option); net delta < 100 and falls as the market drops (the put's negative delta kicks in). You're long volatility and pay time decay for the protection.

### 4.2 Covered call (a.k.a. buy-write / overwrite) = yield enhancement
- **Construction:** long underlying + **short an OTM call** (strike `Xc > S`).
- **Cost:** **receive** the call premium (a credit) — income that cushions small declines.
- **Payoff:** upside is **capped** at `Xc` (you're called away; max gain = `Xc − S0 + premium`); downside is reduced only by the premium received (you still own all the downside below breakeven `S0 − premium`). By §0, *long underlying + short call = synthetic short put* → a covered call has the payoff of **selling a put** at `Xc`.
- **Greeks:** adds **negative gamma, negative vega, positive theta** (you sold an option); net delta < 100. You're short volatility and *collect* time decay — the opposite Greek profile of the protective put.

### 4.3 Collar / fence = bounded both ways, cheap or costless
- **Construction:** long underlying + **long OTM put** (`Xp`) + **short OTM call** (`Xc`), with `Xp < S < Xc`. (A "fence" is the same idea; some desks reserve "fence" for the options-only risk-reversal portion.)
- **Cost:** the short call's premium **finances** the long put. Choose strikes so premiums offset → a **zero-cost (costless) collar**; otherwise a small net debit or credit.
- **Payoff:** P&L is **boxed into a corridor** — floor at `Xp`, ceiling at `Xc`. You give up upside above `Xc` to fund downside protection below `Xp`. The options-only piece (long put + short call) = a **short synthetic underlying** (risk reversal) overlaid on the long position, so a collar *reduces effective delta* toward neutral within the band.
- **Greeks:** the long put and short call partially cancel → **small net gamma/vega/theta** (sign depends on which leg is more OTM / closer to the money). A symmetric collar is roughly vega-/gamma-neutral; net delta is positive but compressed.

**One-line contrasts:** protective put = *pay to cap downside, keep upside* (long vol). Covered call = *get paid, cap upside, keep most downside* (short vol). Collar = *cap both, ~free* (low vol exposure). Synthetic identities: protective put ≈ long call; covered call ≈ short put; collar ≈ long underlying wrapped by a short risk-reversal.

---

## Per-chapter — "what a quant should remember"

**Ch. 14 Synthetics.** Calls and puts are interchangeable via the underlying; the *only* thing that fixes a position's volatility character is its **strikes and expiries**, not the call/put labels. Companion call & put share gamma and vega exactly; their theta differs only by carry. Every spread has multiple equivalent constructions (vertical call=vertical put; call/put butterflies identical; iron = regular done for credit) — always build the cheapest synthetic version.

**Ch. 15 Option Arbitrage.** Internalize put-call parity in all three settlement flavors and its fast stock approximation `C−P ≈ S − X + X·r·t − D`. Conversions/reversals lock a mispricing but carry execution/pin/settlement/interest/dividend risk; the **synthetic-futures delta is `100/(1+r·t)`, not 100.** Boxes = present-valued strike-distance = lending/borrowing; rolls = discounted-strike-difference−dividends = interest-vs-dividend play; time boxes = box−roll. Decompositions: box = sum of two verticals; roll = difference of two calendars.

**Ch. 16 Early Exercise.** Memorize the two criteria: **call early-exercise ⇔ dividend > vol + interest** (only ever the day before ex-div; never without a dividend); **put early-exercise ⇔ interest > vol + dividend** (any day, but respect the pre-ex-div blackout `= div/(X·r/365)` days). Estimate vol value as the **companion OTM option's price**, interest as `X·r·t`, dividend as the cash dividend. American ≥ European; the **early-exercise premium** grows deeper-ITM, shrinks with higher vol, plateaus for stock options but grows unbounded for stock-type-settled futures options. Use **CRR (binomial)** for dividend stocks, **BAW (quadratic)** for speed; both say exercise exactly when **value = parity and delta = 100**. American deltas can exceed 100 → "riskless" arb books drift off delta-neutral in size. Receiving an unwarranted early assignment is a gift; pre-screen with "would I exercise this?"

---

## Batch 4 — Top 10 durable lessons

1. **Put-call parity is the spine of everything here:** `C − P = (F − X)/(1+r·t)` (stock: `≈ S − X + X·r·t − D`). It prices the third contract from any two and is the single check for arbitrage, implied rate, and implied dividend.
2. **Synthetics make calls/puts interchangeable via the underlying.** A position's vol risk lives in its **strikes & expiries**, not in call-vs-put labels; companion call/put have identical gamma & vega.
3. **Conversion = long underlying + short call + long put; Reversal = the mirror.** Do a conversion when the synthetic is rich, a reversal when it's cheap. Profit is captured at the *opening* leg.
4. **"Riskless" arbitrage is only low-risk.** Real exposures: leg/execution, **pin** (finish exactly at strike), **settlement** (carry mismatch ⇒ synthetic-futures delta `= 100/(1+r·t)`), and interest/dividend (rho & dividend risk).
5. **A box is borrowing/lending in disguise** — value `= (Xh−Xl)/(1+r·t)` = present value of strike distance; it eliminates the underlying leg, so it's even safer than a conversion. Box = bull vertical + bear vertical.
6. **A roll (jelly roll) is a dividend-vs-interest trade across expiries** — value `= X/(1+rs·ts) − X/(1+rl·tl) − D`, ≈ `X·r·t − D`; only valid where the underlying is identical across months (stock options). Roll = call calendar − put calendar.
7. **American call early exercise is dividend-driven and rare:** exercise *only* the day before ex-dividend and *only* if **dividend > volatility value + interest value**. No dividend ⇒ never exercise a call early ⇒ American call = European call.
8. **American put early exercise is interest(carry)-driven:** exercise when **interest value > volatility value + dividend value**; it can be optimal on any day, but never inside the pre-ex-div **blackout** of `dividend/(X·r/365)` days.
9. **The early-exercise premium** (American − European) grows as options go deeper ITM and is **larger at lower volatility**; it plateaus for stock options but grows without bound for stock-type-settled futures options. Optimal exercise ⇔ **value = parity and delta = 100**.
10. **Hedging an underlying (Ch.17, not in this file — verify):** protective put = synthetic long call (pay premium, cap downside, stay long upside, long vol); covered call = synthetic short put (collect premium, cap upside, keep most downside, short vol); collar/fence = both at once, ~costless (long put financed by short call), boxing P&L into a corridor with compressed net delta.