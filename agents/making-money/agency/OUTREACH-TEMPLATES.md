# OUTREACH TEMPLATES — Agency cold email (v1, 2026-06-24)

_Goal of the email: ONE thing — get a reply / book a 15-min call. Not to explain everything._
_Send from Cyrus's Gmail. Plain text, no images, no links except the demo (links can hurt deliverability — see note). Short. Human. Casual._

## Universal rules (deliverability + reply rate)
- **Keep it under ~120 words.** Long = spam-flag + ignored.
- **One link max**, and only the demo URL (http://40.65.93.84:8080/speed-to-lead-demo.html). Consider sending link only on the SECOND email to protect deliverability on first touch.
- **Subject lines that worked in this genre:** lowercase, specific, no salesy caps. Use the per-vertical ones below.
- **First line = THEIR specific gap**, in their words. Never "Hi, I run an automation agency."
- **Soft CTA:** "worth a quick look?" / "want me to show you?" — a yes/no, not "book a 30-min strategy call."
- **From name:** Cyrus, real human. Signature = name + one line, no agency logo wall.
- **Send in small batches (15–20/day)** from a warmed inbox to avoid spam folder. Space them out.

---

## PITCH A — HOME SERVICES (Roofing / HVAC)
*Headline = speed-to-lead. "First to respond wins the job."*

**Subject options:**
- `your site says "{SLA_PHRASE}"`
- `quick one about {CITY} leads`
- `the 24-hour thing on your site`

**Body (SLA-hook version — use when their site states a slow SLA):**
```
Hi {FirstName},

Saw {BusinessName}'s site says you'll get back to folks {SLA_PHRASE}. Not a knock — almost every {trade} shop does the same. The problem is the homeowner who fills that form usually messages 3 contractors and books whoever answers first. Studies put it at ~78% going with the first responder.

I set up a system that texts every new lead back within 60 seconds, 24/7 — answers their question, and books them — then automatically asks happy customers for a Google review after the job.

Happy to show you a 2-minute demo of exactly what your customers would see. Worth a look?

— Cyrus
```

**Body (review-gap version — use for the "thin reviews" rows):**
```
Hi {FirstName},

{BusinessName} does great work but only has {ReviewCount} Google reviews — and in {trade}, reviews are basically the whole ballgame for getting found.

I build a simple system that (1) texts every new lead back in under 60 seconds so you stop losing them to whoever answers first, and (2) automatically asks every happy customer for a review after the job — most shops 3–5x their review count in a few months.

Can I show you a quick demo of what it'd look like for {BusinessName}?

— Cyrus
```

---

## PITCH B — LEGAL (Personal Injury / Family Law)
*Headline = the review gap, second value prop = instant intake. PI especially is reviews-driven.*

**Subject options:**
- `{ReviewCount} reviews for {BusinessName}?`
- `quick thought on {BusinessName}'s intake`
- `reviews + intake for the firm`

**Body (PI / thin-reviews — the sharp one):**
```
Hi {FirstName},

You've clearly won serious cases — but {BusinessName} only shows {ReviewCount} Google reviews. For a PI firm that's leaving a lot of clients on the table, because injured people pick a firm almost entirely on reviews and how fast someone responds.

I set up two things for firms like yours: every new inquiry gets a response within 60 seconds (day or night — that's when accidents happen), and every client who settles gets an automatic, tactful review request. Firms usually go from a couple dozen reviews to triple digits.

Open to a 2-minute demo of how it'd work for {BusinessName}?

— Cyrus
```

**Body (family law / slow-SLA version):**
```
Hi {FirstName},

Saw {BusinessName}'s contact form has no instant response — someone reaching out at 9pm in the middle of a divorce decision waits until business hours, and a lot of them call the next firm instead.

I build a system that responds to every inquiry within 60 seconds, 24/7, qualifies them, and gets them scheduled — plus it automatically asks resolved clients for a Google review (you're at {ReviewCount} right now; this reliably grows it).

Worth a quick demo to see what your potential clients would experience?

— Cyrus
```

---

## PITCH C — MED SPA / AESTHETICS
*DO NOT lead with booking — most already have it. Lead with instant text-back for the leads who DON'T self-book + review automation.*

**Subject options:**
- `the leads who don't book online`
- `quick one about {BusinessName}'s DMs`
- `recovering your ghosted leads`

**Body:**
```
Hi {FirstName},

{BusinessName}'s booking page is great for people ready to book — but the leads who call, DM, or fill the form with a question (and don't book themselves) are the ones that quietly slip away when no one replies fast.

I set up a system that texts those leads back within 60 seconds, 24/7 — answers them and gets them booked — and automatically asks clients for a review after their visit. It basically recovers the inquiries you're already paying to generate.

Can I show you a 2-minute demo of exactly what your clients would see?

— Cyrus
```

---

## FOLLOW-UP (one bump, 3–4 days later if no reply)
*Same thread, even shorter. This is where the demo link earns its keep.*
```
Hi {FirstName} — quick bump in case this got buried. Here's the 2-minute demo so you can see it without a call: http://40.65.93.84:8080/speed-to-lead-demo.html

If it's not a fit, no worries at all — just reply "no" and I'll leave you be.

— Cyrus
```
*(After one bump, stop. No third email — that's what generated the SiteLens bounce mess.)*

---

## Token reference (auto-filled from prospects.csv per row)
- `{FirstName}` — owner/contact first name (gmail/owner-name rows = use it; info@ rows = use business name or "there")
- `{BusinessName}` · `{CITY}` · `{trade}` (roofer/HVAC/etc.)
- `{SLA_PHRASE}` — quote their literal slow-SLA phrase from the hook column
- `{ReviewCount}` — from the hook column where present
