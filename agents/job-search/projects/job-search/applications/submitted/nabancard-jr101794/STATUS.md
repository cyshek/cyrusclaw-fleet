# STATUS: BLOCKED — tenant-unsupported (account-already-exists, no sign-in fallback)

Role: Point & Pay (NAB) Solutions Engineer JR101794
URL: https://nabancard.wd1.myworkdayjobs.com/nab/job/US---Remote/Solutions-Engineer_JR101794
Tenant: nab (Workday)
Role ID: 1121
Attempted: 2026-05-25 (LEAN MODE subagent)

## What happened
- Run 1: Driver created account → got through My Information, My Experience, Application Questions → blocked on 2 unmapped questions: "Are you legally eligible for employment in the US?" (dropdown) and "What is the highest level of education you have achieved?" (text).
- Added handlers for both questions to `workday_playwright.py` (legally-eligible→yes, highest-education→Bachelor's Degree, plus how-did-you-hear→LinkedIn). Verified inline.
- Run 2: Driver re-tried account creation (account_created=true was set but creds-loader needs sign-in path). Account-already-exists → form did not advance → blocker `account form did not advance after submit`.

## Blocker
NAB Workday tenant needs **sign-in-first** entry handler (same gap as Nvidia/HPE per TOOLS.md). Driver currently always clicks "Apply Manually" → "Create Account"; when the shared email is already registered with the tenant, account creation silently fails and there's no fallback to the "Sign In" button on the apply page.

## Fix path (for future)
- Option A: Per-tenant email aliasing (cyshekari+nab@gmail.com) — also needs `.workday-creds.json` to store per-tenant alias + password, and a fresh account-create attempt.
- Option B: Detect "account already exists" error → click Sign In → fill stored creds → continue. Requires storing tenant password in creds file (currently not stored for nab; account_created=true is the only marker).

## Driver improvements landed this run (still useful for future tenants)
- `pick_option`: added "legally eligible for employment", "eligible for employment" keys → yes.
- text-question handler: added "highest level of education" → "Bachelor's Degree", "how did you hear" → "LinkedIn".

## Tracker state
- prep_status: NULL (left as-is so a future re-attempt isn't suppressed)
- applied_by/applied_on: unchanged
- agent_notes: see _burndown-v2-log.md entry 2026-05-25 nabancard

