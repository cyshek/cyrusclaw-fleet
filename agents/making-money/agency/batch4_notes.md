# BATCH 4 — Harvest + Staging Notes (2026-06-29)

**Status: STAGED, NOT SENT.** `batch4_payload.json` is ready for review + send. Do not fire until repliers/QC are reviewed.

## Headline numbers
- **Harvested:** 91 fresh businesses (3 new metros × 3 high-ticket verticals).
- **With a findable email:** 57/91 (16 via Hunter before quota died, 41 via direct website scrape).
- **Emailable (email + a real personalization hook):** 49.
- **Final staged batch4:** **45 emails** (dropped 4 junk/placeholder emails — see QC below).
- **Unreachable (no email found anywhere):** 34 — listed at the bottom; re-runnable next month when Hunter's free quota resets, or with a paid Hunter key.

## Metros + verticals (all FRESH — zero overlap with batches 1–3)
| Metro | Vertical | Staged |
|---|---|---|
| Reno, NV | Personal injury law, HVAC | 14 |
| Fort Collins, CO | Personal injury law, Roofing | 19 |
| Tacoma, WA | HVAC, Roofing | 12 |

Final mix: **16 Personal injury law · 16 Roofing · 13 HVAC.**
Email source: **14 Hunter-verified · 31 scraped from the business website.**
Hook mix: 8 review-gap (≤12 reviews) · 7 slow-SLA · 30 contact-form-with-no-instant-response.

## ⚠️ Important context: pipeline changes discovered this run
1. **Expertise.com restructured their site.** The old `parse_expertise.py` (which read `__NEXT_DATA__`) returns 0 rows now — that script tag is gone. Data now lives in per-business **JSON-LD `LocalBusiness` blocks**. New parser written: **`parse_expertise2.py`** (use this going forward). The JSON-LD `url` field is the business's REAL website (better than before), and carries name/phone/city/state/reviewCount/rating.
2. **The `health/med-spas` category 404s now** for every metro tested (Reno, Fort Collins, Tacoma, *and* control cities Austin/Denver/Las Vegas). Expertise appears to have removed/renamed the med-spa category. Dentists (`health/dentists`) also 404 in these metros. So this batch substituted **PI law + HVAC + roofing** (all still live and proven). If med spas are wanted again, the category slug needs rediscovery (their root sitemap is just a stub — no category index).
3. **Hunter.io key is on the FREE plan: 50 searches/month, and all 50 are now used.** That's why only the first 16 domains (all PI law, processed first) got Hunter emails — the rest hit HTTP 429 (quota exceeded), not rate-limiting. The free site-scrape fallback (`sitescrape4.py`) recovered 41 more emails for free. **To enrich the remaining 34 unreachable + future batches, either wait for the monthly reset or upgrade the Hunter key.**

## QC pass (everything the make_batch2 QC cared about, applied)
- ✅ **Singular/plural reviews:** "1 review" vs "N reviews" — verified clean (auto-checked).
- ✅ **Review-gap angle capped at ≤12 reviews.** Firms with more get the neutral "quick thought on your intake" / "contact form, no instant response" angle — never insulted with a low-review jab.
- ✅ **First names: real human names only.** Killed the exact bugs from prior batches: "Hi Attorney," "Hi Officecrew," "Hi Betterskin," plus initial+surname junk ("Ttribble"/"Jthroop"/"Fhellard"/"Kward" from `f.lastname@` Hunter emails) and surname-on-gmail ("Impallari"). All ambiguous → "there" (always safe). Result: 9 genuine first-name greetings (Alayna, Angela, Bob, Curtis, Dara, David, Joe, Matt, Nick), 36 "there".
- ✅ **Possessives fixed.** Names ending in "s" get an apostrophe only ("Sunworks' site", not "Sunworks's site"). 6 such names corrected.
- ✅ **Broken SLA fragments rewritten.** The scraper sometimes captured a partial phrase ("get back to you as soon"). Now normalized: → "says they'll get back to you as soon as they can", bare windows → "promises a response within one business day / 24 hours". Verified grammatical.
- ✅ **Dropped 4 bad emails:** `youremail@yourbusiness.com` (ProRoofing NW — site template placeholder), `hello@mail.com` (Anchor Roofing — generic freemail, not their domain), `rob@gafs.com` (Ampro Builders — GAF *manufacturer* domain, scrape false-positive), `eben@eyebytes.com` (Eco Air NW — web-dev agency footer).
- ✅ **Deliverability:** every body 95–134 words (under the ~120 guideline), exactly ONE link (the Cal.com booking page), plain text, "— Cyrus" signature.
- ✅ **45 unique recipients, no duplicates, all valid `to` addresses.**

## Booking CTA (in every email)
"If it's worth a look, grab whatever 15-min slot works for you here: https://cal.com/cyshek — I'll walk you through exactly what it'd look like for {Business} (no pressure, no hard sell)."

## How to send (when approved)
A sender clone is NOT pre-made for batch4, but `send_batch2.py` works if you repoint `PAYLOAD`/`LOG` to `batch4_payload.json` / `batch4_sendlog.csv`. Recommend sending in 15–20/day chunks from the warmed inbox (same as prior batches). Run `check_bounces_batch2.py` (repointed) ~a few hours after to catch bounces.

## Files produced this run
- `parse_expertise2.py` — NEW JSON-LD parser (Expertise.com changed; old parser is dead).
- `targets4.txt`, `targets4b.txt` — the listicle URLs harvested (+ the dentist attempts that 404'd).
- `raw/*.html` — fetched listicle HTML (6 live PI/HVAC/roofing pages; med-spa/dentist 404 stubs).
- `harvest4_raw.json` (91, tagged) → `harvest4_deduped.json` (91, vs 61 excluded domains) → `harvest4_sitescrape.json` (emails+hooks) → `harvest4_merged.json` → `harvest4_emailable.json` (49).
- `excluded_domains.json` — the 61 already-contacted domains (prospects.csv + all sendlogs).
- `hunter4.py`, `sitescrape4.py`, `merge4.py`, `make_batch4.py`, `qc_batch4.py` — the chain.
- **`batch4_payload.json`** — the 45 staged emails. ← review + send this.

## UNREACHABLE (34 — no email found; re-try with Hunter quota or paid key)
Low-review ones worth prioritizing on a Hunter retry: David M. Sargent (5), Electromatic Refrigeration (5), FM Roofing (6), AAA Roofing (8), Veteran Roofers (8).
Full list: Hotchkin Law, Law Office of William R. Kendall, Adriana Guzman Fralick, Kidwell & Gallagher, Klearman & Associates, Neahusan Law, David R. Houston, Fischer Law Group, David M. Sargent, Michael's Plumbing, Jet Plumbing, 4 Seasons Heating & Cooling, Sparks Heating and Air, Lincoln Heating & Air, Paul's Plumbing & Heating, Anderson Heating & A/C, Fox Plumbing & Heating, Sunset Air, Griffis Heating and Air, G&G Heating and Air, Comfort Craft, Tahoma Comfort Systems, Electromatic Refrigeration, Wood Street Builders, Choice City Home Services, FM Roofing, Storm Guard Roofing, Cooper Construction, Eagle View Home Solutions, AAA Roofing, Three Tree Roofing, Veteran Roofers, Capital Roofing Install & Repair, State Roofing.
