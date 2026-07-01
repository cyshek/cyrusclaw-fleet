# STATUS: SUBMITTED

slug: contentful-7875317
role_id: 3988
role: Associate Solution Architect, Professional Services
company: Contentful
url: https://job-boards.greenhouse.io/contentful/jobs/7875317
confirmation_url: https://job-boards.greenhouse.io/contentful/jobs/7875317/confirmation
confirmation_text: "Thank you for your application! We've successfully received your application."
submitted_by: auto-gh-residential
submitted_on: 2026-06-30
resume_attached: true
cover_letter_attached: true
notes: |
  GH Enterprise reCAPTCHA (sitekey 6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0).
  Required residential proxy (JOBSEARCH_CDP=http://127.0.0.1:19223).
  Email OTP verification code VIraHKEx required after first 428 captcha-failed.
  Fix applied: Playwright-native force click for needs_review eligibility dropdown
  (question_66276231 = "Are you eligible to work in the country you have applied to?" -> Yes)
  Root cause: phone ITI listbox open (display:block) after setNative phone fill caused
  SEL_PICK ctrl.click() to toggle-close eligibility dropdown every other call.
  Fix: hide ITI via style.display='none', then page.click(force=True).
