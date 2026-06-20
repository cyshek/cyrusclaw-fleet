# Natenberg — Batch 5B: Volatility Revisited (ch20) + Position Analysis (ch21)

Source: `research/natenberg/batches/05b_volrevisited_position.txt` (read end-to-end; ~2900 lines). Paper-quant study notes. Formulas transcribed from text; `(verify: ...)` flags where the OCR/typesetting is ambiguous or a sign/index looks off.

---

## CHAPTER 20 — VOLATILITY REVISITED

### The three volatilities — keep them strictly distinct

This is the conceptual spine of the chapter. Natenberg is careful that these are *different objects* and conflating them is a classic error.

1. **Historical / realized volatility** — the *actual* volatility the underlying *has already exhibited* over some past window. Computed from a series of past returns (annualized standard deviation of log returns). Backward-looking. "Realized" and "historical" are used near-interchangeably; "realized over the next N days" is what you'd *like* to forecast.
2. **Implied volatility** — the volatility number that, plugged into a pricing model, makes the model's theoretical value equal the option's *current market price*. It's the market's *collective forecast/price* of future volatility — a market-derived input, not a measured statistic. Forward-looking but model-dependent.
3. **Future (future realized) volatility** — the volatility the underlying *will actually exhibit* over the life of the option, from now to expiration. **This is the only volatility that ultimately determines an option-held-to-expiration's P&L** (given delta-neutral dynamic hedging). It is **unknowable in advance** — everything else (historical, implied) is an *estimate* of this. The entire forecasting problem is: estimate future realized vol.

> Quant takeaway: the trade you actually have when you buy/sell vol and hedge is **implied (what you paid) vs. future realized (what you get)**. Historical vol is just one estimator of future realized. Don't trade "implied vs historical" thinking it's the real edge — it's a proxy for "implied vs *future*."

### Forecasting volatility — the methods

**(a) Simple historical / intuitive projection.** Look at historical vol over several past windows (e.g., 6-, 12-, 26-, 52-week), identify the underlying's typical vol characteristics, and project forward — ideally matching the historical window length to the option's time to expiration (use ~3-month historical vol to forecast a 3-month option). More data = better, and lets you match horizons. Natenberg notes many traders do this *intuitively*.

- **Caveat on time-series treatment:** overlapping historical-vol windows are **not a true time series** — the 52-wk window overlaps the 26-, 12-, 6-wk windows, so the points are not independent. To apply proper time-series models you should use the **underlying returns** themselves (which *do* form a true time series), not the overlapping vol numbers.

**(b) EWMA — Exponentially Weighted Moving Average.** Greater weight on more recent returns, geometrically decaying weight on older returns. General form for the variance estimate over the next period:

  σ² = α₁r₁² + α₂r₂² + … + αₙrₙ²   (where rₙ is the **most recent** return in the book's indexing)

Constraints:
- weights sum to 1:  Σ αᵢ = 1.00
- more recent ⇒ heavier:  αₙ > αₙ₋₁

Pick λ ∈ (0, 1). The weights that satisfy both constraints are:

  **αᵢ = λ^(i−1)·(1 − λ) / (1 − λⁿ)**

Behavior of λ:
- **smaller λ** ⇒ recent returns weighted much more heavily; estimate quickly discounts old returns (fast/reactive).
- **larger λ** ⇒ less distinction between old and new; long memory. As λ → 1.00 (never exactly 1), all weights converge to 1/n (≈ equal-weighted simple variance).
- **Common risk-management choice: λ ≈ 0.94** (this is the classic RiskMetrics value).

> **Recursive form requested in the task.** Natenberg gives the *weighted-sum* form above, not the one-line recursion, but they're equivalent. The standard recursive EWMA the task asks for:
>
>   **σ²_t = λ·σ²_{t−1} + (1 − λ)·r²_{t−1}**
>
> i.e. today's variance estimate = λ × yesterday's estimate + (1−λ) × yesterday's squared return. (verify: the book never prints this recursion explicitly — it's the well-known equivalent of the αᵢ = λ^(i−1)(1−λ) weighting in the n→∞ limit where the 1/(1−λⁿ) normaliser → 1. The recursion and the finite weighted sum agree as n grows. Index convention: here r²_{t−1} is the most recent observed squared return feeding the estimate for t.)

- **Two things EWMA ignores** (explicitly per Natenberg): (1) the **correlation between successive returns**, and (2) the **mean-reversion** characteristic of volatility. EWMA is "relatively simple."

