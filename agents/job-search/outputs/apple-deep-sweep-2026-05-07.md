# Apple deep careers sweep — 2026-05-07

## Result
- **JDs scanned:** 1,325 unique postings across 10 software sub-teams (US, en-us)
- **Title-filtered out (senior/staff/principal/lead/manager/architect/etc. or out-of-scope title):** 665
- **JDs deeply read for `minimumQualifications` experience text:** 660
- **Dropped on min-experience ≥ 4 yrs:** 189
- **Dropped as duplicates of pre-existing tracker rows:** 4
- **Appended to tracker.md:** **467**

## Per-category counts added
| Category | Count |
|---|---|
| SWE | 154 |
| infra/platform/SRE/backend | 165 |
| ML / AI | 146 |
| new-grad / early career | 2 |
| **Total** | **467** |

## Per-experience-tag counts added
| Tag | Count |
|---|---|
| exp:unstated | 245 |
| exp:0+yrs | 5 |
| exp:1+yrs | 27 |
| exp:2+yrs | 59 |
| exp:3+yrs | 131 |

(Roles with min ≥ 4 yrs dropped per filter rule.)

## Source / method
1. The `https://jobs.apple.com/en-us/search` page is a JS SPA — server HTML returns no role data.
2. Reverse-engineered the unofficial JSON API used by the SPA:
   - `GET https://jobs.apple.com/api/v1/csrfToken` → returns header `x-apple-csrf-token` and sets `jssid` cookie.
   - `POST https://jobs.apple.com/api/v1/search` with `X-Apple-CSRF-Token` and the cookie. Filter payload schema (decoded from the JS bundle):
     ```json
     {
       "query": "",
       "filters": {
         "locations": ["postLocation-USA"],
         "teams": [{"team":"teamsAndSubTeams-SFTWR","subTeam":"subTeam-AF"}]
       },
       "page": 1,
       "locale": "en-us",
       "sort": "newest",
       "format": {"longDate":"MMMM D, YYYY","mediumDate":"MMM D, YYYY"}
     }
     ```
   - Per-role JD: `GET https://jobs.apple.com/api/v1/jobDetails/{positionId}-{slug}` → returns `jobSummary`, `description`, `minimumQualifications`, `preferredQualifications`, etc.
3. Sub-teams swept under team `SFTWR`:
   `AF` (Apps & Frameworks), `CLD` (Cloud & Infra), `COS` (Core OS), `DSR` (DevOps & SRE), `EPM` (Eng Project Mgmt), `ISTECH` (IS&T), `MCHLN` (ML & AI), `SEC` (Security & Privacy), `SQAT` (Software QA, Automation & Tools), `WSFT` (Wireless Software).
4. 660 detail JSONs fetched in parallel (10 workers), then `minimumQualifications` regex-scanned for `\d+\s*\+?\s*(years|yrs)` → minimum stated yrs.

## Filter rule applied
- `minimumQualifications` mentions any year requirement: take the **minimum** number found.
  - `min ≤ 3` → KEEP, tagged `exp:N+yrs` (where N = min year value, including 0/1/2/3).
  - `min ≥ 4` → DROP as `skip-too-senior`.
- No year mentioned in `minimumQualifications` → KEEP, tagged `exp:unstated`.
- Title-level senior signals (`senior|sr|staff|principal|lead|manager|director|architect|head of|chief|distinguished`) → DROP up front (665 dropped here).
- Out-of-scope titles (retail, sales, hardware-only, design, etc.) → DROP up front.
- Non-US-locations-only postings → DROP. (US-multi-location and Cupertino-only are KEPT.)

## Blockers / notes
- **Browser tool intentionally not used.** Per task brief and prior failure note (snap-Chromium SingletonLock perm error on this host) the entire sweep was done via curl/Node.js against the unofficial JSON API. No browser launched.
- **CSRF token + cookie required** for the search/jobDetails endpoints (otherwise 401). One token was reused for the entire 660-JD detail fetch with no rate-limiting issues.
- **No pages blocked** during the sweep.
- Sub-team API totals (records returned by API): AF≈?, CLD=?, COS=233, DSR=104, EPM=166, ISTECH=204, MCHLN=339, SEC=82, SQAT=244, WSFT=112. (AF & CLD logs scrolled off but their pages were fetched and counted in the 1,325-unique total.)
- 4 existing Apple tracker rows (200662000, 200661989, 200662004, 200661716) were detected and skipped.
- The "scan-blocked" Apple row at line 63 of `tracker.md` is left untouched per instructions, although it is now stale (this sweep proves the JSON API works without a browser).

## Wall-clock
- Discovery + filter + tracker edit: ~25 min (mostly spent grepping the JS bundle to reverse-engineer the search payload schema; once that was pinned, the actual fetch was <2 min).
