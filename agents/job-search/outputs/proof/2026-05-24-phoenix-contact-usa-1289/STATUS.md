submitted — 2026-05-25 03:55 UTC

confirmation_url: https://job-boards.greenhouse.io/phoenixcontact/jobs/7609238003/confirmation
confirmation_text: Thank you for applying. You will receive a confirmation email. If you do not see it, please check your spam folder.
verification_code_used: 4rk5ZEKZ (sent to cyshekari@gmail.com, fetched via fetch_company_code.py)
submitted_by: auto (job-search subagent, role 1289)
resume_attached: Cyrus_Shekari_Resume_phoenixcontact_7609238003_v2.pdf

Notes:
- AI-use questions answered "No." per 2026-05-13 policy.
- Demographics declined (gender / hispanic_ethnicity / veteran_status / disability_status).
- US work-authorized = Yes ("If hired, can you provide proof of citizenship or verification of your Legal Right to Work in the U.S.?" → Yes).
- Sponsorship = No ("No - I will NOT require Phoenix Contact to sponsor me now or in the future.").
- Current/former Phoenix Contact employee = No.
- Restrictive covenants = No.
- "How did you hear about this specific opening?" = LinkedIn.
- SMS opt-in declined (No).
- GDPR Acknowledgement = Acknowledge.
- "What experience do you have in electronic component or industrial sales?" — tailored cover answer (Pro Painters CRM sales pipeline + Microsoft customer-facing technical experience).
- "Where are you located?" — Kirkland, WA; open to relocating for SF.
- Country (address) field rendered required even though not in dryrun schema; filled via typeahead → United States. Form displays "+1" due to shared iti widget but submission succeeded.
- Email security-code gate triggered (Phoenix Contact requires verification before final submit). 8-char code captured from Greenhouse mail, accepted on first try.
- Required LABEL_RULES added to greenhouse_dryrun.py for: "electronic component or industrial sales" (essay placeholder), "where are you located" (city_state), "current or former <X> employee" (answer_no), "proof of citizenship or verification of your Legal Right to Work" (work_authorized).