**(c) ARCH / GARCH family.** EWMA's shortcomings motivate ARCH (Engle, 1982 — "autoregressive conditional heteroskedasticity"; Engle won the 2003 Nobel) and its generalization **GARCH**. Per Natenberg, a GARCH model has **three components**:
1. a **volatility estimate** (e.g., something EWMA-like),
2. a **correlation component** capturing **volatility clustering** — "large returns tend to be followed by large returns, small by small" (autocorrelation in |returns| / returns²),
3. a **mean-reversion component** specifying **how fast** volatility reverts to its long-run mean.

Natenberg explicitly leaves GARCH math to time-series texts (out of scope), but the *idea* (cluster + mean-revert + a base vol estimate) is the takeaway.

### Implied volatility as a predictor of future volatility

- If markets are efficient (efficient-market hypothesis), implied vol *ought to* be the best available predictor of future realized vol.
- Empirically (S&P 500, 2002–2010, 3-month and 12-month): **implied is at best an imperfect predictor.** Key findings:
  - **Index realized vol tends to LEAD implied vol** — the market *reacts* to realized vol. When the index gets more volatile, implied rises (after the fact); when it calms, implied falls. The lag is even more evident over 12-month horizons. (Vividly true in 2008 ↑ and 2009 ↓.)
  - Plotting **(future realized − implied)**: positive ⇒ implied was too low (vol exploded beyond what was priced); negative ⇒ implied was too high (options were overpriced).
  - For much of the sample, implied **overpredicted** future vol by **up to ~10 vol points** — i.e., **options tend to be overpriced** under normal conditions.
  - But dramatic exceptions exist: **Sept 8 2008**, 3-mo future realized = 72% while implied = 22% (implied ~50 points TOO LOW — a vol explosion); **Nov 20 2008**, 3-mo future = 45% vs implied = 65% (implied ~20 points too high).
- **The insurance analogy** (important framing): options are normally overpriced the way insurance premiums exceed expected payout — buyers willingly overpay for the *rare* occasions of a vol explosion (the "fat tail" event). Sellers (market makers) also pass on the **cost of replication via dynamic hedging** and the cost of **model imperfections**. Together these can *justify* the persistent implied-vol premium.

> Quant takeaway: the **implied-minus-realized spread (variance/vol risk premium) is real and usually POSITIVE** (implied > subsequent realized), which is why systematic vol-selling has positive expectancy *on average* — but it's a short-tail / "picking up nickels" payoff with occasional violent losses. Sizing and tail control matter more than the average edge.

### Term structure of implied volatility

- **Setup:** If at-the-money implied vol is the same across months (e.g., 25% in Mar/Jun/Sep), and realized vol starts to rise, implied vol rises **but not uniformly** across expirations.
- **Mean reversion drives the term-structure shape:** vol is more likely to revert to its mean over **long** horizons than short. So **near months move more; far months move less** (they stay closer to the mean vol).
  - Example (rising): Mar 25→30, Jun→28, Sep→26.
  - Example (falling): Mar 25→20, Jun→22, Sep→24.
- **Typical term structure** (Fig 20-12): short-term implied is more variable and sits further from the mean; long-term implied hugs the mean vol. The curve flattens toward the mean as you go out in time.
- **Why total vega can lie.** A position with **net vega = 0** is **NOT necessarily vega-neutral**, because near and far vegas don't move 1-for-1. Worked example (vegas by month, "whippiness" factors relative to the primary/April month):

  | Month | Apr | Jun | Aug | Oct |
  |---|---|---|---|---|
  | Months to exp | 2 | 4 | 6 | 8 |
  | Total vega | +15 | −36 | −21 | +42 |
  | Naïve sum | | | | **= 0** |
  | Relative move per 1pt in Apr IV | 3.0/3=1.0 | 2.0/3=0.67 | 1.5/3=0.50 | 1.1/3=0.37 |

  - Naïve: 15 − 36 − 21 + 42 = 0 ⇒ *looks* vega-neutral.
  - **Vega-adjusted to the primary (April) month:** weight each month's vega by its relative responsiveness:
    - Jun: −36 × 0.67 = −24.12
    - Aug: −21 × 0.50 = −10.50
    - Oct: +42 × 0.37 = +15.54
    - Adjusted total: +15.00 − 24.12 − 10.50 + 15.54 = **−4.08** per 1-pt move in April IV.
  - So the "vega-neutral" book is actually **short ~4 vega** in April-equivalent terms. It **prefers IV to fall**. (The book also shows a quick P&L check: a 3-pt rise in April IV ⇒ (3×15) − (2×36) − (1.5×21) + (1.1×42) = −12.30 loss; a fall ⇒ +12.30.)

