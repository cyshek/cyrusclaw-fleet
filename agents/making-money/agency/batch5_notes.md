# BATCH 5 — Harvest + Staging Notes (2026-06-30)

**Status: STAGED, NOT SENT.** `batch5_payload.json` (30 records) is ready for review + send.
No `batch5_sendlog.csv` exists → nothing has been sent. Do not fire until reviewed.

**The point of batch 5 = PERSONALIZATION OVERHAUL.** Batches 1–4 ran ~84% "Hi there" and ~43%
generic `info@`. Batch 5 lifts real-first-name greetings to **43%** and personal/owner inboxes
to **60%** of the staged set — and softens the first-touch CTA to a reply ask with **zero links**.

## Headline numbers
- **Harvested (fresh listicles):** 215 businesses (5 fresh metros × PI / HVAC / roofing / plumbing), 212 after dedupe.
- **With a findable, on-domain email (free scrape, NO Hunter):** 100/212. After dropping 20 off-domain/freemail scrape false-positives → clean pool.
- **Emailable (clean email + a real personalization hook):** 72.
- **Final staged batch 5:** **30 emails** — selected to maximize personalization + keep city/vertical spread.
- **Real-first-name greetings:** **13/30 = 43%** (vs batch1–4 ~15%).
- **Personal / owner inbox (not generic info@):** **18/30 = 60%** (vs batch1–4 ~43% *generic*).

## Cities + verticals (3 primary FRESH metros + 2 fresh top-ups + 1 recovered lead)
All metros are FRESH (zero domain overlap with batches 1–4 / excluded_domains.json). Reno appears
only via the explicitly-requested recovered lead (a batch-4 typo correction), not a new harvest.

| Metro | PI law | HVAC | Roofing | Plumbing | Total |
|---|---|---|---|---|---|
| Albuquerque, NM | 5 | 1 | 2 | 2 | 10 |
| Colorado Springs, CO | 0 | 5 | 2 | 2 | 9 |
| El Paso, TX | 2 | 1 | 3 | 0 | 6 |
| Fresno, CA | 0 | 1 | 1 | 0 | 2 |
| Greenville, SC | 2 | 0 | 0 | 0 | 2 |
| Reno, NV (recovered) | 0 | 1 | 0 | 0 | 1 |

Final mix: **9 Personal injury law · 9 HVAC · 8 Roofing · 4 Plumbing.**
Email source: **18 personal/owner inbox · 12 generic (info@/office@/support@).**
Hook mix: **15 slow-SLA · 9 intake/contact-form (PI + HVAC) · 6 review-gap (≤12 reviews).**

## The 13 real-name greetings (high-precision — see name-safety below)
Angela (Paschall Plumbing, recovered), Stan (915 Do It Right), Chad (JR & Co), Lance (Wainwright &
Associates), Josh (Bradley Law), Jonathan (Garcia Legal), Oreanna (Davis the Plumber), Shiloh
(Rocky Mountain Roofing), Gabriel (Gabriel S. Perez Law), Casey (Red Rhino Roofing), Ben (Bentek
Plumbing), Adam (Adam Oakey Law), Cesar (Cesar Ornelas Injury Law).
*Every one is either a personal first.last/first@ inbox or a first name that also appears in the
firm name (Adam Oakey, Cesar Ornelas, Gabriel Perez) — i.e. confidently the principal.*

## Recovered lead (explicitly requested) — INCLUDED
`angela@paschallplus.com` — **Paschall Plumbing, Heating, and Cooling** (Reno, NV, HVAC). The
batch-4 typo was `pashallplus.com`; corrected domain `paschallplus.com` has verified Google MX.
Greeting "Hi Angela," (personal local-part). Marked `email_source: site-personal(recovered-lead;
verified MX)`. Sourced from `recoverable_leads.csv`.

## CTA CHANGE (done) — softer reply ask, ZERO links on first touch
Old (batch4): "grab whatever 15-min slot works for you here: https://cal.com/cyshek …".
**New (batch5), in every body:** *"Want me to send over a 2-minute demo so you can see exactly
what your customers/clients would experience? Just reply and I'll fire it over."*
- **No cal.com link on first touch** (it moves to the follow-up bump). **0 links/email** (verified).
- Bodies plain text, **90–104 words**, single "— Cyrus" sig.

## Personalization mechanics (how the names + inboxes were found, free)
- **`sitescrape5.py` / `harvest5_scrape_mt.py`** (threaded, 16 workers): crawl home + up to 4 of
  contact/about/team/our-team/meet-the-team/attorneys pages; collect mailto+regex emails and an
  owner/principal first name from JSON-LD (`Person`/`founder`) and text near owner/principal/
  founder/managing-partner triggers.
- **Personal-inbox preference:** when multiple emails exist on the domain, prefer a personal
  local-part (`first@` / `first.last@`) over `info@/office@/support@`. `email_source` records it
  honestly (`site-personal` vs `site-generic`).
