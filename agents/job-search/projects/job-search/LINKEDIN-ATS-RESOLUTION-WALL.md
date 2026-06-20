# LinkedIn → ATS Resolution: Anonymous Wall

**Date:** 2026-05-23
**Status:** BLOCKED on anonymous-only constraint. Classification-only fallback shipped.
**Author:** subagent

## TL;DR

The P1 task "use a headless browser to resolve the off-site ATS URL for LinkedIn-discovered jobs" was **infeasible as scoped**. LinkedIn anonymously never exposes the off-site URL — neither via the rendered DOM, nor via embedded JSON, nor via any unauthenticated API endpoint. The original BACKLOG estimate ("~1s/job → ~15min for 900 jobs. Worth it.") was based on an untested assumption that a browser would see what `requests` couldn't. It doesn't.

What was shipped instead: a **classifier** that uses the offsite/onsite signal in LinkedIn's HTML to triage each row into one of three buckets:
- `linkedin-easy-apply` → set `status='skip'`. These are LinkedIn-internal applications with no external URL; fundamentally unresolvable without LinkedIn auth.
- `linkedin-offsite-unresolved` → flag updated, status untouched. External ATS exists but URL is hidden. Recoverable if/when LinkedIn auth path is built.
- `unknown` → no offsite/onsite signal in HTML. Likely expired posting or stale ID.

## What was probed (and failed)

1. **`/jobs/view/<id>` page in headless Chromium** — apply button is wrapped in `contextual-sign-in-modal`; click triggers sign-in modal, no popup, no redirect, no URL leak. Page HTML contains `apply-link-offsite` / `apply-link-onsite` strings but NO external URL.
2. **`/jobs-guest/jobs/api/jobPosting/<id>`** — same: offsite/onsite signal but no URL.
3. **All `<script>` tags** — 4 total, none contain `applyUrl` / `applyMethod` / similar.
4. **JSON-LD / OpenGraph metadata** — no apply URL.
5. **Speculative endpoints** (`/apply`, `/applyExternal`, `/applyOffsite`, `/applyRedirect`) — all 404.
6. **Clicking through modal** — modal has no "continue as guest" path; dismiss button is the only escape.

LinkedIn's anti-bot beacon (`li.protechts.net/index.html?...&uc=scraping`) fires on the anonymous page load, confirming they're aware of and actively fingerprinting this surface.

## What was shipped

`projects/job-search/role-discovery/linkedin_ats_resolver.py` — standalone classifier:
- Iterates `roles` where `source_key LIKE 'linkedin:%' AND status NOT IN ('closed','skip','rejected') AND flags LIKE '%manual-apply%'`.
- Fetches `/jobs-guest/jobs/api/jobPosting/<id>` via headless Chromium.
- Classifies as offsite / onsite / unknown.
- Updates tracker.db row accordingly (see TL;DR for the three buckets).
- Rate-limited 1.6s/req, 429 backoff, commits every 25 rows.
- Run: `.venv/bin/python linkedin_ats_resolver.py [--limit N] [--dry-run] [--verbose]`
- ~13s for first 6 fetches × ~1.6s per request = ~9 min for the full 345-row backlog.

## 50-row probe results (2026-05-23 02:45 UTC)

```
scanned: 50
resolved: 0           (0% — the wall)
offsite_unresolved: 17 (34% — external ATS exists, URL hidden)
easy_apply: 18         (36% — LinkedIn-internal only)
unknown: 15            (30% — likely expired postings)
fetch_failed: 0
```

## Paths forward (ranked)

### 1. Status quo + classifier (DONE)
Easy-Apply rows are now `skip` (clean triage). Offsite-unresolved rows are flagged for future attention. Cyrus's xlsx now distinguishes "could be auto-applied if we had LinkedIn auth" from "is fundamentally Easy-Apply".

### 2. LinkedIn authenticated session (P1 BLOCKER — needs Cyrus decision)
The only path to URL resolution. Two sub-options:
- **a. Use Cyrus's actual LinkedIn account** — risks LinkedIn flagging/banning his real account (they detect scraping aggressively; `uc=scraping` beacon confirmed). Probably a bad idea given the long-term cost.
- **b. Burner LinkedIn account** — needs setup (phone verification, profile build-out to avoid restriction). Lower risk to Cyrus's main account but takes effort and might still get banned.

### 3. Paid scraping API (money decision)
- Bright Data, ScraperAPI, Oxylabs offer LinkedIn job-posting endpoints. Typical pricing $30-100/mo for the volume we'd need (~900 jobs/run, weekly = ~4k/mo). Returns the off-site URL anonymously.
- **Cyrus needs to approve spend.** Recommend: ScraperAPI's $49/mo plan covers this and is the lowest-friction option.

### 4. Drop LinkedIn → ATS resolution entirely
- The 17/50 = 34% offsite-unresolved bucket extrapolates to ~117 rows where we know an external ATS exists but can't see the URL. Not a trivial loss — these are real apply opportunities.
- But it might be more leverage to spend cycles on other P1 work (Apple custom ATS, staffing-firm filter) than to throw money/risk at LinkedIn.

## Recommendation to main agent

Surface path #3 (paid scraping API, ~$49/mo) to Cyrus as a money-spend decision. Until that's approved, classification is the best we can do.

Also: the LinkedIn discovery adapter (`adapters/linkedin.py`) should NOT have `resolve_ats=True` wired through, because resolution is impossible anonymously. Left as-is (`DEFAULT_RESOLVE_ATS = False` is correct).
