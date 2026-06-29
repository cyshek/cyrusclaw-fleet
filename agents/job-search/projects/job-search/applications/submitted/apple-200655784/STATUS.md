STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T09:00:01+00:00

role_id: 109
ats: apple (reqid: 200655784)
company: Apple
role: Character Animator- Generative AI Experiences Software

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200655784-0836/character-animator-generative-ai-experiences-software?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (2298 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200655784_200655784_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=109;
then re-run render_xlsx.py.
