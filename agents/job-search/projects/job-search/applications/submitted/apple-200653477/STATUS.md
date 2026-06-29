STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T08:46:04+00:00

role_id: 98
ats: apple (reqid: 200653477)
company: Apple
role: AR/VR Applications Engineer - Photos, Vision Products Software

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200653477-3401/ar-vr-applications-engineer-photos-vision-products-software?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (3271 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200653477_200653477_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=98;
then re-run render_xlsx.py.
