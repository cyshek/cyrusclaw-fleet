BLOCKED — 2026-05-24T20:43:00+00:00

category: jd-404
role_id: 800
company: OpenAI
role: Technical Program Manager, Human Data
ats: ashby
apply_url: https://jobs.ashbyhq.com/openai/71004494-9a55-4ed5-b458-2ff475f0d881
confirmation_url: (none — job listing no longer exists)

## What happened
inline_submit.py JD-fetch aborted in 0.5s with:
  RuntimeError: Ashby job 71004494-9a55-4ed5-b458-2ff475f0d881 not found in board for openai

Verified independently via Ashby posting-api:
  curl https://api.ashbyhq.com/posting-api/job-board/openai → 699 jobs
  Grep for id 71004494 → no match
  Grep for title "Technical Program Manager, Human Data" → no match
  Closest title still live: "Program Manager, Human Data" (id 932c9cc1-c542-4f67-8d0d-443de87b8213),
  which was already submitted in a prior session (folder exists in applications/submitted/).

The HTML page https://jobs.ashbyhq.com/openai/71004494-... returns 200 but
renders just "Jobs" with no posting content — the SPA correctly resolves to
an empty/missing-posting state.

## Tactic ladder executed
1. inline_submit.py --role-id 800 → ABORT(jd-fetch) — job not in Ashby board.
2. Manual verification via Ashby posting-api → confirmed the posting id is gone
   from OpenAI's live board (not just a transient hiccup).
3. Did NOT proceed to browser execution / captcha retry — without a live JD
   we can't tailor the resume or generate cover answers, and we'd be
   submitting to a removed listing.

## Tracker
- applied_by / applied_on: NOT touched (no real submission).
- agent_notes: updated with `BLOCKED 2026-05-24: jd-404 | ...`
- tracker.db backup: `tracker.db.bak.20260524-r800`

## Unblock
Either:
- Confirm role is permanently gone → close out tracker row (status='skip' or similar).
- If relisted under a new id, update `app_url` to the new URL and re-queue.
- (Optional) Apply to the closely related "Program Manager, Human Data" if a
  second pass against OpenAI Ashby is desired — but that role is already
  submitted in this session as `openai-932c9cc1-c542-4f67-8d0d-443de87b8213`.
