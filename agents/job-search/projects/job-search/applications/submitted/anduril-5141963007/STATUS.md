submitted — 2026-05-25 17:13 UTC

confirmation_url: https://job-boards.greenhouse.io/andurilindustries/jobs/5141963007/confirmation
confirmation_text: Thank you for applying. Your application has been received. If there is a fit, someone will be getting back to you.
verification_code_used: H50figGg (8-char post-submit; brief said no code expected, but Anduril DOES use one — surfaced as a learning)
submitted_by: auto (job-search subagent, SUBMIT 1374 brief, lean-mode)
resume_attached: Cyrus_Shekari_Resume_andurilindustries_5141963007_v2.pdf

Notes:
- ATS: legacy boards.greenhouse.io (job-boards.greenhouse.io redirect target).
- No cover essay questions. No US-citizen / ITAR / SkillBridge dropdowns on this particular role variant.
- Country dropdown (phone-input country) needed a manual fix:
  - dryrun spec did NOT list the `#country` react-select as a field — it's nested in the PhoneInput fieldset and was missed by the GH boards-api shape.
  - first submit attempt failed with "Select a country" error; the visible value is shown as only the dialing code "+1" (custom formatSingleValue) which is confusing.
  - resolved by opening the react-select via mousedown/mouseup/click on .select__control and picking "United States +1" option, then re-clicking Submit.
- Brief said "no 8-char post-submit code" — that was wrong for Anduril. Greenhouse mailed `H50figGg` to cyshekari@gmail.com immediately after the (real) submit, and the page rendered 8 `security-input-N` slots. Filled via native setter+input event, Submit auto-enabled, click landed on /confirmation.
- AI-use questions: N/A (none on form).
- Demographics: none on form.
