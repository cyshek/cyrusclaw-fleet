STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T08:55:49+00:00

role_id: 102
ats: apple (reqid: 200660978)
company: Apple
role: Business Systems Analyst, Apple Cloud Network

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200660978-3401/business-systems-analyst-apple-cloud-network?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (5802 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200660978_200660978_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=102;
then re-run render_xlsx.py.
