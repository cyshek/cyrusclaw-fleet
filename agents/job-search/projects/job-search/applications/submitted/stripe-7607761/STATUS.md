SUBMITTED — 2026-05-24T23:38 UTC

role_id: 1171
company: Stripe
role: Partner Solutions Architect - AWS
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=stripe&token=7607761
confirmation_text: "Thank you for applying. Thank you for submitting your application to Stripe..."
verification_code_used: 30dvaWJU
submitted_by: auto (job-search single-role worker, role 1171 — 4th REPLAY of 1019/1049/1055 path)
resume_attached: Cyrus_Shekari_Resume_stripe_7607761_v2.pdf

Notes:
- 4th Stripe submit using the validated path. Clean replay; no new gotchas.
- **PERMANENT FIX VALIDATED**: adapters/greenhouse_iframe.py::extract_gh_jid now
  handles Stripe path-based URLs (stripe.com/jobs/listing/.../<jid>/apply).
  detect_ats() returned 'greenhouse_iframe' directly on the unmodified
  app_url — NO more in-flight tracker hack needed (1055's TODO closed).
- Direct embed URL: https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7607761
- gh_jid token (7607761) extracted from Stripe URL path by the new
  greenhouse_iframe adapter shim.
- Resume upload via Playwright connect_over_cdp + page.set_input_files
  (file did stick; #resume gets replaced after upload so post-verify
  via #resume returns null — instead we grep for filename in DOM text).
- Form fill via inlined stripe_filler.js logic via browser.act:evaluate.
- Security code arrived almost instantly. Greenhouse sender:
  no-reply@us.greenhouse-mail.io. Subject: "Security code for your
  application to Stripe".
- NO captcha challenge. Consistent with 1019/1049/1055 — Stripe direct
  embed is unblocked on this Azure host today.
- Submit flow:
  1. Reused 1055's tab (t472) - navigated to embed URL
  2. CDP set_input_files('#resume', ...)
  3. Run inlined stripe_filler logic via evaluate
  4. Click "Submit application" → 8 security-input boxes appear
  5. Fetch code from Gmail (~10s)
  6. Fill 8 boxes via setNative + Event(input/change)
  7. Click "Submit application" → /embed/job_app/confirmation

Field outcomes (from filler):
- All 9 text fields filled (first/last/email/phone/employer/title/school/
  degree/cityState). University of Houston confirmed (permanent fix from
  stripe_filler.js line 79).
- 7 dropdowns picked: country=+1, reside=US, auth=Yes, sponsor=No,
  remote=Yes intend, prevStripe=No, whatsapp=No
- nycHybrid: 'no inp' (not on this form — same as 1019/1049/1055)
- mselects: US checkbox in "countries anticipate working" ✓
- candidate-location: Kirkland, Washington, United States ✓
- Demographics: all 4 declined (gender, hispanic_ethnicity,
  veteran_status, disability_status)

Form characteristics for this role:
- No AI-disclosure question
- No travel% question (despite "Partner Solutions Architect - AWS" title)
- Standard Stripe GH form, identical to 1055's

Caveat re: title fit
- This is a Partner Solutions Architect role, not a PM role per se. JD likely
  emphasizes AWS partnership solution engineering. Cyrus has 2 yrs FT PM/TPM
  experience with cloud/Azure exposure. Submitted per parent agent's curation
  given est_tc=$334K.
