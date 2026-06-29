STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T08:02:46+00:00

role_id: 2524
ats: apple (reqid: 200665706)
company: Apple
role: NPI Capacity Program Manager - iPhone

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200665706-0836/npi-capacity-program-manager-iphone?team=OPMFG

=====================================================================

Packet contents:
  - JD.md                 (2924 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200665706_200665706_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=2524;
then re-run render_xlsx.py.
