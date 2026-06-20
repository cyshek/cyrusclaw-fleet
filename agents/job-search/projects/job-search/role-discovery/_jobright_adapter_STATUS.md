# JobRight adapter build — STATUS

## Verified facts (from spike + my own fetches)
- 12 public category slugs from `https://jobright.ai/sitemap-remote-jobs.xml` (AUTHORITATIVE, not hardcoded guesses):
  business-finance-hr-legal, customer-support-success, data-ai, hardware-embedded,
  healthcare-life-sciences, infrastructure-security, manufacturing-industrial,
  marketing-growth, product-design, public-sector-education,
  sales-business-development, software-engineering
- Each `/remote-jobs/<slug>` page = Next.js, `<script id="__NEXT_DATA__">` → `props.pageProps.defaultData` = 30 items.
- Per item: `jobResult` + `companyResult`. Company name is in **companyResult.companyName** (jobResult.companyName is EMPTY — 30/30). Title=jobResult.jobTitle, location=jobResult.jobLocation, publishTime ISO UTC, applyLink=jobright.ai/jobs/info/<id> WRAPPER (100%, not direct ATS → discovery-only).
- jobId = 24-hex in applyLink path.

## Plan
- adapters/jobright.py: SOURCE adapter, fetch(company,slug,**opts)->List[Role], source="jobright".
- tracker_merger.py: add `jobright:` source_key branch (jobId from URL) + add 'jobright' to the manual-apply/discovery-only tag set.
- adapters/__init__.py: register "jobright".
- companies.yaml: add JobRight source entry.
- weekly_run.sh: confirm crawl includes it (run.py loads all companies.yaml entries → auto-included).
- test_jobright_adapter.py + fixture test_fixtures/jobright_product_design_next_data.json (offline parse).

## Phases
- [x] study-pattern (linkedin adapter, tracker_merger, run.py, core.Role, tracker_db schema)
- [x] fixture captured (test_fixtures/jobright_product_design_next_data.json, 30 items)
- [x] DB backed up: tracker.db.bak.20260611-205952-jobright-adapter
- [x] write adapter
- [x] register (merger source_key branch + discovery-only set + auto-close skip; __init__ REGISTRY; companies.yaml entry)
- [x] weekly_run.sh: NO edit needed — line 33 `run.py --workers 12` crawls ALL companies.yaml entries (jobright auto-included); line 61 `tracker_merger.py` tags it discovery-only. Verified no per-adapter allowlist.
- [x] tests green: 12 passed
- [x] live-verify: run.py --only JobRight -> fetched=331 across 12 categories, kept=5 (filter_roles). Merged: 5 inserted. Newest publishTime=2026-06-11 21:01:24.
- [x] dedup idempotent: re-run merger = 0 inserts/5 matched, 5 distinct source_keys, no dupes.
- [x] QUEUE EXCLUSION: 0 jobright rows match sequential_burndown WHERE, 0 match AGENTS.md burndown variant, 0 match inline_submit.pick_batch. (status='manual-apply' on insert + jobright.ai URL matches no ATS host.)
- [ ] commit (only my files)

## KEY DESIGN NOTE
- jobright rows inserted with status='manual-apply' (NOT '') so they're excluded from the status='' burndown queue immediately (the burndown SQL keys on status, not flags/URL). Scoped to jobright only in merger to not change google/etc behavior.
- DB rows: id 2913-2917, all status='manual-apply' flags='posted:... manual-apply discovery-only'.
