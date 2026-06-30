# Agency Reply Playbook — fast, on-brand responses to outreach replies

**Purpose:** When a prospect replies to cold outreach (batches 1–4), respond *fast* and *well*. Speed-to-lead applies to us too — the whole pitch is "answer inquiries in 60 seconds," so a slow/sloppy reply from us is hypocritical and kills credibility. Target: respond within the hour during waking PT hours.

**The offer (keep consistent in every reply):**
- AI system that texts every new lead back within **60 seconds, 24/7**, answers their question, and books them.
- **Auto review requests** to happy customers after the job/visit.
- Booking link: **https://cal.com/cyshek** (always offer a specific next step).
- Pricing (only when asked): **$1.5–3k one-time setup + $500–1k/mo** (anchor; flexible by size). Never lead with price.
- Voice: warm, concise, zero hard-sell, signed **— Cyrus**. Lowercase-friendly, human, no corporate filler.

**Golden rules:**
1. Every reply ends with ONE clear ask (book a time, or a yes/no question). Never leave it open-ended.
2. Match their energy + vertical. Mirror their words.
3. One link max. Don't paste pricing unless asked.
4. If they're warm → push to the **call**, don't try to close over email. The call is where it's won.
5. Always reply from cyshekari@gmail.com, in-thread (keeps "re:" continuity).
6. **Flag any genuinely-interested reply to Cyrus immediately** (Discord #making-money) — he runs the sales call. My job: book it on his calendar + brief him.

---

## A) INTERESTED — "tell me more" / "how does it work?" / "sounds interesting" / "sure, let's talk"

**Goal: convert curiosity → a booked 15-min call. Don't over-explain; tease + book.**

### A1. Generic interested
> Subject: re: [their subject]
>
> Hi [First],
>
> Awesome — happy to show you. Easiest way is a quick 15 min where I share my screen and walk you through exactly what it'd look like for [Business]: a lead fills your form (or calls/DMs), and within 60 seconds they get a text back that answers them and offers a time to book — fully automated, 24/7.
>
> Grab whatever slot works here: https://cal.com/cyshek
>
> If a couple of specific questions are easier over email first, fire away — whatever's simplest for you.
>
> — Cyrus

### A2. They asked a specific "how does it work" question
Answer the ONE question in 2–3 sentences, then book. Example (HVAC/roofing):
> Hi [First],
>
> Good question — it plugs into wherever your leads already come in (web form, Google, Facebook, or a missed call), and the second one lands it fires off a text in your business's voice: answers their question, and offers to book. You approve the message templates up front, so it always sounds like you. Nothing changes about how you actually do the work — it just stops leads from leaking out before someone can reply.
>
> Honestly it lands faster in a 15-min screen-share than over email — want to grab a time? https://cal.com/cyshek

### A3. "Send me some info / a one-pager"
Give a tight summary, still push the call as the better option:
> Hi [First],
>
> For sure. Short version: I set up an AI assistant that auto-texts every new lead within 60 seconds, 24/7 — answers them, qualifies, and books them onto your calendar — plus it asks happy customers for a Google review after the job. Setup's on me to configure; you just approve how it sounds.
>
> I can send a one-pager, but it really clicks when you see it live on a 2-min screen-share — here's my calendar if you want the fast version: https://cal.com/cyshek. Either way, glad to help.
>
> — Cyrus

---

## B) NOT INTERESTED / "we're all set" / "no thanks" / "remove me"

**Goal: leave a clean, gracious impression (door open for later) — and HONOR opt-outs immediately.**

### B1. Soft no ("we're good" / "not right now")
> Hi [First],
>
> Totally fair — appreciate you letting me know. If your lead response ever feels like it's leaking (after-hours inquiries, or leads going cold before someone can reply), the door's open. Wishing [Business] a great rest of the year.
>
> — Cyrus

### B2. Hard no / "remove me" / "stop emailing"
**Action: STOP all follow-up to this address immediately — add to exclude set (see ops note below). Then one short courteous line:**
> Hi [First],
>
> Done — you won't hear from me again. Thanks for the note, and best of luck with the season.
>
> — Cyrus

*(After replying: set this address's `"replied": true` in any pending followup payload AND add it to `followup_exclude.json` so the orchestrator never touches it again.)*

### B3. Annoyed / "how did you get my email" / "is this spam"
Be transparent, humble, and offer the off-switch:
> Hi [First],
>
> Fair to ask — I found [Business] through your public Google Business listing while looking at [city] [vertical]s, and reached out because I build lead-response automation for shops like yours. No list-buying, nothing shady. If it's not useful, I'm happy to leave you be — just say the word and you won't hear from me again. Sorry for the interruption either way.
>
> — Cyrus

---

## C) NO BUDGET / "can't afford it" / "too expensive" / "what's the cost"

**Goal: don't discount reflexively; reframe to ROI, offer a smaller on-ramp, keep the relationship.**

### C1. "What does it cost?" (price question — NOT a no yet)
Anchor with ROI first, give the range, push to call:
> Hi [First],
>
> Depends a little on your setup, but it's typically a one-time setup in the **$1.5–3k** range plus **$500–1k/mo** to run it. The way I'd frame it: if it saves even one or two jobs a month that would've gone to whoever replied first, it more than pays for itself — and for most [vertical]s that's a low bar.
>
> Happy to map it to your actual lead volume on a quick call so the numbers are real, not hypothetical: https://cal.com/cyshek
>
> — Cyrus

### C2. Genuine "no budget right now"
Stay warm, offer a lighter entry or a later check-in:
> Hi [First],
>
> Completely understand — no pressure at all. Two thoughts: (1) I can usually start with a stripped-down version (just the 60-second auto-text-back, no monthly bells and whistles) that's a much smaller lift, or (2) if now's just not the time, I'm glad to circle back in a quarter. Whatever's useful — and if neither, no worries at all.
>
> Want me to put together what the lighter version would look like? https://cal.com/cyshek
>
> — Cyrus

### C3. "Already have someone / using [competitor/tool]"
Don't trash the incumbent; probe the gap:
> Hi [First],
>
> Nice — sounds like you're ahead of most then. The one thing I'd gently check: does your current setup reply to brand-new leads within ~60 seconds, *after hours and on weekends*? That's where most "we've got it handled" shops still quietly lose people. If it already does, you're genuinely set and I'll get out of your hair. If there's a gap, I'd love to show you how we close it — 15 min: https://cal.com/cyshek
>
> — Cyrus

---

## D) HIGH-VALUE EDGE CASES

### D1. "Is this an AI / a bot / are you a real person?"
Be honest, disarm with it:
> Hi [First],
>
> Ha — fair question given what I'm selling. I'm a real person (Cyrus), and yes, I use automation to handle outreach efficiently — which is exactly the kind of system I'd set up for [Business], pointed at your leads instead of mine. Happy to hop on a quick call so you can see there's a human behind it: https://cal.com/cyshek
>
> — Cyrus

### D2. "Can you do [adjacent thing] — website, ads, SEO, CRM?"
Say yes if plausibly in scope (it's an automation agency), book to scope it:
> Hi [First],
>
> Yeah, that's squarely in what I do — [restate their ask] is a common add-on once the lead-response piece is in. Let's get on a quick call and I'll scope exactly what you need: https://cal.com/cyshek
>
> — Cyrus

### D3. Auto-reply / out-of-office
Do nothing. Don't count as a reply. Let the normal cadence continue (the scan won't flag OOO as a human reply since it matches on From-address = recipient, so double-check: if an OOO auto-reply trips the replier scan, manually clear that address from `followup_exclude.json` so they still get the follow-up).

### D4. Wrong person / "talk to our office manager / owner"
> Hi [First],
>
> Thanks — really appreciate you pointing me the right way. Mind passing my note to [name], or sharing the best email? Happy to take it from there. Either way, thank you.
>
> — Cyrus

---

## OPS — what to DO when a reply lands (checklist)

1. **Read it, classify** (A / B / C / D above).
2. **Reply in-thread** from cyshekari@gmail.com within the hour (PT waking hours). Personalize the bracket fields.
3. **If interested (A) →** ping Cyrus in Discord #making-money with: who replied, vertical, what they said, and that I've replied + offered the cal link. He runs the call.
4. **If hard-no / opt-out (B2) →** add the address to `followup_exclude.json` (`exclude` array) AND set `"replied": true` in any staged followup payload, so the orchestrator never re-contacts them.
5. **If positive/negative human reply (any) →** the daily orchestrator's scan already auto-excludes anyone whose From-address matches a recipient, so they drop out of follow-ups automatically. The manual step above is belt-and-suspenders for opt-outs.
6. **Log it** in today's `memory/YYYY-MM-DD.md`: who, classification, outcome.

## DELIVERABILITY NOTE (from 2026-06-30 manual sweep)
- 6 hard bounces found + excluded: pashallplus.com, advancedroofingtechnologies.com, info@chasenw.com, info@highroadroofing.com, jthroop@friedmanthroop.com, impallari@gmail.com (552). All "address/domain not found" type — **good news: zero spam/policy blocks**, so sender reputation is clean.
- **Recoverable:** `angela@pashallplus.com` was a TYPO — real domain is **paschallplus.com** (has Google MX). Re-send corrected as `angela@paschallplus.com` in the next batch.
