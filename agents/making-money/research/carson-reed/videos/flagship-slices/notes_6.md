# Flagship slice 6 notes (~chars 682k–820k)

Source: Carson Reed, "Complete AI Agency Tutorial for 2026" (~10hr free YouTube course). This is the FINAL slice — the AI-caller build-out, client ad setup, scaling, hiring, founder psychology, and the closing pitch. Everything below is attributed to Carson.

---

## Topics / modules covered (in order)
1. **AI caller build (Retell AI)** — full setup, demos, client account proof, GoHighLevel automations (basic + advanced).
2. **Module / Video 9 — Funnels & Ads for clients (B2C)** — Meta ads setup, instant lead forms, calendar booking step.
3. **Module 14 — Scaling client acquisition** — lookalike audiences, retargeting, creative testing, Andromeda Meta update.
4. **Module 15 — Hiring & team building** — who to hire, when, pay rates, SOPs.
5. **Module 16 — Leadership & founder psychology** — operator → CEO mindset.
6. **Module 17 — "What's next" / THE PITCH** — the closing funnel into his paid mastermind.

---

## Business model (reconfirmed)
- **Service sold:** AI-powered marketing agency. Run Meta ads → capture leads (instant forms) → AI voice caller follows up & books appointments → client closes. "Lead ops in" model (you outbound-call the leads that opted in).
- **ICP / niches named:** real estate agents (home buyers OR home sellers), roofers, high-ticket med spas / medical aesthetic clinics, stem-cell clinics, insurance, healthcare, Roth-conversion/retirement financial.
- **Delivery is template-driven:** Carson gives a GoHighLevel snapshot + his "Symphonic/Sympona Connector" app + prompt-builder GPT so the whole thing is mostly pre-built.

### Price points / numbers mentioned ($)
- Client agency fees referenced: "two, three grand, maybe four grand up front"; also "$5k up front" framed as a lot / not realistic for everyone (defends paid-trial periods).
- Retell talk-time cost: **~8–9¢/min** (GPT-5 mini, fast tier).
- Phone number purchase: **~$1–$1.50** (Twilio or Telnyx; Telnyx lands in spam much less).
- GoHighLevel "place call" trigger: **+1¢ per trigger**.
- Retell optional verified number promo: **$100/mo** (says not necessary when starting).
- Cost-per-lead benchmarks (industry-dependent, ASSERTED): real estate home buyers **~$6/lead**; med spa / high-ticket clinics **$50–$100/lead**.
- Ad spend tiers: beginner $20–$50/day; "scaling" $150–$200+/day; his agency currently **$500–$1,000/day**.

---

## Tools / software / platforms named (+ purpose)
- **Retell AI** (retellai.com) — core AI voice-caller platform. Free to create account. Build voice agent → single-prompt agent → start from blank. Carson uses a **referral/affiliate signup link** that grants extra credits + extra support (his dev visited Retell HQ in San Francisco).
- **GPT-5 mini, "fast" tier** — the LLM powering the Retell agent (cheapest, ~8–9¢/min).
- **Retell voices** — "Simo" and "Grace" rated best-performing; "Haley" okay. Female agents perform better (his pattern observation). Supports many languages (Romanian, French, Chinese, German, Hindi, etc.).
- **ChatGPT custom GPT — "Carson prompt GPT script"** — his prebuilt agent that interviews you and outputs the full Retell caller prompt. Toggle "thinking" off during intake, then turn thinking ON for final generation.
- **Manus AI** — used to clean up the generated prompt (remove "pause / wait for lead to respond" stage directions that get spoken aloud), to vet/clean scraped lead lists, write ad copy, and build SOPs.
- **GoHighLevel (GHL)** — CRM / automation hub. His affiliate link gives viewers the full snapshot (pipelines + automations) free.
- **"Symphonic / Sympona / Sana Connector" app** (his team-built GHL marketplace app) — installs into GHL, syncs the Retell agent directly to the GHL calendar, auto-adds call summaries + tags to contacts, exposes the native "Place Call" function. Heavily emphasized as the differentiator. Connect via Retell **API key** (Retell → Settings → API keys → copy → paste into connector → Update API key).
- **Twilio / Telnyx** — phone number providers inside Retell (Telnyx preferred — less spam).
- **Meta / Facebook Ads Manager + Business Suite** — running client ads, billing, instant forms.
- **Facebook Instant Forms (lead forms)** — preferred B2C lead capture over websites.
- **Arc Ads (Arcads)** — AI UGC/video ad generator (import script → pick AI actors: Lauren, Silus, Charlotte).
- **Canva** — image/static ad creatives.
- **Claude** — ad copy (alongside Manus).
- **Lucidchart** — his hiring org-chart diagram.
- **Upwork / recruitment agencies** — sourcing media buyers, list-scrapers, team.

