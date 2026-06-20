# STATUS: SUBMITTED ✅

- **When:** 2026-05-26 ~16:28 UTC (chain-004)
- **Method:** AUTO via `role-discovery/workday_playwright.py` (Workday anonymous create-account flow with email-link activation)
- **Tenant:** curtisswright (curtisswright.wd1.myworkdayjobs.com / CW_External_Career_Site)
- **Role:** Sales Engineer, JR11374-1, US-CA-Brea (Nuclear)
- **Confirmation:** userHome cross-check — "my applications" found; review page returned "You already applied to this job"
- **Account:** cyshekari@gmail.com (creds nested in .workday-creds.json under curtisswright)

## Source changes shipped this chain
1. `pick_option()` added "ever been employed by" → No, "I certify" → Yes
2. Text question handler added signature pattern "name and current date" / "state your name" / "sign and date" → "Cyrus Shekari, MM/DD/YYYY"
3. Salary handler — when prompt requires NUMBER (e.g. "do NOT put Negotiable or leave blank"), fills 150000 instead of "Open to discuss"

All in `role-discovery/workday_playwright.py`. Should generalize across Workday tenants.

## Significance
**First non-Adobe Workday tenant submitted end-to-end.** Account creation + email verification + 8-step Workday flow all worked.
