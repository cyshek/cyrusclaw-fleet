SUBMITTED — 2026-05-25T01:00 UTC

role_id: 788
company: Okta
role: Product Manager - Identity Threat Protection
location: (per JD)
est_tc: $62K (Levels stale; Okta PMs realistically $250K+)
fit: ?
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=okta&token=7603685
confirmation_text: greenhouse confirmation page reached (conf=true, fieldErrs=[], grecapErr empty)
verification_code_used: pWaac5Dq
submitted_by: auto (job-search single-role worker, role 788)
resume_attached: Cyrus_Shekari_Resume_okta_7603685_v2.pdf
tracker_db_backup: tracker.db.bak.20260524-role788

Notes:
- okta.com host→slug mapping already present in `adapters/greenhouse_iframe.HOST_TO_GH_SLUG`.
- Wrapper-iframe lookup failed (www.okta.com careers wrapper doesn't expose #grnhse_iframe); runner fell back to direct `/embed/job_app?for=okta&token=7603685` and submitted successfully.
- Two permanent pipeline fixes landed:
    1. `greenhouse_dryrun.py` LABEL_RULES: added `"have you worked for"` and `"have you worked at"` → `worked_at_company_before` (Okta's "Have you worked for Okta in the past?" was a blocker; prior rules only matched "have you EVER worked"). Placed adjacent to existing "have you ever worked for" rule.
    2. `greenhouse_filler.py` JS_TICK_GDPR_CONSENT: broadened label regex to include `i acknowledge and agree|processing of my personal data|by checking this box, you consent`, AND now also tests the parent fieldset's `<legend>` text (not just the `<label>` next to the checkbox). Okta's two consent checkboxes label their inputs only "Yes" / "I acknowledge" with the consent text in `<legend>`, so the prior label-only match missed them entirely (caused first TIMEOUT — fieldErrs="This field is required" on the privacy-policy acknowledgement).
- Application questions on Okta form: standard PII + LinkedIn URL + "Have you worked for Okta in the past?" (No) + two consent fieldsets (both ticked). 17/25 filled, 4 declined (demographics), 3 unresolved (all conditional "if yes, please describe" follow-ups to No answers, safe to leave empty), 1 filled-needs-review (the consent checkbox value, ticked correctly).
- Single email verification code (`pWaac5Dq`) fetched via gmail_imap.wait_for_verification_code; runner one-shot filled #security-input-0..7, clicked Submit, confirmation page reached.
- Resume upload: same Filestack quirk as Comet/Guidewheel — `click_attach` reported "no #resume input and no filename" mid-step, but `verify_resume` confirmed `filename_visible=true` (committed before the check ran).
