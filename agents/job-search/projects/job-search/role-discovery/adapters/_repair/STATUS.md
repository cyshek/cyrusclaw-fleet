# Adapter Repair STATUS — apple

**Last updated:** 2026-06-05 ~07:05 PDT
**Subagent:** adapter-repair-apple

## Phase
COMPLETE — candidate GREEN, report written, Discord sent (msg 1512458561152618559 → channel 1501827950474166332).

## Target
- Adapter: **apple** (only target this run; not present in `newly_broken[]` which is null, identified by task brief + `_smoke-results.json` shows `status=fail`).
- Error: `ReadTimeout: HTTPSConnectionPool(host='jobs.apple.com', port=443): Read timed out. (read timeout=45)`
- Fails at `_fetch_page(1)` → `http_get(SEARCH_URL, timeout=45)`.
- Baseline contract (`_smoke-baseline.json`): role_count 93; sample_role keys company/title/url/location/posted_at/exp_required. require_posted_at=True.

## Done
- Read brief, smoke-results, baseline, live adapter, probe def.

## Next
- Reproduce: hit `https://jobs.apple.com/en-us/search?page=1&location=united-states-USA&sort=newest` with curl + python requests to see if it's transient slowness, hard block, or shape change.
- Distinguish: timeout-only (retry/slow) vs anti-bot wall (escalate) vs endpoint move.

## Findings (key)
- **NOT a shape change.** Page still embeds escaped JSON (`\\"positionId\\"` etc.). Live `apple._parse_page` against a fresh fetch parsed **20/20 items** cleanly, all PAT_* regexes aligned (compound_id 19 → handled by fallback).
- **NOT an endpoint move / NOT 404.** `https://jobs.apple.com/en-us/search?...` returns **200 in ~0.4s** via BOTH curl and python `requests` right now.
- **NOT anti-bot.** The only `captcha` hits are i18n UI label strings (`jobsite.search.errorCaptcha`), not an active wall.
- **Root cause = transient ReadTimeout.** Smoke run hit a one-off hung/slow response. The adapter has no retry; `_fetch_page`'s `try/except RuntimeError` does NOT catch `requests.exceptions.ReadTimeout`, so a single read hiccup aborts the whole `fetch()`.
- Uses scalar `timeout=45` (connect+read combined). Better: split connect/read + retry with backoff on timeout.

## Outcome (FINAL)
- **Live adapter probe: 93 roles in 217.8s** = exact baseline match → confirms the smoke failure was a **transient ReadTimeout**, not a real break.
- **Candidate GREEN** (`adapters/_repair/apple.py.candidate`): adds bounded retry+backoff + (connect,read) tuple timeout; parsing byte-identical. Verified via `_verify_apple.py` (import + parse real body + live page-1 fetch via retry wrapper + contract check). `py_compile` clean.
- **Report:** `/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/_adapter-repair-apple-20260605-1409.md` (Summary/Diff/Smoke/Candidate path/RECOMMEND MERGE).
- Only 1 target this run (apple). No second adapter in scope (`newly_broken` null; brief named apple only).

## Next
- (none) — returning final summary to parent.

## Blockers
None. NOTE: this was a transient blip — merge is a robustness improvement, not strictly required; live adapter already healthy.
