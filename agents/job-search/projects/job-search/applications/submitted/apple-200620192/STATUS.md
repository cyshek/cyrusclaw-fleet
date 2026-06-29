STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T08:51:17+00:00

role_id: 100
ats: apple (reqid: 200620192)
company: Apple
role: Bluetooth Software Performance Engineer, Wireless Technologies & Ecosystems

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200620192-3543/bluetooth-software-performance-engineer-wireless-technologies-ecosystems?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (2280 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200620192_200620192_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=100;
then re-run render_xlsx.py.
