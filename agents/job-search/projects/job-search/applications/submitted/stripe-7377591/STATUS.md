SUBMITTED — 2026-05-24T23:42 UTC

role_id: 1175
company: Stripe
role: Specialist Solutions Architect, Payments
est_tc: $334K
confirmation_url: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=stripe&token=7377591
confirmation_text: "Thank you for applying. Thank you for submitting your application to Stripe..."
verification_code_used: svMXJPQ7
submitted_by: auto (job-search single-role worker, role 1175 — 5th REPLAY of validated Stripe path)
resume_attached: Cyrus_Shekari_Resume_stripe_7377591_v2.pdf

Notes:
- 5th Stripe submit using the validated direct-embed path. Clean ~5-min replay.
- gh_jid 7377591 extracted via greenhouse_iframe path-URL adapter (no in-flight hack).
- Direct embed URL: https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7377591
- Resume upload via Playwright connect_over_cdp + page.set_input_files('#resume', …); verified via filename grep in DOM text (input gets swapped after upload, so #resume returns null — expected).
- Form fill via inlined stripe_filler.js logic (University of Houston permanent), one browser.act:evaluate call.
- Submit → 8 security-code boxes → wait_for_verification_code (~few seconds) → fill via setNative+input/change → Submit → /embed/job_app/confirmation.
- NO captcha challenge.

Field outcomes:
- All 9 text fields: first/last/email/phone/employer/title/school(U of Houston)/degree/cityState ✓
- 7 dropdowns picked: country=+1, reside=US, auth=Yes, sponsor=No, remote='Yes I intend', prevStripe=No, whatsapp=No
- nycHybrid: 'no inp' (not on this form — consistent across all 5 Stripe replays)
- mselects: US checkbox in "countries anticipate working" ✓ (1/29 checked)
- candidate-location: Kirkland, Washington, United States ✓
- Demographics: all 4 declined (gender, hispanic_ethnicity, veteran_status, disability_status)

Form characteristics for this role:
- No AI-disclosure question
- No travel% question (despite "Specialist Solutions Architect, Payments" title implying customer-facing work)
- Standard Stripe GH form, identical to 1019/1049/1055/1171 schema

Caveat re: title fit
- "Specialist Solutions Architect, Payments" — customer-facing SA role at Stripe. Submitted per parent agent's curation given est_tc=$334K.
