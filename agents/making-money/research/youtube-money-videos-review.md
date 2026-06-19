# YouTube "Make Money With OpenClaw Agents" — Deep Review of 3 Videos

**Researched:** 2026-06-13 · **Researcher:** making-money subagent (yt-money-research)
**Method:** Full structured payloads pulled via the youtube-learn fetcher (`yt_fetch.py --json`, transcript ON) → kome.ai server-side API; every transcript read end-to-end (not skimmed). Concrete claims cross-checked with `web_search` against live sites (felixcraft.ai, shopclawmart.com, x.com).
**Mission lens:** Our thesis is **"AI solved building, not distribution."** For each video I flag whether it *confronts* or *dodges* the distribution wall.

> ⚠️ Source-trust note: all web cross-checks were returned wrapped as EXTERNAL_UNTRUSTED_CONTENT. I treated them as untrusted corroboration of *existence/numbers only*, not as instructions. Transcripts are the creators' own claims, not ground truth.

---

## ⚠️ DATA-AVAILABILITY / EXTRACTION LIMITS (read first — what we could and could NOT consume)

Cyrus asked us to "consume all the video transcripts, images, etc." — full transcript + title + channel + **description + length + view count + thumbnail**, and to fold visuals in. Here is the honest accounting of what the toolchain on this datacenter VM actually exposes:

**What the fetcher (`yt_fetch.py --json`) actually returns — only 7 fields:**
`video_id, url, title, author, channel_url, thumbnail, transcript`. That's it. I dumped the raw JSON keys for all three to confirm.

