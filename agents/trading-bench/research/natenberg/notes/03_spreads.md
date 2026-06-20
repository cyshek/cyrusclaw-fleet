# Natenberg — Batch 3 Study Notes: Spreads & Volatility Strategies

**Source:** `research/natenberg/batches/03_spreads.txt` (5,587 lines), *Option Volatility & Pricing*, 2nd ed.
**Chapters actually covered in this batch:** tail of **Ch. 9** (Risk Measurement II — higher-order Greeks), **Ch. 10** (Introduction to Spreading), **Ch. 11** (Volatility Spreads), **Ch. 12** (Bull & Bear Spreads), **Ch. 13** (Risk Considerations — *partial*; file ends mid-chapter at the "Adjustments" worked example, on the line *"Which method is best?"*).

> **⚠️ SCOPE CORRECTION (verify against batch map):** The subagent brief said this batch covers chapters 10–14 including **Synthetics (synthetic underlying/options, iron butterflies & condors, conversions/reversals, put-call parity)**. **That material is NOT in this file.** Grep confirms zero occurrences of `synthetic`, `conversion`, `reversal`, `iron`, `box`, or `jelly roll`. Chapter 14 (Synthetics) and the rest of Ch. 13 must spill into **Batch 4**. So the put-call-parity / conversion-reversal section requested in the brief **cannot be written from this batch** — I've put a placeholder section at the end noting exactly what's deferred, plus the parity facts that *are* derivable from the calendar-spread rho discussion here. Flagging so the Batch 4 note picks up the slack.

Throughout, sign conventions: **+gamma** = profits from movement / long premium; **−gamma** = profits from a quiet market / short premium. Gamma and theta **always** have opposite signs (movement helps ⇒ time hurts, and vice versa). **+vega** = helped by rising implied vol; **−vega** = helped by falling implied vol. "Delta neutral" = initial directional bias ≈ 0.

Garbled OCR bits are flagged inline as **(verify: …)**.

---

## 0. Chapter 9 tail — higher-order Greeks (context for the spread chapters)

The batch opens mid-Ch. 9. Key carryover facts the spread chapters lean on:

