# Apple Sweep v3 — 2026-05-07

## Summary

Coverage target: Apple orgs **outside SFTWR** (App Store ops, AppleCare, Operations, Marketing, Corporate, and Student/new-grad programs).

## Approach

- Tried the documented `team=APPST/CARE/OPMFG/MKTSL/CRPSV/STDNT` URL filters on `https://jobs.apple.com/en-us/search`.
  **Finding: server-side `team=` URL filter is broken** — every team query returned the same recent-US-jobs pool (608 unique listings, identical first-page results across all 6 teams). Probably a careers-site SPA where the filter only kicks in client-side via JS.
- Worked around by crawling the unfiltered listing pages (the v2 unauth `/api/role/search` POST endpoint now redirects to a 404 page, also broken), then using the `https://jobs.apple.com/api/v1/jobDetails/{id}?lang=en-us` endpoint (still works) to pull `teamNames` and full JD content for true per-team classification.
- Pre-filter on slug: dropped Senior/Sr/Staff/Principal/Lead/Director/Manager (non-PM)/Distinguished/VP, dropped explicit eng-IC slugs (SWE, ML, SDE, SRE, Data Engineer, etc.), dropped retail/finance/legal/recruiter/designer noise, kept anything PM/PgM/TPM/EPM/Solutions, and force-kept Students.
- JD-content filter: same drop rules on full title + YOE check (drop ≥4 yrs, keep ≤3 or unstated).
- Deduped by base reqId across post-locations.
- Cross-checked against existing 471 Apple rows in tracker.md by jobNumber and URL — none of the 30 were already present.

## Counts

- Pre-existing Apple rows in tracker.md: **471 unique reqIds**
- Listings crawled: **608 unique reqIds** (across "team=APPST/CARE/OPMFG/MKTSL/CRPSV/STDNT" — all yielding the same global pool, plus the explicit STDNT-INTRN/CPRG/ECT URLs)
- Net new vs tracker: **530 candidates**
- Pre-filter drops: senior=117, eng-IC slug=126, other-noise=28, no-keep-signal=204
- **JDs actually opened: 55** (after pre-filter)
- JD-content drops: yoe≥4=9, fetch_failed=0
- After dedup-by-reqId: **30 net-new rows appended to tracker.md**

## Per-team count of added rows (by JD `teamNames`)

- **Hardware (HRDWR)**: 6 — engineering program managers (NPI/CapEx, visionOS, Hardware Test, CPU Pre-Silicon, Packaging, Product Design)
- **Software and Services (SFTWR)**: 7 — these are PM/EPM titles v2 missed (v2 only added engineering-IC titles in S&S)
- **Corporate Functions (CRPSV)**: 4 — ASO Readiness PgM, AIML TPM, Analytics & Review PgM, Privilege PgM
- **Operations and Supply Chain (OPMFG)**: 1 — Technical Program Manager - iPad
- **Hardware + Operations (combined)**: 1 — Business Operations EPM - PACE
- **Machine Learning and AI (MLAI)**: 1 — EPM, Search Quality and Infrastructure
- **Students / new-grad (STDNT)**: 10 — all internship umbrella postings (Legal, HW Eng, HW Tech, Ops/Mfg Design, EPM, ML/AI, SWE, Business/Marketing, Product Design, MBA)

Note: nothing tagged **APPST**, **CARE**, or **MKTSL** by `teamNames`. The `teamNames` taxonomy from the JD JSON doesn't include those literal codes — Apple buckets them under broader categories ("Software and Services" wraps App Store; "Corporate Functions" wraps Marketing-adjacent PgMs).

## Total dropped (with reasons)

- **Senior/Staff/Principal/Director/Lead title in slug**: 117
- **Explicit engineering-IC title in slug** (SWE, ML, SDE, SRE, Data Eng, FPGA, hardware design, biomedical-eng): 126
- **Retail/finance/legal/recruiter/designer/operator noise**: 28
- **No PM/SE/Student keep-signal in slug**: 204 (skipped without fetching JD)
- **YOE ≥ 4 yrs in JD body**: 9
- Total considered: 530 net-new IDs → 30 kept (5.7%)

## Blockers / notes for follow-up

- **`team=` URL filter on jobs.apple.com is broken**. If Cyrus wants strict per-org enumeration, would need either a real browser (the SPA renders the filter client-side) or to find the new internal API replacement for `/api/role/search` (the v2 POST endpoint now 301-redirects to `apple.com/pagenotfound`). Right now we're working off the global recent-US pool.
- The "no SFTWR" scope was muddied by the broken filter — I included 7 S&S-tagged PM rows because they were genuinely net-new and matched Cyrus's role-type prefs (v2 only added engineering-IC titles in S&S, never PMs). Easy to filter out by note tag if undesired.
- All 10 student-program rows are umbrella internship postings (one URL per discipline) rather than individual reqs. Cyrus may want to drop the SWE/HW/Design ones as not matching the new IC-engineering exclusion, but I kept them per the "STDNT = always keep" rule. The MBA one is a good fit.
- No CARE / AppleCare-Engineering rows surfaced. Either the team has nothing currently posted in US, or they're posted under different `teamNames` than the JD JSON exposes. Worth probing the careers SPA with a real browser if Cyrus cares.

## Elapsed

~12 minutes wall clock.
