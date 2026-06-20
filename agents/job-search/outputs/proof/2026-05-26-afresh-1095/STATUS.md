SUBMITTED — 2026-05-26 (auto)

role_id: 1095
company: Afresh
role: Sales Engineer
url: https://job-boards.greenhouse.io/afresh/jobs/5986020004
confirmation_url: https://job-boards.greenhouse.io/afresh/jobs/5986020004/confirmation
runner: greenhouse_iframe_runner.py
verification_code_used: fRuNngCZ

Notes:
- resume_bind_failed=true (Filestack swap, no replacement input — same class as Lyft 716).
- Submit click still fired because GH iframe runner allowVisibleCaptcha=true; security-code interstitial appeared; Gmail-polled 8-char code submitted via JS_SUBMIT_VERIFICATION_CODE; confirmation page reached.
- Validates that the generic 8-char security-code post-submit branch in greenhouse_iframe_runner.py works even when Filestack upload fails server-side IF the tenant doesn't enforce resume server-side at the email-verify stage. Afresh did not block missing resume.
