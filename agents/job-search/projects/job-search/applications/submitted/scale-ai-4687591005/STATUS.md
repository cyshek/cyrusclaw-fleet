submitted — 2026-05-13 16:43 UTC

confirmation_url: https://job-boards.greenhouse.io/scaleai/jobs/4687591005/confirmation
confirmation_text: Thank you for applying. Your application has been received. If there is a fit, someone will be getting back to you.
verification_code_used: LPv9g0Ll
submitted_by: auto (job-search subagent debug-and-harden-filestack-upload)
resume_attached: Cyrus_Shekari_Resume_scaleai_4687591005_v2.pdf

Notes:
- AI-use questions: N/A on this form.
- Demographics declined (gender / hispanic_ethnicity / veteran_status / disability_status). No race field on this form.
- Country: United States (typeahead). Phone iti: +1 / 3468040227.
- Security clearance dropdown: "No". Required follow-up text added: "No, I do not currently hold a security clearance and am not actively pursuing one."
- **First validation of the new upload-then-Attach Filestack pattern.** Resume committed cleanly (filename appeared in body, #resume removed from DOM), no retry needed.
- Email verification gate triggered after first Submit click; resolved via gmail_imap.wait_for_verification_code() and re-click of "Submit application".
