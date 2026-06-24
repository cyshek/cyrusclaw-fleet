submitted — 2026-05-25 02:36 UTC

confirmation_url: https://job-boards.greenhouse.io/gradial/jobs/4245923009/confirmation
confirmation_text: Thank you for applying to Gradial. We've received your application and appreciate your interest in our mission. Our team thoughtfully reviews every submission. If your experience aligns with our current needs, we'll be in touch regarding next steps.
verification_code_used: 5Lu5gIeF (email gate — Greenhouse 8-char security code sent to cyshekari@gmail.com)
submitted_by: auto (job-search subagent, role 1157)
resume_attached: Cyrus_Shekari_Resume_gradial_4245923009_v2.pdf

Notes:
- Greenhouse direct (job-boards.greenhouse.io/gradial), invisible reCAPTCHA — passed.
- AI-essay ("What excites you most about working in AI today?") answered with cover_answer_generator output (tailored to Gradial's marketing/creative-ops mission).
- Seattle 5-day in-office = Yes (Cyrus based in Kirkland, WA — Seattle metro).
- US-auth=Yes, sponsorship=No, state=Washington.
- No demographics dropdowns on this form.
- Two-step submit: first Submit triggered email-code gate; second Submit (with code) → /confirmation.
- LABEL_RULES additions made in source (greenhouse_dryrun.py) for:
  - "in-office work week" / "five-day in-office" → answer_yes
  - "what excites you" → why_company_essay (then overridden via cover_overrides at fill time)