- **Gamma, theta, and vega of an option are all greatest at-the-money (ATM)** and decay as the option goes deep ITM or far OTM. This is the single most-used fact in Ch. 11–13 (it's why ATM options dominate butterfly/calendar/vertical construction).
- **As time to expiration shrinks, the theta of an ATM option *increases*** (decay accelerates into expiry). This is the engine of the calendar spread.
- **Longer-dated options have larger vega** than equivalent short-dated options (a vol change moves the long-dated leg more). Also the engine of the calendar spread (opposite leg of the same trade).
- **Volga (vomma)** = sensitivity of vega to a change in vol (∂vega/∂vol). Re-used in Ch. 13 to explain why long butterflies (+volga) outperform short straddles (≈0 volga) and ratio spreads (−volga) under big vol moves.
- **Vanna / charm** mentioned as cross-Greeks (∂delta/∂vol and ∂delta/∂time). ATM vega is roughly **constant w.r.t. changes in vol** (volga≈0 ATM) — used repeatedly.

**Quant remember:** every spread's behavior in this batch reduces to *where on the strike axis the constituent options sit*, because gamma/theta/vega peak ATM. Memorize the ATM-peak shape and you can reconstruct any spread's Greek profile.

---

## Chapter 10 — Introduction to Spreading

- A **spread** = a position of opposing contracts (long vs. short) designed to profit from a *relationship* (direction, vol, time, or rate) while reducing exposure to factors you don't have a view on. It hedges out the risk you can't predict and isolates the one you can.
- **Spread orders quote as a single bid/ask** for the whole package regardless of how the individual legs are priced — for a straddle quoted 6.25/6.75, the market maker is indifferent whether the call is 3.75 & put 3.00 or any other split, as long as the legs sum to the package price. Common spreads (straddle, strangle, butterfly, simple vertical, calendar) can usually be executed **all at once at one net price**.
- **Execution mechanics:** electronic exchanges accept the simple spread types natively; **complex / unusual-ratio spreads (butterflies, Christmas trees, odd ratios) often must be legged in or routed to a broker / open-outcry desk.** Spread contingency order types listed: All-or-none, Fill-or-kill, Immediate-or-cancel, Market-if-touched, Market-on-close, Not-held, One-cancels-the-other, Stop-limit, Stop-loss.
- **Double-check every order** — a spread carries a lot of fields (qty, month, strike, type, buy/sell) and miscommunication is easy.

**Quant / paper-account note:** On a basic paper options account you typically *can* submit single-leg and the simplest multi-leg spreads, but **multi-leg net-price execution and the exotic contingency types may not be supported** — you may have to leg in manually and wear the slippage. Plan backtests/paper fills accordingly.

---

## Chapter 11 — Volatility Spreads

A **volatility spread** expresses a view on *how much* the underlying moves (and on implied vol), not *which way*. Therefore **all volatility spreads are constructed ≈ delta-neutral.** Once a position carries a large delta, directional risk dominates and it's no longer a vol spread. The four-quadrant taxonomy:

| Gamma | Vega | Helped by |
|---|---|---|
| + | + | More volatile underlying **and** rising implied vol |
| − | − | Quieter underlying **and** falling implied vol |
| + | − | More volatile underlying **but** falling implied vol |
| − | + | Quieter underlying **but** rising implied vol |

Only **calendar spreads** live in the bottom two (split gamma/vega) rows; nearly everything else has gamma and vega the *same* sign.

### Master summary table (Natenberg Fig. 11-30, reproduced)

| Spread | Δ\* | Γ | Θ | Vega | Downside | Upside |
|---|---|---|---|---|---|---|
| Long straddle | 0 | + | − | + | Unlimited reward | Unlimited reward |
| Long strangle | 0 | + | − | + | Unlimited reward | Unlimited reward |
| Short butterfly | 0 | + | − | + | Limited reward | Limited reward |
| Short condor | 0 | + | − | + | Limited reward | Limited reward |
| Call ratio spread (buy > sell) | 0 | + | − | + | Limited reward | Unlimited reward |
| Put ratio spread (buy > sell) | 0 | + | − | + | Unlimited reward | Limited reward |
| Short straddle | 0 | − | + | − | Unlimited risk | Unlimited risk |
| Short strangle | 0 | − | + | − | Unlimited risk | Unlimited risk |
| Long butterfly | 0 | − | + | − | Limited risk | Limited risk |
| Long condor | 0 | − | + | − | Limited risk | Limited risk |
| Call ratio spread (sell > buy) | 0 | − | + | − | Limited risk | Unlimited risk |
| Put ratio spread (sell > buy) | 0 | − | + | − | Unlimited risk | Limited risk |
| **Long calendar spread** | 0 | **−** | **+** | **+** | Limited risk | Limited risk |
| **Short calendar spread** | 0 | **+** | **−** | **−** | Limited reward | Limited reward |

\* All initially ≈ delta neutral. Note the two calendar rows are the *only* ones where Γ and vega disagree in sign.

---

### 11.1 Straddle

- **Construction:** same strike, same expiry, one call + one put. **Long straddle** = buy the call + buy the put (ATM). **Short straddle** = sell both.
- **Greeks (long):** Δ≈0, **+Γ, −Θ, +vega.** Short straddle: **−Γ, +Θ, −vega.**
- **Market view:** long straddle wants a **big move either direction AND rising implied vol**; short straddle wants the market to **sit still AND implied vol to fall.**
- **P&L at expiration:**
  - Long: cost = call premium + put premium = the debit *D*. **Breakevens = strike ± D.** Max loss = *D* (if it pins the strike). **Profit unlimited up, large/"unlimited" down** (bounded only by underlying→0).
  - Short: mirror — max profit = credit received (pins strike), **unlimited risk both directions.**
- **When to use / risk:** Natenberg's repeated warning — **straddles & strangles are the riskiest of all spreads**, long *or* short, because they carry the **largest gamma and vega** and thus the **least margin for error.** Losing slowly day-after-day on a long straddle that doesn't move hurts as much as losing all at once on a short straddle that gaps. The *direction* of profit is secondary; the *magnitude* of the move is what matters.

### 11.2 Strangle

- **Construction:** same expiry, **different strikes**, OTM call + OTM put. **Long strangle** = buy OTM put (lower strike) + buy OTM call (higher strike). **Short** = sell both.
- **Greeks:** identical *signs* to straddle (long: +Γ, −Θ, +vega; short: −Γ, +Θ, −vega) but **smaller magnitudes** per dollar because the legs are OTM.
- **P&L:** Long strangle — two breakevens further apart than a straddle: **lower strike − debit** and **upper strike + debit**; cheaper to put on, needs a *bigger* move to pay. Max loss = debit, realized anywhere **between** the two strikes at expiry. Short strangle — credit kept if underlying finishes between the strikes; **unlimited risk** outside.
- **Use/risk:** same "riskiest spread" caveat as straddle. Cheaper long premium but lower probability of profit; short strangle collects less but has the same unlimited tails.

### 11.3 Butterfly

- **Construction:** three **equally spaced** strikes, all same type (all calls *or* all puts), same expiry, **fixed ratio 1 × 2 × 1.** **Long butterfly** = buy 1 wing (low) − sell 2 body (middle) + buy 1 wing (high). Short = reverse. Example: +1 Mar 90c / −2 Mar 100c / +1 Mar 110c.
- **Greeks (long, body ATM):** Δ≈0, **−Γ, +Θ, −vega** → behaves like a **short straddle but with capped risk.** Short butterfly: +Γ, −Θ, +vega → like a long straddle with capped reward.
- **P&L at expiration (this is the cleanest in the batch — worked example):**
  - Long fly worth **0** if underlying ≤ low wing or ≥ high wing; worth its **maximum = the strike spacing** (e.g. 10.00) if underlying pins the **body** strike. Value is always in **[0, strike-spacing]**, so a long fly always costs a (small) debit.
  - **Max profit = (strike spacing − debit paid)**, achieved at the body. **Max loss = debit**, outside the wings. Two breakevens = body ± (something < spacing); piecewise-linear tent shape.
- **Call fly = put fly (European):** a 90/100/110 *call* butterfly and a 90/100/110 *put* butterfly with identical strikes/expiry have **identical payoffs**; if they trade at different prices there's an arbitrage (buy cheaper, sell dearer). *(Caveat for American options + early-exercise/borrow risk.)*
- **Use/risk:** the go-to substitute for a short straddle when you **like the short-vol thesis but can't stomach unlimited loss.** Because risk is capped, flies are **traded in much larger size** than straddles (e.g. 300×600×300 fly can be *less* risky than 100 short straddles). **Size ≠ risk** — risk depends on structure, not just contract count.

### 11.4 Condor

- **Construction:** **four** strikes, all same type, same expiry, **ratio 1×1×1×1.** Equal spacing between the two *lowest* strikes and between the two *highest* (the middle gap can differ). Body = the two inner strikes, wings = two outer. **Long condor** = buy both outer wings, sell both inner body strikes. (A condor is a butterfly with its single body strike split into two → "a strangle with limited risk/reward," vs. the butterfly being "a straddle with limited risk/reward.") **Butterflies & condors together = "wingspreads."**
- **Greeks (long):** Δ≈0, **−Γ, +Θ, −vega** (same signs as long fly; flatter, wider profit zone).
- **P&L:** value bounded in **[0, spacing between the two higher (or two lower) strikes]**. Max value when underlying finishes **between the two inner strikes** (a *plateau*, wider than the fly's single peak). Buyer pays a debit expecting a pin between the inner strikes; seller collects expecting a finish outside the wings.
- **Use:** lower gamma/vega than a butterfly → even gentler P&L, wider sweet spot, smaller max profit. Good when you want short-vol exposure over a *range* rather than a point.

### 11.5 Ratio spread (and backspread / frontspread)

- **Construction:** buy and sell **unequal** numbers of the same-type, same-expiry options, sized ≈ delta-neutral. The point is an *asymmetric* P&L — pick the side you think is more likely.
- **Two families:**
  - **Buy more than you sell** (e.g. +3 Oct 105c / −1 Oct 95c) → **"backspread."** **+Γ, −Θ, +vega.** Wants movement / rising vol. Worked example (underlying 100, expiry P&L): at 80 → +3.00, at 100 → −2.00, at 120 → +23.00. **Profit unlimited on the favored side** (upside for a call backspread), small loss if it sits still, small profit on the wrong-way big move. **A delta-neutral "buy-more" ratio spread should always be put on for a CREDIT** (under a standard pricing model).
  - **Sell more than you buy** → **"frontspread."** **−Γ, +Θ, −vega.** Acts like a **short straddle but with limited risk on one side** (limited downside risk if you sold more calls; limited upside risk if you sold more puts) and **unlimited risk on the other.** Typically a debit when selling more than buying. *(Terms "backspread/frontspread" are archaic; most traders just say "ratio spread, buy/sell more, ratio X:Y.")*
- **Call ratio (buy>sell):** limited reward downside, **unlimited reward upside.** **Put ratio (buy>sell):** **unlimited reward downside,** limited upside.
- **⚠️ Direction-inversion risk (Ch. 12 detail, but applies here):** a ratio spread's delta is **not stable.** A negative-gamma ratio (sell>buy) can **flip from + to − delta** if the underlying runs (all legs → delta 100). A positive-gamma "buy>sell" ratio can flip the other way as **time passes or vol falls** (deltas migrate away from 50). So even a "bullish" ratio can become bearish. Volatility view must remain primary.

### 11.6 Christmas tree (ladder)

- **Construction:** mimics a **strangle** with limited risk/reward on one side.
  - **Call Christmas tree:** buy (sell) one call at a lower strike, and sell (buy) **one call each at two higher strikes.** Example long: +1 Oct 90c / −1 Oct 95c / −1 Oct 105c.
  - **Put Christmas tree:** buy (sell) one put at a higher strike, sell (buy) one put each at **two lower strikes.**
  - All same type, same expiry, strikes chosen for ≈ delta-neutral.
- **Greeks:** **Long Christmas tree** (1 bought, 2 sold) → like a **short strangle with limited risk one side**: **−Γ, +Θ, −vega.** **Short Christmas tree** (1 sold, 2 bought) → like a **long strangle with limited profit one side**: **+Γ, −Θ, +vega.**
- **P&L:** non-symmetric (skewed tent/strangle shape). Same general rule as ratio spreads: *more bought than sold ⇒ +Γ/−Θ/+vega; more sold than bought ⇒ −Γ/+Θ/−vega.*
- **Use:** when you want strangle-like vol exposure but with a directional lean and a capped tail on the side you fear.

### 11.7 Calendar (time) spread — the special case

- **Construction:** **same strike, same type, two different expiries.** **Long calendar** = **buy the longer-dated, sell the shorter-dated** option (e.g. +1 June 100c / −1 April 100c). Short calendar = reverse. Best with **ATM (ideally at-the-forward) strikes**, where time value — and therefore the spread's value — is maximized.
- **Greeks — the unique one:** **Long calendar = −Γ, +Θ, +vega.** (Short calendar = +Γ, −Θ, −vega.) **This is the only common vol spread where gamma and vega have *opposite* signs.**
- **Why:** the short-dated ATM option **decays faster** (theta accelerates near expiry) → you profit from time if the market sits → **−Γ / +Θ.** Simultaneously the long-dated leg has **bigger vega** → a rise in implied vol widens the spread → **+vega.** So a long calendar **wants two "contradictory" things at once: a quiet underlying (so the front decays) AND rising implied vol (so the back inflates).** This really happens — e.g. a scheduled announcement (CEO statement, earnings) where nothing moves *now* but the market prices in future movement → implied vol rises while spot is flat → calendars widen. If the event turns out irrelevant, implied vol collapses → calendars narrow.
- **P&L shape:** **limited risk, limited reward** both directions. Value **peaks when the underlying sits at the strike** at front-month expiry (both legs ATM = max time value in the back leg, front leg worthless). A **big move either way collapses the spread** (the long leg eventually loses its time value too). Rising implied vol widens it; falling implied vol narrows it.
- **Stock vs. futures wrinkle:** in **stock** options every expiry shares one underlying (e.g. GE stock), so the legs always track. In **futures**, different option expiries can have **different underlying futures contracts** (e.g. March option → March future, June option → June future) which can diverge. To isolate vol, **hedge the calendar with an offsetting futures calendar spread** sized delta-neutral (e.g. long 10 June calls/short 10 March calls ≈ +500/−500 deltas → buy 5 March futures, sell 5 June futures). Not needed/possible in stock options.
- **Interest-rate & dividend sensitivity (the rho facts that ARE in this batch):**
  - **Long *call* calendar (stock): +rho** (rising rates lift the longer-dated forward more → spread widens). **Long *put* calendar: −rho.** Short calendars flip the signs.
  - **Dividends act opposite to rates:** higher dividends **narrow** a call calendar, **widen** a put calendar (and vice versa). Natenberg: a call calendar has "negative dividend risk," a put calendar "positive dividend risk."
  - Magnitude scales with the **gap between expiries** (6-month gap >> 1-month gap). Push rates high enough and a put calendar can even go **negative**; push dividends high enough and a call calendar can too.
  - **Short-squeeze caveat:** a no-dividend call calendar should always be worth ≥ carry cost — *unless* you can't borrow stock to carry the short, in which case you may be forced to exercise the long leg early and forfeit its time value.

### 11.8 Time butterfly (time fly)

- **Construction:** same strike, same type, **three different expiries**, roughly equal time between them. Wings = outer expiries, body = inner expiry. = simultaneously **buying one calendar spread and selling another that share a common month.** Example: +1 May 100c / −2 June 100c / +1 July 100c = (sell May/June calendar) + (buy June/July calendar).
- **Logic:** since the *short-term* calendar is worth more than the *long-term* calendar (front decay is faster), buying the body / selling the wings (i.e., buying the short-term calendar, selling the long-term one) **nets a debit.** *(File truncates mid-explanation here — text cuts off at "Because the entire position will result…" — verify the exact sign of the resulting cash flow in the full chapter, but the construction and the "short calendar worth more than long calendar" reasoning are explicit.)*

### 11.9 Diagonal spread

- **Construction:** like a calendar but the two legs have **different strikes** (different expiries *and* different strikes). Can be 1:1 or ratioed.
- **Behavior:** too many variants to generalize — **each diagonal must be analyzed on its own.** The **one** generalizable case: a **1:1 diagonal, same type, with the two legs at approximately equal deltas behaves almost exactly like a plain calendar spread** (−Γ, +Θ, +vega for the long version). Natenberg's examples pair e.g. +1 June 115c (Δ23) / −1 April 110c (Δ23).

### 11.10 General laws restated (Fig. 11-30 logic)

- All vol spreads ≈ **delta-neutral**; if delta gets big, it's a directional trade, not a vol trade.
- **Helped by movement ⇒ +Γ ⇒ "long premium."** Hurt by movement ⇒ −Γ ⇒ "short premium."
- **+Γ ⟺ −Θ** and **−Γ ⟺ +Θ**, always. You can't have both movement-help and time-help.
- **+vega** ⇒ helped by rising implied vol; in practice traders read vega as sensitivity to **implied** vol specifically.
- Risk ranking by gamma/vega magnitude: **straddles & strangles = biggest (riskiest); butterflies & condors = smallest; ratio spreads & Christmas trees in between.**

**Chapter 11 — what a quant should remember:**
1. Memorize the four-quadrant (Γ-sign × vega-sign) map; every named spread slots into it, and **only calendars split the signs.**
2. Construction shortcuts: butterfly = **1×2×1**, condor = **1×1×1×1**, both equally spaced, same type, same expiry; long = buy the wings. Ratio/Christmas-tree direction of Greeks is set purely by **bought vs. sold count** (buy more ⇒ +Γ/−Θ/+vega).
3. The calendar's "wants a quiet market AND rising IV" duality (−Γ, +Θ, +vega) is the one genuinely non-obvious profile — and in stock options it carries **rho** (call calendar +rho, put calendar −rho) and **dividend** risk because the two legs price off two different forwards.
4. **Size ≠ risk.** A 300-lot butterfly can be safer than a 100-lot short straddle. Always reason about the *structure's* tails, not the contract count.
5. Diagonals don't generalize — except the 1:1, equal-delta, same-type diagonal, which ≈ a calendar.

---

## Chapter 12 — Bull & Bear Spreads (directional)

There's no law requiring delta-neutrality. To take a **directional** view you can use the underlying, a naked option, or a directional *spread*. Natenberg's thesis: a good directional trader still respects the **volatility implications** of the chosen structure, or he's no better off than just trading the underlying.

### 12.1 Naked positions (the baseline to beat)

- Bullish: **buy calls** (low IV) or **sell puts** (high IV). Bearish: **buy puts** (low IV) or **sell calls** (high IV).
- **Problem = thin margin for error.** Long options lose if the market doesn't move *fast enough* to beat theta; short options give time-decay help but carry **unlimited** tail risk. Experienced traders prefer structures with a bigger margin for error — the same philosophy as for vol trades.

### 12.2 Directional use of ratio / butterfly / calendar spreads (and their inversion trap)

You can bias any of these by skewing the ratio or shifting the strikes — **but volatility stays the primary driver, so the directional character can invert:**
- **Ratio spread, biased bullish** (e.g. buy 2 June 100c / sell 3 June 110c, net +28 delta): if the market rockets to 130–140 all deltas → 100 and the position flips to **−100 delta** (bearish) even though you were right about direction. Conversely a "buy-more" ratio can flip from +Δ to −Δ as **time passes or vol falls** (deltas migrate away from 50; e.g. +28 → −25).
- **Butterfly, biased bullish:** put the *body* strike above spot (e.g. spot 100, buy the 105/110/115 fly → wants a finish at 110 → +delta). But if the market overshoots the body (→120) the fly **inverts to −delta** (now you want it to fall back). Below the body = bullish, above the body = bearish.
- **Calendar, biased bullish:** a long calendar wants the front to expire **ATM**, so set the strike **above** spot for bullish (June/April 110 calendar with spot 100 → +delta), **below** for bearish. Same inversion through the strike: a move from 100→120 flips a bullish 110 calendar to bearish.
- **Takeaway:** in all three, **−gamma forces the delta to invert once the underlying crosses the key strike.** If you want direction to *stay* your primary exposure, use a vertical.

### 12.3 Vertical spreads (the clean directional tool)

- **Construction:** two options, **same type, same expiry, different strikes.** **Bull spread = buy the lower strike, sell the higher strike** (works with calls *or* puts). **Bear spread = buy the higher strike, sell the lower strike.** A bull call spread is a **debit**; a bull put spread is also a debit *(in Natenberg's construction)* — and a call vertical and put vertical with the **same two strikes/expiry have ≈ the same delta and ≈ the same P&L profile.**
- **Greeks:** a vertical's gamma/vega/theta are **small** and, crucially, the **sign of the delta is stable across all conditions** (a bull spread stays bullish; it never inverts) — that's the whole point vs. the ratio/fly/calendar above. Max gamma/vega/theta occur **just below the lowest strike or just above the highest strike.**
- **P&L at expiration:** classic capped ramp. For strikes K_low < K_high, **max value = strike spacing** (e.g. 5.00). Bull spread → worth max if underlying ≥ K_high at expiry, worth 0 if ≤ K_low. **Max profit = spacing − debit; max loss = debit; one breakeven** inside the strikes. Wider strikes ⇒ more bullish/bearish (bigger delta) **and** bigger max profit/loss.
- **Why a vertical over the underlying:** **limited, defined risk.** 25 vertical spreads at Δ20 = 500 deltas just like 5 long futures, but the spreads have a **capped** loss while the futures are open-ended. You give up unlimited upside for a much smaller drawdown when wrong. And uniquely, options add a vol dimension: a correctly-volatility-priced bull spread can profit even if the market **fails to rise** (or in some cases falls), which an outright long cannot.

#### The key vertical-selection rule (very testable)

Given a directional view, **which strikes?** All same-delta verticals look equally directional, but they differ in *price/edge* and in *gamma sign*:

> **Always focus on the at-the-money (really at-the-forward) option. If implied vol is LOW, structure the spread so you are BUYING the ATM option. If implied vol is HIGH, structure it so you are SELLING the ATM option.**

Reasoning (from Ch. 6): the **ATM option is the most sensitive in total points to a vol change**, so it's the most over-/under-priced one. Worked example (8 wks, vol 25%): a bull call spread can be built as **95/100** (buy ITM, sell ATM) or **100/105** (buy ATM, sell OTM), both Δ20.
- The **95/100** spread is *always worth more* (2.91 vs 1.92 theoretical) because it profits in **more** scenarios — it pays even if the market just **sits still** (the long 95 is already ITM). It has **+Θ / −Γ.**
- The **100/105** spread **needs the market to rise** to pay → it has **−Θ / +Γ.** It's cheaper, so it **maximizes profit when right and minimizes loss when wrong** on a *big* move.
- So: **if your vol estimate > implied** (you expect movement) → prefer the **100/105** (the "needs movement" spread); **if your vol estimate < implied** (you expect quiet) → prefer the **95/100** (the "profits even if still" spread). At 20% IV you buy the ATM (100) → forced into 100/105; at 30% IV you sell the ATM (100) → forced into 95/100. The rule mechanically falls out.
- **Same logic for put verticals**: buy the ATM put when IV low, sell the ATM put when IV high. **The spread containing the ITM option is always priced higher than the one containing the OTM option** (it profits in more cases).
- A strong-view trader can also use **deep OTM verticals** (e.g. 115/120 with spot 100): tiny cost, tiny delta, but executable in huge size for a leveraged, capped-risk directional bet.

**Chapter 12 — what a quant should remember:**
1. **Vertical = the only directional spread whose delta sign can't invert.** Ratio/fly/calendar biases all flip through the key strike because of −gamma. If you want a *durable* directional bet, use a vertical.
2. The **buy-ATM-when-IV-low / sell-ATM-when-IV-high** rule is the master heuristic for choosing vertical strikes, and it simultaneously decides whether you end up with the +Θ ("profits if still") or −Θ ("needs movement") variant.
3. Directional size = (spread delta) × (number of lots); pick strike width for delta-per-spread, then size for total exposure. Wider strikes = more directional + bigger max P&L.
4. Verticals trade unlimited upside for capped downside vs. the underlying — and can win without the market moving your way if you got vol right.

---

## Chapter 13 — Risk Considerations (partial; ends mid-chapter)

The organizing idea: **theoretical edge** (expected profit if your inputs are right) is a single number, but **risk is multi-dimensional.** A spread can look great on edge and be unacceptable on one risk axis. You must hold edge roughly constant and then compare risks.

### 13.1 The five risks (definitions)

- **Delta (directional) risk** — wrong about direction. Delta-neutral removes initial bias but not all directional risk (only within a limited range).
- **Gamma (curvature) risk** — a **large move, either direction.** +Γ has no real gamma risk (movement helps); **−Γ can rapidly lose its edge on a big move.**
- **Theta (time-decay) risk** — the flip side of gamma. **+Γ ⟺ −Θ always.** A −Θ trader must ask: how long can the market stay quiet before my edge is gone?
- **Vega (volatility) risk** — wrong vol input / a move in implied vol. Every nonzero-vega position has it. Ask: how far can vol move against me before profit vanishes?
- **Rho (interest-rate) risk** — usually the **least important** input; matters mainly for calendars/long-dated/stock options.

Any spread with **nonzero gamma or vega has volatility risk.**

### 13.2 Comparing spreads at equal edge — the core worked example

Natenberg takes three negative-vega spreads (all options overpriced at 18% vol), **resized so all have ≈ equal theoretical edge (~6.0)**, then compares *risk*:
- **Spread 1 — short straddle** (−15 May 48c / −20 May 48p): biggest −Γ (−406) and −vega (−2.6). **Unlimited risk both directions.** Volga ≈ 0 (vega constant in vol).
- **Spread 2 — call ratio spread** (+35 May 50c / −70 May 52c, sell more): smallest −Γ (−165) and smallest −vega (−0.875) at *current* conditions. **Unlimited upside risk; flattens to a tiny profit on the downside.** **Negative volga** — vega gets *more* negative as vol rises (loss accelerates) and *less* negative as vol falls (profit decelerates). Best breakeven vol (~23%) but the advantage **evaporates at extreme vols** — at 30–40% it bleeds almost as fast as the short straddle.
- **Spread 3 — long put butterfly** (+100/−200/+100 May 46/48/50p): **limited risk both directions.** **Positive volga** — loss *decelerates* as vol rises, profit *accelerates* as vol falls → it **outperforms 1 & 2 under any *dramatic* vol move**, even though it loses faster than Spread 2 for *small* vol increases.
- **Verdict:** on pure gamma+vega risk, **Spread 3 (long butterfly) is best** (limited both ways + benevolent volga). **But practical drawbacks:** it's a **3-sided spread** → harder/costlier to execute (bid-ask, legging risk), and needed **huge size (100×200×100)** to match edge → **liquidity** constraint. If the fly is impractical, **Spread 2 beats Spread 1** decisively (far bigger margin for error on both price and vol). **Never the short straddle if you can avoid it.**

### 13.3 Breakeven volatility & volga

- **Breakeven (implied) volatility of a spread** = the vol at which the position shows zero P&L — a direct extension of single-option implied vol. Used to rank vol risk (Spread 1 ~21%, Spread 2 ~23%, Spread 3 ~21.5%).
- **Volga decides behavior under big vol moves:** +volga (long fly) = vol changes *help*; −volga (ratio, some diagonals) = vol changes *hurt* and accelerate losses; ~0 volga (ATM straddle, short calendar) = symmetric, vega constant.

### 13.4 Calendar / diagonal risk extras

A second worked set (Spreads 4–6: short put calendar, diagonal call spread, put diagonal ratio) and a stock-option set (Spreads 7–10: call/put calendars and diagonals) reinforce:
- Calendars/diagonals carry **rho and dividend risk** because the two legs price off **two different forwards**: **call calendars/diagonals → +rho, −dividend sensitivity; put calendars/diagonals → −rho, +dividend sensitivity.** Magnitude scales with the expiry gap. Usually small vs. gamma/vega, but matters at size.
- A **short calendar's vega is roughly constant (volga≈0)** — symmetric vol tradeoff; diagonal/ratio variants carry negative volga and can see vega flip sign at low vol.

### 13.5 "How much margin for error?" → size the trade to the edge

- No universal number — depends on the market and the trader. Better framing: **let the margin for error set the SIZE.** Small margin (e.g. spread implied 23% vs your 25% estimate) → trade **small** (10-lot). Large margin (implied 18% vs 25%, a rare cheap level) → trade **big** (100-lot). **Position size should scale with how much can go wrong before the edge flips.**

### 13.6 "What is a good spread?"

- **A good spread is not the one with the biggest profit when right — it's the one with the *smallest loss when wrong*** (within a reasonable margin for error). "Winning trades take care of themselves; losing trades that don't give back all your gains are what matter." Survival > maximization: a strategy that earns +$7k half the time and −$5k half the time has +$1k expectancy but **ruins you if the first −$5k hits when you only have $3k.** Never run a strategy where short-term bad luck ends your career.

### 13.7 Efficiency (gamma/theta ratio)

- Quick same-expiry risk-reward proxy: **efficiency = |gamma / theta|.**
  - **+Γ / −Θ position** (long premium): want this ratio **large** (max reward-per-decay).
  - **−Γ / +Θ position** (short premium): want this ratio **small** (min curvature-risk per time-reward).
- Example: Spreads 1/2/3 efficiencies 959 / 1,212 / 925 → for short-premium you want it small → **Spread 3 (925) best**, consistent with the full analysis. **Caveat:** efficiency only captures gamma/theta; once legs span **different expiries, vega/volga matter too** and you need fuller analysis.

### 13.8 Adjustments (chapter cuts off here)

- **Delta-neutralize with the underlying = a risk-neutral adjustment** (underlying has 0 gamma/theta/vega) → fixes delta without touching the other Greeks.
- **Adjusting with options changes delta AND gamma/theta/vega simultaneously** — you may unintentionally swap one risk for another. New traders forget this.
- Worked setup (truncation point): sell 20× 95/105 strangles (−32/+34 deltas → −40 initial). Market falls to 97 → deltas −39/+25 → position now **+280 delta.** To re-neutralize while holding, three choices: **(1) sell underlying, (2) sell calls, (3) buy puts** — and **"Which method is best?"** is exactly where this batch's text ends. *(Answer + full adjustment analysis presumably continues in Batch 4.)*

**Chapter 13 — what a quant should remember:**
1. **Hold edge constant, then compare risk.** Edge is one number; risk is a vector (Δ, Γ, Θ, vega, rho, + volga/dividend for split-expiry trades). Bigger size always inflates edge, so edge alone is meaningless without risk normalization.
2. **Margin for error sets position size**, not the other way round. Big cushion → big size; thin cushion → small size or pass.
3. **A good spread minimizes the loss when wrong.** Survival-first. The efficiency ratio |Γ/Θ| is a fast same-expiry screen, but breakeven-vol and **volga** (curvature of vega) decide who wins under *extreme* vol moves — long butterflies (+volga) are robust, ratio spreads (−volga) are fragile at the tails.
4. **Adjust with the underlying to keep other Greeks fixed; adjust with options only if you mean to change the vol profile too.**
5. Limited-risk structures (flies, condors, verticals) beat unlimited ones (straddles, strangles, naked) at equal edge **whenever you can execute the size/liquidity** — the practical cost of multi-leg execution is the main thing that pushes you back toward the simpler 2-sided trade.

---

## Synthetics / Put-Call Parity / Conversions-Reversals / Iron Flies & Condors — **DEFERRED to Batch 4**

**This material is not in Batch 3** (Ch. 14 begins after the file's truncation point). What the brief asked for here must be sourced from the next batch. For continuity, the parity-adjacent facts that *are* established in Batch 3:

- **Stock-option calls and puts react oppositely to rates & dividends** (rising rates: calls↑/puts↓; rising dividends: calls↓/puts↑) and the effect grows with time to expiry — this is the put-call-parity shadow that drives calendar-spread rho/dividend signs documented above. (Full parity identity *synthetic underlying = long call + short put, same strike/expiry*, and conversion/reversal arbitrage, are **expected in Batch 4** — flag and carry forward.)
- **Call butterfly = put butterfly** (same strikes/expiry, European) is the one explicit parity-style equivalence proven in this batch, enforced by no-arbitrage.

> **Action for Batch 4 note:** pick up synthetic long/short underlying, synthetic options, conversion (long stock + long put + short call) / reversal, box spreads, **iron butterfly** (= call spread + put spread / short straddle vs. long strangle financed) and **iron condor**, and the full put-call-parity identity. None are derivable from Batch 3 text.

---

## Paper-account feasibility (basic Alpaca-style paper options account)

- **Readily feasible:** long/short single options, **long & short verticals** (debit/credit call & put spreads), **long straddle/strangle**, **long butterfly/condor**, **long calendar/diagonal**. These are defined-risk or covered by standard approval and are the bread-and-butter of any paper options account.
- **May need higher approval / margin even on paper:** **short (naked) straddles/strangles**, **short butterflies/condors**, and **ratio spreads where you sell more than you buy** — these carry *unlimited* risk and on a real broker need the top options tier; a basic paper tier may block the naked legs. **Short calendars** and **diagonal ratios** likewise.
- **Execution-quality caveat (matches Ch. 10/13):** multi-leg **net-price** orders and exotic contingency types (MIT, OCO, not-held, stop-limit on spreads) may be **unsupported** on a basic paper API — you'll often **leg in** and eat slippage, which *understates* real-world cost in backtests. **3-/4-leg spreads (flies, condors, Christmas trees) are the most exposed** to this and to liquidity gaps.
- **Futures-options-specific items don't apply** to an equity/ETF paper account: the futures-calendar delta-hedge of a calendar spread, and the multiple-underlying-futures wrinkle, are **N/A** for stock/ETF options (single underlying per name) — but the **rho & dividend** sensitivities of stock-option calendars **do** apply and matter for any dated spread held through an ex-div or a rate move.

---

## Batch 3 — Top 10 durable lessons

1. **Every spread reduces to where its legs sit on the strike axis**, because gamma/theta/vega all peak ATM. Master the ATM-peak shape and you can reconstruct any structure's Greeks from memory.
2. **The four-quadrant map (Γ-sign × vega-sign) classifies every vol spread — and only calendars split the signs** (long calendar = −Γ, +Θ, **+vega**: wants a quiet underlying *and* rising implied vol simultaneously).
3. **Γ and Θ always have opposite signs.** Movement-help ⟺ time-hurt. No structure escapes this; "long premium" (+Γ/−Θ) vs. "short premium" (−Γ/+Θ) is the fundamental axis.
4. **Construction cheat-sheet:** butterfly = 1×2×1, condor = 1×1×1×1 (equal spacing, same type, same expiry, long = buy the wings); straddle = same strike call+put; strangle = OTM call+put; calendar = same strike, buy far/sell near; vertical = same type, two strikes, bull = buy lower. Ratio/Christmas-tree Greek-signs are set purely by **bought-vs-sold count** (buy more ⇒ +Γ/−Θ/+vega).
5. **Straddles & strangles are the riskiest spreads, long or short** — biggest gamma/vega, least margin for error. Limited-risk cousins (butterfly↔straddle, condor↔strangle, Christmas tree↔strangle, ratio↔straddle) cap the tail; **size ≠ risk** (a 300-lot fly can be safer than a 100-lot short straddle).
6. **Verticals are the only directional spread whose delta sign can't invert.** Ratio/butterfly/calendar directional biases all **flip through the key strike** because of −gamma, so use a vertical when you want a *durable* directional bet with defined risk.
7. **Vertical strike rule:** **buy the ATM option when implied vol is LOW, sell the ATM option when implied vol is HIGH** (the ATM option is the most mispriced in total points). This also decides whether you get the "+Θ profits-if-still" (e.g. 95/100) or "−Θ needs-movement" (e.g. 100/105) variant — pick the latter when your vol estimate exceeds implied.
8. **Calendars/diagonals carry rho & dividend risk** because their two legs price off two different forwards: **call calendar → +rho / −dividend; put calendar → −rho / +dividend**, scaling with the expiry gap. (Stock options share one underlying; futures calendars need a futures-spread hedge to isolate vol.)
9. **Compare strategies at equal theoretical edge, then judge risk** (a vector: Δ, Γ, Θ, vega, rho, plus **volga** and dividend for dated trades). **Volga** decides the tails: +volga (long butterfly) is robust to big vol moves; −volga (ratio spreads) is fragile. Efficiency = |Γ/Θ| is a fast same-expiry screen, but it ignores vega — once legs span different expiries you need full analysis.
10. **A good spread minimizes the loss when you're wrong, not maximizes the profit when you're right — and margin for error sets your size.** Survival-first: never run a strategy where one stretch of bad luck ends you. Big cushion (implied vol far from your estimate) ⇒ trade big; thin cushion ⇒ trade small or pass. Adjust delta with the **underlying** to leave the other Greeks untouched; adjust with **options** only when you deliberately want to reshape the vol profile.

---

*Note compiled from a full end-to-end read of `03_spreads.txt` (5,587 lines). Batch covers Ch. 9-tail → Ch. 13 (partial). **Synthetics / put-call parity / conversions-reversals / iron flies & condors are NOT in this batch — deferred to Batch 4** (see deferral section above). Source-text typos flagged inline with **(verify: …)**; the most material one carried in from the Batch-3 summary is a short-strangle row mistakenly printed with +gamma in the book text, which should be −gamma.*