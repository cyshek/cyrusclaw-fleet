# OPTIONS.md — Business Idea Scorecard (living doc)

_Running tally of every business direction we've evaluated, rated on the two axes Cyrus cares about._
_Last updated: 2026-06-08_

## Scoring axes (1–5)
- **CEILING** — realistic best-case revenue. 5 = exit/unicorn-scale possible · 4 = $10–40k/mo · 3 = $10–20k/mo · 2 = <$5k/mo · 1 = pennies
- **AUTONOMY** — how much agents run without Cyrus (build + distribution + sales + ops). 5 = Cyrus just owns accounts/legal · 3 = some human touch · 1 = Cyrus must be the face / do sales calls

## Tiers
- **S** — high ceiling AND high autonomy (the dream quadrant). Rare.
- **A** — strong on one axis, acceptable on the other; worth doing.
- **B** — viable but compromised (good ceiling but needs Cyrus, or autonomous but low ceiling).
- **C** — fallback / floor only.
- **D** — researched and rejected.

---

## THE SCORECARD

| Tier | Option | Ceiling | Autonomy | Time-to-$ | Status | Notes |
|------|--------|:-------:|:--------:|-----------|--------|-------|
| **A** | **Vertical-AI client-deliverable tool** (AI Website/SEO Audit w/ "make your own" footer) | 3.5 | 3.5 | days-build, weeks-to-signal | 🏆 PICKED — swing #1 | DE-RISKED & WON head-to-head. Loop fires in a POSITIVE in-demographic context (recipient = prospect, often also a marketer). Substance is FREE + credible: Google PageSpeed/Lighthouse API gives real scores + Core Web Vitals + fixes. Niche is fragmented/under-built (every audit Show HN tiny: ~13-22 pts) yet real paid demand ($20-300+/mo white-label audits). Risks (output polish, footer survival) are DESIGN-fixable: hosted interactive link (not strippable PDF) + footer-removal = paid feature. Agent ships v1 in 1-2 wk. |
| **A** | **Embedded "Powered-by" AI widget** (free AI widget on users' public pages) | 4 | 3 | days-build | 🟢 swing #2 engine | Proven "made with" badge loop (Typeform/Framer). Loop weakens exactly when users pay/remove badge. Reusable engine. |
| **A** | **Data-moat programmatic-SEO product** (Nomadlist/Wise/Zapier model) | 4 | 4 | 4–12 mo | 🟢 live candidate | Scores 4/4. Growth engine = agent cron (aggregate data → gen pages → refresh → API). Distribution = Google, no audience. Risk: slow ramp + Google AI Overviews eating informational traffic (mitigate: transactional/fresh/filterable data). The patient high-autonomy compounder. |
| **B** | **Vertical-AI meeting notetaker** (sales-call niche, auto-CRM + follow-up) | 2 | 2 | days-build | ❌ LOST de-risk — dropped | Bot CAN still join (recall.ai ~$0.50/hr, white-label) but loop is STRATEGICALLY DEAD: "AI bot joined" signal turning TOXIC (consent/compliance backlash — HN "Otter recording w/o consent" 612 pts; orgs blocking 3rd-party bots), $0 category floor (Fathom/Fireflies free + Zoom/Google/Teams bundle it), differentiator (CRM+follow-up) already shipped by incumbents. Risks are STRUCTURAL not fixable. |
| **B** | **Two-sided "invite-the-counterparty" AI tool** (AI reference-check / feedback / deal-room) | 4 | 3 | days–weeks | 🟡 on table | Mandatory invite = strong loop, but cold-start two-sided density is brutal (chicken-and-egg partly negates the cold-start edge). |
| **C** | **UGC "result-card" AI toy + retention hook** (shareable score/card/roast) | 3 | 2 | 1 day | 🟡 lottery ticket | Highest-variance + highest-throughput swing. Huge spike potential, terrible retention. Only worth it with a pre-built retention/monetization hook. Cheap enough to fire many as top-of-funnel. |
| **D** | **Agent-tool (MCP) registry** | 5 | 2 | — | ❌ shelved | High ceiling but weak odds + crowded land-grab + low buildability (2/5). Credibility bar too high for cold start. |
| **B** | **High-ticket vertical B2B micro-SaaS** ($99–999/mo) | 4 | 2 | 2–6 mo | 🟡 on table | Big ceiling (34 customers @ $299 = $10k MRR) BUT closing cold B2B needs a human on demo calls. Autonomy collapses. |
| **B** | **Upgraded marketplace app** (Shopify/HubSpot, up-market vs App Guardian) | 3 | 3 | 1–3 mo | 🟡 on table | Faster/safer than pSEO, lower ceiling. Possible barbell "base" while a swing compounds. |
| **B** | **Productized AI done-for-you service** (AI SEO/lead-gen/SDR agency) | 3 | 2 | weeks | 🟡 on table | Fastest cash, worst combo. Needs human sales + QA. Sells at ~2x rev, not 15x. |
| **C** | **App Guardian** (Shopify theme/app change-monitor + 1-click rollback) | 2 | 4 | 1–2 mo | ⚪ floor | Verified real demand (PageFly etc. 1-star "corrupted my store"). Clean recurring (insurance), no payment surface, low risk. The safe floor. ~$5k/mo best case — Cyrus wants bigger. |
| **D** | **Vertical AI, regulated niche** (Harvey-style legal AI) | 5 | 1 | N/A | ❌ rejected | Unicorn ceiling but needs VC + domain experts + enterprise sales. Not an agent-run-from-cold play. |
| **D** | **Preorder/partial-payment Shopify app** | 3 | 3 | 3–6 mo | ❌ shelved | Sharp demand but highest tech risk — Shopify payment-capture wall is exactly why incumbents fail. Touches money. |
| **D** | **Etsy true-profit Chrome extension** | 2 | 4 | 1–3 wk | ❌ shelved | Fast build but weakest demand proof + cheapest hobbyist payers ($5–12/mo), high churn. |
| **D** | **Thin pSEO / scaled AI content / thin affiliate** | 1–2 | 5 | — | ❌ dead | Google March 2026 update = domain-level penalty (-87% traffic). Only data-MOAT pSEO survives. |
| **D** | **Reddit/LinkedIn automation as primary distribution** | — | — | — | ❌ dead | Auto-banned / auto-nuked. Organic burners OK as a *lane*, not a foundation. |

---

## Distribution decisions (locked)
3-engine machine for whatever we build:
1. **Marketplace built-in buyer intent** (foundation where applicable).
2. **Paid ads** — Cyrus approved a small test budget; deploy only once a funnel exists.
3. **Organic burner content** — throwaway accounts, biased to channels where AI content survives + spreads (short-form video, YouTube SEO, Pinterest, quality-gated pSEO). Guardrail: burners point at burnable redirects/landing pages, NEVER straight at the core brand domain (protect domain from spam-flags).

## Irreducible human touchpoints (Cyrus, one-time)
Stripe/payment KYC (gov ID, DOB) · legal entity + signatures · business bank acct · phone/SMS/ID verification + captchas · developer/publisher accounts (Shopify Partner, Chrome Web Store, Apple/Google) · occasional video calls (bank/acquisition due diligence) · tax forms. Agents run everything continuous on top.

## Core strategic truths (don't relitigate)
- AI solved **building**, not **distribution**. Distribution is the entire game and the hardest thing to automate cold.
- Every verified cold-start winner got distribution via: pre-existing audience, a launch platform, **product-led virality**, a **marketplace's built-in traffic**, or a **compounding data/SEO moat**. Pick one of these or it makes $0.
- Base44's $80M was downstream of **distribution** (250k users/$3.5M ARR in 6mo via founder's rep+audience), not the product. To match "his reach" cold = manufacture audience-scale distribution without an audience → only product-led virality or a data/SEO moat do that without Cyrus.
- **Throughput is our unfair advantage:** agents can build+relaunch many high-ceiling swings cheaply; a solo human gets 1–2/yr. The machine is the bet, not any single idea.
- **The frontier is a tradeoff:** higher ceiling usually demands more human involvement. The only known exceptions that bulge toward high+high are **data-moat pSEO** and a **true product-led viral loop**.

