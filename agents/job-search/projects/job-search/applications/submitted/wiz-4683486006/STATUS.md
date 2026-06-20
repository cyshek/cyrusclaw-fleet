SUBMITTED — 2026-05-25T15:38 UTC

role_id: 1370
company: Wiz
role: Partner Solutions Architect - South East
location: Remote - USA
fit: 92
exp_required: 3+ yrs
ats: greenhouse_iframe (wiz.io wrapper → wizinc Greenhouse board)
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=wizinc&token=4683486006
verification_code_used: Pmr2x7MV
submitted_by: auto (job-search SUBMIT subagent, role 1370)
resume_attached: Cyrus_Shekari_Resume_wizinc_4683486006_v2.pdf
tracker_db_backup: tracker.db.bak.20260525-role1370

Notes:
- NEW iframe-wrapper host: `wiz.io` → GH slug `wizinc`. Added to `adapters/greenhouse_iframe.HOST_TO_GH_SLUG` (permanent pipeline fix — recurrent: weekly crawl will continue seeing more Wiz roles).
- TWO RUNS REQUIRED. First run failed with `outcome: TIMEOUT` due to two unresolved field issues which the pipeline silently submitted with `filled_needs_review` status; the embed form's server-side validation rejected:
    1. "Please select the state where you currently reside" — value was 'WA' but options were full state names ('Washington', etc).
    2. "Have you ever worked for the local, state, or federal government?" — generic `state` LABEL_RULE incorrectly matched on the word "state" inside this Yes/No label and stuffed 'WA' in.
- Permanent pipeline fixes shipped before second run:
    1. `r_state()` resolver in `greenhouse_dryrun.py` now maps US abbreviations → full names when option list contains full names (e.g. WA→Washington). Returns the abbrev as-is otherwise.
    2. Added LABEL_RULES entries to govt/civilian block (placed BEFORE generic `state` rule on line 209):
        - "worked for the local, state, or federal government" → answer_no
        - "local, state, or federal government" → answer_no
        - "state, or federal government" → answer_no
        - "federal government" → answer_no
    3. Generalized `r_answer_yes`/`r_answer_no` to match options whose label STARTS WITH 'Yes'/'No' (e.g. "Yes, I consent to the retention of my data." — Wiz's talent-pool consent uses this multi-word phrasing).
    4. Added LABEL_RULES for Wiz custom screener Qs (also benefits any other GH tenant using similar copy):
        - "retain your data", "consider you for future opportunities", "future opportunities" → answer_yes
        - "contractor of alphabet", "employee, intern, student ambassador" → answer_no (Wiz's template inexplicably asks Google/Alphabet employment history — Cyrus has none)
        - "if you answered yes to the question above", "previous google/alphabet username", "google/alphabet username" → optional_blank
- Second run: `filled=17, review=0, declined=4, unresolved=0, blockers=0`. Runner submitted cleanly, hit email-verify gate, gmail_imap fetched code `Pmr2x7MV`, runner re-submitted, confirmation page reached.
- Direct-embed fallback fired (wrapper iframe URL didn't expose the GH iframe inside wiz.io's Next.js app) — runner correctly fell through to `https://job-boards.greenhouse.io/embed/job_app?for=wizinc&token=4683486006`.
- Invisible reCAPTCHA Enterprise present; bypassed via direct Submit click (standard pattern, same as Stripe/Dropbox/Guidewheel).
- Demographics: all four EEOC declined per standard policy.
- This role had a related earlier classifier story: retro-skipped on title rule (the word "Partner" triggered seniority-blocklist), then RESTORED today after the title rule was fixed to exempt Partner SA / Partner SE / channel-partner IC titles. Classifier rule fix is already shipped (see TOOLS.md "Job classifier" section / today's daily memory). This submission validates the restore decision.
