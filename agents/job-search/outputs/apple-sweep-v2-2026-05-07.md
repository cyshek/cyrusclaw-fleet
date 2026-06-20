# Apple Sweep v2 — 2026-05-07

## Summary
- **Approach**: Listing crawl via `https://jobs.apple.com/en-us/search?team=...&page=N` across 11 SFTWR sub-team families (apps-frameworks, cloud/infra, core-os, devops/SRE, EPM, IS&T, ML infra, ML/AI, security/privacy, SQAT, wireless software). 30 pages each.
- **JD detail fetch**: `https://jobs.apple.com/api/v1/jobDetails/{jobNumber}` (unauth JSON, works fine).
- **Pre-existing Apple rows in tracker.md**: 471 unique job numbers (from earlier `apple-deep-sweep 2026-05-07` and `bigtech-sweep 2026-05-06`).
- **Listing crawl found**: 499 unique Apple SFTWR job numbers in US.
- **Net new vs tracker**: 297 candidate IDs.
- **After filename/title pre-filter** (drop senior/staff/principal/lead/director/manager/program-manager/project-manager/HR/sales/hardware-only and bare "software-engineer"): 94 JDs to fetch.
- **JDs actually opened (JSON)**: 94.
- **Kept after content + Cyrus-pref filter**: 22 → trimmed 7 non-engineering (App-Review specialists, logistics tech, critical-facilities supervisors, product-design producer, human interface designer) → **15 appended to tracker.md**.

## Per-team count of added rows
- ML / AI: 7
- infra / platform / SRE / security: 7
- SE (Solutions Engineering — GSE): 1
- new-grad: 0 (none surfaced beyond what was already in tracker)

## Total dropped (with reasons summary)
72 dropped during JD content pass:
- "SWE-only per Cyrus pref" (titles like plain "Software Engineer", "iOS Engineer", "Frameworks Engineer", "App Developer" with no ML/SE/infra/new-grad signal) — bulk of drops
- "exp:N+yrs" with N≥4 — significant chunk (5+, 7+, even 20+ for security architect)
- "senior/non-IC title" (Manager, Lead, Architect with manager flavor)

## Blockers
- None on this pass. The earlier subagent runtime "stale completion event" did not recur. Browser tool was NOT needed — `curl` against the unauth `api/v1/jobDetails/{id}` endpoint was sufficient.

## Notes for follow-up
- The previous deep-sweep had already been very thorough (471 rows). This v2 ran against the same SFTWR family + slightly different filter (Cyrus's new "skip plain SWE" rule), so the net new is genuinely incremental, not a re-discovery of the same JDs.
- Worth a separate sub-sweep if the user wants: AppleCare (CARE), University recruiting (jobs.apple.com/en-us/students), and APPST (App Store) — those team families are NOT covered here.

## Elapsed
~7 minutes wall clock.