---

## AI caller setup specifics (Retell)
Agent settings Carson configures:
- Welcome message → **AI speaks first → custom message**: `Hello, is this {{contact name}}?`
- Real-time transcription: remove background noise + background speech, optimize for accuracy; vocabulary "general" (or "medical" for healthcare).
- Call settings: voicemail detection ON + hang up on voicemail; user keypad input OFF; **end call on silence ~1 min**; max call duration **15–20 min**.
- Speech: optional background ambiance (coffee shop / call center) — he leaves none; optional backchannels ("yeah, uh-huh").
- Skips knowledge base / webhooks / post-call analysis (connector handles summaries automatically).
- Prompt-GPT intake captures: outbound, using connector=yes, platform=Retell, why calling (opt-in/referral consent — stay compliant), company name, website (it scrapes), agent name (e.g. "Sarah"), call-recording disclosure (needed in CA + some states — do your research; he says "no" assuming non-disclosure states), target audience, disqualifiers, qualifying questions ("How many home deals have you closed?").

### GHL automations bundled in the snapshot
- **Basic automations folder (4):**
  1. Trigger on Facebook lead form / website form → wait 3 min → **concurrency limiter (15 simultaneous calls; Retell caps ~18–20)** → Place Call (select voice connection/agent) → move in pipeline → tag "called."
  2. Post-call: detect inbound vs outbound → add call-summary notes to contact → organize pipeline (lead not interested / did not respond) + tags.
  3. **Booked appointment** automation → moves to "booked," tags, and **removes contact from all other workflows** so they stop getting called.
  4. No-response SMS: wait 10 min → "Hey {first name}, just tried calling…" (insert your name) → tag.
- **Advanced automations folder** — long nurture sequence: double-dial after first call, then **2 calls/day (AM + PM) through day 6** (max legally 4×/day; uses business hours, ~8am–8pm / 8–5; Sat/Sun toggle). Uses a stage-picker + a single dedicated **"Place Call" workflow** that funnels ALL calls through one concurrency limiter (batch size 18, every 10 min) to avoid overloading the agent. 11 tags track pipeline stage (day 1 PM, day 3 PM, etc.).
- AI-caller pipelines (basic + advanced): stages = booked / call in progress / lead did not respond / lead not interested.

---

