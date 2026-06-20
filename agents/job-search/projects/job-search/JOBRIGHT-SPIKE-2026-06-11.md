# JobRight.ai Discovery-Source Spike — 2026-06-11

**Type:** Throwaway feasibility spike (NOT a production adapter). Anonymous HTTP/curl reads only, sampled.
**Question:** Can jobright.ai feed our pipeline as a DISCOVERY source, exploiting its recency-sorted listings (fresh roles, incl. fast-fresh Google rows)?

---

## Verdict: GO-IF / PARTIAL

**GO** for *discovery + recency signal* (excellent, free, unauthenticated).
**NO-GO** for *direct submission* unless we recover the real ATS apply URL — which is the make-or-break for our engine and is currently **auth-walled**.

> **One condition that flips it to full GO:** a logged-in JobRight **session cookie** from Cyrus (his free account) wired into the adapter, IF (to verify) the authed `/swan/*` API returns the underlying ATS URL. The public surface alone gives us *what's fresh* but not *where to apply directly*.

---

## Evidence per question

### 1. Public reachability — STRONG
- `/remote-jobs/<category>` pages (e.g. `product-design`, `sales-business-development`) are **Next.js** pages whose `<script id="__NEXT_DATA__">` embeds **`props.pageProps.defaultData` = 30 fully-populated job objects**, server-rendered, **NO auth**.
- `robots.txt` **Allows** `/jobs/*`, `/role/*`, `/remote-jobs/*`; **Disallows** the personalized surfaces (`/jobs/recommend`, `/jobs/liked`, `/jobs/profile`, `/matching`).
- Per-job fields present in public JSON: `jobTitle`, `companyName`, `companyResult.*` (size/funding/linkedin/url), `jobLocation`, `isRemote`, `workModel`, `jobSeniority`, `minYearsOfExperience`, `h1BStatus`, `employmentType`, `jobSummary`, `requirements[]`, `coreResponsibilities[]`, `jobId` (24-hex Mongo ObjectId), `applyLink`, **`publishTime`**, **`publishTimeDesc`**.
- `/role/<title>` (e.g. `/role/prompt-engineer`) = marketing landing page, **not** a feed. Ignore.
- Sitemaps (`sitemap.xml` → `sitemap-remote-jobs.xml` etc.) list only ~13 category landing URLs, **no individual job slugs**. So the category-page `__NEXT_DATA__` is the harvest surface, not the sitemap.

### 2. Recency axis (KEY) — CONFIRMED, this is the value
- **`publishTime`** (e.g. `2026-06-11 20:12:39`, ISO UTC) + **`publishTimeDesc`** (e.g. `"1 minute ago"`) on every row.
- Category pages are **newest-first**: `product-design` top row posted **1 min before my fetch**; `sales-bd` top row **3 min before**. Both lists span only ~1-2 hours of postings across 30 rows.
- So harvesting `/remote-jobs/<category>` on a short cron yields **minutes-fresh roles** — exactly the fast-fresh sourcing Cyrus sees on their site. (Note: this is the GENERIC freshest feed, not his personalized matches — those are behind `/matching` + login.)
- Recency is exposed by **field + default ordering**, not a `?sort=` param. ~13 categories × 30 = ~390 freshest roles per sweep, no auth.

### 3. Apply-URL resolution — **MAKE-OR-BREAK FAILURE (anon)**
- `applyLink` / `url` = **`https://jobright.ai/jobs/info/<id>` WRAPPER**, never a direct ATS link.
- **100% of 60 sampled rows** (2 categories × 30) had `applyLink` host = `jobright.ai`. Zero greenhouse/lever/ashby/workday/etc.
- The wrapper page (`/jobs/info/<id>`) `__NEXT_DATA__` has **NO** `originalUrl`/`externalUrl`/`sourceUrl`/`applyUrl` field; `jobRecruiterProfileUrl` is empty. `canonical` points back to itself.
- JS bundles reference `/jobs/external` (client page, returns 200 = renders, no `Location` redirect) and backend **`/swan/job/jt-apply`** — i.e. the real outbound URL is fetched by the React app from the authed API and/or routed through their autofill, **not present in any anonymous HTML**.
- **Consequence:** our engine (which needs the real ATS URL to submit) **cannot** get a submittable link from the public surface. We'd only have a `jobright.ai/jobs/info/<id>` URL, which requires *their* autofill/Agent to apply.