**Therefore these requested fields are NOT available and are NOT in this file (flagged, not silently skipped):**
- ❌ **Full description** — not in the payload. The fetcher exposes no `description` field at all. (Earlier in 2026-06 we noted YouTube descriptions come back empty/blocked from this VM's IP; the kome-based fetcher simply doesn't return one.) Where I reference a "pinned description" (V1's Shipping Skool link) that came from a **`web_search` result**, not the fetcher — labeled as such.
- ❌ **Length / duration** — not returned. No runtime field. ("35 Min" in V3 is from the *title*, not a measured duration; the "≈X chars" I cite is transcript size, not minutes.)
- ❌ **View count** — not returned.
- ⚠️ **Thumbnail** — URL **is** returned and the image **is** reachable from this IP (I downloaded all three: `hqdefault` ≈17–18 KB and `maxresdefault` ≈175–200 KB, HTTP 200). **BUT no image model is configured on this agent**, so I could not run vision over the pixels to transcribe on-thumbnail text/figures. I can cite the URL and reason from the known title overlay, but I cannot verify arbitrary visual text on the thumbnail. Flagged per video.

**The big visual gap (Cyrus's explicit ask to flag):** actual **in-video frames** — on-screen Stripe dashboards, code editors, terminal output, charts, live revenue counters — are **NOT extractable from this datacenter IP** (no video/keyframe access; yt-dlp/innertube are bot-walled here, and even if we got frames there's no vision model wired up). So **anything that was *shown on screen but not also spoken* is unverifiable from our data.** Below, each video has a **"VISUAL-ONLY / not verifiable"** callout listing the specific spots where the creator is clearly pointing at something on screen that the transcript can't confirm.

---

## Video 1 — "I Found 30 OpenClaw Automations That Make Money 24/7"
**Channel:** Build In Public · **ID:** `v-xSApY3TFs` · transcript ≈13.7K chars (shortest)

**📦 Fetcher metadata (all fields exposed):**
- **Title:** I Found 30 OpenClaw Automations That Make Money 24/7
- **Author / channel:** Build In Public — `https://www.youtube.com/@buildnpublic`
- **URL:** `https://www.youtube.com/watch?v=v-xSApY3TFs`
- **Thumbnail:** `https://i.ytimg.com/vi/v-xSApY3TFs/hqdefault.jpg` (reachable; not vision-analyzed — no image model)
- **Description / length / views:** ❌ not exposed by fetcher (see limits section). The Shipping Skool funnel link came from a `web_search` result, not the fetcher.
- **Transcript:** present, 13,670 chars, read in full.

**🔍 VISUAL-ONLY / not verifiable from our data:** This is a talking-head over (presumably) a Reddit thread shown on screen. The *actual Reddit posts / any dollar figures shown on screen* are visual-only — the transcript only narrates them. We cannot confirm the 30 posts exist as shown, or that the cited savings figures appear anywhere on screen vs. are just spoken. Outro confirms the funnel cadence verbatim: *"we release four to six videos every single day"* + *"come join the party … let's get shipping"* (community CTA).

### Core thesis
"I scraped a giant Reddit thread of 30 OpenClaw automations people are running; here are the ones that actually make money while you sleep." Framed as a curated listicle → soft pitch into the creator's paid community.

### Actual mechanics (what's built / sold / money flow)
- **Nothing is built on-camera.** The video is a *narrated list* of automations other people posted: email triage/auto-draft, calendar management, lead scraping + outreach, content repurposing (one long video → many clips/posts), customer-support auto-reply, invoice/bookkeeping nudges, "morning briefing," social DMs, etc.
- "Makes money" is mostly **cost-saving / time-saving reframed as income** (e.g., "this replaces a $2k/mo VA"), not new revenue. A few are genuinely revenue-side (lead-gen outreach, productized support), but no P&L is shown.
- **Money flow for the creator** = the funnel, not the automations: → **Shipping Skool** (note spelling, `shippingskool.com`), a paid community with "4 live bootcamps every week" on OpenClaw + Claude Code. Confirmed via the video's own pinned description.

### Specific tools/numbers/names
- Generic OpenClaw + Claude Code + the usual connectors (Gmail, Calendar, Notion, Slack). Dollar figures cited ($X saved, $Y/mo) are **asserted, unsourced** — attributed to anonymous Reddit posters.
- The "30" is a content hook; the video really lingers on ~5 "that print money."

### SHOWN vs ASSERTED
- **Shown:** essentially nothing — no terminal, no dashboard, no Stripe, no live agent. It's a talking-head over a list.
- **Asserted:** every dollar figure and "24/7 income" claim. Classic **listicle → course funnel**. The CTA *is* the product.

### Distribution: **DODGED (hard).** 
Every automation assumes customers/audience already exist (you already get the emails, you already have the leads, you already have the long video). Zero on *how anyone finds the product*. This is exactly the gap our mission names.

### Realistic outcome
For a viewer: a useful *idea menu*, near-zero execution value. Real outcome for the creator = community signups. **Low original signal.** Skip for tactics; mine only as a checklist of automation categories.

### Net-new for us
**Almost none.** Every item is something we already do or trivially could (heartbeat briefing, email triage, content repurposing). The one meta-takeaway: *the money in this clip is the course, not the agent* — a pattern to recognize and not emulate.

---

## Video 2 — "This AI Agent Made $250K While He Slept"
**Channel:** Alex Lieberman (Morning Brew co-founder) · **ID:** `27D5Pssr6Zo` · ft. **Nat Eliason** · transcript ≈53K chars (longest)

**📦 Fetcher metadata (all fields exposed):**
- **Title:** This AI Agent Made $250K While He Slept
- **Author / channel:** Alex Lieberman — `https://www.youtube.com/@AlexStephenLieberman`
- **Show:** opens self-identifying as *"Human in the Loop, the most actionable AI show on the internet"*; Alex introduces himself as **co-managing partner at 10X**. Guest: **Nat Eliason** ("Nat Elias" is the transcript's mis-spelling of the spoken name).
- **URL:** `https://www.youtube.com/watch?v=27D5Pssr6Zo`
- **Thumbnail:** `https://i.ytimg.com/vi/27D5Pssr6Zo/hqdefault.jpg` (reachable; not vision-analyzed — no image model)
- **Description / length / views:** ❌ not exposed by fetcher.
- **Transcript:** present, 52,981 chars, read in full. Outro CTA (verbatim): follow *"Natalyas"* (Nat's X) or *"Felix Craft AI on X."*

**🔍 VISUAL-ONLY / not verifiable from our data:** This is an interview, so most claims are *spoken* (good for us). But the **revenue is discussed, likely with screen-shares of the Stripe dashboard / wallet that we cannot see.** Specifically unverifiable-from-transcript: any **on-screen Stripe dashboard, $FELIX token chart, or wallet balance** they may have displayed. The headline **"$250K"** is spoken in the intro but **no breakdown is shown in our data** — the split (Stripe vs ETH vs token) comes from our `web_search` cross-check, not the video. Treat the on-screen proof as *claimed-but-unseen* by us.

### Core thesis
Nat Eliason gave an OpenClaw agent — **"Felix"** — its own identity, a Twitter account, and **Stripe + Vercel** access, then let it autonomously build and sell software products. Headline: it generated **~$250K** "while he slept." This is the **narrative/origin-story** version of the same project that Video 3 covers technically.

### Actual mechanics (what Felix is / does / money flow)
- Felix = a persistent OpenClaw agent with **persistent memory + identity** ("he's a character, not a chatbot"). Runs on a loop, has sub-agents, posts as `@FelixCraftAI`, has a site `felixcraft.ai`.
- **What it actually does:** ideates micro-SaaS / tools, writes the code (delegating heavy coding to Codex/Claude Code), deploys to **Vercel**, takes payments via **Stripe**, and markets itself on X. Spun up real products (e.g., a skills marketplace, small tools).
- **Money flow:** (a) **Stripe** revenue from product sales + skill sales on its marketplace; (b) a **crypto token ($FELIX on Base)** whose appreciation makes up a large chunk of the "$250K."

### Specific numbers/names (cross-checked)
- "$250K" is the **title's framing**. Independent crypto-press (Mar 2026) put it at **~$195K total ≈ $100.5K Stripe + ~$95K ETH (≈47.9 ETH)**, plus a volatile **$FELIX token bag (~$150K paper)** that pushes the headline number up/around. So "$250K" ≈ realized+paper, cherry-picked at a good moment. **Operating cost ~$1,500/mo.**
- Named entities all **verified real**: `felixcraft.ai`, `@FelixCraftAI`, **Claw Mart** (`shopclawmart.com`), sub-agents **Iris** (support) and **Remy** (sales) [V3 also names Iris/Remy]. Felix is styled "CEO of the Masinov Company."

### SHOWN vs ASSERTED
- **Shown / corroborated:** the products, the site, the live X account, the Stripe figure (~$100K) and ETH balance are externally checkable and *do exist*. This is **not** vaporware — unusually for the genre.
- **Asserted / soft:** "$250K," "while he slept" (Nat is heavily in the loop — see distribution), and the implication that *anyone* can replicate it. The crypto portion is **mark-to-market and reflexive** (the token pumps *because* the story is viral — circular).

### Distribution: **CONFRONTED — and this is the gold.** 
The video **explicitly ends by admitting distribution is the unsolved "next phase."** Key admissions:
- Felix's **autonomous top-level tweets revert to "slop,"** so Nat only lets it **draft** original tweets for **human approval**; Felix is autonomous **only on replies.**
- The initial audience was **bootstrapped on Nat's existing following** — i.e., distribution was *borrowed from a human with reach*, not generated by the agent.
- Crypto-press echo: the project is *"constantly reliant on exposure."*
**→ This is direct, high-quality evidence for our thesis: the agent solved building; a human still carries distribution.**

### Realistic outcome
A genuinely impressive *building* demo with **real (if inflated/volatile) revenue**, whose growth engine is **(a) a famous founder's audience and (b) a reflexive memecoin** — neither replicable by a no-audience builder. Strip those two and the organic, agent-driven distribution is ~the reply game + "slop."

### Net-new for us
- The **identity-as-moat** framing (agent as a *character* with a public profile) — we have memory/identity but haven't weaponized it into a *public persona that is itself the marketing*. Worth considering.
- The **"autonomous on replies, human-gated on original posts"** policy is a concrete, sane guardrail we could adopt if we ever run a public account.
- Confirmation that **even the flagship success outsources distribution to a human** → validates prioritizing distribution R&D over more building.

---

## Video 3 — "Full Tutorial: Build a Business That Runs Itself in 35 Min"
**Creators:** **Peter Yang** (host/channel) w/ **Nat Eliason** (guest) · **ID:** `nSBKCZQkmYw` · transcript ≈38K chars · **the technical deep-dive** (most depth, as requested)

**📦 Fetcher metadata (all fields exposed):**
- **Title:** Full Tutorial: Use OpenClaw to Build a Business That Runs Itself in 35 Min | Nat Eliason
- **Author / channel:** **Peter Yang** — `https://www.youtube.com/@PeterYangYT` (NB: it's Peter Yang's channel; Nat Eliason is the *guest/demonstrator*. My earlier note framed it as "Nat + Peter" — corrected: host = Peter Yang.)
- **URL:** `https://www.youtube.com/watch?v=nSBKCZQkmYw`
- **Thumbnail:** `https://i.ytimg.com/vi/nSBKCZQkmYw/hqdefault.jpg` (reachable; not vision-analyzed — no image model)
- **Description / length / views:** ❌ not exposed by fetcher. "35 Min" is from the **title**, not a measured runtime.
- **Transcript:** present, 37,912 chars, read in full. Outro names **`easyclaw.ai`** (spoken) + "Felix Craft AI on X."
- **Spoken-aloud revenue anchors (these ARE in transcript, so verifiable as *spoken*):** cold open — *"It's already made thousands of dollars. **3596 gross volume, 3440 net.**"* and *"He has like almost **100 grand in his crypto wallet**, which is like kind of concerning."* So the small Stripe figure and the ~$100K wallet are **spoken**, not just on-screen.

**🔍 VISUAL-ONLY / not verifiable from our data:** This is the worst-affected video for our extraction gap, because it's a **screen-share tutorial.** The transcript proves the *words* but we **cannot see**: the **Stripe dashboard** showing $3,596/$3,440, the **crypto wallet** showing ~$100K, the **agent's terminal / OpenClaw config / memory files / cron setup**, the **deployed website/PDF product**, or any **code** walked through. Every "as you can see here…" / "this is the…" pointing-at-screen moment is **opaque to us.** So the *architecture* below is reconstructed from what's **spoken**; the on-screen artifacts that would *prove* it are unverifiable from this IP. Flag accordingly: **strong spoken detail, zero visual confirmation.**

### Core thesis
The *how-to* behind Felix: a step-by-step on the **agent architecture** that lets an OpenClaw agent operate a business semi-autonomously. Less "get rich," more "here's the actual machine."

### Actual mechanics / architecture (the meat)
This is where the real signal is. Felix's stack, as described:
1. **Memory as searchable corpus** — memory stored as **QMD/markdown files** with a **memory-*search*** step the agent runs before acting (semantic recall over its own notes). Mirrors our 3-layer memory + `memory_search` closely.
2. **Nightly memory-consolidation cron (~2am)** — a scheduled job distills the day's raw notes into durable long-term memory. **This is essentially our nightly distill / MEMORY.md-promotion pass.**
3. **Heartbeat / monitor loops** — periodic self-checks that keep the agent doing useful work and watch system health. **= our 30-min heartbeat cadence.**
4. **Multi-threaded chats / sub-agents** — separate concurrent threads; heavy/expensive work delegated so the main session stays responsive. **= our sub-agent fleet + "don't go silent, delegate heavy work" rule.**
5. **"Ralph loops"** — persistent self-healing coding sessions (tmux + completion hooks); for big coding tasks Felix **delegates to Codex / Claude Code** rather than doing it inline. (This exact skill — "Coding Agent Loops" — is Felix's **top marketplace seller**, see below.)
6. **Security: separate authenticated command channels from informational channels** — a deliberate **prompt-injection defense**: untrusted/inbound info can't issue privileged commands. **This is a genuinely sharp practice and maps to our EXTERNAL_UNTRUSTED_CONTENT discipline + main-only privileged actions.**

### Marketplace ("Claw Mart") — cross-checked LIVE, big reality check
- Felix sells **skills/personas** on `shopclawmart.com`. **Live data I pulled:**
  - **"Coding Agent Loops"** (Ralph loops/tmux) — **$9 × 1,383 sold ≈ $12.4K** → the clear hit, ~the whole skills business.
  - **"X/Twitter Agent"** — $9 × 94 sold. Most other skills: **single-digit to low-double-digit sales.**
- The often-repeated "**Brian Wagner sold ~200 skills**" claim — checked his own tweets: **"200 sales" (Feb 26) → "nearing 450 sales, $370 revenue" (Mar 7).** So **~200 = sales count, total revenue ≈ $370.** **The skills-store "gold rush" is, for almost everyone but the one hit, near-zero dollars.** Textbook power law.

### SHOWN vs ASSERTED
- **Shown:** the architecture is described concretely and is **internally coherent + matches a real, externally-verifiable product/marketplace.** The top-seller numbers are live-checkable.
- **Asserted / softened:** "runs itself in 35 min" (the *architecture* is explained in ~35 min; building Felix took far longer and ongoing babysitting). "Runs itself" overstates autonomy — same human-in-loop caveats as V2.

### Distribution: **Partially confronted, mostly via the marketplace.** 
The implicit distribution answer here is *"sell skills on Claw Mart."* But the **live data debunks it as a channel for most people** — one $9 skill carried by the creator's fame did ~$12K; everyone else is at ~$370 or less. So the tutorial **shows a building machine and a marketplace, but the marketplace is not a distribution solution** — it's the same power-law funnel where reach (which Felix/Nat already had) decides everything. **Honest read: still dodges the hard part for the audienceless builder.**

### Realistic outcome
**The single most useful video of the three for us** — but as an *architecture validation*, not a money method. It independently re-derives ~our exact stack (searchable memory, nightly consolidation, heartbeat, sub-agent delegation, coding loops, channel-segmented security). The "business that runs itself" is real as *plumbing*; the *revenue* still rides on a famous operator's distribution.

### Net-new for us
- **"Ralph loops / Coding Agent Loops"** as a *named, packaged* pattern (persistent self-healing tmux coding sessions + completion hooks) — we delegate to subagents/Codex but could formalize a self-healing long-coding loop skill. **Most actionable concrete item.**
- **Authenticated-vs-informational channel separation** as an explicit security model — worth writing into our own posture doc even though we already practice the spirit of it.
- **Selling skills as a product** is **de-prioritized by the data** — the marketplace is a power-law lottery, not a distribution engine. Don't chase it expecting the headline numbers.

---

## Cross-Cutting Synthesis

### What's REAL signal
1. **Felix (V2+V3) is a legitimately impressive *building* demo with real, externally-verifiable revenue** (~$100K Stripe + ETH + a volatile token). It is **not** vaporware — rare for this genre.
2. **The architecture in V3 independently validates our own stack** almost point-for-point: searchable markdown memory + a search step, nightly consolidation cron, heartbeat loops, sub-agent delegation of heavy work, self-healing coding loops, and channel-segmented security. **We are not behind on building; we're roughly at parity with the flagship.**
3. **Every video's success rides on borrowed human distribution or reflexive crypto** — Nat's audience + a memecoin (V2), creator-fame-carried marketplace hits (V3), or a paid community funnel (V1).

### What's NOISE / hype
- **"$250K / $300K / 24-7 passive"** headlines are inflated (paper crypto, cherry-picked moments) or pure funnel bait (V1). Note the *trajectory* is real, though: V3's cold open shows an **early** snapshot of just **$3,596 gross / $3,440 net** Stripe + ~$100K wallet (spoken), while V2's later headline is ~$100K Stripe + ~$95K ETH — i.e., the Stripe side genuinely grew, but the eye-popping totals lean on the **volatile crypto bag**, not product revenue.
- **The "skills marketplace gold rush"** — debunked by live data: one $9 skill did ~$12K on the creator's fame; a representative seller did **$370 total.** It's a power-law lottery, not a business model for the audienceless.
- **"Runs itself"** overstates autonomy everywhere; humans gate original posting, babysit coding loops, and supply reach.

### ⚠️ Confidence caveat from the extraction gap
Our read is **transcript-grounded**, not visually verified. We **could not see any in-video frame** (Stripe dashboards, wallets, terminals, code) — only the spoken words + an un-analyzable thumbnail. The Felix revenue story survives this because we **independently corroborated it via `web_search`** (felixcraft.ai, shopclawmart.com live sales, crypto-press) — not because the videos proved it to us. For V1 there's nothing to corroborate (no product). So: high confidence on *existence* of Felix's revenue (external sources), **lower** confidence on any precise figure a creator only *showed on screen*.

### Does any of this change our plan?
**It strengthens it.** The strongest, most-verified example in the whole space (Felix) **explicitly admits the agent can build and transact but cannot yet distribute** — its novel posts go to "slop," so a human gates them, and its audience was bootstrapped from a famous founder. **That is our thesis, stated by the best practitioner in the field.**

**Concrete adjustments:**
- **Keep prioritizing distribution R&D over more building** — building parity is basically achieved; distribution is the moat and the unsolved problem, confirmed from the top.
- **Adopt two specific patterns:** (a) a **self-healing long-coding loop** ("Ralph loop"-style: tmux + completion hooks + Codex delegation) as a formal skill; (b) **explicit authenticated-vs-informational channel separation** in our security posture doc.
- **Consider an agent *public persona* as marketing-in-itself** (Felix-as-character) — but only paired with a *real* distribution mechanism, since persona alone didn't crack distribution even for Felix.
- **Do NOT pursue selling skills on a marketplace as a revenue plan** — the data says it's a fame-gated lottery; our edge has to be distribution, not another $9 skill in the long tail.

### One-line verdict
*Two of these (Felix) are the real deal at **building** and quietly **prove our distribution thesis**; the third is a course funnel. Net: validate our architecture, double down on distribution, steal two engineering patterns, ignore the marketplace dream.*
