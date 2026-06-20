submitted — 2026-05-19 04:59 UTC

confirmation_url: https://job-boards.greenhouse.io/scaleai/jobs/4692201005/confirmation
confirmation_text: "Thank you for applying. Your application has been received. If there is a fit, someone will be getting back to you."
verification_code_used: xWuKF2MS (Gmail security code, 8 chars)
submitted_by: auto (job-search subagent — Formik widget fix run 2026-05-19)
resume_attached: Cyrus_Shekari_Resume_scaleai_4692201005_v2.pdf

Fields filled:
- Text: first_name, last_name, email, phone (auto-formatted to (346) 804-0227), LinkedIn URL
- Country picker (new Formik #country widget): United States +1 via OLD mouseup+click recipe
- 4 question dropdowns (No / Yes / No / No)
- Demographics declined: gender, hispanic_ethnicity, veteran_status (3 via JS_DECLINE_DEMOGRAPHICS); disability_status set to "I do not want to answer" via labeled retry
- Resume uploaded via Filestack (#resume → click Attach AFTER setInputFiles)

Notes:
- AI-use questions answered "No." per policy.
- Demographics declined.
- **2026-05-18 bug NOT reproduced today.** Yesterday's run reported "Select a country" rejection on the same form. Today the standard `JS_PICK_DROPDOWNS` (mouseup+click on .select__control then on matching option div) worked first-try — the chip displays "+1" (just the country code, no flag text) which may have caused yesterday's verifier to mis-report failure. See memory/2026-05-19.md for full investigation + the fiber-walk Formik recipe (`wo.props.onChange({label, value})`) as a documented fallback.
