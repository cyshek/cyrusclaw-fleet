submitted — 2026-05-25 15:14 UTC

confirmation_url: https://job-boards.greenhouse.io/heygen/jobs/5113581007/confirmation
confirmation_text: Thank you for applying. Your application has been received. If there is a fit, someone will be getting back to you.
verification_code_used: LuZ7K9YV (HeyGen 8-char email verification gate; fetched via gmail_imap)
submitted_by: auto (job-search subagent, role 1378)
resume_attached: Cyrus_Shekari_Resume_heygen_5113581007_v2.pdf

Notes:
- Greenhouse iframe (job-boards.greenhouse.io) — invisible reCAPTCHA v3, no captcha challenge surfaced.
- HeyGen ALSO ships an 8-char email verification gate (similar to Anthropic). Code arrived in cyshekari@gmail.com inbox; submitted via 8 `security-input-N` single-char inputs; second Submit click landed `/confirmation`.
- Demographics: form had no demographic dropdowns or GDPR checkbox — clean minimal Greenhouse form.
- Two custom essays (LLM-shipped-thing + largest enterprise deployment) were tailored by cover_answer_generator after I added `point us` / `point me` / `show us` / `show me` hints to OPEN_QUESTION_HINTS and routed the labels through `why_company_essay` placeholder in greenhouse_dryrun.LABEL_RULES.
- Country dropdown id collides with the phone iti country-code selector (United States = +1). Pre-filled correctly via the typeahead path.

Pipeline changes shipped this run (will benefit future roles):
- `greenhouse_dryrun.py` LABEL_RULES: added 2 entries (HeyGen Q1 + Q2 prompts) routing to `why_company_essay`.
- `cover_answer_generator.py` OPEN_QUESTION_HINTS: added `point us|point me|show us|show me` so directive-style essay prompts (no '?') get tailored answers instead of fallback to generic template.
