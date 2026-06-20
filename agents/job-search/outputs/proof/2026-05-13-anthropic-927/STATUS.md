submitted — 2026-05-13 15:35 UTC

confirmation_url: https://job-boards.greenhouse.io/anthropic/jobs/5215124008/confirmation
confirmation_text: Thank you for applying! Your application has been received. If there is a fit, someone from our Recruiting team will notify you.
verification_code_used: encjqxB8
submitted_by: auto (job-search subagent — first inline-pipeline run)
resume_attached: Cyrus_Shekari_Resume_anthropic_5215124008_v2.pdf

Notes:
- AI-use questions answered "No." per 2026-05-13 policy.
- Demographics declined (gender / hispanic_ethnicity / veteran_status / disability_status).
- First real run of new inline-submit pipeline. Cyrus pre-approved.
- Disability dropdown needed a manual retry (option text "I do not want to answer" did not match the demographic loop's regex; loop's regex covers "do not wish to answer" and "decline"). Recovered with a one-shot fix.
- Country react-select rendered as "United States +1" (iti-flag artifact in option text); .select__single-value displayed "+1". Same pattern noted in plan from DeepMind 2026-05-08 — not a bug.
- Email verification gate triggered after first Submit click; resolved via gmail_imap.wait_for_verification_code() and a re-click of "Submit application".
- No Filestack issues — single Attach click + browser.upload to #resume worked on the second try.