## The throughput machine (decided structure)
Don't build 12 unrelated apps (= 12 zombies). Build **2–3 reusable ENGINES** (deliverable-generator spine, embeddable-widget spine, notetaker spine) and **relaunch each across 5–10 niches**. Per swing: ship → seed manually (no loop ignites from a vacuum) → measure **K-factor in 2–4 weeks** → if K>0.3 + real retention, pour fuel in; else archive and re-skin the engine onto the next niche. Quality-of-swing (real loop) > quantity. Agents make the per-swing build cost ~$0, which is the ONLY lever we have without an audience — it raises shots-on-goal, not per-shot odds.

## REALITY CHECK on the $80M dream (don't forget this)
- Cold-start exit-scale via pure product-led virality = **<1% lottery** (~1-in-500 per product). Base44's $80M, Dropbox's referral, Calendly's loop — ALL had a non-viral primary engine underneath (founder audience / paid+PR / years of SEO). **A viral loop amplifies a seed; it does not manufacture the seed.**
- Throughput is **HALF-real**: Levels ran ~30–40 lifetime swings → ~2 durable businesses (~10% hit rate), **zero hit $80M**; low-8-figures over a DECADE. Throughput reliably produces **base hits ($5–50k/mo cashflow), not grand slams.**
- **Honest reframe of the goal:** base case = build a *portfolio of ramen-profitable winners* via throughput; the exit-scale outcome is a cheap lottery ticket that portfolio *funds*, not a plannable target. EV per single swing ≈ $0; the machine is +EV only because build cost ≈ $0 AND each swing embeds a real loop.

## Decision log
- 2026-06-07: Goal → fully AI-run business, long-term profit/exit. Dropped $1k/30d. Full trust (revocable).
- 2026-06-07: Strategy → marketplace-native micro-app first. Picked App Guardian from demand mining.
- 2026-06-08: Cyrus rejected ~$5k/mo ceiling → researched higher-ceiling ideas → data-moat pSEO surfaced as best high+high.
- 2026-06-08: Cyrus wants Base44-scale reach → reframed to viral-loop swing + throughput machine. Research pass #3 in flight.
