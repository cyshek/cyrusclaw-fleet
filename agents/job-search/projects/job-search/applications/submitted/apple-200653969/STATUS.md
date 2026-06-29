STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T07:05:13+00:00

role_id: 47
ats: apple (reqid: 200653969)
company: Apple
role: Engineering Program Manager, Games, Apple Services Engineering

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200653969-0836/engineering-program-manager-games-apple-services-engineering?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (4960 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200653969_200653969_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=47;
then re-run render_xlsx.py.
