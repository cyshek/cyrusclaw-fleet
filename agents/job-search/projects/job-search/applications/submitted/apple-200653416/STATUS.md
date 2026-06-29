STATUS: PREP-READY-MANUAL-APPLE
Generated: 2026-06-29T08:09:15+00:00

role_id: 295
ats: apple (reqid: 200653416)
company: Apple
role: Data Engineer (Agentic AI, LLM Training), G&A Solutions Engineering (GSE)

=====================================================================
APPLY HERE (MANUAL — Apple-ID SSO + 2FA required):

    https://jobs.apple.com/en-us/details/200653416-0157/data-engineer-agentic-ai-llm-training-g-a-solutions-engineering-gse?team=SFTWR

=====================================================================

Packet contents:
  - JD.md                 (3473 chars of JD body)
  - Cyrus_Shekari_Resume_apple-200653416_200653416_v2.pdf  (tailored resume PDF — upload this)
  - cover_answers.md      (JD context + resume upload notes)
  - meta.json, prefill.json

Apple-ID SSO + 2FA means auto-submit is not possible.
Open the apply URL above, sign in with Apple ID, upload the tailored
PDF, paste answers from cover_answers.md, submit.

Once submitted, stamp tracker.db:
  UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD',
    prep_status='submitted' WHERE id=295;
then re-run render_xlsx.py.
