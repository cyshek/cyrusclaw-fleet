# himalayas_discover.py — net-new employer discovery (review notes)

**Status:** prototype, LIVE-VALIDATED end-to-end, `--apply`-gated (never blind-merges). Built overnight 2026-06-09 for BACKLOG "Options to ADD #1" (discovery breadth on non-LinkedIn boards). Tests: `test_himalayas_discover.py` (13 green); full engine suite 931 green.

## What it does
Finds **net-new employers** hiring our target roles (PM / TPM / Program / Project Manager / Solutions Engineer / Solutions Architect / Sales Engineer / Customer Engineer / APM) by crawling the **open Himalayas jobs API** (`https://himalayas.app/jobs/api`, ~105k jobs, no auth, no captcha), then verifying each net-new company actually has a public Greenhouse / Ashby / Lever board (via the proven `bulk_discover_slugs.probe`), and emitting ready-to-merge `companies.yaml` entries.

## Why Himalayas (and not Wellfound / YC WaaS)
The brief named Wellfound/AngelList + YC Work-at-a-Startup, but **both are HTTP-dead from this VM's IP**:
- **Wellfound** → DataDome 403 (IP-bound bot wall).
- **YC WaaS** `/jobs` + `/companies` → login-wall / 406 to a non-browser UA; the public Algolia key is dead.
- **Himalayas API** → fully open JSON, exposes `companyName / companySlug / title / seniority / locationRestrictions` — everything a keyword pass needs. It satisfies the P2 intent ("net-new companies, NOT IP-walled like LinkedIn").

## Pipeline (mirrors `yc_discover.py` for codebase consistency)
1. **fetch** — offset-walk the API (caps `limit` at 20/req), 429-backoff/retry (5 tries, ≤30s), cache to `output/himalayas_jobs.json`.
2. **keyword** — keep ONLY titles passing the **live classifier KEEP gate** (`jd_llm_classifier.title_has_target_role` AND no `extract_title_skip` hit) → single source of truth, never surfaces senior/FDE/SWE/people-manager titles. `--us-only` drops rows whose `locationRestrictions` exclude US/Americas/remote.
3. **clean** — drop Himalayas' literal `"name"` placeholder leakage (~10% of rows) and staffing/recruiter middlemen via the shared `staffing_blocklist.is_staffing_firm` (same list the LinkedIn pipeline uses).
4. **dedup** — drop companies already in `companies.yaml` (normalized name) and any resolved `adapter/slug` already covered under a different name.
5. **probe** — verify a real public GH/Ashby/Lever board exists (prefers the Himalayas slug, then name-derived variants).
6. **emit** — write `output/himalayas_discover_hits.json` + print merge-ready YAML. `--apply` required to append; backs up `companies.yaml` → `.yaml.bak.himalayas` first.

## Usage
```
.venv/bin/python himalayas_discover.py --us-only --max-jobs 3000 --apply   # auto-apply (default, wired into weekly_run.sh)
.venv/bin/python himalayas_discover.py --us-only --max-jobs 2000            # dry-run: print YAML only
```

**Auto-apply is now the default** (Cyrus 2026-06-15). `weekly_run.sh` runs this as Step 0 before the main crawl, so net-new verified companies are added to `companies.yaml` and immediately picked up by the Step 1 crawl in the same weekly run. Idempotent: never adds a company whose normalized name OR resolved `adapter+slug` already exists.

## Live validation (2026-06-09)
- API reachable; `totalCount=105264`; fetch/paginate/cache all work.
- 2920-job crawl → 44 target-role companies → 42 net-new → **2 verified GH boards: MEMX, Elation Health** (predecessor run).
- 1600-job crawl → 26 target-role cos → 0 verified boards that batch (newest-first ordering shifts overnight). After the placeholder+staffing clean: 23 cos. The misses are **genuine**: the surfaced enterprises (Amgen, Booz Allen, Stryker, College Board, Magellan Health) run Workday/iCIMS/SAP, which we don't auto-crawl — so 0 GH/Ashby/Lever hits is correct, not a probe bug.

## Reality / expectation note
Himalayas skews **enterprise / healthcare / consulting remote** (Workday/iCIMS/SAP-heavy), so the GH/Ashby/Lever hit-rate is low (~5%) but **real and net-new**. It's a complementary **3rd breadth source** alongside `yc_discover.py` + the LinkedIn-matrix — not a high-volume firehose. Recommend running it at `--max-jobs 3000+` periodically and reviewing the handful of verified hits before `--apply`.

## Status (2026-06-15)
Auto-apply enabled. Wired into `weekly_run.sh` as Step 0 (runs before main crawl so net-new companies are discovered + crawled in the same weekly run). No manual review step.
