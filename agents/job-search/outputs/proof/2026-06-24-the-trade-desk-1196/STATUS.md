submitted — 2026-05-26 06:48 UTC

role_id: 1229
ats: greenhouse (job-boards iframe, thetradedesk tenant)
confirmation_url: https://job-boards.greenhouse.io/thetradedesk/jobs/5139192007/confirmation
confirmation_title: Thank you for applying
confirmation_excerpt: "Thank you for your interest in our position. We confirm that we have received your application!"
verification_code_used: W1lMy3od (8-char Greenhouse security code, fetched via fetch_company_code.py from cyshekari@gmail.com)
submitted_by: auto (job-search subagent, chain worker #003)
resume_attached: Cyrus_Shekari_Resume_thetradedesk_5139192007_v2.pdf

Per-attempt notes:
- Form fields filled via native value setter; react-selects opened via mousedown/mouseup/click on .select__control.
- Phone country dropdown (`#country`) NOT in dryrun spec; filled with "United States +1" via the same react-select pattern.
- Manual override on "have you been employed with TTD" → "N/A" (dryrun spec correct, but planner stored it as wrong-typed string).
- Conditional fields `question_12044548007` (TTD work email) and `question_12044549007` (manager) had garbage pre-fill values from the planner; CLEARED to empty since previous-employee=N/A.
- "How did you hear" planner wanted "LinkedIn" but options are 7 high-level categories; picked "Social Media".
- All 5 demographic dropdowns (bare-numeric ids 4008515007 etc.) set to "I don't wish to answer".
- GDPR consent checkbox ticked.
- 8-char security code prompt appeared post-submit click; fetched code from Gmail (`Greenhouse <no-reply@us.greenhouse-mail.io>`); filled 8 single-char `security-input-N` slots via native value setter + input/change/keydown/keyup events; second submit click landed on /confirmation.
- AI-use questions: none on this form.
- reCAPTCHA Enterprise sitekey 6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0 was loaded (invisible size, visible width=256px iframe) but did NOT gate submit — TheTradeDesk substitutes their own 8-char security code flow.

Cross-cutting observation: TheTradeDesk reCAPTCHA Enterprise script loaded without CSP block. **TheTradeDesk is NOT in the CSP-CAPTCHA-BLOCK-BLOCKLIST class** (unlike Similarweb/Ascend). The 8-char code is the gate, and `fetch_company_code.py` handles it cleanly.
