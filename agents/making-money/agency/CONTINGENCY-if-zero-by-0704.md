# Agency Outreach — "If Zero Replies by 07-04" Contingency Memo

**Date:** 2026-06-30 (management tick audit)
**Situation:** 89 touch-1 cold emails across 4 batches + 30 follow-ups sent. **0 replies, 6 hard bounces.** Batch-2 touch-2 auto-fires ~07-01. This memo: is the outreach actually good, are these the right targets, and what's the pivot if still 0 by 07-04.

---

## PART 1 — Is the outreach genuinely compelling? (honest audit)

**Verdict: the COPY is good. The TARGETING and GREETING are the weak links. And the sample is still too small to declare the offer dead.**

### What's strong (don't change)
- **Bodies are specific and human.** Each opens with the prospect's actual gap (their review count / "contact form but no instant response" / a quoted slow-SLA phrase), not "Hi, I run an automation agency." Length 95–134 words. Soft CTA. Plain text. This is textbook-correct cold email — better than 90% of what these owners get.
- **The offer itself is real and valuable** (60-sec speed-to-lead text-back + automated review requests). For roofers/HVAC/PI, "first responder wins ~78% of the time" is a true, felt pain.
- **Deliverability hygiene is right:** one link, plain text, "— Cyrus" sig, small daily batches.
- **Send mechanics are clean:** all 89 logged SENT, only 6 hard bounces (6.7%) — **this is NOT a send-failure problem.**

### What's weak (the actual likely causes of 0 replies — data-backed)
1. **84% of emails open with "Hi there" (only 15% use a real first name).** The body personalizes the *business*, but the human's eye hits the greeting first, and "Hi there" reads like a blast. **This is the single cheapest fix with the highest leverage.**
2. **43% went to generic inboxes (info@ / office@).** These are the graveyard of cold outreach — often unmonitored, auto-filtered, or read by a gatekeeper with zero authority to book a call. Personal/owner inboxes reply multiples higher. Nearly half our volume is aimed at the lowest-yield address type.
3. **Inbox PLACEMENT is the great unknown — and the most likely silent killer.** A brand-new, lightly-warmed Gmail sending 45 near-identical templated emails in a day, each containing a `cal.com` link (and earlier an `http://40.65.93.84:8080` raw-IP demo link), is a classic Promotions-tab / Spam-folder pattern. **If these are landing in spam, copy quality is irrelevant.** We have no placement telemetry — we only know they left our outbox.
4. **The CTA asks for a calendar booking on a cold first touch.** "Grab a 15-min slot" is a bigger ask than "worth a quick look? reply and I'll send a 2-min demo." A reply is a 2-second yes; booking a slot with a stranger is a commitment. Lead-gen orthodoxy: **first touch should ask for a REPLY, not a meeting.**

### The honest statistics (most important framing)
- Realistic cold-email reply rates for unwarmed, single-sender, SMB cold outreach: **~1–3% on a good day, often <1% to generic inboxes.**
- 89 emails × 1–3% = **~1–3 replies *expected*.** Getting 0 is **disappointing but inside normal variance** — it is NOT yet proof the offer is broken. We are drawing conclusions from a sample that's barely large enough to see a single reply.
- **Translation:** the right move is not "the offer is dead, pivot everything." It's "fix the 2–3 obvious leaks AND get to a real sample size (300–500 sends) before judging the offer." Don't over-update on a 0/89 that the math predicted could easily be 0.

---

## PART 2 — Are these the right niche targets?

**Mostly yes, with one structural reservation.**
- **Roofing / HVAC / PI law are correct verticals**: high ticket (one job/case >> our fee), real speed-to-lead pain, reviews-driven, non-technical owners who won't build this themselves. Good fit.
- **Reservation:** these owners are *busy, in-the-field, and skeptical of inbound pitches* — they're pitched constantly by SEO/marketing vendors and have built reflexive "delete" habits. Email alone to this segment is a low-yield channel **even with perfect copy.** This argues for adding a channel (phone), not changing the vertical.
- **Geographic spread is fine** (fresh metros each batch, no overlap), but spreading thin across many metros means no local density / referral compounding. Minor.

