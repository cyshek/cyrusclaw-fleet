STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T07:28:26+00:00

role_id: 62
ats: apple (reqid: 200648579)
company: Apple
role: Product Design Engineering Program Manager - Apple Vision Pro

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200648579-0836/product-design-engineering-program-manager-apple-vision-pro?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (3427 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200648579_200648579_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=62;
then re-run render_xlsx.py.
