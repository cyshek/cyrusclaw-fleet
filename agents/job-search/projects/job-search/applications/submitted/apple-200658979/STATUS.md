STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T07:45:58+00:00

role_id: 76
ats: apple (reqid: 200658979)
company: Apple
role: SoC Debug and Automation Engineering Program Manager

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200658979-0836/soc-debug-and-automation-engineering-program-manager?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (3088 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200658979_200658979_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=76;
then re-run render_xlsx.py.
