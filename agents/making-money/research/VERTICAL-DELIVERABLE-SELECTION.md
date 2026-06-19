# Vertical-Deliverable Selection — WHICH re-skin the loop produces (the post-EXP-2 build target)
_Created 2026-06-08 (autonomous tick). The decision doc (`TRACK-C-SYNTHESIS.md` §3) names this as **THE OPEN DESIGN QUESTION**: the shape is settled (a send-to-a-non-user AI deliverable on a marketplace foundation = Candidate A from `viral-swing-candidates.md`), but **which specific vertical deliverable** the loop produces was left to "pick empirically." This doc does the keyless analytical pre-work so that the moment EXP-2 returns a verdict, the build target is already chosen with evidence instead of re-litigated. My known weak spot is ECONOMIC OPTIMISM, so the loop + ceiling claims are scored harshly._

> See VERTICAL-WHOA-EVIDENCE.md — falsifiable real-engine evidence on the G1/G2 ranking (2026-06-09): whoa-rate V3 100% > V2 63% > V1 50%; G1 density is LOWEST for V1, which keeps #1 only on G2 loop-overlap.

> **One-line answer:** Of eight concrete vertical re-skins, the winner is **SiteLens-as-is (web/SEO/perf audit for marketing freelancers & SMB-services), launched Chrome-Marketplace-native** — it is the ONLY candidate that maxes the rare Calendly property (the loop's *recipient is disproportionately also a target user*) AND is fully keyless-buildable AND is already 85%-built (EXP-2). The ranked queue behind it (the "family of swings" order) is: **#2 Local-Business Listing/Google-Profile audit → #3 Shopify/e-com store audit → #4 AI-Proposal generator (horizontal) → then the long-tail re-skins.** Two candidates are KILLED on loop leakage (contractor inspection report, restaurant menu audit) because their recipients are NOT in the ICP.

---

## 0. Why this decision matters NOW (not after EXP-2)

EXP-2 (SiteLens) proves the **mechanic** generically: does a send-to-a-non-user audit self-propagate (K≥0.4)? It does **not** by itself tell us **which vertical re-skin to commit the real build to** — and the synthesis explicitly defers that ("the experiments below pick the winner empirically rather than guessing the vertical now"). But three things make the empirical-only stance incomplete:

1. **EXP-2's SiteLens was chosen as the *smallest testable* deliverable, not the *best commercial vertical*.** If we treat "EXP-2 passed → build SiteLens bigger" as automatic, we may be optimizing the test artifact instead of the business. Conversely, if SiteLens *is* the best vertical (this doc argues it is), then EXP-2 isn't just a test — it's a head start on the real build, which materially de-risks the whole barbell.
2. **The synthesis's own hard gates for the vertical (§3: recipient-says-whoa, recipient-overlaps-ICP, share-is-mandatory, keyless-buildable) were never *applied* to specific verticals.** That application is pure desk analysis — $0, no gate, and it's the difference between "we'll figure out the vertical later" and "here's the ranked build queue, fire on EXP-2 verdict."
3. **The "family of swings" machine (`viral-swing-candidates.md` §7) needs a *queue order*** — which re-skin is swing #2, #3, #4 — so that the instant one swing is killed/shipped, the next spawns without a fresh research cycle. That order is decided here.

This is decision-prep, not make-work: it converts a vague "lean: product-led-loop tool; the question is WHICH vertical" into a scored, fire-ready queue.

---

## 1. The gates each vertical re-skin must clear

Re-stated from `TRACK-C-SYNTHESIS.md` §3 + `viral-swing-candidates.md` §3/§5, scored 0–5. The **non-negotiable** one is G2 (ICP-overlap) — it's the single property that made Calendly's loop compound and is the difference between K that climbs and K that leaks to zero.

| # | Gate | What 5 looks like | What kills it (≤2) |
|---|---|---|---|
| **G1** | **Recipient says "whoa" / screenshots it** | Output is visceral, specific, and about *their* asset; a recipient forwards it unprompted | Generic AI-slop → brand-on-every-audit becomes a *negative* |
| **G2** | **Recipient overlaps the ICP** (the Calendly property — THE gate) | The person who *receives* the deliverable is themselves a likely buyer of the tool | Recipient is a pure consumer who will never buy the tool → loop leaks → K→0 |
| **G3** | **Share is MANDATORY to the core job** | You cannot do the job without exposing a non-user (the deliverable *is* the thing you send) | Share is an optional "refer a friend" → K≈0 |
| **G4** | **Keyless / cheap agent-buildable substance** | Real signal from free/public data (raw HTML, public APIs, no paid keys) | Needs an expensive API or human judgment to produce credible output |
| **G5** | **Ceiling ≥$10k/mo with comparables** | Named real businesses of this shape near/above the line | Caps below $10k/mo |
| **G6** | **Marketplace-native launch surface exists** | A store (Chrome/Shopify/etc.) whose buyer-intent search supplies cold-start | No marketplace → pure cold outreach to ignite |

**Decision rule (inherited from the rubric):** any candidate with **G2 ≤ 2 is KILLED** regardless of other scores — a deliverable whose recipients can't convert is a loop that leaks to zero, the exact TRAP the synthesis warns about. G1 ≤ 2 is also fatal (negative-brand loop).

---

## 2. The candidate verticals (concrete re-skins of the one engine)

All are instances of Candidate A: an AI tool that produces a branded deliverable the user **sends to a prospect/client/counterparty**, carrying a "⚡ make your own" footer. The engine (crawl/analyze → score → branded hosted report + share hook + ref-attributed loop) is shared; only the *analysis target* and *ICP* change.

| Code | Vertical re-skin | User (who generates) | Recipient (who's sent it) | Analysis target |
|---|---|---|---|---|
| **V1** | **Web/SEO/perf audit** (= SiteLens, EXP-2) | Marketing freelancer / SMB-services seller | The prospect SMB they're pitching | Any website (HTML/SEO/perf/share-card) |
| **V2** | **Local-Business Listing / Google-Profile audit** | Local-SEO / GMB freelancer, agency | Local business owner (the prospect) | Public Google Business Profile + maps/citation signals |
| **V3** | **Shopify / e-com store audit** | E-com growth freelancer / agency | Store owner (the prospect) | Shopify storefront (theme/SEO/CRO/perf) |
| **V4** | **AI-Proposal / scope generator** (horizontal) | Any freelancer/agency | The prospect for the deal | (Inputs: scope + the prospect's site) |
| **V5** | **Social-profile / brand audit** | Social-media manager / personal-brand consultant | Creator / SMB prospect | Public social profile(s) |
| **V6** | **Contractor / home-inspection report** | Contractor, home inspector | Homeowner client | Property (photos/checklist) |
| **V7** | **Restaurant menu / online-presence audit** | Restaurant-marketing freelancer | Restaurant owner | Menu + listings + site |
| **V8** | **Resume / LinkedIn audit** | Career coach / resume writer | Job-seeker client | Resume file + LinkedIn profile |

---

## 3. The scorecard (harsh on loop + ceiling; G2 is the kill gate)

Scores 0–5. **KILL** = any G1 or G2 ≤2. Bold = the decisive gate for that row.

| Vertical | G1 whoa | **G2 ICP-overlap** | G3 share-mandatory | G4 keyless-build | G5 ceiling | G6 marketplace | Verdict |
|---|---|---|---|---|---|---|---|
| **V1 Web/SEO audit (SiteLens)** | 4 | **5** | 5 | 5 | 4 | 5 | **WINNER — advance** |
| **V2 Listing/GMB audit** | 4 | **4** | 5 | 4 | 4 | 4 | **#2 queue** |
| **V3 Shopify/e-com audit** | 4 | **3–4** | 5 | 4 | 4 | **5** | **#3 queue** |
| **V4 AI-Proposal (horizontal)** | 3 | **4** | 5 | 4 | 4 | 3 | **#4 queue** |
| **V5 Social/brand audit** | 4 | **3** | 4 | 3 | 3 | 3 | hold |
| **V6 Contractor/inspection** | 4 | **1** | 5 | 2 | 4 | 2 | **KILL (G2)** |
| **V7 Restaurant menu audit** | 3 | **1** | 4 | 3 | 3 | 3 | **KILL (G2)** |
| **V8 Resume/LinkedIn audit** | 4 | **2** | 4 | 3 | 3 | 4 | **KILL (G2)** |

### Why the kills (this is where most candidates die — exactly as the rubric predicts)

- **V6 Contractor/inspection report — KILL on G2=1.** The recipient is a *homeowner*. A homeowner who receives a slick inspection report will essentially **never sign up to generate their own inspection reports** — they're a one-time consumer, not a peer. The loop leaks 100% on the recipient side → K collapses to zero no matter how impressive the report. Also G4=2 (credible inspection data needs photos + human judgment, not keyless public signal). Textbook TRAP: great-looking deliverable, dead loop.
- **V7 Restaurant menu audit — KILL on G2=1.** Recipient is a *restaurant owner* who wants customers, not a tool to audit *other* restaurants. No peer-overlap → no recruitment → K→0. (A restaurant owner is a buyer of *marketing services*, not of an *audit tool*.)
- **V8 Resume/LinkedIn audit — KILL on G2=2.** Recipient is a *job-seeker*. Job-seekers are transient and rarely become career-coaches who'd buy the tool; the overlap is thin and one-directional. Tempting (huge volume) but the loop leaks. (Note: a job-seeker MIGHT forward to a peer job-seeker — a weak consumer-UGC loop — but that's V-D-class UGC, not the Calendly inherent loop, and it doesn't recruit *buyers*. Held as a possible UGC-toy swing, not a Candidate-A build.)

### Why the survivors rank as they do

- **V1 (SiteLens) wins — and it's the rare G2=5.** When a marketing freelancer sends a website audit to a prospect SMB, the recipient (the SMB owner) is themselves **the exact person who hires marketers and might run an audit on a competitor or their own next project** — and, critically, *other marketers/agencies* who receive these audits (because audits get forwarded inside the buyer's org and shared in marketing circles) are *directly* the ICP. This is the one vertical where the recipient pool is maximally enriched with target users = the Calendly overlap. It's also **already built (EXP-2, 85 tests green)** and **keyless-maxed** (raw HTML/SEO/perf/share-card, no paid key needed for the core report). G1=4 only (not 5) because the "whoa" still partly wants the live-perf ring (PSI, a Cyrus-gated free key) for the last 10% — but the keyless benchmark-percentile hook (hardening pass 4) already supplies most of the visceral punch.
- **V2 (Listing/GMB audit) is the strongest *next* swing.** Local-SEO is a massive freelancer market; the recipient is a local-business owner (a buyer of local-marketing services, decent G2=4) and the deliverable ("your Google Business Profile is missing X, Y, Z; you're invisible for [category] near you") is **visceral and local = high whoa**. Slightly lower G4 (some GMB signals are keyless-scrapeable from the public profile/maps, but the richest data sits behind Google's APIs/ToS — needs care to stay keyless + ToS-clean). Natural swing #2 because it reuses ~80% of the engine and hits a *different* freelancer ICP, widening the family without new infrastructure.
- **V3 (Shopify/e-com audit) has the best G6=5** (Shopify App Store buyer-intent is the cleanest marketplace cold-start in the whole research — Category 4 winner) but a slightly thinner G2 (a Shopify store owner is a buyer of *apps/services*, moderately likely to be a peer; agencies that serve e-com ARE strong peers). Ranks #3 because the marketplace surface is gold but the build needs e-com-specific analysis (theme/CRO/Liquid) = more re-skin work than V2.
- **V4 (AI-Proposal generator) is the horizontal generalization** — strong G2 (recipient is a prospect, sender is a freelancer; proposals get forwarded among decision-makers) but lower G1 (a proposal is *expected*, less "whoa" than an unsolicited audit that exposes problems) and lower G6 (no obvious single marketplace; it's a standalone-SaaS shape). Ranks #4: a good later swing once the audit-family loop is proven, because "audit → proposal" is a natural product expansion (the audit *becomes* the top of the proposal).
- **V5 (Social/brand audit) held, not killed.** G2=3 (recipient is a creator/SMB, moderate overlap) and G1=4 (social audits are visceral), but G4=3 (most social platforms wall their data → keyless signal is thin and brittle, and ToS-risky to scrape) drags it. Revisit only if a keyless public-signal source proves robust.

---

## 4. THE DECISION

**Build target on EXP-2 PASS = V1 (SiteLens) as the committed v1, launched Chrome-Marketplace-native (EXP-3's "PagePeek" is the marketplace beachhead of the same engine).**

This is the decisive, non-obvious conclusion the empirical-only framing missed: **the test artifact and the best commercial vertical are the same thing.** That means:
- EXP-2 is not a throwaway probe — a PASS converts directly into the real build with near-zero pivot cost. The 85-test engine, the benchmark-percentile data-moat seed, and the ignition-targeting harness are all *already the v1*.
- We do **not** need to guess or re-research the vertical post-experiment for the spine. The spine's vertical is locked: **web/SEO/perf audit for the marketing-freelancer/SMB-services ICP.**
- The **data-moat leg** of the barbell is *also* already seeded inside V1 (the compounding `scores.jsonl` benchmark distribution = a proprietary score-distribution dataset that sharpens at $0). So V1 simultaneously serves the spine (loop) AND begins the compounding leg — the exact barbell shape, in one artifact.

**The "family of swings" queue (fire order, post-spine-validation):**
1. **V1 SiteLens** (spine, already built) — prove K with ignition seeding (the EXP-2 gate).
2. **V2 Listing/GMB audit** — first re-skin; different freelancer ICP, ~80% engine reuse, high local-whoa.
3. **V3 Shopify/e-com audit** — best marketplace surface (Shopify App Store), e-com re-skin.
4. **V4 AI-Proposal generator** — horizontal expansion; the audit becomes the proposal's spine.
5. (Hold: V5 social/brand pending a robust keyless data source. Killed: V6/V7/V8 on loop leakage.)

Each subsequent swing only spawns **after** V1's loop is empirically validated or killed (no firing loop-less re-skins — `viral-swing-candidates.md` §2 trap). If V1's K passes, V2/V3 are near-free additional tickets on a proven engine; if V1's K fails, the whole Candidate-A family is suspect and the barbell leans to the marketplace/data-moat leg (per the synthesis FAIL branch).

---

## 5. What would FLIP this decision (the falsifiers — watch these)

- **If EXP-2 returns K-FAIL on V1**, do NOT immediately try V2/V3 hoping a different vertical saves the loop — first diagnose *which half* of K failed (reach/seed vs recipient→creator conversion; `report.mjs` surfaces both). A reach failure might be vertical-agnostic (ignition problem, affects all re-skins equally); a conversion failure might be specific to the SMB-owner recipient (then V3's agency-recipient or V4's decision-maker recipient could genuinely differ). Only re-skin if the failure is *conversion-side and recipient-specific*.
- **If EXP-3 (Chrome cold-start) shows the store supplies real organic installs**, that *raises G6 for the marketplace-native verticals* (V1-via-PagePeek, V3) and could promote V3 (Shopify, the strongest marketplace) ahead of V2 in the queue — because marketplace-supplied cold-start partially solves the ignition wall that the synthesis calls the #1 risk.
- **If a keyless, ToS-clean, robust local-business data source is found** (e.g. a stable public GMB/maps signal), V2's G4 rises 4→5 and it becomes nearly as strong as V1.
- **My optimism check:** I'm probably over-weighting V1's G2=5. The honest risk is that in practice the audit recipient (SMB owner) hands it to their *existing* marketer rather than signing up themselves — meaning the real recruited user is the *competitor marketer*, which is fine for K but means the loop recruits *supply-side* (more freelancers) not *demand-side* (more SMBs). That still compounds K (more freelancers = more audits sent) but it's a different growth shape than I'm modeling. EXP-2's instrumentation (creator-vs-recipient cookie + ref-chain) will reveal which it is — trust that readout over this projection.

---

## 6. Status / handoff

- **Decision locked (reversible on EXP-2 evidence):** spine vertical = **V1 SiteLens (web/SEO/perf audit, marketing-freelancer ICP), Chrome-marketplace-native.** Build target chosen; no post-experiment vertical re-research needed for the spine.
- **Queue locked:** V1 → V2 → V3 → V4; V6/V7/V8 killed on loop leakage; V5 held.
- **Unblocks:** the moment Cyrus clears the EXP-2 ignition gate (free PSI key + domain ~$12 + ~30-min hand-seed of ~20–50 audits) and EXP-2 returns PASS, the real v1 build = the EXP-2 engine itself, hardened — **zero pivot, zero re-research.** If FAIL, §5 gives the exact branch logic.
- **No Cyrus gate touched by this analysis** ($0, desk work). The gates it *informs* (PSI key, domain, Chrome dev $5) are already flagged in the backlog.
