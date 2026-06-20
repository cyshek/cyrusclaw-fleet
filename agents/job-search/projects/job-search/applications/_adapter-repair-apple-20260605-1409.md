# Adapter repair — `apple` — 20260605-1409 (07:09 PDT)

## Summary
**What broke:** The 2026-06-05 smoke run failed `apple` with a one-off `ReadTimeout` on `jobs.apple.com` (`read timeout=45`, `duration_ms=99032`). **Root cause = transient network hiccup, NOT a shape/endpoint/anti-bot change.** The page contract is fully intact and the *live* adapter fetches all 93 roles right now with zero code changes (verified end-to-end below).
**What I changed (candidate only):** Added bounded retry + backoff around every HTTP GET in the adapter and split the scalar `timeout=45` into a `(connect=15, read=45)` tuple, so a single slow/hung response retries instead of aborting the whole crawl. Parsing logic is byte-identical.

## Diagnosis detail
- **NOT a shape change.** Page still embeds backslash-escaped JSON (`\"positionId\"`, `\"postingTitle\"`, `\"postDateInGMT\"`, `\"transformedPostingTitle\"`, `\"teamCode\"`). The live `apple._parse_page()` parsed **20/20 items per page**, all `PAT_*` regexes aligned (compound-id short-by-1 already handled by the existing `disc_by_pid` fallback).
- **NOT an endpoint move / NOT 404.** `https://jobs.apple.com/en-us/search?page=1&location=united-states-USA&sort=newest` returns **HTTP 200 in ~0.4s** via BOTH `curl` and Python `requests` immediately before and after the failure.
- **NOT anti-bot / captcha.** The only `captcha` substrings in the body are i18n UI label strings (`jobsite.search.errorCaptcha`, `jobsite.common.captchaExpired`) baked into the page — not an active challenge.
- **Why it aborted hard:** the original `_fetch_page` used a scalar `timeout=45` (connect+read combined) and the pagination loop's `try/except RuntimeError` did **not** catch `requests.exceptions.ReadTimeout`, so one read hiccup propagated out and killed `fetch()`. The 99s `duration_ms` shows the request was already struggling well past the 45s read window.

## Reproduction / proof it's transient (live adapter, unmodified)
```
$ .venv/bin/python -c "import sys,time; sys.path.insert(0,'.'); from adapters import apple; t0=time.time(); r=apple.fetch(); print('DONE', round(time.time()-t0,1),'s  count',len(r))"
  [apple] 93 title-qualifying postings; fetching JD detail for each to extract YOE...
  [apple] kept 93 matching roles (from 972 total US postings)
=== DONE in 217.8 s ===
count 93
  Apple | Software/Firmware Engineering Program Manager - Beats | 2026-06-04 | exp:10+yrs | https://jobs.apple.com/en-us/details/200666851-0836/...
  Apple | Program Manager - SWE Infrastructure | 2026-06-04 | exp:unstated | https://jobs.apple.com/en-us/details/200666799-0836/...
```
Role count **93** exactly matches the baseline contract (`_smoke-baseline.json` role_count: 93).

## Smoke output (candidate)
Verified via `adapters/_repair/_verify_apple.py` (loads candidate via `SourceFileLoader`, does NOT touch the live package):
```
=== 1. import candidate ===
  OK: module loaded; has fetch: True | has _get_with_retry: True
=== 2. parser against cached real body ===
  parsed items: 20
    114438158 | US - Specialist: Seasonal, Part-time | 2026-06-05 | team APPST
    200666969 | US-Operations Specialist | 2026-06-05 | team APPST
=== 3. live 1-page fetch via retry wrapper ===
  live page-1 parsed: 20 items
=== 4. contract check on synthesized Role objects ===
  contract OK on 3 synthesized roles (company/title/url/posted_at all present)

RESULT: GREEN — candidate imports, parses real body, live-fetches via retry wrapper, satisfies contract.
```
> Note: the verify driver intentionally does NOT re-run the full ~218s crawl (the live probe above already proved 93-role end-to-end shape). The candidate differs from live ONLY by the retry wrapper, so behavior is identical except it survives transient timeouts.

## Diff
```diff
--- adapters/apple.py	2026-05-11 05:05:41 +0000
+++ adapters/_repair/apple.py.candidate	2026-06-05 14:07:07 +0000
@@ from __future__ import annotations
 import re, html as _html, time
 from typing import List
+import requests
 from core import Role, http_get, parse_experience
+
+# --- transient-failure hardening (added by adapter-repair, 2026-06-05) ---
+CONNECT_TIMEOUT = 15
+READ_TIMEOUT = 45
+HTTP_RETRIES = 3          # total attempts per URL
+RETRY_BACKOFF = 2.0       # seconds, multiplied by attempt index
+
+def _get_with_retry(url, *, headers=None, params=None, label="apple"):
+    last_exc = None
+    for attempt in range(1, HTTP_RETRIES + 1):
+        try:
+            return http_get(url, headers=headers, params=params,
+                            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
+        except requests.exceptions.RequestException as e:
+            last_exc = e
+            if attempt < HTTP_RETRIES:
+                wait = RETRY_BACKOFF * attempt
+                print(f"  [{label}] transient {type(e).__name__} on attempt {attempt}/{HTTP_RETRIES}; retrying in {wait:.0f}s")
+                time.sleep(wait)
+    raise last_exc
@@ _fetch_page
-    r = http_get(SEARCH_URL, headers=HEADERS, params=params, timeout=45)
+    r = _get_with_retry(SEARCH_URL, headers=HEADERS, params=params)
@@ fetch pagination loop
-        except RuntimeError as e:
-            print(f"  [apple] page {page} failed: {e}")
+        except (RuntimeError, requests.exceptions.RequestException) as e:
+            print(f"  [apple] page {page} failed after retries: {e}")
             break
@@ detail-page fetch
-            r = http_get(url, headers=HEADERS, timeout=45)
+            r = _get_with_retry(url, headers=HEADERS)
```
(Full unified diff: `diff -u adapters/apple.py adapters/_repair/apple.py.candidate`)

## Candidate path
`/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/adapters/_repair/apple.py.candidate`

## Recommend merge
- **RECOMMEND MERGE:** `cp /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/adapters/_repair/apple.py.candidate /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/adapters/apple.py`
- Low risk: parsing logic unchanged; the patch only adds retry/backoff resilience to the exact failure mode the smoke test hit. Merging hardens the adapter against future one-off `jobs.apple.com` slowness.
- **Alternatively, NO-OP is also defensible** — the live adapter already returns 93 roles, so this smoke failure was a transient blip. The candidate is purely a robustness improvement so the next blip self-recovers instead of paging this subagent again.
