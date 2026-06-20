# Vercel — Forward Deployed Engineer, v0 (5872425004)

## Status: ✅ SUBMITTED & VERIFIED

**Submitted at:** 2026-05-13 ~01:33 UTC
**Confirmation URL:** https://job-boards.greenhouse.io/vercel/jobs/5872425004/confirmation
**Confirmation text:** "Thank you for applying. Your application has been received. If there is a fit, someone will be getting back to you."
**Verification code used:** `M1Mtin1p` (8 chars, mixed case — case sensitive!)
**Resume:** Cyrus_Shekari_Resume_vercel_5872425004_v2.pdf

## Field values used
- first_name: Cyrus
- last_name: Shekari
- email: cyshekari@gmail.com
- phone: (346) 804-0227, Country dropdown = "United States +1"
- LinkedIn: https://linkedin.com/in/cyshekari
- GitHub: https://github.com/cyshek
- based-in-countries: United States
- visa sponsorship needed: No
- work authorization: I am authorized to work in the country due to my nationality
- restricted states: No
- acknowledge/confirm: Acknowledge/Confirm
- accuracy: I have reviewed and confirmed that all the information provided is accurate and complete.
- how heard: LinkedIn

## Lesson learned (codified)
Greenhouse 8-char verification codes are CASE SENSITIVE and can include lowercase letters.
The original `gmail_imap._extract_code` returned the literal case from the email,
but my wrapper `fetch_company_code.py` was uppercasing the result — that produced
"Incorrect security code" on first attempt with `M1MTIN1P`. Fixed by removing
`.upper()` calls. Real code was `M1Mtin1p`.
