STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T07:54:45+00:00

role_id: 965
ats: apple (reqid: 200661870)
company: Apple
role: Audio New Product Introduction Operations Program Manager (NPI-OPM)

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200661870-0836/audio-new-product-introduction-operations-program-manager-npi-opm?team=OPMFG

=====================================================================

Packet contents:
  - JD.md                 (2993 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200661870_200661870_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=965;
then re-run render_xlsx.py.