- **Implied-vol term-structure model — three required inputs** (per Natenberg):
  1. a **primary month** (benchmark; often the front month, but not always — in agricultural/energy markets pick a month tied to planting/harvest/weather; also front-month IV is unstable near expiry, so many traders evaluate the front month *separately* and run the model on all *other* months),
  2. a **mean volatility** that IV reverts to,
  3. a **"whippiness" factor** — how fast IV in other months moves relative to a 1-unit move in the primary month.
  Models are usually "home-grown."

- **Term structure evolves** (EuroStoxx 50, 2010): downward-sloping when near-term realized is high (backwardation), can **invert to upward-sloping** (contango) when index vol falls, snaps back down after a vol spike, flattens when vol settles. **Front-month IV can disconnect** from the rest of the curve (e.g., Dec 2010 generally upward-sloping but front month much higher) — a common, recurring feature.

- **Seasonal vol factor:** in some markets the term structure isn't just realized-vol + mean. Examples:
  - **Agriculturals:** summer expirations carry persistently higher IV (drought/heat risk) regardless of date.
  - **Energy / natural gas:** the **October** natural-gas contract consistently trades at *inflated* IV because it expires end-September and captures the **Atlantic hurricane season** (Jun–Nov, peak Aug–Sep) risk to Gulf-coast operations. (Fig 20-16/20-17: Oct IV highest of all months in 2009.)
  - These seasonal humps make a clean term-structure model hard to build.

### Forward volatility (analogous to forward interest rates)

- Question: given short-term IV σ₁ to t₁ and long-term IV σ₂ to t₂, what **forward vol σ_f** does the market imply *between* t₁ and t₂ (no-arb)?
- Unlike interest rates (∝ time), **variance is ∝ time** (vol ∝ √time). The no-arb relation:

  **σ_f² · (t₂ − t₁) = σ₂²·t₂ − σ₁²·t₁**

  ⟹  **σ_f = √[ (σ₂²·t₂ − σ₁²·t₁) / (t₂ − t₁) ]**