---

## PART 3 — The pivot ladder if still 0 replies by 07-04

Do these **in order**, cheapest/highest-leverage first. Most are reversible and need no money.

### Tier 1 — Fix the leaks FIRST (free, do before any big pivot) — for batch 5
1. **Kill "Hi there." Get the owner's real first name** (LinkedIn, state contractor license lookup, the "Meet the team" page, Hunter when quota resets). If truly unfindable, use the business name ("Quick one for the Gafco team") before falling back to "there."
2. **Stop emailing info@ as the primary.** Prioritize owner/personal inboxes. If only info@ exists, that prospect drops to a phone-first track (Tier 3), not an email.
3. **Change the first-touch CTA from "book a slot" to "want the 2-min demo?"** Ask for a one-word reply. Move the cal.com link to the FOLLOW-UP only (it already is on follow-ups — just remove it from touch-1). Lowers the ask, protects first-touch deliverability.
4. **Verify inbox placement.** Send a test to a seed account we control across Gmail/Outlook and SEE which tab/folder it lands in. If Promotions/Spam → warm the domain properly (custom sending domain + SPF/DKIM/DMARC, not bare gmail.com) before scaling further. **This may be the whole problem.**

### Tier 2 — Add a real second channel (highest expected ROI)
5. **PHONE / SMS beats email for this exact segment.** These are phone-first trades. A 20-second call ("saw your site, you're losing leads to slow response, can I text you a 2-min demo?") or a direct SMS gets 5–20x the response of cold email. We have every prospect's phone in the payloads already (`phone` field). **This is the single biggest lever and should arguably happen regardless of email results.** Cyrus does calls; I can build the call list + a tight script + an SMS-send path (Twilio ~$0.0079/msg, needs his approval to fund + a number).
6. **LinkedIn touch** for the PI-law / owner-operator segment (they're on LinkedIn more than roofers). Connection request + soft note. Free, different inbox, higher open rates.

### Tier 3 — Reframe the OFFER (if Tiers 1–2 still flat after a real sample)
7. **Lead with a free, concrete deliverable instead of a pitch.** "I recorded a 90-sec Loom of what happens when someone fills out YOUR contact form right now — want it?" A specific, already-done artifact (their actual form, their actual gap, on screen) converts far better than "I set up a system…". More work per prospect, much higher reply rate — worth it at lower volume.
8. **Niche down the offer to ONE wedge** (e.g. *just* "automated Google-review requests" — simpler, cheaper, lower-risk yes than a full speed-to-lead system) to get a foot in the door, then expand. A smaller first ask closes more.

### Tier 4 — Paid, only if organic + phone prove the offer converts
9. **Cold-email-at-scale tooling** (Instantly / Smartlead + multiple warmed domains, ~$40–100/mo) to send 500–1000/day with proper warmup and placement — *only* after we've proven a reply→call→close motion manually. Don't pay to scale a funnel that hasn't converted once.
10. **Paid ads** are premature; skip until we have a proven offer + a landing page that converts.

---

## Recommendation (what I'd actually do)
- **07-01:** let batch-2 touch-2 fire as scheduled (sunk cost, harmless, tests follow-up reply rate).
- **Before batch 5:** implement Tier 1 fixes (real names, owner inboxes, reply-CTA, placement test). These are free and address the most probable causes.
- **In parallel, build the PHONE/SMS track (Tier 2 #5)** — this is the highest-EV move and plays to Cyrus's strength (he does the calls). Bring him a ready call list + script. Needs his go-ahead to fund Twilio (~$10–20 to start) + pick a number.
- **Don't declare the offer dead.** 0/89 is statistically a non-event; the leaks above + a real sample (target 300–500 quality sends and/or 50 calls) come first. Re-judge the OFFER only after that.

**One decision needed from Cyrus:** approve a small SMS/Twilio budget (~$10–20 to start) so I can stand up the phone-first track? Everything else in Tier 1 I can do autonomously for batch 5.
