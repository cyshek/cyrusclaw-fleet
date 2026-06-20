# Big-Tech Browser Sweep — 2026-05-06

Subagent: bigtech-sweep
Wall-clock: ~30 min (full budget used)

## Scope note
The tracker.md filter rule on file is PM/TPM/Solutions Engineer scope.
This task explicitly broadened scope to **SWE / ML / AI / infra / new-grad / early-career**.
Existing PM-scoped `scan-blocked` rows for these 4 companies were left in place
(annotated with "PM scope; SWE rows added 2026-05-06"); new SWE rows were
appended underneath each.

## Per-company results

### Microsoft — 17 added
- Source: `apply.careers.microsoft.com/careers?query=software+engineer&filter_seniority=Entry`
- Browsed full Entry-level + "software engineer" result set (~44 jobs across global; 21 US-targeted JDs fetched)
- Kept all roles where min stated experience ≤ 3 yrs OR unstated.
- Dropped:
  - "Software Engineer - Backend" (4+/6+/8+ yrs) — too senior
  - "Member of Technical Staff - Data Infra - MAI Superintelligence" (6+ yrs) — too senior
  - "Member of Technical Staff - Pre Training - MAI Superintelligence" (4+ yrs) — too senior
  - "Member of Technical Staff - Data Infra - MAI Superintelligence" (alt, 6+ yrs) — too senior
  - All non-US (Norway, Poland, Denmark, Canada, Czech Republic, Netherlands, India, Australia, UK)
  - Non-SWE roles (Data Center Tech, Critical Environment Tech, Cloud Solution Architect, Data Center PM)

### Google — 10 added
- Source: `google.com/about/careers/applications/jobs/results/?target_level=EARLY&q=software&employment_type=FULL_TIME&location=United%20States`
- ~95 EARLY-level US results; vast majority were Data Center Technician / Facilities Tech (hardware-only) — dropped per scope.
- Kept SWE/ML/security/infra TPM-I roles with min ≤ 3 yrs.
- Dropped:
  - Hardware-only / Data Center Technician roles (~70 rows) — out of scope
  - "Strategic Cloud Engineer, Google Public Sector" (8+/5+ yrs) — too senior
  - "Technical Product Support Manager, Gemini App" (8+/5+ yrs) — too senior
  - GTM/Sales-adjacent roles (Analytical Lead Associate, Product Solutions Manager, gTech Ads, Product GTM StratOps)
  - Hardware Test/Validation Engineer roles (university-grad but hardware scope)
  - "TEST POSTING" placeholder

### Meta — 5 added
- Source: `metacareers.com/jobsearch?teams[0]=Software%20Engineering` (62 items but UI only renders ~10 visible cards; deeper scroll didn't trigger more loads — known SPA virtualization issue)
- Kept SWE/ML/AI roles with min ≤ 3 yrs.
- Dropped:
  - "Software Engineer, Infrastructure" 8+/4+ — too senior (id 2486789151677735)
  - "Software Engineer (Technical Leadership)" — too senior
  - "Software Engineer, Machine Learning" 8+/4+ (id 998357492128826) — too senior
  - "Software Engineer, Product" 8+/4+ — too senior
  - "Partner Engineer, Generative AI" — Bangalore-primary, GTM-adjacent
- **Partial blocker:** Meta's job list virtualizes — only first batch (~10 jobs of 62) was scrapeable without auth. New College Grad sub-team filter returned 0 items in current session (likely cycle-closed).

### Apple — 4 added
- Source: `jobs.apple.com/en-us/search?team=...software-categories...&location=united-states-USA`
- Apple JDs do NOT use the "X+ years" pattern in their HTML — Minimum Qualifications are skill-based, not year-based, so most US SWE roles default to `exp:unstated`.
- Reviewed first page (40 cards). Kept individual-contributor SWE roles only.
- Dropped:
  - All "Sr/Senior/Staff/Principal/Manager/Lead" titles (10+ rows)
  - "Data Scientist" (200661978-3543) — Min Quals state 5+ yrs in quality eng — too senior
  - "Systems Engineer, Retail Experiences" — 5+ yrs macOS — too senior
  - "Full Stack Software Engineer, Productivity Apps" (both location variants) — 5+ yrs — too senior
  - "Product System Test Engineer, Wireless Technologies" — hardware-adjacent test
  - "Engineering Program Specialist, SWE Programs" — program coordinator scope
- **Apple search UI paginates server-side; only first page scraped within budget.**

## Totals

| Company | Added | Dropped (sampled) | Notes |
|---------|------:|------------------:|-------|
| Microsoft | 17 | 4+ too senior, ~20 non-US/scope | Eightfold platform; full Entry-level set covered |
| Google    | 10 | ~70 hardware/DC tech, 5+ too senior, ~5 GTM | Heavy data-center-tech noise in EARLY results |
| Meta      | 5  | 5 too senior (4+ yrs path) | UI virtualization limits visibility past first batch |
| Apple     | 4  | 10+ senior/manager titles, hardware/test | Min quals are skill-based, mostly `exp:unstated` |
| **Total** | **36** | | |

## Blockers / partial coverage
- **Meta:** SPA only renders ~10 visible cards; deeper pagination/scroll didn't trigger fetches. Needs a different approach (auth, intercepted XHR, or manual filter combos) to enumerate all 62 SE roles.
- **Apple:** Only first page (40 cards) of the multi-team search scraped. Second/third pages not enumerated within budget.
- **Microsoft:** Eightfold `/api/apply/v2/jobs` returns 403 PCSX-auth error; in-browser DOM scrape worked, but is ordering-sensitive (date-sorted, max ~100 jobs even with broad filter).

## Time spent
~30 minutes wall-clock, full budget consumed. Most time spent on Microsoft DOM enumeration + Google EARLY-results pagination (which is heavily polluted with non-SWE data-center roles).
