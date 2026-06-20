submitted — 2026-05-22 16:48 UTC

confirmation_url: https://job-boards.greenhouse.io/smartsheet/jobs/7776527/confirmation
confirmation_text: Thank you for your interest in Smartsheet! Your application has been received.
verification_code_used: BVYCy6HV (gmail_imap fetched fresh code from Greenhouse email)
submitted_by: auto (job-search subagent, role 867)
resume_attached: Cyrus_Shekari_Resume_smartsheet_7776527_v2.pdf

Notes:
- AI-use questions answered "No." per 2026-05-13 policy.
- Demographics declined (all 5 new-style demographic_question_* selects + 4 legacy EEO selects).
- Country dropdown ("United States +1") had to be re-picked after initial submit attempt threw "Select a country" — phone iti country setNative didn't propagate to React state. Workaround: open #country react-select directly and click "United States +1" option.
- candidate-location is a react-select async typeahead (not Google Places); standard setNative→input→select pattern works.
- GDPR consent checkbox (gdpr_demographic_data_consent_given_1) was required + ticked.
- Email-verification gate fired on first submit; fresh 8-char code arrived ~4 min after click.
