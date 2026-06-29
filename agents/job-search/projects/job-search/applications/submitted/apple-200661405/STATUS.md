STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T04:46:30+00:00

role_id: 33
ats: apple (reqid: 200661405)
company: Apple
role: ASO Readiness Program Manager

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200661405-0836/aso-readiness-program-manager?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (4536 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200661405_200661405_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=33;
then re-run render_xlsx.py.
