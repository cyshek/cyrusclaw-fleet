# Real-Time AI Copilot for Live Conversations — Competitive Landscape & Pricing Teardown

_Compiled 2026-06-03. Scope: tools that listen to a live call (system audio + mic), transcribe, and feed a rolling transcript + user context into an LLM to surface answer/coaching suggestions on a discreet overlay in near-real-time. Focus = legit use (sales, CS, pre-sales, meetings), NOT interview cheating. All $ figures are publicly listed/reported as of mid-2026; quote-based enterprise pricing noted as such._

---

## 1. The Players (grouped)

### (a) Live whisper / overlay copilots — the direct analogs
These are the closest to the proposed product: a stealth desktop overlay that listens and surfaces suggested answers live.

| Tool | What it does | Real-time? | Pricing | Funding / scale |
|---|---|---|---|---|
| **Cluely** | Stealth macOS/Windows overlay; reads audio + screen, surfaces AI answers/notes via hotkey across Zoom/Meet/Teams/Webex/Slack. Rebranded from "Interview Coder." Now pivoting messaging to "AI meeting assistant" for sales/meetings. | **Yes** (claims 300ms; Business Insider testing found **5–10s actual latency**) | Free (limited) / **$19.99/mo Pro** / **$149.99/mo Pro+Undetectability**. No annual discount, no team pricing. | Raised **$120M+** total (started at $5.3M seed). Has Wikipedia page, iOS app. **2025 data breach exposed 83K users'** transcripts/screenshots. Sources: cluely.com/pricing, toolradar.com/tools/cluely/pricing, interviewsidekick.com/blog/cluely-review |
| **Parakeet.ai** (ParakeetAI d.o.o., Slovenia) | Real-time interview copilot: transcribes interviewer audio, detects questions, overlays GPT-5/GPT-4.1/Claude-4-Sonnet answers. macOS/Windows. | **Yes** | **Pay-per-use credit model** (no flat sub). Actual $ hidden until login; promo-code-gated discounts. | No disclosed funding, no Crunchbase. Self-reports 1.5M users (unverified). Caveat: **process name visible in Activity Monitor**. Source: interviewsidekick.com/blog/parakeet-ai-review |
| **Others in this niche** | Interview Coder (origin of Cluely), Final Round AI, LockedIn AI, Sensei, Verve AI, Lockedin — almost ALL positioned at **interview cheating**. Pricing clusters $30–$96/mo. | Yes | $20–$96/mo typical | Mostly tiny/solo or seed-stage; high churn, app-store-policy and detection risk. |

**Key takeaway:** the overlay-copilot category is _commercially_ dominated by interview-cheating tools. Cluely is the only one with real scale/funding, and it's bleeding trust (breach, latency lies, detection arms race). The **legit-use overlay copilot for sales/CS is essentially greenfield** in the "discreet live whisper" form factor — but see §3 for why that's both opportunity and trap.

### (b) Sales conversation intelligence — mostly POST-call, enterprise
| Tool | What it does | Real-time? | Pricing | Funding / scale |
|---|---|---|---|---|
| **Gong** | Category-defining revenue intelligence. Records/transcribes calls, analyzes deals, coaching, forecasting. | **Mostly post-call** (analysis, not live whisper) | 3-part: **$5K–$50K platform fee** + **$1,360–$1,600/user/yr** + **$7.5K–$28.5K onboarding**. ~$238/user/mo effective Y1. ~$194K Y1 TCO for 100 users. Quote-based, opaque, 5–7% YoY renewal uplifts. | Public-scale (~$300M+ ARR, multi-$B valuation). Source: claap.io/blog/gong-pricing, oliv.ai/blog/gong-io-pricing |
| **Chorus (ZoomInfo)** | Conversation intelligence, now bundled into ZoomInfo. Post-call analysis + coaching. | Post-call | Bundled w/ ZoomInfo (quote-based; often $$$). | Acquired by ZoomInfo 2021 (~$575M). |
| **Otter.ai** | Live transcription + notes; "OtterPilot for Sales" adds CRM sync + live insights. | **Partial live** (live transcript/captions; insights lean post) | Free (300 min/mo) / Pro ~$17/mo / Business ~$30/mo / Enterprise. Source: otter.ai/pricing | VC-backed (~$60M+ raised), millions of users. |
| **tl;dv** | Meeting recorder + AI notes, multi-language, CRM push. | Post-call | Free tier / paid ~$18–$29/seat/mo (annual discounts). | Seed/Series-A scale, EU-based. |
| **Attention** | AI for sales: live + post-call, auto-fills CRM, real-time battlecards/coaching prompts during calls. | **Yes — live coaching** | Quote-based (~$50–$100+/seat/mo reported). | Series A (~$14M, a16z). One of the few _true live sales-assist_ players. |
| **Momentum** | AI that listens to sales calls, auto-syncs to Salesforce/Slack, deal summaries. | Mostly post-call | Quote-based. | Seed/Series-A. |

