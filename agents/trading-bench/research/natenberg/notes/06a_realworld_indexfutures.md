# Batch 6A — Stock Index Futures/Options (ch22) + Models and the Real World (ch23)

Source: `research/natenberg/batches/06a_realworld_indexfutures.txt` (~2617 lines, read end-to-end).
Scope note: batch is ch22 + ch23. The very tail spills into **ch24 Volatility Skews** (~lines 1980→end); I summarize that spillover briefly at the bottom but the real ch24 belongs to a later batch.
Paper-quant context. No trades, no scheduling. Read-only except this file.

---

## CHAPTER 22 — STOCK INDEX FUTURES AND OPTIONS

### How an index is built (price- vs cap- vs equal-weighted) and the DIVISOR

- **Index value = raw index value / divisor.** Divisor is set initially so the index starts at a round number (e.g. 100). `Divisor = raw index value / target index value`.
  - Example: raw price-weighted sum 150, target 100 → divisor 1.50. Raw cap sum 68,000, target 100 → divisor 680.
- **Price-weighted index** (e.g. Dow): each stock's weight ∝ its *price*. Raw value = sum of component prices.
- **Cap-weighted index** (e.g. S&P 500): each stock's weight ∝ its *market capitalization* (price × shares outstanding).
- **Equal-weighted index**: each stock has the same weight regardless of price/cap.

**Divisor adjustments** keep the index continuous/logical through corporate actions:
- **Stock split** in a *price-weighted* index: raw price drops, so divisor must be recomputed (`new divisor = new raw / target`) — investor's holding value didn't change, so the index shouldn't jump. (2-for-1 split of an 80 stock → divisor 1.50→1.10 in the example.)
- **Stock split in a CAP-weighted index: NO divisor change** — capitalization is unchanged by a split (price halves, shares double). This is a key asymmetry.
- **Component replacement** (company delisted/acquired/falls below threshold → replaced by a new one): divisor must be recomputed to keep the index continuous.
- Index calculators publish a press release announcing every new divisor + reason.

### Total-return indexes
- Traditional index: a dividend payout makes the component price (and thus the index) drop on ex-div day.
- **Total-return index**: dividends assumed *immediately reinvested*, so dividend-driven price declines do NOT lower the index. The divisor is adjusted on each dividend so the index holds.
  - Example: stock pays 1.00, opens down 1.00 ex-div → divisor nudged 1.50→1.49 so index stays 100.
- Best-known total-return index: German **DAX**. S&P 500 publishes both a price and total-return version; the price version is far more widely followed.

