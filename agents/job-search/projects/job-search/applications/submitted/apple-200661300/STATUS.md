STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T04:57:19+00:00

role_id: 46
ats: apple (reqid: 200661300)
company: Apple
role: Engineering Program Manager, Customer Systems Platform Services

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200661300-0836/engineering-program-manager-customer-systems-platform-services?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (4224 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200661300_200661300_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=46;
then re-run render_xlsx.py.