- **Name SAFETY (precision over recall — ambiguous → "Hi there,"):**
  - Greeting name is taken from a **personal, on-domain** email local-part first (strongest
    signal); a generic-inbox row is only named if the scraped owner name **also appears in the
    business name**. HTML-only owner names on generic inboxes → "there" (too risky).
  - Hard-blocks generic words (info/office/contact/**contactus**/support/team…), business/role
    words (law/attorney/heating/roof…), a **geography + filler blocklist** (Colorado/County/Santa/
    Grandma/Locally/Tips/You/That…), initial+surname junk (R. Lobb→`rlobb`, P. Tena→`ptena`,
    `jimvc`), and the business name as a "name" (`peakview@peakviewroofing.com`).
  - These killed the exact false positives this batch threw up ("Hi Grandma/Santa/Contactus/Oug/
    Motorcycle/Tips/You/Vihayster"). Net 13 clean names survive.
- **Off-domain / freemail email rejection:** dropped 20 scrape false-positives whose email domain
  ≠ business domain or was freemail/host junk (`john@smith.com`, `…@yahoo.com`, `…sg-host.com`,
  `…awesomeservice.com`). Better to fall back than mis-send to the wrong person.

## QC pass — `qc_batch5.py` (repointed from qc_batch4 logic) → **0 issues**
- ✅ singular/plural reviews ("3 reviews", and would catch "1 review"); review-gap only on ≤12.
- ✅ first names: real human only; no role/biz/geo words, no digits, no non-alpha. 13 named, 17 "there".
- ✅ **CTA: 0 cal.com links, 0 links of any kind on first touch; demo reply-ask present in all 30.**
- ✅ possessive ("Sunworks' site" not "Sunworks's"); "— Cyrus" sign-off on all; no literal `\n` in bodies.
- ✅ word count 90–104 (≤140 guard, ≥60 guard); 30 unique recipients, no dup recipients, all valid `to`.
- ✅ **Pre-flight (`_precheck5.py`):** 0 recipient overlap with batches 1–4 sendlogs; **0 domain
  overlap with excluded_domains.json**; 0 malformed addresses; links/email = [0].

## Pipeline issues hit (and handled)
1. **First threaded scrape run died at 208/212 without writing output** (sibling-session kill +
   no incremental dump). Fix: added `fut.result(timeout=120)` + a periodic
   `harvest5_sitescrape.partial.json` safety dump, then re-ran clean (212/212, DONE line written).
2. **Owner-name scraper over-recalls** (grabs geography/filler/sentence words near triggers). Fixed
   downstream with the strict name-safety gate above (precision-first), not at scrape time.
3. **Off-domain email false-positives** from footers / web-dev agency addresses / example emails.
   Fixed with the on-domain+freemail rejection in `merge5.py` (dropped 20).
4. **`write`-tool mangled newlines into literal `\n`** in every generated script (known issue). All
   email bodies were built with `chr(10).join([...])` (zero bare `\n`); helper scripts were repaired
   with chr(10)-based fixers and re-validated (`ast.parse`) — every script parses.
5. **Hunter NOT called** (free quota exhausted until 2026-07-19). Emails are 100% free website scrape.
6. **Roofing category 404s for Greenville SC** and **plumbing 404s for El Paso TX** on Expertise.com —
   skipped those two cells; the rest of each metro is live.

## Files produced this run (batch5-named; no batch4 clobber)
- `harvest5_tag.py` → `harvest5_raw.json` (215, tagged via `parse_expertise2.py`).
- `dedupe5.py` → `harvest5_deduped.json` (212 fresh unique domains; 0 excluded, 3 intra-batch dups dropped).
- `sitescrape5.py` (enhanced scraper: personal-email pref + owner-name) + `harvest5_scrape_mt.py`
  (threaded driver) → `harvest5_sitescrape.json` (212; email=100, owner-name=80, hooks=173).
- `merge5.py` → `harvest5_merged.json` + `harvest5_emailable.json` (72; off-domain dropped; recovered
  lead injected).
- `make_batch5.py` → `batch5_payload_full.json` (all 72 drafted, the stable full set).
- `select5.py` → **`batch5_payload.json`** (the 30 staged, personalization-weighted). ← review + send this.
- `qc_batch5.py` (QC) · `_precheck5.py` (overlap/format pre-flight).
- `raw5/*.html` — the 16 live fetched listicles.
- `send_batch5.py` — sender clone (repointed copy of send_batch2.py). **DO NOT RUN without approval.**

## How to send (when approved — DO NOT auto-send)
A dedicated sender isn't required: `send_batch2.py` works if you repoint `PAYLOAD`/`LOG` to
`batch5_payload.json` / `batch5_sendlog.csv`. **`send_batch5.py` is that exact repointed clone** —
run `python3 send_batch5.py` only after explicit approval. Same mechanics as prior batches:
Gmail `SMTP_SSL`, 6s spacing, "Cyrus" From. Recommend **15–20/day chunks** from the warmed inbox.
A few hours after, run a bounce sweep (`check_bounces_batch2.py` repointed to the batch5 log) to
catch hard bounces. Follow-up bump (with the cal.com demo link, per OUTREACH-TEMPLATES.md) goes
out 3–4 days later to non-repliers — that's where the link earns its keep now.

## Depth bench (unused, available next pass)
42 more clean emailable rows sit in `batch5_payload_full.json` beyond the 30 staged (mostly generic
`info@`/`office@` form-no-instant rows in Albuquerque / Colorado Springs / El Paso, plus all of the
remaining Fresno + Greenville). They can backfill batch 5 or seed batch 6 with no new harvest.