## Client ad setup (Video 9 — B2C)
- Get **full admin access** to client's Meta Business Manager; create their page + ad account; client must add a credit card **+ backup payment** (declined payment → ban risk; Carson's been banned, warns hard).
- Campaign: objective **Leads**. CBO (campaign budget) vs ABO (adset budget) explained — ABO for equal-split testing. Special ad category "Housing" for real estate.
- **Conversion location = Instant Forms** (NOT website) for B2C — easier opt-in, lower-intent consumer audience converts better than long landing pages.
- Example budget: **$30/day split as two adsets @ $15/day** (one image ad + one video ad to split-test). Rule of thumb: $30/day → max 2–3 ads; <$20/day → 1 ad.
- **Instant form build:** "More volume," 2 multiple-choice qualifying questions (e.g. "Would you be looking to sell your home? Yes/No" with conditional logic to knock off No's; "What area in Seattle are you in?"), then contact info (first name, last name, phone [not optional], email).
- **Critical "completion screen" hack:** add a custom completion headline ("Wait — one more step") + CTA button **"Book Call"** linking to the GHL calendar scheduling link. Claim (ASSERTED from his data): **~50% of form submitters who reach this step go to the site and book a call**.
- **GHL ↔ Facebook integration:** GHL Settings → Integrations → connect client's FB → map lead form fields → contacts auto-populate → triggers nurture/AI-caller automations. Warns: failing to integrate = lose ~50% of leads who never self-book.

### Sample ad offers (scripts/quotes)
- Sellers: *"Seattle homeowners, get your free home evaluation today. Click learn more below."*
- Buyers: *"Seattle first-time home buyers, get your free home list today in the local area. Click learn more below."*
- Generated video script titled *"Thinking of selling your home"* via Arc Ads.

---

## Scaling tactics (Module 14)
- **Ceilings:** 0→10k/mo fast, then systems break; 10–20k ceiling because fulfillment + CAC intensify.
- **Lookalike audiences:** pay an Upwork scraper (~$100) to scrape ~20–30k industry leads (e.g. real estate agents, stem-cell clinics) → feed to **Manus to vet/clean** (20k → ~7k matched: name/last name/email/phone/owner all match) → upload to Facebook as 1% or 2% lookalike. Speeds up targeting massively. Only do this once you already have budget/clients.
- **Budget allocation (his agency):** ~90% across 3 adsets (lookalike / interest-stacked / broad — start with **broad**); ~10% to **retargeting** (audience of landing-page viewers who never opted in, EXCLUDE those who booked). Retargeting hooks (quote): *"Hey, I've seen you before… you probably getting annoyed of seeing my ads…"* — tailor to industry.
- **Andromeda Meta update:** algorithm now rewards testing MANY creatives. His agency runs **~138–150 ads** built from a UGC creator filming ~10 hooks × ~4 bodies × ~5 CTAs, edited into permutations.
- **Winner duplication loop:** launch ~30 creatives → ~3 winners → duplicate winners into a "winners campaign" w/ higher budget, cut losers, keep cycling remaining ~23 to find new winners (avoids constantly buying new ads).
- **Image vs video ads:** image = higher volume, lower intent (best for beginners, $30–50/day, hard to mess up); video = fewer but higher-intent leads (used at high scale).
- **Cut rule:** kill an ad once it hits **~2.5–3× your target cost-per-lead** (e.g. $20 goal → cut at ~$60 CPL).
- **Monitoring:** small spenders check ads 2–3×/week max — don't over-tinker; let winners spend.

---

## Hiring / team (Module 15) — pay rates
Three departments: **Executives** (CFO/COO/CGO — only at very high scale, ignore for most), **Sales**, **Client Success**.
- **Don't hire until ≥$10k/mo.** Learn every skill yourself first ("can't teach ice skating if you've never skated"). Build SOPs from winning clients before delegating.
- **Order:** outsource **Client Success / fulfillment FIRST, sales LAST** (bad sales hire cuts off cash flow; bad fulfillment hire you can survive).
- **Media buyer** (runs client ads): $500–$1,000/mo per client (1k is high end), then part/full-time flat **$1.5k–$4k/mo**. One full-time media buyer can handle **~50–60 client accounts**. Notes peers paying Philippines media buyers <$1,000/mo full-time managing ~50 accounts via SOPs.
- **Developer** (builds AI callers): **10–20% of deal closed** (20% is high end), later flat + bonuses.
- **Client Success Manager (CSM):** hire at **$25–50k/mo** revenue. Pay **$3–6k/mo**. Should be UK/US/Canada, strong English, upbeat (first/main client contact). Reports up; media buyer + dev report to CSM.
- **Closer:** **10%** of deals closed. **Phone setter:** **5%**. Self-set closer = 15%. Hire sales only at **$25k/mo+**.
- **Sales manager:** at **$50–100k/mo+**, **~10%** on top → with closer+setter+manager ~25% revshare total goes to sales.
- **VAs:** ~$200–300/mo (Philippines/overseas) for small tasks.
- **Incentive structure advice:** don't pay flat (e.g. not flat $5k) — pay ~$2.5k base + earn the rest, or they get lazy.
- **"Hire slow, fire fast."** Do 10–15 (some do 30) interviews per role.
- **SOPs** (standard operating procedures) repeatedly stressed — Manus can help build media-buyer SOP + developer SOP so cheap overseas hires just follow the doc.

---

## Real numbers / PROOF (SHOWN vs ASSERTED)

### SHOWN (live on screen in his Retell client dashboards)
- **Client #1 (call-transfer client):** **962,000** outbound calls to opted-in leads; 84% unsuccessful; **~15% (~150,000)** converted to a live transfer to a sales agent. Metrics shown: pickup rate, success rate, transfer rate.
- **Client #2 (insurance, booked calls):** ~15,000 calls; **62% successful** (turned into live calls), ~37% unsuccessful.
- **Client #3 (healthcare, booked appts):** ~9,000 calls; **63% (~5,000)** successful; ~36% turned into live booked appointments. (Leads = client's internal list + ads he runs for them.)
- Live demo: AI caller dials Carson's own phone (Seattle 206 number) on camera — "Hello, is this Carson Reed?"
- Multiple voice demos (Simo, Grace, "Sarah" agent), a pre-made **2:40 demo call** ("American Retirey Club" / Roth conversion) he gives viewers to play on their own sales calls.

### ASSERTED (claims, not shown with proof)
- ~50% of instant-form submitters self-book a call after the completion-screen CTA.
- His agency currently spends $500–$1,000/day; runs ~138–150 ads.
- 2024 mistake: scaled to **~$120k/mo with ~20 full-time staff**, near-zero profit margins; cut to **~5 people** who outproduced the 20.
- Business partner / mastermind member: 19yo from Italy running a med-spa agency at **>$200k/mo** (was $127k/mo before dropping out of school), 6–8 full-time staff.
- He's been a business owner ~3–3.5 years; "from broke to where I'm at today."

---

## THE CLOSING PITCH / FUNNEL (Module 17 — what the free video sells)
- **Framing:** The 10-hour course is given free; Carson repeatedly says it's "a paid course that would generally be about **$5,000 to $10,000**" released free because he couldn't afford courses when he started. Builds reciprocity + authority via the shown client metrics.
- **What it ultimately sells:** his **private AI Agency Mastermind** — described as a 1-on-1 mentorship / private mastermind group, started **January 2025**. Big group of like-minded members running the exact same business model, scaling to "big numbers." Interviews with members already featured on his YouTube channel (social proof).
- **Perks dangled throughout the course** that route into the mastermind: access to his **AI developer** for high-level projects, his **monthly Q&A / coaching call** (repeatedly told viewers to "bring questions to my monthly call"), the GHL snapshot + connector app, SOPs, and "extra credits/support" via his Retell affiliate link.
- **Price:** NOT stated in the video — "it does cost money," "I'm not a charity." Directed to **the link in the description below**.
- **CTAs:** "find the link in the description to work with me 1-on-1," "speedrun the process," join to be "around people doing the same thing and learn from me directly." Plus engagement CTAs: like, subscribe, comment what you learned / future video requests.
- **Urgency / scarcity:** soft, not hard-deadline. Urgency framed as a **"massive wealth shift" between people using AI vs those who aren't** — "be on the right side of history," ride the trend. Bucket-sorts viewers: broke/no funds → just follow the free course and close first clients; have funds + want acceleration → join the mastermind.
- **Tone:** low-pressure, "completely up to you," repeatedly says the main ask is just to take action; positions the paid offer as optional acceleration rather than necessity.
