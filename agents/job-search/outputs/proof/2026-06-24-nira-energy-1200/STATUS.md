SUBMITTED — 2026-05-25 02:42 UTC (2026-05-24 19:42 PDT)

confirmation_url: https://job-boards.greenhouse.io/niraenergy/jobs/4964468008/confirmation
confirmation_text: Thank you for applying. Your application has been received. If there is a fit, someone will be getting back to you.
verification_code_used: 4ppfnkkb (8-char email security code, fetched via fetch_company_code.py)
submitted_by: auto (job-search subagent, role-id 1200)
resume_attached: Cyrus_Shekari_Resume_niraenergy_4964468008_v2.pdf

Form schema:
- 8 dryrun fields filled cleanly (first/last/email/phone + LinkedIn + GitHub).
- Country dropdown: not actually required by submission (the rendering shows flag+code only as placeholder; the "Select a country" helper-text-error appeared but was a phantom — submission succeeded without ever picking an option that displayed differently).
- No essays, no demographics, no GDPR checkbox, no sponsorship/AI questions.
- NEW PATTERN: Greenhouse 8-character email "Security code" challenge fired on first submit. Pipeline didn't know about it but recovered: form text said "verification code was sent to cyshekari@gmail.com. To submit your application, enter the 8-character code". Used `fetch_company_code.py Nira <ts>` which pulled `4ppfnkkb` from `Security code for your application to Nira Energy` (no-reply@us.greenhouse-mail.io). Typed one char per `#security-input-{0..7}` via native value setter, then Submit → /confirmation in ~5s.

Notes:
- reCAPTCHA enterprise (invisible v3) frame was present but did not block. Standard GH pattern.
- Total time including code fetch: ~7 minutes from inline_submit start.
