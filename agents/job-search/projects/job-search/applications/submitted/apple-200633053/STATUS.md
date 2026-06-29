STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T08:32:01+00:00

role_id: 93
ats: apple (reqid: 200633053)
company: Apple
role: AirPlay Audio Networking Engineer, Audio & Media Technologies

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200633053-3543/airplay-audio-networking-engineer-audio-media-technologies?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (2930 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200633053_200633053_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=93;
then re-run render_xlsx.py.
