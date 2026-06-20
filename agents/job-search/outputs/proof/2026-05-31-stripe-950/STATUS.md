SUBMITTED — 2026-05-24T22:32 UTC

role_id: 1019
company: Stripe
role: Product Manager, Startup Products
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=stripe&token=7901987
confirmation_text: "Thank you for applying. Thank you for submitting your application to Stripe..."
verification_code_used: jMgmhRn2
submitted_by: auto (job-search single-role worker, role 1019)
resume_attached: Cyrus_Shekari_Resume_stripe_7901987_v2.pdf

Notes:
- Same v2 Greenhouse-iframe pattern as roles 878/879/950 (May 19 submits).
- Tactic: navigated **directly** to https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7901987
  instead of going through stripe.com/jobs/listing/<slug>/<jid>/apply. The greenhouse_iframe_runner
  failed twice (wrapper redirect changed to listing page without iframe, then iframe Frame timed
  out from Playwright's wait_for_selector). Driving directly via the OpenClaw browser tool worked.
- Resume upload: `browser:upload` was reported ok but did not stick (input.files stayed 0).
  Worked around by attaching to the running browser over CDP from a one-shot Playwright script
  (`page.set_input_files('#resume', ...)`). Greenhouse v2 then replaced the input with a filename
  paragraph (<p>Cyrus_Shekari_Resume_...pdf</p>) — that confirms attach.
- Form fill via `stripe_filler.js` evaluated inline through the browser tool. Skipped fields
  (school/degree/nycHybrid) returned 'no inp' — not on this form, harmless.
- Submit flow: navigate to embed URL → fill text/dropdowns/checkboxes/demographics → upload resume
  → click Submit → 8-char security code arrives via Greenhouse email (jMgmhRn2) → fill the 8
  security-input-N boxes → click Submit again → /embed/job_app/confirmation page.
- NO captcha challenge surfaced this run (reCAPTCHA Enterprise iframe was visible at 256x60 but
  no challenge gate fired). Contradicts the 2026-05-23 ABORT-CAPTCHA-FAIL observation on
  stripe-7815794; possible explanations: warm browser session in this VM, fresh IP score, or
  Stripe's gate doesn't fire 100% of the time. Worth noting as a "single-tenant captcha is
  flaky, not always blocking" data point.
