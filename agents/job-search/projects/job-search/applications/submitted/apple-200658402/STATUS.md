STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T07:18:24+00:00

role_id: 55
ats: apple (reqid: 200658402)
company: Apple
role: iPhone Product Design Engineering Program Manager (PD EPM)

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200658402-0836/iphone-product-design-engineering-program-manager-pd-epm?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (4346 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200658402_200658402_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=55;
then re-run render_xlsx.py.
