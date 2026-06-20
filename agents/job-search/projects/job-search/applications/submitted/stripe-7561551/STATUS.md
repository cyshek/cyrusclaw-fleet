SUBMITTED — 2026-05-24T23:27 UTC

role_id: 1055
company: Stripe
role: Product Manager, Commerce Systems
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=stripe&token=7561551
confirmation_text: "Thank you for applying. Thank you for submitting your application to Stripe..."
verification_code_used: 8kEugZhM
submitted_by: auto (job-search single-role worker, role 1055 — 3rd REPLAY of 1019/1049 path)
resume_attached: Cyrus_Shekari_Resume_stripe_7561551_v2.pdf

Notes:
- 3rd Stripe submit using the validated path. Clean replay; no new gotchas.
- gh_jid token (7561551) extracted from Stripe URL path. Stripe direct URL
  (stripe.com/jobs/listing/.../7561551/apply) is NOT supported by
  inline_submit.py's detect_ats(). Workaround: temporarily patched app_url
  to "https://stripe.com/jobs/search?gh_jid=7561551" in tracker.db so
  GH_RX_ALT (?gh_jid=\d+) matched, ran inline_submit, then restored the
  original app_url. BACKLOG: teach detect_ats to handle Stripe direct URLs
  by extracting the trailing /<jid>/ segment as gh_jid.
- Direct embed URL: https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7561551
- Resume upload via Playwright connect_over_cdp + page.set_input_files
  (browser tool's act:upload returned ok=true but file did NOT stick —
  same observation as 1049). Used /tmp/upload_resume_1055.py.
- Form fill via inlined stripe_filler.js (note: stripe_filler.js on disk
  is already a top-level `async () => {...}` expression, NOT a module
  export; pasted the body into browser act:evaluate fn parameter).
- Security code arrived in ~10 seconds. Greenhouse sender:
  no-reply@us.greenhouse-mail.io. Subject: "Security code for your
  application to Stripe".
- NO captcha challenge. Consistent with 1019/1049 observation (Stripe
  captcha gate is intermittent, not always blocking).
- Submit flow:
  1. Navigate embed URL (reused 1049's confirmation tab)
  2. CDP set_input_files('#resume', ...)
  3. Run inlined stripe_filler logic via evaluate
  4. Click "Submit application"
  5. 8 security-input boxes appear → fetch code from Gmail
  6. Fill 8 boxes via setNative + Event(input/change)
  7. Click "Submit application" again → /embed/job_app/confirmation

Field outcomes (from filler):
- All 9 text fields filled (first/last/email/phone/employer/title/school/
  degree/cityState). University of Houston confirmed (permanent fix in
  stripe_filler.js line 79, shipped after 1049).
- 7 dropdowns picked: country=+1, reside=US, auth=Yes, sponsor=No,
  remote=Yes intend, prevStripe=No, whatsapp=No
- nycHybrid: 'no inp' (not on this form — same as 1019/1049)
- mselects: US checkbox in "countries anticipate working" ✓
- candidate-location: Kirkland, Washington, United States ✓
- Demographics: all 4 declined (gender, hispanic_ethnicity,
  veteran_status, disability_status)

Caveat re: YOE
- This is the Seattle (Commerce Systems) variant. JD likely requires
  5+ yrs PM; Cyrus has 2 yrs FT. Submitted per parent agent's curation.