### 4. Auth wall scope — DOCUMENTED (not defeated)
- All backend job/apply endpoints return **401** anonymously: `/swan/job/detail`, `/swan/job/get`, `/swan/recommend/list/jobs`, `/swan/job/jt-apply` (all `?jobId=<id>`).
- Wrapper SSR shows `"logined": false`. The public 30-per-category feed renders fine logged-out; **the real apply URL + personalized matches + recency-sorted personal feed need login**.
- **Auth mechanism (documented, NOT attempted):** standard web session — login at `/onboarding-v3/signup` (Disallowed paths suggest email/resume onboarding), backend at `*.jobright.ai/swan/*` + `business.jobright.ai`. A logged-in browser session would carry a session cookie/Bearer that authorizes `/swan/*`. **Exact cookie/token name NOT captured** (would require an actual logged-in session, out of scope for this spike). To unlock: Cyrus provides his authenticated session (cookie header) → we replay it against `/swan/job/detail?jobId=<id>` and verify whether it returns the underlying ATS URL. **Unverified assumption:** that the authed API exposes the raw ATS URL at all (JobRight's business model is to keep apply inside their Agent, so they may deliberately withhold it even when authed — this must be tested before any build).

### 5. Data quality / overlap — GOOD fit, meaningful additive
- Sampled rows are **real direct-employer roles** (Drake Software, Translated, Telix Pharmaceuticals, GuidePoint Security, Twin Health, Epiq, Altera Digital Health), each with rich company metadata (Crunchbase, LinkedIn, funding) — not obvious aggregator dupes.
- Titles in the PM/Project/Product-Design/Product-Marketing space = **squarely our target profile**; US/remote relevant.
- Overlap vs our ~381-company crawl: qualitative read — JobRight aggregates **8M listings / ~400k/day across ALL ATSes incl. many companies we DON'T crawl**, so it's **substantially additive** for breadth + freshness. But because it normalizes everything to its own wrapper, we lose the native ATS URL we depend on (see Q3).

### 6. Rate-limiting / blocking — CLEAN (for now)
- Azure datacenter IP got **HTTP 200 on every public page** (category pages 600KB+, wrapper, robots, sitemaps). **No** Cloudflare/DataDome/`cf-chl`/`captcha-delivery`/"Just a moment" markers.
- Public read surface is currently friendly to our egress (unlike Levels/LinkedIn). A high-volume sweep could still trip rate limits later → use polite intervals + the residential-egress fallback if it ever 403/429s.

---

## Effort estimate for a real adapter

| Scope | Size | Notes |
|---|---|---|
| **Discovery-only** (harvest public `/remote-jobs/<cat>` `__NEXT_DATA__` → rows with publishTime, company, title, location) | **S** | Parse one JSON blob per category; ~13 categories. Plugs in as `adapters/jobright.py` → `tracker_merger`. |
| **+ Real ATS URL recovery (authed)** | **M-L** | Requires Cyrus session cookie + verifying `/swan/*` returns the raw URL; if it does, map jobId→ATS URL via authed API. If JobRight withholds the raw URL even when authed → this path is **dead** and discovery rows would be unsubmittable wrappers. |

**Where it plugs in:** new `projects/job-search/role-discovery/adapters/jobright.py` (category-page `__NEXT_DATA__` parser) → feeds `tracker_merger` like any other adapter. The recovered ATS URL would populate `app_url` so our existing ATS runners can submit. Without it, rows would be `manual-apply` wrappers (low value — similar to the LinkedIn-stranded problem).

---

## Recommendation to Cyrus (2-3 sentences)

JobRight's public category pages are a clean, unauthenticated, **minutes-fresh** firehose (~390 freshest roles/sweep, rich metadata, our target PM/Project/Design titles, no IP block) — great as a *discovery + recency* signal and a **small** adapter to build. **But every public listing is a `jobright.ai/jobs/info/<id>` wrapper with the real ATS apply URL hidden behind their authenticated `/swan/*` API**, so as-is the rows aren't directly submittable by our engine. **Recommendation: GO on a small discovery-only adapter for the fresh-roles signal; before investing in submission, hand me your logged-in JobRight session cookie so I can verify whether the authed API actually returns the underlying ATS URL — if it does, we unlock direct submission (M effort); if JobRight deliberately withholds it (likely, given their Agent business model), we keep it as a freshness-radar only.**

---
*Spike artifacts (throwaway, not committed): `role-discovery/_jobright_spike_*` scripts + `_jobright_spike_tmp/`. Delete when done.*
