STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T08:40:46+00:00

role_id: 95
ats: apple (reqid: 200633092)
company: Apple
role: App Store Frameworks

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200633092-0836/app-store-frameworks?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (1659 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200633092_200633092_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=95;
then re-run render_xlsx.py.