### (c) Meeting notetakers — commodity, cheap, huge install base
| Tool | What it does | Real-time? | Pricing |
|---|---|---|---|
| **Fireflies.ai** | Bot-joins meetings, transcribes, AI summaries, "AskFred" assistant. | Live transcript yes; AI mostly post | Free (unlim transcription, 800 min storage) / **Pro $18/mo ($10 annual)** / Business ~$19 / Enterprise ~$39. Source: fireflies.ai/pricing |
| **Fathom** | Bot or bot-free capture, instant summaries, CRM sync, coaching scorecards. | Summary near-instant post-call | **Free forever (unlimited)** / Premium $20 ($16) / **Team $19 ($15)** / Business $34 ($25). Source: fathom.ai/pricing |
| **Granola** | Mac-native notetaker; listens to system audio (no bot), enhances your own notes. | Live capture, post enhancement | Free tier / ~$18/mo / Business ~$35. Backed by Lightspeed/a16z. |
| **Otter** | (see above) | Partial live | $0–$30/mo |

### (d) CS / support agent-assist — real-time, enterprise contact-center
| Tool | What it does | Real-time? | Pricing | Funding |
|---|---|---|---|---|
| **Cresta** | Real-time agent assist for contact centers: live transcription, suggested responses, compliance prompts, coaching during calls. **This is the closest enterprise analog to the proposed product, but for call-center seats.** | **Yes — true live whisper** | Quote-based enterprise (per-seat, typically $100–$300+/seat/mo at scale). | ~$270M+ raised, Series D, ~$1.6B valuation (Greylock/Sequoia). |
| **Forethought** | AI support automation + agent assist (suggested replies, knowledge surfacing). | Live + automation | Quote-based enterprise. | ~$90M+ raised. |
| **Cogito, Balto, Observe.AI** | Real-time agent guidance, emotion/compliance nudges, QA. | Yes | Enterprise quote-based. | Balto/Observe = Series B/C; Observe ~$200M raised. |

---

## 2. Pricing Patterns Across the Category

