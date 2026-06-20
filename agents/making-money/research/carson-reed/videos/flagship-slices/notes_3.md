# Flagship slice 3 notes (~chars 272k–410k)

Source: Carson Reed, "Complete AI Agency Tutorial for 2026" (10-hr flagship). All claims attributed to **Carson**. This slice covers the GoHighLevel build-out (Module 10, videos 3–8) and the start of client acquisition (Module 11, videos 1–2).

---

## Business model (recap from this slice)
- **Service sold:** AI marketing/automation agency — runs lead-gen + AI systems for local businesses; everything hosted/operated inside **GoHighLevel (GHL)**.
- **ICP / niche:** Local service businesses. Recurring examples named: **real estate agents** (his own first niche, "in needly" agency), plumbers, HVAC, roofers, dentists, high-ticket medical spa / treatment clinics.
- **Offer angle / pricing (referenced, not built here — pulled from earlier "offer" + "pricing structure" slides):**
  - **Pay-per-result** model OR **guarantee** model: e.g. "90 days, 10 listing appointments (or 10 jobs / 10 patients) or you don't pay."
  - Pricing structure includes **retainers** + **PIF (paid-in-full)** structure + pay-per-result.
  - **Clients put on 6-month agreements** for real estate (long fulfillment cycle); dentists won't sign 6-month deals (shorter sales cycle).
  - **One-sentence offer explanation** = the marketing angle, reused across funnel headline, calendar name, nurture emails, ads.
- **His own brands (proof of model):** parent co **100k AI agency.com** ("save or make an extra $100k/yr using AI" — deliberately broad); sub-brands under it (e.g. high-ticket med-spa brand); first agency = real estate, named "in needly" (admits it was a bad/confusing name but still made "a lot of money").

---

## Topics / modules covered in THIS slice (in order)

### Module 10 (GoHighLevel setup) — videos 3–8
**V3 — Sales pipeline setup**
- 3 pipelines exist in the snapshot; top 2 = for **AI caller** (ignore until that module). Main = **"Lead to Sales Pipeline."**
- Stages: New Lead → Disqualified Lead → Booked Appointment → (Lost Deal / Interested / Closed, etc.). Fully customizable via Pipelines → edit (add/remove/reorder/delete stages).
- Add opportunity = create a Contact → drop the contact card into a stage; drag cards across stages to stay organized (no-shows, cancels, follow-ups, closed deals).
- Contacts compile in **Contacts → smart list** section.
- **Dashboard** shows pipeline analytics (count per stage) once leads populate.
- Snapshot already wired to the automations; user shouldn't need to change anything.

