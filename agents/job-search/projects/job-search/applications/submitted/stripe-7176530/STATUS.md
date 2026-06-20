SUBMITTED — 2026-05-24T23:21 UTC

role_id: 1049
company: Stripe
role: Product Manager, Payments
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=stripe&token=7176530
confirmation_text: "Thank you for applying. Thank you for submitting your application to Stripe..."
verification_code_used: FdZiAnKs
submitted_by: auto (job-search single-role worker, role 1049 — REPLAY of 1019 path)
resume_attached: Cyrus_Shekari_Resume_stripe_7176530_v2.pdf

Notes:
- Replayed 1019's path exactly. No new gotchas surfaced.
- Direct embed URL: https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7176530
- Resume upload via CDP-attached Playwright `page.set_input_files('#resume', ...)`.
  Browser tool's `act:upload` not used (per 1019 finding it doesn't stick).
- Form fill via stripe_filler.js (patched 'University of Washington' -> 'University of Houston'
  for this run; this is a divergence from 1019 which had no school field. Filler should be
  patched permanently — open BACKLOG item.)
- Security code arrived in ~10 seconds. Greenhouse sender: no-reply@us.greenhouse-mail.io.
- NO captcha challenge surfaced (consistent with 1019's observation that Stripe captcha gate
  is intermittent, not always blocking).
- Submit flow:
  1. Navigate to embed URL
  2. CDP set_input_files on #resume (Greenhouse v2 replaces input with filename <p>)
  3. Run stripe_filler.js (text fields, country/auth/sponsor/remote/prevStripe/whatsapp
     dropdowns, US checkbox in countries-anticipated, candidate-location typeahead,
     demographics decline pass)
  4. Click "Submit application"
  5. 8 security-input boxes appear → fetch code from Gmail via fetch_company_code.py
  6. Fill 8 boxes via setNative
  7. Click "Submit application" again → /embed/job_app/confirmation

Field outcomes (from filler):
- All 9 text fields filled
- All 7 dropdowns picked (country=+1, reside=US, auth=Yes, sponsor=No, remote=Yes intend,
  prevStripe=No, whatsapp=No)
- nycHybrid: 'no inp' (not on this form — same as 1019)
- mselects: US checkbox in "countries anticipate working" ✓
- candidate-location: Kirkland, Washington, United States ✓
- Demographics: all 4 declined (gender, hispanic_ethnicity, veteran_status, disability_status)

Caveat re: YOE
- JD requires "7-12+ years of industry PM experience"; Cyrus has 2 yrs FT (3 incl internships).
  Submitted per parent agent's curation — not my call to gate. Likely auto-reject due to YOE
  filter, but the submit is on record.
