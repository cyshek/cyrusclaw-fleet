# FOLLOW-UP SEQUENCE — Notes, Cadence & Cron Recommendation (2026-06-29)

**Status: STAGED, NOT SENT.** Touch-2 templates + generator + a sample payload are built. No cron created (left for the parent/Cyrus per instructions).

## Why we're adding this (highest-leverage change)
We had **zero follow-up logic**. Cold outreach roughly **doubles reply rate** with a second touch — most replies land on touch 2–3, not touch 1 (the first email usually just gets buried). This is the cheapest win available: same leads, no new harvesting, ~2× the replies.

## What got built
- **`followup-templates.md`** — per-vertical "touch 2" templates (Home Services / Legal / Med spa) + an optional touch-3 "breakup" email. All SHORTER than touch 1, reference the first email softly ("floating this back up" / "didn't hear back — no worries if it's not a fit"), restate the ONE core benefit (60-sec lead response, 24/7), same Cal.com booking link, easy out ("reply 'not now' and I'll leave you be"). No guilt-trips.
- **`make_followup.py`** — reads a batch sendlog CSV + its original payload and produces `followupN_payload.json` of touch-2 emails for everyone in that batch. Robust to the old batch1 payload shape (which lacks `vertical`) by falling back to `prospects.csv`. Same first-name hardening as batch4 (real names only → else "there").
- **`send_followup.py`** — clone of `send_batch2.py`. Only sends rows where `"replied"` is falsy and `"to"` is present. Usage: `python3 send_followup.py followup1_payload.json followup1_sendlog.csv`.
- **`followup1_payload.json`** — SAMPLE generated from `batch1_sendlog.csv`: 15 touch-2 emails (3 each across Med spa / PI / Family / HVAC / Roofing).

## ⚠️ Reply detection is NOT automated here — manual exclusion required before send
We cannot perfectly detect who already replied programmatically in this environment. So `make_followup.py` includes **every** contacted business and marks each row `"replied": null`. **Before sending any follow-up batch**, the parent/Cyrus must:
1. Check the Gmail thread / agency-reply-monitor for anyone who replied (positive OR negative — "not interested" still means STOP).
2. For each replier, either set `"replied": true` on their row or delete the row.
`send_followup.py` will skip any row where `replied` is truthy, as a safety net.

## Recommended cadence
- **Touch 1:** day 0 — the original batch send (batch1/2/3 already sent; batch4 staged).
- **Touch 2:** **day +3 to +4** after touch 1. Reply on the original thread if possible (better deliverability + context). Use `make_followup.py` → review → remove repliers → `send_followup.py`.
- **Touch 3 (optional breakup):** **day +7 to +10** after touch 1. The "permission to close the file" email (in `followup-templates.md`). Often the highest-reply email in a sequence. Send ONCE, then STOP forever. (Three emails is the hard ceiling — over-sending is what caused the SiteLens bounce mess.)
- **Always exclude repliers before each subsequent touch.**

## Batch-by-batch follow-up status (touch-2 due dates)
| Batch | Sent (touch 1, UTC) | Touch-2 window (day +3–4) | Notes |
|---|---|---|---|
| batch1 (15) | 2026-06-26 | **~2026-06-29 to 06-30 → DUE NOW** | sample `followup1_payload.json` already generated |
| batch2 (27) | 2026-06-27 | ~2026-06-30 to 07-01 | run `make_followup.py batch2_sendlog.csv batch2_payload.json followup2_payload.json` |
| batch3 (2)  | 2026-06-28 | ~2026-07-01 to 07-02 | tiny; can fold into batch2's send |
| batch4 (45) | not sent yet | +3–4 days after it sends | generate after batch4 touch-1 goes out |

## Suggested cron approach (DO NOT create — left for parent/Cyrus)
A daily low-frequency cron could automate the *generation + reminder* (not the send, which needs manual replier-exclusion):
- **Daily ~9am PT, channel-bound:** for each batch whose touch-1 age is 3–4 days and which has no `followupN_sendlog.csv` yet, run `make_followup.py` to produce the payload, then **ping Cyrus**: "Batch N follow-ups staged (M emails). Review repliers, then I'll send." Keep the human in the loop for the actual send.
- A second optional rule at touch-1 age 7–10 days generates the touch-3 breakup payload the same way.
- Reuse the existing per-agent light-touch cron pattern; bind to the agency Discord channel; use sonnet (cheap, it's just generate+notify). The SEND step stays manual/approved.

## QC already applied to follow-ups
Same first-name hardening as batch4 (verified on the batch1 sample: no "Hi Attorney,"/"Hi Officecrew,"/"Hi Betterskin," — all resolve to real first names or "there"). Bodies are short (≤70 words target), one link (Cal.com), plain text.