**V4 — Calendar & booking system**
- Calendar → Calendar Settings → "Demo Calendar" (pre-built in snapshot; must **Activate** it via the 3-dots — imports inactive by default).
- **Calendar name = sales asset:** name it for the offer, e.g. "Real Estate Agents – 10 Listing Appointments in 90 Days" or "…Pay-Per-Close." Never "Demo Calendar." Use ChatGPT for a ≤2-sentence description (prospects see name + description on booking page).
- **Meeting invite title:** `{contact name} ✕ {your business/your name}` using a contact-name custom field.
- **GHL quirk — add yourself as your own employee/user to take calls:** Agency view → Settings → Team → Add user under a **second email** (same email glitches because it's already the agency owner). Name it e.g. "Carson R" (vs agency-owner "Carson Reed") to distinguish. Role = **Account admin** (not agency admin) → assign the sub-account → check all → Save. Then in calendar edit, assign that "Carson R" user as the call-taker.
- **Calendar settings values:** slot interval 30 min; **meeting duration 60 min** (it's the demo/sales call); minimum scheduling notice ~12 hrs; **date range 3–4 days max** (people forget bookings; 3 is his max, 5 if busy); consent checkbox ON; autoconfirm new meetings YES; assign contacts to representative ON.
- **Connect Zoom + Google Calendar:** top-right icon → "Login as" the employee (Carson R) → Settings → My Profile → Calendar Settings → connect Google/Outlook/iCloud + connect Zoom (video conferencing). **Linked calendar** = writes bookings to your real calendar; **Conflict calendars** = reads your calendar to block already-busy slots (e.g. 8–5 availability but 10am busy = 10am unbookable).
- **Meeting location:** Edit calendar → Meeting Location → select Zoom or Google Meet (must be video, NOT phone — it's a 60-min pitch/discovery/close call). After setup, switch back to main agency account; never use employee account again.

**V5 — Websites & funnels**
- **Business name:** broad vs niche. Don't obsess — "don't spend more than an hour on this." Use ChatGPT to brainstorm (named examples: Pipeline AI, Pipe Pros AI, Flow Gen Agency, Realtor IQ, Agent Scale AI, Closing Flow, Estate Engine AI).
- **Domain:** buy on **GoDaddy** (easier than buying inside GHL). Connect: Settings → Domains & URL redirects → Connect domain → Funnel and Website → enter domain → GHL auto-detects GoDaddy → Authorize → Connect → link to the direct-calendar funnel/booking page.
- **3 funnels in snapshot:**
  1. **VSL funnel** (has friction — video sales letter page before booking). Only use if spending **≥$100/day** (ideally **$150/day**) on ads + you have case studies/testimonials.
  2. **Direct-to-calendar funnel** ("Funnel 2") — recommended for **99.9% of users**; highest appointment volume. Use for any budget $20–$300/day.
  3. **Client onboarding funnel** — 5 steps: (1) expectations video, (2) connect Facebook Business Manager (gives you access), (3) CRM/GHL overview (each client gets own sub-account), (4) intake form, (5) submission/database. One link = automated onboarding.
- **Funnel flow:** ad → (VSL page) → opt-in form → booking page (synced calendar) → **Thank-You / pre-call page**.
- **Pre-call page (huge for show/close rate):** 3–20 min pre-call video setting expectations + "confirm by clicking Yes or it's auto-cancelled" + objection-handling videos. Host on Wistia, unlisted YouTube, or upload raw file to GHL editor.
- **Editing pages:** Edit → headline = "{niche} looking to scale to {X}" + one-sentence offer explanation; padding/font adjustable; insert calendar element (General → Calendar → Demo Calendar) with redirect "Go to next step." Add logo (optional). Privacy policy + terms of use pages included in snapshot. **Exit-intent pop-up** (cursor leaves page → calendar form) already built — just delete placeholder text + select Demo Calendar.
- **Logo tip:** generate with ChatGPT → Canva for transparent PNG.

**V5 — Payment processors (collecting payments)**
- US: can operate as **sole proprietor** until first client closes (then consider a legal entity).
- **Stripe** — open as a **backup only**. NOT for high-ticket; risk of shutdown on payments over ~$500–$1,000 (Stripe treats high-ticket as high-risk; built for e-commerce $12–$30 payments).
- **Fanbasis (fanbasis.com)** — his **#1 recommended**, used full-time by him + team; book a demo call, get account + decent processing fees, real human support (close with their team). [A third processor was named but redacted in transcript as "____ / is like a ____"; he says just use Fanbasis + Stripe backup.]

**V6 — Automations & workflows (all pre-built in snapshot, "fill in the blanks")**
- 3 key workflows (ignore "Sana connector" folder = AI caller):
  1. **10-email lead nurturing sequence** — trigger: Opportunity created → New Lead in Lead-to-Sales pipeline. Sends 10 emails over 10 days (1/day). Mainly for VSL/opt-in funnels (direct-to-calendar bookers skip it). Fill in niche/offer, tweak subjects (e.g. "Looking for more {X}"). Uses custom fields: `{username}` = assigned user (you).
  2. **Appointment confirmation & reminder workflow** — trigger: Customer booked appointment (Demo Calendar). Sends pre-call confirmation **email + SMS**, **24-hr**, **1-hr**, **10-min** reminders; auto-pulls Zoom/Meet link; asks "reply YES to confirm." Adds opportunity to **Booked Appointment** stage. **Removes contact from the 10-email nurture** on booking. Requires 2 custom values set: **Company Name** + **Pre-Call Video Link** (copy the thank-you/pre-call page URL into Settings → Custom Values).
  3. **Client-closed workflow** — trigger: tag **"client closed."** When you close a client, go to Contacts → their card → Add Tag "client closed" → fires welcome SMS + welcome email ("Welcome to the family… click link to start onboarding") containing the **onboarding funnel link**.
- Always set workflows from **Draft → Published** or they won't fire.
- **Contracts:** Payments → Documents & Contracts → New → upload PDF (can draft with AI if no lawyer; he recommends a lawyer but "not legal advice") → add signature boxes → send to client's contact. Strongly recommends putting all clients on contracts.

**V7 — Phone number (A2P 10DLC) + email domain**
- **Phone number:** Settings → Phone Numbers → Add Number → filter → **turn OFF toll-free** (1-800 has lower response) → choose area code (his = 206 Seattle) → buy (**$1**). Save the number.
- **A2P 10DLC verification (required to send SMS):** Trust Center → Start Registration. Follow the **A2P verification doc** included in his resources/docs (bottom of resource doc). Apply as **yourself** (not client). Requirement: provide a **real connected URL** with (a) privacy policy link at bottom, (b) terms of service link at bottom, (c) **consent checkbox** on booking page ("consent to receive content, texts, calls, emails directly from this company"). Edit the templated privacy policy/terms pages (date, business/LLC name, email, website) and hyperlink them at the bottom of the booking page. Approval takes **a few hours to 48 hrs**. Once approved → link the A2P campaign to the number (3-dots → select campaign).
- **Email setup (avoid spam):** Settings → Email Services. Default lead-connector email → always spam.
  - **Option A (quick):** Add service → use Gmail + create a **Google app password** → paste under email → emails send from your real address (shows in Gmail Sent folder).
  - **Option B (recommended):** Add Service → **Dedicated Domain & IP** → Add Domain → create a **subdomain** (e.g. `em.acquiregrowth.io`) → Authorize via GoDaddy → verify → **Set Headers** = default From name/email (e.g. "Carson Reed", `carson@em...`) → Save. Best deliverability he's seen; learned this from ~8–9 different GHL reps.
- Repeatedly pushes **GHL support** (top-right "Need Help" → 24/7 Zoom room, chat, or ticket) — says it's why the **$297 plan** and **$497 ($500/mo) plan** matter (extra support).

**V8 — Best practices / scaling (close of Module 10)**
- **Keep it simple, don't overbuild.** The snapshot foundation alone can scale an agency to **six figures/month**; for $10k/mo it's "all you need." Follow the snapshot.
- Next module = client acquisition ("the fun stuff").

### Module 11 (Client acquisition) — videos 1–2 (start)
**V1 — The 3 methods of client acquisition**
- **(0) Warm network / referrals** (unlisted "method #1"): contact people you already know in your niche; even just ask for honest feedback on offer/pricing. Carson did this — had parents arrange a 1-hr meeting with a local realtor he knew, "picked their brain," didn't sell. Easiest closes but **not scalable**.
- **(1) Outreach** — DMs (IG/FB/LinkedIn), cold email, cold calls. **Free (costs time).** Carson is lukewarm/discouraging: did it 6 months, only hit **3–5k/mo**; "hit or miss," what 90% of YouTube tells you to do; causes most quitting.
- **(2) Organic content** — post YouTube/IG content teaching your niche how to use AI (e.g. "how real estate agents leverage AI in 2026"). **Free (costs time).** Link to book a call in every video description. Produces **highest-trust, easiest buyers**; even 20–100 views can close a $5k client. Snowball/asset — slow to start, compounds. Recommends doing it **regardless** of other method.
- **(3) Paid ads** — Facebook/Instagram (Meta). **Costs money, no guarantee, but most predictable/scalable.** "Every agency at $100k/mo+ is doing paid ads." Books sales calls "while you sleep" via the algorithm targeting ideal prospects.
- **Path-by-situation advice:**
  - Money available → **paid ads** (+ organic content).
  - **Zero money → GET A JOB** (min wage $10–$20/hr) to fund ads, rather than grinding DMs all day. (Says people laugh at this advice; he funded his first business with a job he had from age 15–16.)
  - Truly can't get a job (e.g. 14 yrs old) → outreach + organic content (do BOTH, harder).
- **Recommended ads budget:** "at least **$1,000–$1,500/month**" (~$33–$50/day).

**V2 — Paid ads A–Z (setup begins; mostly the Facebook account/portfolio steps in this slice)**
- Covers: paid-ads 101 + budgeting → FB personal account → business account/portfolio → ad account → business/agency page → video+image ads & copy (with AI) → optimize landing page → Facebook pixel → launch + monitor.
- **Two ad angles** (pull from offer slide): **pay-per-result** model on ads, and/or **guarantee** (e.g. "90 days, 10 listing appointments or you don't pay").
- **Budgeting mechanics:** "$10/day for 10 days ($100 total) gets the SAME data as $100/day for 1 day" (given identical ads). Budget = whatever you have.
  - **Floor: ~$30/day** (lower = too slow, leads to impulsive decisions).
  - **Ceiling for beginners: ~$200/day** (~$6k/mo).
  - **Sweet spot: $50–$150/day.**
- **Cost-per-call varies by offer + industry (his averages):**
  - Real estate agents: **~$30–$40 per booked sales call** (cheap; easy to close, **hard/slow to fulfill** — biggest financial decision, 6-mo cycle).
  - Dentists: **~$100–$200 per booked sales call** (expensive, harder to get, but **higher LTV / better clientele**, shorter fulfillment).
  - Best real data on ad quality comes from **Facebook/Instagram itself**.
- **Facebook account structure:** must have a **personal account** to run ads → it connects to a **Business Portfolio** (search Google "create Facebook business portfolio" → Start Now). Never run ads off the auto-assigned **personal ad account** (super restricted; he once mistakenly set up all campaigns there). Run from the **Business Portfolio** → Business Settings → Ads Manager. Slice cuts off mid-explanation of reaching the Ads Manager page.
- **Tools shown for ads research/copy:** ChatGPT, **Manus (manus.app)**, **Lucidchart** (planning), Facebook Ads Manager.

---

## Tools / software / platforms named (with purpose)
- **GoHighLevel (GHL)** — all-in-one CRM/funnel/calendar/automation/phone/email/payments/contracts hub. Plans pushed: **$297/mo** (full features) and **$497 (~$500)/mo** (whole plan, max support); 30-day trial link + snapshot/bonuses provided.
- **GoDaddy** — buy domain (easiest), then connect/authorize into GHL.
- **Zoom** (~$10–$11/mo; recommended) or **Google Meet** (free w/ Google Workspace) — video for the 60-min sales call.
- **Google Calendar / Outlook / iCloud** — linked + conflict calendars in GHL.
- **Stripe** — payment processor, **backup only** (not high-ticket).
- **Fanbasis (fanbasis.com)** — **primary** payment processor (high-ticket, human support).
- **Wistia / unlisted YouTube / Loom / OBS / phone** — host or record pre-call & objection videos.
- **Canva (canva.com)** — transparent logo.
- **ChatGPT** — business names, calendar descriptions, logos, copy, country-specific payment advice.
- **Manus (manus.app)** — ads research.
- **Lucidchart** — solution chart / planning ("paid ads 1" outline).
- **Facebook / Instagram (Meta) Ads Manager + Business Portfolio + Pixel** — paid ads.
- **Twilio A2P 10DLC** (via GHL Trust Center) — SMS compliance.
- **Google app password** — alt email sending method.

---

## Real numbers / proof — SHOWN vs ASSERTED
**SHOWN (on screen in this slice):**
- His GHL agency owner account + team (names blurred), multiple owned domains incl. **carsonre.com**, **acquiregrowth.io** (used as live demo), pre-built snapshot funnels/calendar/automations, his Facebook personal + business accounts (3-yr-old personal acct), Business Settings page with a team.
- Demonstrated: $1 phone-number buy, A2P approved-state screenshot, custom values, email subdomain setup.

**ASSERTED (numbers, no hard proof in this slice):**
- Outreach got him to **3–5k/mo** over **6–8 months**; flipped on paid ads → **15–20k/mo "instantly"** working with real estate agents only ("all documented on my channel").
- Snapshot foundation can scale to **six figures/month**.
- People close **$5k clients** from organic videos with only ~50–100 views.
- Cost-per-call figures ($30–40 RE / $100–200 dentists) = his stated averages.
- Knows people running **20–30x ROAS** ("$1 in → $20–30 out"; called extreme).
- Close rates: experienced closers 30–40%, beginners ~10%.

---

## Funnel / mastermind / community + price
- **Free monthly Q&A calls** for buyers (must sign up; emailed invites/reminders). Buyers also get monthly emails from Carson.
- Pushes **YouTube comments** as the channel to ask him questions / document journey (he replies).
- Mentions a **mastermind** ("all the guys inside my mastermind who are crushing it… almost all with paid ads") — **no price/name/join details given in this slice**.
- No separate paid community/course funnel priced in this slice beyond the GHL plan affiliate pitch ($297 / $497).