- **Notetakers (commodity floor):** Free tiers are now **table stakes and genuinely generous** (Fathom = unlimited free; Fireflies = unlimited transcription free). Paid = **$10–$25/seat/mo**. This is a brutal, race-to-zero segment. Do not enter here.
- **Live overlay copilots (consumer/prosumer):** **$20–$150/mo**, single-seat, no team plans, often credit-based. High willingness-to-pay for "undetectability" (Cluely's $149.99 tier) but that premium is tied to the _cheating_ use case.
- **Sales conversation intelligence (enterprise):** **$1,300–$1,900/user/yr + platform fees** (Gong). Effective **$100–$240/seat/mo**. Sticky, opaque, sales-led, 6-figure contracts.
- **CS agent-assist (enterprise):** **$100–$300+/seat/mo**, quote-based, long sales cycles, on-prem/compliance demands.
- **STT (variable cost):** real-time streaming is **$0.0025–$0.0077/min** = **$0.15–$0.46/hr** of audio (see §4). A heavy user on 4 hrs/day of calls ≈ 80 hrs/mo ≈ **$12–$37/mo in raw STT** — meaning STT is a real but manageable COGS line; LLM tokens for suggestions are the bigger swing.

**Pattern summary:** the market is **barbelled** — cheap commodity notetakers at one end ($0–$25), heavy enterprise platforms at the other ($100–$240/seat). The **prosumer live-copilot middle ($20–$60/seat, self-serve, real-time)** is thinly populated by trust-damaged players (Cluely) and cheating tools.

---

## 3. Where the White Space Is (specific & honest)

**Where you CANNOT win:**
- **Generic notetaking** — Fathom/Fireflies give it away free with unlimited usage. Dead on arrival.
- **Enterprise revenue intelligence** — Gong/Chorus own this; requires a sales org, SOC2, integrations, multi-quarter cycles. A solo + Cyrus cannot wedge here.
- **Interview cheating** — the obvious "easy money" lane is saturated, getting actively detection-countered (recruiter tools that catch Cluely), app-store-risky, and ethically off-limits per the brief.

**Where a small, focused MVP COULD wedge (the honest gaps):**
1. **Vertical-specific live answer copilot for a niche with high-stakes, knowledge-heavy live calls — and no incumbent.** Examples:
   - **Solo/SMB pre-sales & solutions engineers** doing technical demos who need instant recall of product specs/pricing/objection rebuttals. Gong is too heavy/expensive; notetakers don't surface live answers. A **$30–$50/mo single-seat "live demo copilot" that ingests YOUR product docs/spec sheets and whispers answers** is a real gap.
   - **Customer-success ICs at SMBs** handling renewal/upsell calls without a Cresta-sized budget.
   - **Independent consultants / agencies / fractional execs** on client calls who want their own knowledge base surfaced live.
2. **"Bring your own context docs" as the wedge.** The incumbents surface _generic_ AI answers or _post-call_ analysis. Very few do **live, RAG-grounded answers from the user's own uploaded docs** (battlecards, pricing, KB, past-deal notes) with <2s latency. That grounding + privacy ("your docs, your overlay, nothing shared to a vendor cloud breach") is a credible differentiator _against Cluely specifically_ (whose breach is a live trust wound).
3. **Trust/privacy positioning.** Cluely just leaked 83K users. A **local-first / privacy-forward** live copilot ("transcript and docs stay on-device or in your own keys") is a real narrative wedge, especially for regulated-adjacent SMB verticals.
4. **Latency as the product.** Cluely's real-world 5–10s latency is the gap between marketing and reality. A genuinely **<2s** overlay (achievable with Deepgram/AssemblyAI streaming + a fast small LLM like Groq) is a demonstrable, demo-able edge.

**Honest caveat:** every one of these is a _narrow_ wedge, and "live answer suggestion" is a feature that Otter/Fireflies/Attention can bolt on. The defensibility is **vertical depth + context-grounding UX + trust**, not the core tech (which is a weekend's worth of STT+LLM plumbing).

---

## 4. Technical Building Blocks (STT + latency)

Real-time streaming STT pricing (2026), the foundational COGS:

| Provider / model | Streaming price | WER (accuracy) | Notes |
|---|---|---|---|
| **AssemblyAI Universal-Streaming** ⭐ | **$0.15/hr ($0.0025/min)** — cheapest | Universal-2 ~5.9% | 6 languages; LeMUR for LLM analysis on top; $50 free credit (~333 hrs streaming) |
| **Deepgram Nova-3** ⭐ | **$0.0077/min ($0.46/hr)** PAYG; $0.39/hr Growth | **5.26% (best batch)**; best real-time latency | $200 free credit (~433 hrs). Industry default for low-latency streaming. |
| **OpenAI gpt-4o-mini-transcribe** | **$0.003/min** | ~5–7% | Streaming via WebSocket (since Mar 2025); cheap, decent |
| **OpenAI gpt-4o-transcribe** | $0.006/min | ~35% better than whisper-1 | Streaming supported |
| **Groq (Whisper large-v3-turbo hosted)** | ~$0.02–$0.04/hr equivalent, **extreme speed** | Whisper-class | Groq's edge = throughput/latency, good for fast turnaround |
| **Whisper self-hosted (large-v3-turbo)** | infra-only | Whisper-class | 6× faster than large-v3; no per-min fee but you run GPUs |
| Google Chirp 3 | $0.016/min standard | best multilingual | most expensive of the group; built-in denoiser |

Sources: apiscout.dev/guides/speech-to-text-api-comparison-2026, deepgram.com/learn/speech-to-text-api-pricing-breakdown-2025, assemblyai.com/blog.

**Typical latency budget for a <2s overlay:**
- Streaming STT partial transcript: **~200–500ms** (Deepgram/AssemblyAI real-time).
- LLM answer generation: the bottleneck. A small/fast model (Groq Llama, GPT-4o-mini, Claude Haiku) with first-token streaming gets **~300–800ms to first token**; full short answer ~1–1.5s.
- **Net achievable: ~1–2s to useful on-screen suggestion** — realistic with the cheap streaming STT + a fast model, IF you keep the prompt/context tight (rolling transcript window + RAG-retrieved doc snippets, not the whole KB).
- Cluely's failure (5–10s) suggests they over-stuff context or use a slow model. **Beating them on latency is a tractable engineering goal, not magic.**

**Rough COGS per active user/mo** (4 hrs calls/day, 20 days = 80 hrs/mo):
- STT: 80 hrs × $0.15–$0.46/hr ≈ **$12–$37/mo**.
- LLM: heavily depends on trigger frequency; with mini models and gated triggering (only on detected questions), plausibly **$5–$20/mo**.
- **Total COGS ~$17–$57/active power-user/mo** → a $40–$60/mo price point has thin-but-real margin on heavy users, healthy margin on average users. Gating LLM calls (only fire on question-detection, not every utterance) is the key lever.

---

## 5. Verdict — Buildable wedge, or "cool tech, bad business"?

**Verdict: A narrow, buildable wedge exists — but it's a feature-grade product in a fast-commoditizing space, not a defensible platform. Proceed only with a sharp vertical + trust angle, not as "Cluely but legit."**

Honest scorecard:
- ✅ **Tech is genuinely buildable solo.** Streaming STT + fast LLM + overlay UI = a real MVP in days-to-weeks. <2s latency is achievable and is a real, demoable edge over Cluely's 5–10s reality. COGS are manageable with question-gated LLM triggering.
- ✅ **Trust/privacy white space is real and timely.** Cluely's 83K-user breach is a live wound; a privacy-forward, BYO-docs, local-first copilot has a credible counter-narrative.
- ✅ **The "your own context docs, surfaced live" RAG angle is underserved** by both the cheap notetakers (post-call, generic) and the expensive enterprise platforms (heavy, slow to deploy).
- ⚠️ **But the core capability is a feature, not a moat.** Otter/Fireflies/Fathom/Attention can each bolt "live answer suggestions from your docs" onto an existing distribution base. Defensibility must come from **vertical depth (one niche, done excellently)** + **UX/latency** + **trust**, none of which a solo builder holds durably.
- ⚠️ **Distribution is the actual hard part, not the build.** This is a crowded, marketing-driven category (Cluely won on virality, not tech). A solo agent + Cyrus has no sales org for enterprise and faces free-tier competitors for prosumer.
- ❌ **Do NOT** try to compete head-on with Gong (enterprise), with free notetakers (commodity), or in the interview-cheating lane (saturated, risky, off-brief).

**Recommended shape if pursued:** a **single-seat, $30–$60/mo, vertical-specific live "answer copilot"** (pick ONE: solo/SMB pre-sales engineers, or independent consultants, or SMB customer-success) that (1) ingests the user's own product/KB docs, (2) surfaces RAG-grounded suggestions in <2s via Deepgram/AssemblyAI streaming + a fast model, (3) leads hard on **privacy/local-first** as the anti-Cluely. Validate with 5–10 paying users in one vertical before building anything broad. Treat it as a **lean, possibly-lifestyle-scale** product, not a venture-scale platform — the venture-scale lanes are already owned.

---
_Sources cited inline. Pricing for Gong, Chorus, Attention, Cresta, Forethought is quote-based; ranges reflect public reports/third-party estimates and should be verified before any go/no-go decision. Cresta funding/valuation figures are from general market reporting and approximate._