- Generalized to n consecutive periods (total vol from t₀ to tₙ given forward vols σᵢ over [tᵢ₋₁, tᵢ]):

  **σ_{t0→tn} = √[ Σᵢ σᵢ²·(tᵢ − tᵢ₋₁) / (tₙ − t₀) ]**

  (verify: the OCR prints the summand as `σ²_{i,(i−1)} × (tᵢ − tᵢ₋₁)` divided by `tₙ − t₀`, all under a sum — i.e. variance-additive-in-time, term-weighted by each interval length; the clean reading is the total-variance = sum of forward-variances × their time spans, then ÷ total time, all under a sqrt. That's the standard variance-additivity identity and is almost certainly the intended formula.)

- **Calendar-spread implied vol** — the single vol that, applied to *both* legs, reprices the calendar spread to its market price. Quick approximation for an **at-the-money** calendar (because ATM vega is roughly constant in vol): given leg prices O₁, O₂ and vegas V₁, V₂,

  **Spread implied vol (as a whole-number %) ≈ (O₂ − O₁) / (V₂ − V₁)**

  i.e. spread price ÷ spread vega. (Approximate — rounding + vega drifts slightly with vol — but good for a fast over/under-priced read.)

- **Using it:** the calendar-spread-IV (or forward-vol) curve acts as a **magnifying glass** over the raw term-structure curve, exposing which *individual months* are rich/cheap **relative to each other** (not whether the whole complex is rich/cheap). EuroStoxx Feb-2010 example: Jun was **underpriced**, Sep/Dec **overpriced** vs the best-fit line ⇒ buy Apr/Jun calendar + sell Jun/Sep calendar = a **time (horizontal) butterfly**.
  - Geometry note: when the term-structure curve is downward-sloping, all calendar-spread IVs plot *below* the curve; when upward-sloping, *above*; a *smooth* calendar-IV curve ⇒ no obvious mispriced calendars.

### Ch20 — what a quant should remember
- **Three vols are different objects**; the only one that pays you is **future realized**, which is unobservable — everything is an estimator of it.
- **Vol clusters** (autocorrelated magnitude) and **mean-reverts** — these two empirical regularities are the whole basis of EWMA/GARCH and of the term-structure shape.
- **EWMA** = `σ²_t = λσ²_{t−1} + (1−λ)r²_{t−1}`, λ≈0.94 typical; **GARCH** adds clustering + mean-reversion on top.
- **Implied usually > subsequent realized** (vol-risk premium, "insurance" markup) — but with rare violent reversals; realized **leads** implied.
- **Net vega = 0 ≠ vega-neutral**: weight per-month vegas by their relative IV responsiveness (whippiness) to the primary month before summing.
- **Variance is additive in time** ⇒ forward-vol and calendar-spread-IV math; use them to spot *relative* month-to-month mispricing (time butterflies).
- **Seasonal IV humps** exist (ag summers, nat-gas October/hurricanes) — don't model them away.

---

## CHAPTER 21 — POSITION ANALYSIS

Core thesis: for a **complex multi-leg book**, knowing today's Greeks is only **step one**. You must also know **how those Greeks change** as price, vol, and time move — and what the position **collapses into** at the extremes. "Today's market conditions cannot be tomorrow's conditions."

### Aggregating Greeks across legs (the mechanics)
- **Net Greek = Σ (contracts × per-contract Greek)** for each of delta, gamma, theta, vega, rho. Underlying contributes delta = +100 per long contract (×1 the share/contract multiplier), zero to the other Greeks.
- Worked totals example (the Fig 21-9 book, underlying 101.25, 6 wks, σ=27%): summing 5 call strikes + 5 put strikes + 13 underlying gives **Totals: Delta −297.4, Gamma −24.13 (≈−25.8 used in text), Theta +0.2483, Vega −0.759**. (The book tabulates each strike's position-Greek = qty × unit-Greek, then column-sums to call totals, put totals, underlying, grand total — this is exactly the "build a net risk picture" mechanic.)

### Pre-model trick: rewrite via synthetics to recognize the structure
- A scary-looking mixed call+put+underlying position can be collapsed using **synthetics** (put = synthetic call − underlying, etc.) into **all-calls (or all-puts)**. Once rewritten, it may reveal a familiar structure.
- Worked: a 9-leg mess (+29 underlying, ±44/±7/±33/±51/±30/±12 across March 65/70/75/80 calls & puts at underlying 71.50) rewrites to **+42 March 65 calls / −84 March 75 calls / +42 March 70 calls** — wait, it nets to **a long butterfly** (+42×70C, −84×75C, +42×65C... text's body line is the 70/75/65 butterfly). A long fly wants the underlying to drift to the **inside strike (75)**; since spot is 71.50 < 75, the position is **delta-positive**. (Call fly ≈ put fly.) Lesson: synthetics let you *reason about direction without a model* in clean cases — but real books rarely collapse this neatly, so a model is normally required.

### The central worked example — "all Greeks = 0" is NOT safe
Position: **Long 10 Sep 95 puts / Short 10 Sep 105 calls / Long 5 underlying** (underlying 99.60, 9 wks, σ=18%). This is a **risk reversal / split-strike**. With the given per-contract Greeks (95P: Δ−25 Γ4.3 Θ−0.019 V0.132; 105C: Δ+... mirror):
- **Delta = 0, Gamma = 0, Theta = 0, Vega = 0.** Looks bulletproof. **It isn't** — because the Greeks are local and *change* as conditions move. The scenario behavior:

  | Change in conditions | Resulting Δ | Resulting Γ | Resulting Θ | Resulting Vega |
  |---|---|---|---|---|
  | **Rising underlying** | Negative | Positive | Negative | Positive |
  | **Falling underlying** | Negative | Positive | Negative | Positive |
  | **Time passes** | Positive | 0 | 0 | 0 |
  | **Volatility rises** | Negative | 0 | 0 | 0 |
  | **Volatility falls** | Positive | 0 | 0 | 0 |

- **Key intuitions used to derive the table** (all from "Γ/Θ/vega peak at the money" + "deltas move toward/away from 50"):
  - Underlying falls → moves toward the 95 strike → 95P gamma ↑, 105C gamma ↓ → net **Γ turns positive** → with +Γ, a falling market makes Δ **negative**.
  - Underlying rises → toward 105 → 105C gamma ↑, 95P gamma ↓ → net **Γ turns negative** → a rising market also makes Δ **negative**. (Odd but true: Δ goes negative *either* direction, because Γ flips sign across the current price — 99.60 is an **inflection point**.)
  - **Vol rises** → call deltas → +50, put deltas → −50 (underlying stays 100). Long puts (now Δ more negative than −25) + short calls (now more positive than +25) ⇒ net **Δ negative**. E.g. 95P→−30, 105C→+30: (10×−30) − (10×30) + (5×100) = **−100**. Vol falls (deltas → away from 50, e.g. ±20): ⇒ **+100**.
  - **Time passes** ≈ vol falls (deltas move away from 50, options go further OTM) ⇒ the 5 long underlying dominate ⇒ **Δ positive**.
  - Summary one-liners: *if vol rises, you want the market to fall; if vol falls, you want it to rise.*

### Reading risk off P&L / Greek graphs (the graphical vocabulary)
- **Delta from the P&L-vs-price graph:** negative-Δ ⇒ line slopes **upper-left → lower-right**; positive-Δ ⇒ **lower-left → upper-right**; Δ-neutral ⇒ locally **horizontal**.
- **Gamma:** **positive Γ = a "smile"** (curves up; movement either way *helps*); **negative Γ = a "frown"** (curves down; movement either way *hurts*). Lower vol ⇒ **more curvature** (gamma magnified); higher vol ⇒ flatter (gamma muted). An **inflection point** (here 99.60) is where Γ flips sign and the graph is locally straight.
- **Gamma vs Theta are ALWAYS opposite signs**: +Γ position **loses** value as time passes with no movement (graph shifts down); −Γ **gains** (shifts up).
- **Gamma vs Vega can be either same or opposite**: independent of whether you want movement (Γ sign), you can separately want IV up or down (vega sign). +vega ⇒ graph shifts up as IV rises; −vega ⇒ shifts up as IV falls.

### Net contract position at the extremes (tail/jump analysis) — DO THIS
A discipline Natenberg stresses ("learned through painful experience"): ask **what the book collapses into on a huge move**, when every option goes deep ITM (acts like ±underlying) or far OTM (→ 0).
- **Upside contract position** = Σ(all calls) + underlying (puts → 0). **Downside contract position** = Σ(all puts as short underlying) + underlying (calls → 0).
- Risk-reversal example: short on a huge move *both* ways (downside = short 5, upside = short 5) ⇒ delta → −500 in either tail (Fig 21-7). 
- Fig 21-9 book: upside contract position **+6** (net short 7 calls + long 13 underlying) ⇒ a massive rally eventually makes it **long 6 → unbounded profit** (so Γ must turn positive on the way up, Δ eventually positive); downside contract position **+8** (net long 5 puts + long 13 underlying) ⇒ a violent crash leaves it **long 8 underlying-equiv → potentially disastrous**. Far-OTM shorts "that couldn't possibly go ITM" *do* (takeovers, disasters, political shocks); big moves happen more often than models assume.
- Practical aside: deep-OTM options can be closed at a **cabinet bid** (nominal 1 currency unit) to free up margin / remove worthless legs even below the normal exchange tick.

### Useful back-of-envelope estimates a quant can reuse
- **Where a negative-gamma book is delta-neutral on a move** (its profit-maximizing point): a −Γ position "always wants to become Δ-neutral." Estimate the price by walking Δ off via Γ:
  - target price ≈ spot − (Δ / Γ).  Example: 101.25 − (297.4 / 24.13) = 101.25 − 12.32 = **88.93**. (Approximate — assumes constant Γ; the *true* turn was ~95 because Γ grew much more negative as price fell. Still a fast first read.)
- **Breakeven (implied) volatility of an entire position** — "the IV of the whole book." Given total **theoretical edge** and total **vega**:
  - **breakeven σ ≈ current σ + (theoretical edge / |vega|)**.  Example: 27.00 + (6.00 / 0.759) = **34.90%**. Interpretation: vol can rise ~7.9 points before the edge is eaten. (Actual breakeven was a touch higher, ~36%, because the position had **positive volga** — vega becomes less negative as vol rises; the graph curves up.)
  - **Widen your margin for error** by raising edge without raising vega, or cutting vega without cutting edge: edge 8.00 ⇒ 37.54%; vega −0.65 ⇒ 36.23%.
- **Volatility-move delta estimate via deltas→/away-from-50:** in the extreme where every option's |Δ|→50, recompute net delta to see which way the book leans in high-vol vs low-vol/time-decay regimes. (Fig 21-9: high-vol extreme ⇒ Δ → +700 ⇒ prefer up-moves; low-vol/time-passes extreme ⇒ Δ → −900 ⇒ prefer down-moves.)

### Higher-order Greeks Natenberg tabulates (ch9 recap, used in position scans)
When computer support is available, scan a **table of sensitivities across a price grid** (e.g., 45→95 in 5-pt steps), including 2nd/3rd-order Greeks, to see how risk *evolves*:
- **Vanna** = ∂Δ/∂σ (delta's sensitivity to vol)
- **Charm** = ∂Δ/∂time (delta's sensitivity to time decay)
- **Speed** = ∂Γ/∂(underlying) (gamma's sensitivity to price — +speed means Γ grows as price rises)
- **Color** = ∂Γ/∂time
- **Volga (vomma)** = ∂vega/∂σ (vega's sensitivity to vol; +volga ⇒ vega less negative as vol rises ⇒ breakeven-vol higher than the linear estimate)
- **Vega decay** = ∂vega/∂time
- **Zomma** = ∂Γ/∂σ
(Natenberg's Fig 21-20 lists all of these per price level. The point: higher-order Greeks tell you *how the risk picture will deform*, which a single snapshot of Δ/Γ/Θ/vega hides.)

### The full market-maker book (Fig 21-14) — scenario/what-if workflow
A realistic MM book: calls+puts at 7 strikes × 3 expirations (Apr/Jun/Aug) + 3,300 shares, with a **term-structure assumption baked in** (April = primary month, mean vol 30%, **June IV moves at 75% of April's rate, August at 50%** — and the live IVs 34.27/33.20/32.14% are *consistent* with that: differences from mean 4.27 / 3.20≈0.75×4.27 / 2.14≈0.50×4.27). Vol shifts in the scenario graphs are expressed in **percent terms, not percentage points**, propagated through the whippiness factors (e.g., +20% on April 34.27→41.12 ⇒ June 30+0.75×(41.12−30)=38.34, Aug 35.56).

**The market-maker mantra:** *Get an edge…. Control the risk….* (repeat forever). Goal: positive theoretical edge + intelligently managed risk; the *ideal* is to flatten all risk to a single horizontal positive-P&L line, which is **impossible** for a big book — so instead ask the **three scenario questions**:
1. What will I do if conditions move **against** me?
2. What will I do if conditions move **in my favor**? (Plan to *exploit* good outcomes, not just defend.)
3. What can I do **now** to pre-empt later adverse moves?

**Reading the Fig 21-14 book's risks (the what-if narrative):**
- Greatest threat: a **violent upmove** — above 85 the book goes Δ-negative and bleeds as price rises (upside contract position −76). Hedge: buy higher-strike calls (costly if it's a takeover name with inflated upside calls — but survival may justify it).
- Moderate down-move + rising IV is dangerous: as price falls toward 62 the book takes on **increasingly negative vega**. Buying **April 60/65 puts** kills two birds — cuts the +203 delta *and* the negative vega in the 60–65 zone, and (being short-dated ATM there) brings the most gamma to offset negative gamma in that range.
- Max **positive gamma** near 53 and 72 ⇒ if price parks there the book hits max **negative theta** and decays fast.
- **Theta** is small (−1.9) but **concentrated in April** (large long April-70-call position, close to ATM); theta *accelerates* as those near-ATM options approach expiry.
- **Dividend risk:** long 3,300 shares ⇒ P&L change ≈ Δdividend × 3,300 shares. Neutralize by replacing long stock with **synthetic long stock** (sell stock, buy calls + sell puts same strike → turns it into a box, à la conversion/reversal risk removal).
- **Rho** +12.70 ⇒ a 100bp rate drop costs 12.70.

**Risk limits & capital:** firms/clearing houses cap exposure — e.g., "must hold enough capital to withstand a 20% underlying move either way" or "a doubling of implied vol." Breach ⇒ post more capital or cut size. MMs also **diversify across strikes/expirations**: a concentrated gamma (e.g., −2,388 at the 95 strike while total gamma is ~0) is a *time bomb* if the underlying drifts there — spread risk out, don't let it pile on one strike/expiry/Greek.

### Stock-split mechanics (book-keeping, mostly Δ/Γ only)
For a **Y-for-X** split (X shares → Y shares):
- New stock price = old × X/Y
- New strike = old × X/Y
- New option position (contracts) = old × Y/X
- Underlying contract: **unchanged (100 shares)** *if Y is a whole number* (2:1, 3:1…)
- **New delta position = old Δ × Y/X**
- **New gamma position = old Γ × (X/Y)²**
- **Theta, vega, rho: UNCHANGED.** A split is essentially an accounting change that preserves equity; only Δ and Γ rescale.
- If **Y is not a whole number** (e.g., 3-for-2), fractional contracts aren't allowed, so the clearinghouse keeps 1 contract per old contract and instead **adjusts the underlying multiplier** (e.g., 100 × 3/2 = 150 shares per contract). (Worked: 3:2 on a 60 ATM call → strike 40, underlying 150 sh, Δ 50→75, Γ 5→11.25.)
- Real-world caveat: a split often signals a healthy company and **may come with a dividend change**, which *does* move option values — so "all else equal" rarely holds exactly.

### Ch21 — what a quant should remember
- **Net Greeks = qty-weighted sums per leg**, but a Greek snapshot is necessary-not-sufficient: **how Greeks change** (price/vol/time) is the real risk.
- **All Greeks = 0 today ≠ safe**: a risk reversal can be flat now yet flip Δ negative on *any* big move (Γ sign-flips across an inflection price) and lean opposite ways in high- vs low-vol regimes.
- **Γ and Θ are always opposite-signed; Γ and vega are independent.** "Smile" = +Γ (movement helps), "frown" = −Γ (movement hurts); lower vol magnifies Γ.
- **Always compute the net contract position at the tails** (deep-ITM → ±underlying, far-OTM → 0). Big jumps happen; deep-OTM shorts can detonate.
- Fast estimates worth memorizing: **−Γ book is delta-neutral near spot − Δ/Γ**; **position breakeven vol ≈ σ + edge/|vega|** (adjust up for +volga).
- For multi-expiry books, **bake in a term-structure / whippiness model** (primary month, mean vol, relative-move factors) before trusting net vega, and move vol in **% terms** not points across months.
- **Scenario/what-if grid** across price (and separately vs vol & time), including **higher-order Greeks** (vanna/charm/speed/color/volga/vega-decay/zomma), beats any single snapshot.
- **Diversify risk across strikes/expiries**; a concentrated gamma/vega at one node is a latent blowup.
- Stock split: rescale **Δ (×Y/X) and Γ (×(X/Y)²)** only; Θ/vega/rho unchanged; watch for an accompanying dividend change.

---

## Batch 5B — top lessons

1. **Future realized vol is the only thing that pays you, and it's unobservable.** Historical vol and implied vol are *both estimators* of it. Frame every vol trade as **implied (paid) vs future realized (received)**; historical is a proxy for the latter, not the trade itself.
2. **Vol clusters and mean-reverts** — the two empirical regularities behind every estimator. EWMA captures recency; GARCH adds clustering + an explicit mean-reversion speed. Memorize EWMA: `σ²_t = λ·σ²_{t−1} + (1−λ)·r²_{t−1}`, λ≈0.94.
3. **Implied usually exceeds subsequent realized** (the variance/vol-risk premium — an "insurance" markup of often ~10 vol points), but with **rare violent reversals** (Sep-2008: 3-mo realized 72% vs implied 22%). Realized **leads** implied. Selling vol = positive average expectancy with a nasty left tail; size for the tail.
4. **Term structure of IV is shaped by mean reversion**: near months whip, far months hug the mean. **Net vega = 0 is NOT vega-neutral** — weight per-month vegas by their responsiveness (whippiness) to a primary month before summing.
5. **Variance is additive in time** ⇒ forward vol `σ_f = √[(σ₂²t₂ − σ₁²t₁)/(t₂ − t₁)]` and the ATM calendar-spread-IV shortcut `≈ (O₂−O₁)/(V₂−V₁)`. Use these to find **relative** month-to-month mispricing (time butterflies) — a magnifying glass over the raw curve.
6. **Watch for seasonal IV humps** (ag summers, nat-gas October/hurricane) — structural, not noise.
7. **A Greek snapshot is step one only.** All-Greeks-zero can still blow up; always run **scenario/what-if across price, vol, and time**, check **net contract position at the tails**, and look at **higher-order Greeks** to see how risk deforms.
8. **Two reusable closed-form estimates:** −Γ book turns delta-neutral near **spot − Δ/Γ**; whole-book breakeven IV ≈ **σ + edge/|vega|**.
9. **Diversify risk across strikes/expiries**; concentrated gamma/vega at one node is a time bomb even if the *total* nets to zero.

---

## Vol-estimation ideas for OUR project

Concrete, implementable from **free daily (and where available intraday) data** (e.g., yfinance/stooq for OHLCV; CBOE for VIX/term-structure; we already pull what we need for backtests). All of these are cheap to compute and directly testable as signals.

### A. Realized-vol estimators (the "what is vol now / next" engine)
1. **EWMA realized vol** — `σ²_t = λ·σ²_{t−1} + (1−λ)·r²_{t−1}` on daily log returns, λ≈0.94 (also test 0.97 for slower decay). Annualize ×√252. Cheap, no fitting, reactive. Baseline realized-vol nowcast/1-step forecast.
2. **Rolling close-to-close historical vol** at multiple windows (10/21/63/126/252d) — the simple-historical method; match window to the horizon you're forecasting. Use the *set* of windows as features.
3. **Range-based estimators (much lower variance than close-to-close)** — compute from the same free OHLC:
   - **Parkinson** (uses high-low): σ²_P = (1/(4 ln2)) · mean[(ln(H/L))²]. (verify: standard constant 1/(4 ln 2); not from Natenberg, well-known.)
   - **Garman–Klass** (adds open/close): σ²_GK = mean[ 0.5·(ln H/L)² − (2ln2 − 1)·(ln C/O)² ].
   - **Rogers–Satchell** (drift-robust): handles trending underlyings.
   - **Yang–Zhang** (handles overnight gaps + drift) — best all-rounder if we have clean O/H/L/C.
   These give a **5–8× more efficient** realized-vol estimate per day → better signal-to-noise than close-to-close. Strongly worth adding to the feature set.
4. **GARCH(1,1) one-step & multi-step vol forecast** — `σ²_t = ω + α·r²_{t−1} + β·σ²_{t−1}`, mean-reverting to ω/(1−α−β). Adds the clustering + mean-reversion Natenberg flags that EWMA ignores. `arch` python package fits it in a few lines on free daily returns. Use the **forecast vs current EWMA gap** and the **implied mean-reversion level** as features. (Heavier than EWMA; validate it actually beats EWMA out-of-sample before trusting — Natenberg-consistent skepticism.)

### B. Implied-minus-realized spread (the vol-risk-premium signal)
5. **VRP = implied − forecast/trailing realized.** Concretely: **VIX − (21-day realized vol of SPX)**, or per-name `ATM IV − EWMA realized`. Natenberg's empirical finding (implied normally too high by ~10 pts) says this spread is **usually positive and predictive of vol-selling profitability**. Signal ideas:
   - Go *short* vol (or risk-on) when VRP is **richly positive** vs its own history; stand down / go long vol when VRP **collapses or inverts** (implied < realized — the 2008-style danger zone).
   - Use **(future realized − implied)** in backtests as the *label* to learn when implied is mispriced.
   - **Caveat (Natenberg):** realized *leads* implied, so a naive "short vol because VRP positive" gets run over in regime breaks — pair with a tail/regime filter.

### C. Vol-cone percentile (regime-relative positioning)
6. **Vol cones** — for each horizon (10/21/63/126/252d), compute the historical **distribution** (min / 25th / median / 75th / max, or finer percentiles) of realized vol, then plot **current realized (and current implied) vs that cone**.
   - **Signal:** current realized/implied **percentile within its own cone** — buy vol near the low percentiles, sell near the high percentiles (mean-reversion bet, directly justified by ch20's mean-reversion regularity).
   - Implementing implied-on-the-cone lets us see if options are rich/cheap *relative to how vol has actually behaved at that horizon* — a clean, model-light richness gauge. Cheap to compute from the rolling-historical-vol series we already build in (A2).

### D. Term-structure slope (calendar / regime signal)
7. **IV term-structure slope** — from VIX complex (VIX9D / VIX / VIX3M / VIX6M) or a built ATM-IV-by-expiry curve per name:
   - **Slope = far IV − near IV** (e.g., VIX3M − VIX, or VIX − VIX9D). **Contango (upward-sloping)** = calm regime; **backwardation (downward-sloping)** = stress/near-term-fear regime (ch20: curve inverts down after vol spikes).
   - **Signals:** (i) a **steep-backwardation flag** (near >> far) as a risk-off / reduce-size / tail-hedge trigger; (ii) **forward vol** between two expiries via `σ_f = √[(σ₂²t₂ − σ₁²t₁)/(t₂−t₁)]` to judge whether the *implied future* vol is cheap/rich; (iii) **calendar-spread richness** via the ATM shortcut `(O₂−O₁)/(V₂−V₁)` to spot a specific over/under-priced expiry (time-butterfly setups), exactly the ch20 EuroStoxx workflow.
   - The **VIX/VIX3M ratio** (or its z-score) is a well-known, free, single-number regime gauge worth adding as a feature.

### E. Cross-checks / sanity (Natenberg-flavored discipline)
8. **Build a vega-whippiness map before trusting net vega** in any multi-expiry options backtest: don't sum month vegas raw — scale far-month vega by an estimated relative-response factor to the front (fit the factor from how each month's IV historically moves vs the front). Prevents "looks vega-neutral, isn't" P&L surprises.
9. **Always tail-check the book**: in any options strategy backtest, compute the **net contract position at extreme up/down** and stress a 20% underlying move + a 2× IV move (the clearing-firm-style stress Natenberg cites). Reject strategies whose tail collapses to a large naked ±underlying position.
10. **Label the implied predictor empirically**: replicate Natenberg's Fig 20-11 on our data — plot **(N-day-forward realized − today's implied)** for SPX/our universe to *measure* our own market's vol-risk premium and its regime-dependence, instead of assuming the ~10-pt markup transfers. This both validates the VRP signal (B5) and calibrates position sizing.

**Quick priority for our hunt:** start with **(A1 EWMA + A3 Yang–Zhang/Parkinson realized) → (B5 VRP = VIX − realized) → (C6 vol-cone percentile) → (D7 VIX/VIX3M slope)**. All four are computable from data we already have or can pull free, are individually interpretable, and map 1:1 onto the chapter's empirical regularities (clustering, mean-reversion, persistent positive VRP, mean-reverting term structure).