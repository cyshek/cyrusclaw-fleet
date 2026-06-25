# Prospect List — Research Notes (speed-to-lead / review-automation outreach)

**File:** `prospects.csv` · **Rows:** 53 · **Compiled:** 2026-06-24

## What the offer is matching against
Target = owner-operated local service SMBs that visibly lack an automated
"respond to every inbound lead in <60s + automated review requests" system.
For each prospect I confirmed the business on its real site and recorded the
**specific observable gap** (their own words where possible).

## Count per vertical (in the deliverable)
| Vertical | Rows | Real email | FORM-ONLY (verified contact URL) |
|---|---|---|---|
| Med spa / aesthetics | 16 | 13 | 3 |
| Personal injury law | 10 | 9 | 1 |
| Family law | 9 | 7 | 2 |
| HVAC | 9 | 7 | 2 |
| Roofing | 9 | 6 | 3 |
| **Total** | **53** | **42** | **11** |

Cities sampled (deliberately mid-size, owner-operated, away from national chains):
Chattanooga & Knoxville TN, Boise ID, Spokane WA, Tucson AZ, Grand Rapids MI.

## Which verticals had the richest "obvious gap" signal
Signal density measured across the full **reachable candidate pool** I enriched
(262 sites), not just the 53 shipped:

| Vertical | pool | no online booking | no chat/auto-reply | explicit slow-response copy | thin reviews (<35) |
|---|---|---|---|---|---|
| Roofing | 79 | 68 | 70 | **10** | **31** |
| HVAC | 63 | 47 | 60 | 5 | 12 |
| Personal injury | 50 | 49 | 45 | 4 | **24** |
| Family law | 48 | 44 | 44 | 2 | 15 |
| Med spa | 22 | 5 | 15 | 3 | 0 |

**Richest gap signal, ranked:**
1. **Roofing** — the strongest overall. Highest rate of explicit "we'll get back to
   you within 24–48 hrs / one business day" copy *and* the most thin-review profiles
   (31/79 under 35 reviews). These are contractors running on referrals + a basic
   web form; both halves of the offer (instant response + review engine) land hard.
2. **Personal injury law** — best "review-generation" angle. Half the firms sit at
   <35 Google reviews despite decades in practice and $1M+ verdict pages. PI is a
   reviews-driven purchase, so "you win cases but only have 18 reviews" is a sharp hook.
   Almost none have online intake/booking or chat — pure manual intake.
3. **HVAC** — nearly universal absence of any auto-responder (60/63). Emergency-driven
   demand ("my AC died in Tucson in July") makes 60-second response money-obvious.
4. **Family law** — same intake-gap shape as PI, slightly fewer thin-review firms.
5. **Med spa** — *different* gap shape. Med spas are the most digitally mature of the
   five: most already have online booking (Vagaro/Boulevard/Mangomint) and many run a
   chat widget. So the gap is NOT "no booking" for most — it's **no instant text-back
   for the phone/DM/form leads who don't self-book**, and weak post-visit review asks.
   The 5 med spas with *no* booking widget at all are the hottest med-spa targets.

## Patterns that should shape the outreach copy
- **Lead with their own words.** ~24 sites literally state a slow SLA ("we'll get back
  to you within 24 hours / one business day"). Quoting that line back to them
  ("your site promises 24 hours — your competitor texts back in 30 seconds") is the
  single highest-converting opener in this list. Those rows are marked with that hook.
- **Two distinct pitches, pick by vertical:**
  - *Home services (roofing/HVAC):* speed-to-lead is the headline. Frame around
    "first contractor to respond wins the job" + after-job review automation.
  - *Legal (PI/family):* lead with the **review-gap** ("18 reviews for a firm with
    your track record"), then layer instant intake response as the second value prop.
  - *Med spa:* lead with **instant text-back + review automation**, NOT booking
    (most already have booking). Position it as recovering the no-show/ghosted DM leads.
- **Form-only businesses are the most under-served** and the easiest demo: 11 of 53
  have no findable email at all (contact form only) and no chat — meaning a lead today
  literally waits for a human to open an inbox. Great "watch what happens when I fill
  your form" cold-open.
- **Skip the saturated ones.** Several businesses in the raw pool had 500–4,200 reviews
  and full marketing stacks (e.g. big Tucson HVAC shops); I excluded them — they already
  bought this. The sweet spot is 1–3 location, <40 reviews, no chat widget.
- **Personal (gmail/owner) emails = smaller & hungrier.** Rows with a gmail/owner-name
  address (e.g. roofers) are the most likely to be owner-read and to convert on a
  direct, casual note vs. a corporate pitch to info@.

## Method / data provenance (for trust)
- Business names, sites, phones, and review counts for legal + home-services pulled
  from Expertise.com curated city lists (LocalBusiness JSON-LD) — verified per-site.
- Med spas harvested via DuckDuckGo, confirmed on each clinic's own site.
- Every site was fetched live: emails from `mailto:`/contact pages, booking & chat
  detected by widget fingerprints (Vagaro/Calendly/Boulevard/Podium/Birdeye/etc.),
  slow-response copy by phrase match. **No emails were fabricated** — unverifiable ones
  are listed as `FORM ONLY:` with a confirmed (HTTP 200) contact-page URL.