### Effect of a single component's move on the index (universal rule)
- **% change in index = (% change in stock) × (stock's weight in index).** Holds for price-, cap-, OR equal-weighted indexes.
  - New index = Old index × (1 + Σ %changeᵢ × weightᵢ).
- For a **price-weighted** index specifically, each 1.00 move in *any* component changes the index by `1.00 / divisor` (a CONSTANT point change per point, regardless of which stock or its level). Intuition: the smaller %-impact of a second point up is exactly offset by the stock's increased weighting.
- **Practical use — halted/stale stock:** the index uses each component's *last trade*, which may be stale (trading halt pending news, after-hours, etc.). A trader can re-estimate true index value by plugging the expected reopen price × that stock's weight. Two equivalent methods shown (apply weight×%move, or apply the known points-per-point factor). Gives a better-informed fair value before the stock reopens.

### Volume-Weighted Average Price (VWAP)
- The literal last trade can be an anomaly (tiny 300-share print at a wide-spread edge). Some exchanges set the closing component price via **VWAP** over a window before the close: `Σ(price×volume) / Σ(volume)`. That VWAP feeds the index calc, smoothing out the last-print noise.

### STOCK INDEX FUTURES — fair value / cost-of-carry / dividends

- In theory a long index future would take delivery of all component stocks in proportion; in practice **no index future is physically settled** (unmanageable, would need fractional shares). They are **cash-settled** at expiration: final cash payment = (expiration index value − prior day's futures settlement) × index point value (e.g. $100/point). After that both sides are flat and indifferent to later moves.
- **Fair forward/futures price (general):** `F = S × (1 + r×t) − D` — add carry (interest cost of buying now), subtract the dividends (benefit of owning now). For an index, dividends are NOT a single lump; they're spread across many stocks/dates. Exact F needs each div amount, pay date, weight, plus interest earnable on each div from pay date to maturity → complex.
- **Continuous-dividend approximation (treat dividend as a negative interest rate):**
  - **`F = S × [1 + (r − d) × t]`**, where `d` = average annualized dividend yield of the index (%).
  - Example: S=100, t=4mo, r=6%, d=2.25% → F = 100×[1+(0.06−0.0225)×4/12] = 101.25.
- **Approximation breaks for SHORT-dated contracts**: real index dividends arrive in *discrete, unevenly-spread bundles* (Fig 22-1, Dow daily div payout Oct–Dec). The flat "2.75% annualized" assumption can badly **overstate** the div payout if you enter late in the cycle after most divs already paid (true remaining payout ≈ 0) or **understate** it at other points. Fine for long-dated, dangerous for short-dated.

### Index arbitrage / program trading
- **Index arbitrage / program trading**: when the future deviates from fair value vs the cash basket, buy the cheap side / sell the rich side. Profit = mispricing, but **only fully realized at expiration**, where future & index converge.
  - **Buy program** = buy stocks, sell futures (effectively *borrowing* cash to hold stocks).
  - **Sell program** = sell stocks, buy futures (effectively *lending* cash).
  - Computers compute fair value and fire the basket orders → "program trading."
- **Risks of index arb:**
  - **Interest-rate risk** if not locked at a fixed rate — a rate move changes profitability. Buy program: rate ↑ hurts (you're borrowing); sell program: rate ↑ helps. Magnified for LONG-dated futures, negligible for short-dated.
  - **Dividend risk** — divs estimated, not guaranteed. Buy program: div ↑ helps; sell program: div ↑ hurts. Negligible in a broad index (hundreds of names), but in a **narrow index** even one firm's dividend change can flip profitability.
  - **Short-sale frictions** — sell programs need to short stock; may be prohibited, hard to borrow, and short stock may not earn full interest rebate.
- **AM vs PM expiration / "triple witching":** early program trades dumped huge **market-on-close** orders that disrupted prices. So most index futures/options moved to settle on **opening** prices of components (**AM expiration**) to spread out the matching; **PM expiration** (closing prices) survives on a few contracts. ETF options stay traditional PM. **Triple witching** = third Friday of Mar/Jun/Sep/Dec when index futures, options-on-futures, and cash-index options all expire together (cash-settled).

### Replicating an index, and the futures DELTA (settlement-risk hedge)
- To replicate: hold each stock at its index weight. Price-weighted → equal *number of shares* of each name replicates it; cap-weighted → does NOT (must weight by cap).
- Notional of a futures contract = index level × exchange multiplier (e.g. 100×$1,000 = $100,000).
- **Key subtlety — replicating the INDEX is NOT a perfect hedge of the FUTURE.** The stock side is **stock-type settlement** (P/L unrealized until you close), the futures side is **futures-type settlement** (daily variation cash, earns/pays interest). This mismatch = **settlement risk** (ch15 callback).
- **Treat the cash index as the underlying and give the future a DELTA.** Since `F = S×(1+r×t)` (ignoring divs), the future rises `1+r×t` per 1.0 index move ⇒ **futures delta = 1 + r×t**. To be delta-neutral, hold `(1+r×t)` units of the opposing cash position per future.
  - High r and/or long time → need MORE stock than the equivalent futures position. Near expiry or low r → stock and futures holdings nearly identical. ⇒ the arb's stock leg must be re-adjusted as time passes / rates move.
  - Worked: 4mo, r=6% → factor 1.02 (hold 2% extra stock vs pure replication); 3mo → 1.015 (1.5% extra).

### Bias in the index futures market (one-sided / structural cheapness)
- Equity portfolio managers are overwhelmingly **long** stock and rarely short. To hedge, they **sell index futures** (cheaper/faster than dumping the whole portfolio). This constant selling pressure **depresses futures below theoretical fair value.**
- Arbs can't fully neutralize it: replicating an index isn't always possible, and the arb on the other side is *long* futures → must *short* stock (prohibited in some markets, never as easy as buying, may not earn full interest). ⇒ buying/selling pressure is asymmetric. **Net: persistent downward pressure on index futures prices** worldwide. Inflated futures happen but are the exception.

### STOCK INDEX OPTIONS — two flavors

**(A) Options on index FUTURES**
- Evaluated like any futures option. Exercise/assignment → a **futures position** (then margined/varied), EXCEPT when option and underlying future expire simultaneously → cash settle, no position.
- Example walk-through: long Feb 1000 call, Feb is a *serial* month so underlying = **March** future. If March fut = 1025 at Feb expiry → exercise → long March future bought at 1000, account credited 25 pts × $100 = $2,500; assigned party gets short future, debited $2,500. Both still hold market positions (opposite directions).
- A March 1000 call at March expiry → **AM expiration** (March future settles on opening component prices). ITM → auto cash-settle = (opening index − strike) × multiplier; e.g. open 1040, strike 1000, $100 mult → +$4,000 long / −$4,000 short, then both flat.
- These are **American** (futures options) → some early-exercise value, but: small if **stock-type settlement** (US), effectively zero extra value if **futures-type settlement** (most of Europe/Far East).

**(B) Options on a CASH index**
- First cash index options: CBOE, March 1983 (the OEX = "Options Exchange Index," 100 big US names; later renamed **S&P 100** but kept ticker OEX). Originally American; early-exercise caused unforeseen risk + valuation headaches ⇒ **all exchange-traded cash index options are now EUROPEAN** (no early exercise).
- **No underlying position on exercise** — purely cash settled at expiration: ITM holder credited (|index − strike|)×mult, seller debited same. Typically **AM expiration** (opening component prices).
- **Hedging a cash-index option:** holding the full basket is impractical (many names, fractional shares, constant rebalancing). Practical hedge = the **index futures contract expiring at the same time** as the option; if none lines up, use the **nearest future beyond** option expiry. (Jan/Feb/Mar options → Mar future; Apr/May/Jun → Jun future; etc.) Imperfect (future ≠ cash, can trade off-fair-value) but practical.
- **What underlying price to evaluate with?** For quarterly (Mar/Jun/Sep/Dec) options carried to expiry, cash index & future *converge* at expiry, so **use the futures price as the underlying** — also theoretically right because option values derive from the *forward* price, and the future IS the traded forward. If both cash and futures options expire together on the same index, they're effectively identical and trade at the same prices (tiny early-exercise wrinkle for deep ITM American futures options).
- **Serial-month cash options (no matching future)** — harder. Two ways to get the right forward:
  1. Back out from the next future: `F_Dec = F_Nov×(1+r×t) − D` ⇒ `F_Nov = (F_Dec + D)/(1+r×t)` — but needs the Nov→Dec dividend estimate.
  2. **Easier, preferred:** imply the forward from option prices via **put–call parity**. `C − P = (F − X)/(1+r×t)` ⇒ `F = (C−P)×(1+r×t) + X`. Use a near-ATM call/put. Worked: Nov 1000 call 34.80, put 29.85, 2mo, 6% → F_Nov ≈ 1005. Then if Dec future = 1010, the Nov forward = Dec future − 5.00; as Dec future moves, price Nov cash options off (Dec future − 5).
  - Can cross-check Dec option prices against the Dec future via parity; the "roll" = difference between Dec and Nov synthetics.

### What a quant should remember (ch22)
- **Cost-of-carry for an index = `F = S×[1+(r−d)×t]`** with d the average dividend yield; exact version subtracts the discrete, interest-accumulated dividend stream. The continuous-yield shortcut is fine long-dated, **lies short-dated** because real dividends are lumpy/uneven.
- **A futures position has a delta of `1+r×t` vs the cash index** — hedging cash with futures (or replicating a future with stock) is NOT 1:1, and it drifts with time and rates. The reason it isn't a perfect hedge is the **stock-type vs futures-type settlement mismatch = settlement risk.**
- Index futures carry a **structural downward bias** (portfolio hedgers chronically sell them, arbs can't fully offset because shorting the basket is hard) → empirically they trade *below* fair value more often than above.
- Index products are **cash-settled**; most use **AM (opening-price) expiration**; **triple witching** clusters expiries on the 3rd Friday of the quarter-end month.
- Cash index options are **European**; the practical underlying/hedge is the **matching index future**, and you can **imply the forward via put-call parity** when no matching future exists.
- Divisor mechanics: splits move a *price-weighted* divisor but NOT a *cap-weighted* one; total-return indexes adjust the divisor on every dividend.

---

## CHAPTER 23 — MODELS AND THE REAL WORLD  *(the intellectual-honesty chapter)*

**Framing.** Two risks with a pricing model: (1) **wrong inputs** (handled via the Greeks — delta/gamma/theta/vega/rho — esp. volatility, the one input you can't observe), and (2) **the model itself is wrong** because its *assumptions* are false/unrealistic. Ch23 is entirely about (2).

**The assumptions baked into traditional models** (Black-Scholes / its variants / Cox-Ross-Rubinstein):
1. **Markets are frictionless:** (A) underlying freely buyable/sellable without restriction; (B) unlimited borrow/lend at one single rate for all; (C) no transaction costs; (D) no taxes.
2. **Interest rates constant** over the option's life.
3. **Volatility constant** over the option's life.
4. **Trading is continuous** — no gaps in the underlying price (a diffusion process).
5. **Volatility is independent of the underlying price** (vol doesn't depend on whether the market is rising/falling).
6. **Percent price changes are normally distributed** over small intervals ⇒ **prices lognormally distributed at expiration.**

Natenberg then demolishes each one. Below: **how it breaks** + **what practitioners DO about it.**

---

### Assumption 1 — Markets are frictionless → FALSE

**1A. Underlying not freely tradable.**
- **Futures price limits / locked-limit markets:** when a future hits its daily limit, trading halts (possibly until next day). Workarounds: trade the **cash** market; trade a **futures spread** where one leg isn't locked (buy June/March spread when June is limit-up, then cover the March leg → left long June); or trade **synthetic futures via options** if the option market isn't locked.
- **Stock-index circuit breakers:** exchanges halt trading when an index moves ±X% intraday; rules specify halt duration per % move.
- **Short-sale restrictions** on stock (can't always short, or only under conditions). If you can't freely short, **put prices inflate vs calls**, and conversions/reversals look mispriced. *Practitioner move:* many stock-option traders **carry some long stock as standing inventory** so they can always sell when needed.

**1B. Can't freely borrow/lend, and borrow rate ≠ lend rate (the more serious flaw).**
- **Margin can force liquidation:** even funded traders may face *increased margin* and be unable to meet it → forced to close *before expiration*. Every model (even American ones) assumes you can *always choose to hold to expiry*; the inability to fund margin makes model values unreliable. *Practitioner move:* judge a position not just by max potential loss but by **how much margin it could demand over its life.**
- **Borrow rate > lend rate:** you borrow margin at one rate but the clearinghouse pays you a lower rate on deposits — the model is blind to this spread. The wider the borrow/lend gap, the less reliable model values.

**1C. Taxes** — usually secondary for most traders; rarely makes one strategy beat another (exceptions: portfolio management, dividend-tax-sensitive strategies).

**1D. Transaction costs — a serious, always-present flaw.**
- Brokerage, clearing, exchange-seat costs hit on **entry, exit, AND every adjustment.** A strategy that looks good on model values may be a loser net of costs. *Critical for delta-neutral, high-gamma positions* that need frequent rehedging — cumulative transaction costs can swamp the theoretical edge. *Practitioner move:* fold rehedge frequency × cost into the decision; high-gamma names cost more to keep neutral.

---

### Assumption 2 — Interest rates constant → FALSE (but usually a minor risk)
- Real traders constantly borrow/lend as they open/close, and futures-option traders face changing margin/variation. They typically finance via the clearing firm at a **variable rate** (clearer acts as a bank). And *which* rate applies is ambiguous: borrow rate vs lend rate vs **short-stock rebate** (which depends on borrow difficulty).
- **Why it's usually minor:** rate impact scales with time to expiry; most traded options are short-dated (<1yr), so rates would have to move *dramatically* to matter except for **deep-ITM long-dated** options (high **rho**). Option value is far more sensitive to underlying price and to volatility than to rates.
- *Practitioner move:* don't ignore rho on **long-dated deep-ITM** options (now that LEAPS-type listings exist). For stocks: rate ↑ → forward ↑ → calls worth more, puts worth less. (Figs 23-1/23-2 show value & rho vs rates and vs time.)

---

### Assumption 3 — Volatility constant → FALSE; and option value is PATH-DEPENDENT under hedging
- Real vol arrives in **clusters** — high-vol and low-vol regimes — that *average* to one number, but the model only sees the average and is **indifferent to the order** in which vol unfolds.
- **The killer demonstration (Figs 23-3/23-4/23-5):** two underlying paths, *same* 28% close-to-close realized vol, mirror images (one falling-vol, one rising-vol), both start & end at 100. BS values the 100 straddle at **10.46**. But running an actual **dynamic-hedging simulation**:
  - **Falling vol** (big moves early, calm late) → straddle realizes only **5.94**.
  - **Rising vol** (calm early, big moves late) → straddle realizes **12.82**.
  - ⇒ For an **ATM** option, you profit most when **high vol coincides with high gamma**, and ATM gamma is **highest near expiration**. So late-life vol (rising-vol path) is worth far more than early-life vol → ATM straddle beats BS in rising-vol, lags in falling-vol. (Mirror logic: ATM theta is also highest late, so a calm late period in the falling-vol case bleeds the straddle below BS.)
  - **OTM options are the OPPOSITE**: OTM gamma is highest **early**, so OTM options are worth *more* in a falling-vol (big-moves-early) world and *less* in rising-vol. (80 put / 120 call: BS 0.21 / 0.54; falling-vol 0.44 / 0.89; rising-vol 0.05 / 0.14.)
- **Conclusion:** an unhedged option held to expiry is **path-INdependent** (only terminal price matters), but a **dynamically hedged** option is **path-DEPENDENT** — same realized vol, different value depending on *when* the movement happened. BS is still right *on average*: it's a **probabilistic** model — average over very many random paths at 28% vol converges to the BS value. Any single path almost surely differs.
- *Practitioner responses:* **stochastic-volatility models** exist (treat vol as random) but add complexity and aren't widely used. **Interest-rate products inherently change vol over time** (a bond pulls to par at maturity — not a random walk; different maturities have different rate sensitivities) → spawned **special interest-rate models**, BS-type models are ill-suited there.

---

### Assumption 4 — Trading is continuous (diffusion, no gaps) → FALSE; the real world is JUMP-DIFFUSION
- **Diffusion process** (Fig 23-6a): continuous, no gaps — like temperature (to go 25°→22° it must pass through 24°,23°). BS assumes this AND that you can therefore **rehedge delta-neutral at every instant** — the foundation of capturing theoretical value.
- Reality: exchanges aren't open 24/7 → **overnight gaps**; news hits intraday → instantaneous gaps. **Jump process** (Fig 23-6b): price sits, then instantaneously jumps (like a central bank discount-rate change). Real markets = **jump-diffusion** (Fig 23-6c): mostly smooth, occasional gap.
- **Why gaps hurt (the gamma story):** short an ATM straddle, underlying gaps 100→105. Negative gamma + **no chance to adjust** during an instantaneous move = damage. **Severity explodes near expiration and in low-vol markets** because ATM gamma rises as expiry nears AND as vol falls. The short calls go deep ITM acting like short underlying (delta ~100), and there was no opportunity to buy as it rose. (Fig 23-7: a 100→105 gap adds ~4.37 to a 1-day straddle but only ~0.94 to a 1-year one at 15% vol; the increase is bigger at 15% vol than 25% vol.)
- **Gap sign vs your gamma:** a gap **hurts negative-gamma** positions (can't adjust through the jump) and **helps positive-gamma** positions (you got the move for free). 
- **Real-world implications of gaps:**
  - **At-the-money options close to expiration in a low-vol market are among the riskiest options that exist** (highest gamma, gap-vulnerable). Selling large numbers of them is dangerous; new traders are warned off, and risk managers won't tolerate even experienced traders being short big ATM size into expiry.
  - Because gaps mostly bite the highest-gamma (near-expiry ATM) options, **experienced traders trust model values less and lean on experience/intuition as expiration approaches** — adjust the model where it's known to be wrong.
  - **The diffusion assumption makes BS systematically UNDERvalue options in the real world.** Evidence: average **implied vol > average historical/realized vol** over long periods in almost every market — i.e. option buyers "overpay" relative to a gap-free model. Part is a hedging premium, but part is that the real world *has* gaps the model ignores, so true option value is genuinely higher than gap-free BS says.
- *Practitioner responses:* a **jump-diffusion model** (Merton 1976) adds gaps but needs two new, hard-to-estimate inputs — **average jump size** and **jump frequency**; if you can't estimate them well, it can be *worse* than plain BS. Many traders prefer **intelligent discretion from trading experience** over the more complex model.

### Expiration straddles (the practitioner play that falls out of the gap analysis)
- If selling ATM options into expiry is dangerously asymmetric (high +theta reward, but bigger -gamma loss from a possible gap the model can't price), then **buying ATM options/straddles into expiry** can be a positive-expectation trade — *contrary to the "avoid rapid time decay" conventional wisdom.*
- Logic: with 3 days left, if BS says an ATM call is worth 0.75, its *true* value is likely higher (model ignores gap risk); if it's also trading *below* model (e.g. 0.65), it's likely a good buy. Because of synthetics, if the call is cheap the same-strike put is cheap too → **buy the ATM straddle** to profit from a gap either way.
- **Near expiry, deltas are unreliable too** (model is shaky on both value AND delta), so traders who buy expiration straddles often **abandon delta-neutral rebalancing and just hold to expiry** — not textbook-correct, but practical given the uncertainty.
- **It's a long-run / law-of-large-numbers play** (roulette analogy from ch5): any single expiration straddle is *more likely to lose* (usually no gap), but if you pay below true value, the occasional gap/vol-spike win more than offsets the many small losses. ⇒ **only size it to what you can afford to lose**; don't load up, but when conditions are right, take the bet.

### Assumption 5 — Volatility independent of underlying price → FALSE (vol depends on direction)
- BS assumes a 1-SD move is the same % whether the market is at 75 or 125. Reality: vol depends on *direction of movement*.
  - **Stock indexes: more volatile FALLING, less volatile rising** (the classic equity leverage/fear effect).
  - **Commodities: typically more volatile RISING, less when falling** (opposite).
- *Practitioner response:* the **Constant-Elasticity-of-Variance (CEV) model** lets vol change as the underlying price changes (moves still random, but magnitude scales with price level). Like jump-diffusion, it's mathematically complex and needs an extra input (the vol↔price relationship) → **not widely adopted.** This direction-dependence is a core driver of the **volatility skew** (ch24).

### Assumption 6 — Lognormal prices / normal % returns → FALSE: FAT TAILS, SKEW, KURTOSIS
- Tested on 10yr (2003–2012) daily % changes for **S&P 500, crude oil, euro, Bund** (Figs 23-8a–d), best-fit normal overlaid. Universal finding across *all* exchange-traded markets:
  - **More days with small moves** (peak above the normal curve),
  - **More days with large moves** (fat tails / outliers above the extreme tails),
  - **Fewer days with intermediate moves** (midsection below the normal curve).
- **Skewness** = lopsidedness / one tail longer. Positive skew = right tail longer (the lognormal itself is positively skewed); negative skew = left tail longer; normal = 0. In the data: euro was **positively** skewed; S&P 500, crude, Bund were **negatively** skewed (longer down-tail — equity/bond crashes).
- **Kurtosis** = peakedness + tail-fatness. Positive kurtosis = tall peak + **elongated tails** (*leptokurtic*); negative = flat peak/short tails (*platykurtic*); normal = 0 *(note: raw normal kurtosis is 3; convention subtracts 3 so "excess kurtosis" of a normal = 0).* A positive-kurtosis dist looks like a normal whose midsection got squeezed inward, pushing the peak up and the tails out. **These are the "fat tail" distributions traders mean.**
  - Don't confuse positive kurtosis with low-SD: both have tall peaks, but low-SD has *short* tails while positive-kurtosis has *long* tails.
- **How extreme the tails really are (the punchline):** S&P 500 kurtosis = **10.415** (huge). Its biggest up day +11.58% = an **8.84-SD** event (SD 1.31%) → probability ~**1 in 2 quintillion** under normality; biggest down −9.03% ≈ 6.75–6.89 SD → ~**1 in 350 billion**. Under a normal distribution these "essentially never" happen — yet they happened inside a ~2,535-day sample. Same story (less extreme) for crude/euro/Bund (Fig 23-11 lists each: e.g. crude down 10.80% = 4.80 SD ≈ 1 in 1.26M; euro down 2.40% = 3.69 SD ≈ 1 in 8,900; Bund down 1.50% = 4.10 SD ≈ 1 in 48,000).
  - These are **Taleb's "black swans"** (cited explicitly, *The Black Swan*, 2008). The normal/lognormal assumption catastrophically underprices tail events.

### What a quant should remember (ch23)
- **Every** BS assumption fails in practice; the model is still **the best tool available** — "using a flawed model usually beats using no model at all" — but you must *know where it's wrong and adjust.*
- The **most dangerous, most-mispriced options are high-gamma ones: ATM near expiration, especially in low vol** — because real markets **gap** and you can't continuously rehedge through a jump. Gaps make BS **undervalue** options (implied vol structurally > realized).
- Dynamic hedging makes option P/L **path-dependent** even at one realized vol: *when* the movement happens (vs the gamma profile) determines the realized value. BS is only right **on average**.
- Returns are **NOT normal/lognormal**: **fat tails (excess kurtosis)** + **skew** (equities/bonds skew negative; some FX/commodities positive). Tail events that are "impossible" under normality occur regularly → never trust the model's tail probabilities; size for black swans.
- Vol is **neither constant nor price-independent** (equities: down = more vol; commodities: up = more vol) → drives the skew. Fancier models exist (**stochastic-vol, jump-diffusion, CEV**) but each demands extra hard-to-estimate inputs and can underperform plain BS if those inputs are wrong → most desks prefer **a simple model + skew calibration + experienced judgment.**
- Frictions are real: **transaction costs** crush high-rebalancing strategies; **margin/funding** can force liquidation the model assumes you'd never face; **borrow≠lend rate**, **short-sale limits** (inflate puts), **price limits/circuit breakers** all break "frictionless."

---

## ch24 spillover (Volatility Skews) — brief, belongs to a later batch
*The file's tail (~lines 1980→end) begins ch24. Captured lightly here; full treatment in its own batch.*
- **Volatility skew/smile/smirk** = implied vol varies across strikes, which *can't* happen in a pure BS world (one underlying ⇒ one vol). The market is telling you it doesn't believe BS is efficient.
- **Hedging-pressure explanation:** equity investors are long stock → buy **protective puts at lower strikes** (bid up low-strike IV) and sell **covered calls at higher strikes** (depress high-strike IV) ⇒ **investment skew** ("skew to the downside"; by parity, inflated put IV ⇒ inflated call IV at the same strike).
  - **Demand/commodity skew:** end users fear rising prices → buy upside calls / sell downside puts ⇒ higher strikes carry higher IV.
  - **Balanced skew:** FX-type, both sides hedge → roughly symmetric.
- Skew is *also* partly the model's fault (ch23 vol-is-price-dependent + highest vega at ATM): in equities, falling price → 95 put becomes ATM (vega rises) AND vol rises → its IV inflates; rising price → 105 call's vol falls → consistent with the investment skew.
- **Use the skew as an extra model input.** Fit it (often a polynomial a+bx+cx²+dx³…). Model its *dynamics*: **sticky-strike** (IV fixed per strike — but inconsistent with observed markets), vs **floating skew** (whole curve shifts horizontally with price / vertically with ATM IV). Better x-axis calibrations: **moneyness** (X/S), **log-moneyness** ln(X/S), or **standard deviations** `ln(X/S)/(σ√t)` ("sticky-delta" skew; use forward F for the theoretically-correct at-the-forward=0). Recalibrate the y-axis as IV-minus-ATM or IV-as-%-of-ATM so the skew is comparable as overall vol changes.

---

## Batch 6A — TOP LESSONS

1. **Index cost-of-carry is `F = S×[1+(r−d)×t]`** (dividend treated as a negative rate), exact form subtracts the *discrete, unevenly-bunched* dividend stream + interest on it. The flat-yield shortcut is fine long-dated and **dangerously wrong short-dated** because index dividends arrive in lumps.
2. **A futures position has delta `1+r×t` against the cash index** — so replicating the index does NOT perfectly hedge the future. The gap is **settlement risk**: stock-type (P/L deferred) vs futures-type (daily variation, earns/pays interest). The hedge ratio drifts with time and rates.
3. **Index futures carry a structural downward bias** — chronic portfolio-hedger selling, and arbs can't fully offset because shorting the basket is hard/restricted → futures trade *below* fair value far more often than above.
4. Index derivatives are **cash-settled**, mostly **AM (opening-price) expiration**, with **triple witching** on the 3rd Friday of quarter-end months. **Cash index options are European**; hedge/price them with the **matching future**, and **imply the forward via put-call parity** when no future lines up.
5. **ch23 is the limits-of-the-model chapter — internalize that EVERY Black-Scholes assumption breaks**: frictionless (no — costs, margin, borrow≠lend, short limits, price limits); constant rates (no, minor); constant vol (no — clustered, and makes hedged P/L *path-dependent*); continuous/no-gaps (no — **jump-diffusion**, the biggest practical flaw); vol independent of price (no — equities down=more vol, commodities up=more vol → the skew); lognormal returns (no — **fat tails, excess kurtosis, skew**).
6. **The single most important risk insight:** **gaps** + **high gamma** = where the model lies most. **ATM options near expiration in low vol are the riskiest things you can trade** — never be short large size there. Because real markets gap, BS **undervalues** options (implied vol > realized on average); the practical edge can be **buying cheap expiration straddles** as a long-run, small-size bet on the inevitable gap.
7. **Returns are not normal — plan for black swans.** S&P 500 had ~9-SD days (probabilities like 1-in-quintillions under normality) *inside a 10-year sample*. Never trust a Gaussian model's tail probabilities; size positions so a fat-tail move can't end you. Equity/bond skew is **negative** (fatter down-tail); some FX/commodities are positive.
8. **A flawed model beats no model** — keep BS, but **calibrate the skew, watch the Greeks (esp. rho on long-dated deep-ITM), fold in transaction/funding costs, and override with experience as expiration approaches.** Exotic models (stochastic-vol, jump-diffusion, CEV) each trade one problem for a new hard-to-estimate input, which is why desks mostly stick with a simple model + judgment.

---
*Garbled-text flags (verify):* none materially blocking. Minor OCR/typo noise in the source that I corrected for sense — e.g. Fig 23-5 "falling volatility" 100-call printed as 2.97 where the straddle/text imply the call's value path is irregular **(verify: Fig 23-5 falling-vol 100-call = 2.97)**; Fig 23-11 lists the S&P down-move as **6.89 SD** while the body text says **6.75 SD** for the same −9.03% **(verify: 6.75 vs 6.89 SD)**; the index-arb table shows "1,015 × 2,941" missing a decimal (should be 1.015×2,941≈2,985). None change the lessons.