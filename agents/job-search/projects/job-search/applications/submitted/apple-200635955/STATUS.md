STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T07:13:59+00:00

role_id: 54
ats: apple (reqid: 200635955)
company: Apple
role: iPhone Hardware Engineering Program Manager (HW EPM)

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200635955-0836/iphone-hardware-engineering-program-manager-hw-epm?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (2312 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200635955_200635955_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=54;
then re-run render_xlsx.py.
