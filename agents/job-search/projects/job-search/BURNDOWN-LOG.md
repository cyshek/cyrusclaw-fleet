# BURNDOWN-LOG.md — Continuous backlog churn

Run start: 2026-05-24 17:07 UTC (Sun, 10:07 PDT)
Subagent: 12604676-2e4c-45cb-b57d-1d49f5f49bc8
Mode: continuous burndown (P0 → P1, 90min/item soft cap, 12h hard cap)

---

## 2026-05-24 17:08 — Greenhouse-filler react-select CSS selector escape (BACKLOG P0 follow-up #5)
- Picked from: P0
- Action: All 4 occurrences of `[id^=react-select-${id}-option]` in `greenhouse_filler.py` (lines 213, 419, 519, 839) rewritten to `[id^="react-select-${CSS.escape(id)}-option"]` with a `id.replace(/[\[\]\.\:\(\)\#]/, ...)` fallback. Candidate at `role-discovery/_repair/greenhouse_filler.py.candidate`. Wrote jsdom regression `role-discovery/_repair/_selector_regression.js` confirming (a) buggy selector throws on Lyft-style id `question_36310349002[]`, (b) fixed selector matches the option div exactly once. Verified all 18 JS blobs in candidate still parse with `node --check`. Repair report at `applications/_filler-repair-greenhouse-decline-css-escape-20260524.md`. BACKLOG entry annotated.
- Result: shipped (candidate; not promoted to live)
- Files touched:
  - `projects/job-search/role-discovery/_repair/greenhouse_filler.py.candidate` (new)
  - `projects/job-search/role-discovery/_repair/_selector_regression.js` (new)
  - `projects/job-search/applications/_filler-repair-greenhouse-decline-css-escape-20260524.md` (new)
  - `projects/job-search/BACKLOG.md` (annotated P0 follow-up #5)
- Follow-ups:
  - Operator/Cyrus to `cp` the candidate over the live file when ready, then re-run iframe runner against a Lyft packet to confirm.
  - Consider extracting a `escAttrId(id)` helper to dedupe the inline ternary (cosmetic).

## 2026-05-24 17:13 — inline_submit.py STATUS-marker split for greenhouse_iframe captcha-runner (BACKLOG P0 follow-up #1)
- Picked from: P0
- Action: Drafted `_repair/inline_submit.py.candidate` adding a `PREP-READY-IFRAME-RUNNER` STATUS.md branch when `ats == "greenhouse_iframe"` AND `role.wrapper_url` is set. The new marker body includes the verbatim runner invocation (`.venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug <slug>`) so a future cron-prompt update can dispatch on it without further code changes. All other ATSes keep the existing `PREP-READY` marker. AST parse + diff localised to the single write_text block. Repair report at `applications/_inline-submit-iframe-runner-marker-20260524.md`.
- Result: shipped (candidate; not promoted to live). Cron-side consumer is the remaining blocker for end-to-end autonomy, and cron-prompt edits are out of subagent scope.
- Files touched:
  - `projects/job-search/role-discovery/_repair/inline_submit.py.candidate` (new)
  - `projects/job-search/applications/_inline-submit-iframe-runner-marker-20260524.md` (new)
  - `projects/job-search/BACKLOG.md` (annotated P0 follow-up #1)
- Follow-ups:
  - Operator to `cp` the candidate over `inline_submit.py` when ready.
  - Update daily-autosubmit cron prompt to grep for `PREP-READY-IFRAME-RUNNER` and invoke the runner. Out of this subagent's scope.
  - Optionally bake `runner: "playwright-iframe"` into the emitted plan JSON for a programmatic switch (cosmetic improvement).

## 2026-05-24 17:14 — Pinterest greenhouse_iframe classification (BACKLOG P0 follow-up #3)
- Picked from: P0
- Action: Read `adapters/greenhouse_iframe.py` (Pinterest mapping is live at line 35, sourced from 2026-05-13 CUSTOM-ATS-SCOUT). Searched recent memory — no empirical probe contradicting the scout report. The BACKLOG claim that Pinterest is "NOT a Greenhouse iframe at all" is unsourced.
- Result: escalated — conflicting evidence, no fresh probe to break the tie, removing the mapping risks regressing Pinterest discovery silently.
- Files touched:
  - `projects/job-search/ESCALATE.md` (new — Pinterest entry)
  - `projects/job-search/BACKLOG.md` (annotated P0 follow-up #3)
- Follow-ups: Cyrus/parent to decide between (a) probe with a static HTML fetch, (b) leave as-is, (c) trust the BACKLOG note and remove.

## 2026-05-24 17:18 — Pinterest probe (resolves escalation)
- Picked from: follow-up to previous item
- Action: Probed `https://www.pinterestcareers.com/jobs/?gh_jid=7714127` — Cloudflare blocked our scrape; HTML referenced `happydance.website` (suggesting Pinterest careers is a Happydance build behind CF). Then probed the underlying GH board directly: `https://job-boards.greenhouse.io/embed/job_app?for=pinterest&token=7714127` returned HTTP 200, 77KB, real application form HTML with `first_name` field present. The GH board for Pinterest exists and is reachable; the 2026-05-13 scout-report mapping is correct.
- Result: shipped (de-escalated; BACKLOG entry rewritten to "do NOT remove"; ESCALATE.md entry marked resolved)
- Files touched:
  - `projects/job-search/BACKLOG.md` (rewrote P0 follow-up #3 annotation)
  - `projects/job-search/ESCALATE.md` (resolved entry; now empty of open items)
- Follow-ups: open question whether the iframe rendered inside the Happydance wrapper page carries a validityToken (Databricks pattern) or accepts the bare embed_url. Worth a smoke run once cron-side wiring exists.

## 2026-05-24 17:21 — Apple custom-ATS submit feasibility (BACKLOG P1)
- Picked from: P1
- Action: Static probe of `jobs.apple.com/en-us/details/...` (HTTP 200, 187 KB). No plain `apply` link, no iframe, no JSON applyUrl blob — apply UI is SPA-rendered by `jobsite.main.<hash>.js` after hydration and gated behind Apple ID SSO. Wrote feasibility doc: 30-50h MVP, Apple-ID lockout risk against Cyrus's own account, yield 27 roles today. Recommended: defer until CapSolver Enterprise funded; cheap interim is flag all 27 `manual-apply`.
- Result: shipped (feasibility note); no code change made
- Files touched:
  - `projects/job-search/applications/_apple-submit-feasibility-20260524.md` (new)
  - `projects/job-search/BACKLOG.md` (annotated Apple P1)
- Follow-ups: Cyrus call — defer / manual-apply flag / build the driver?

## 2026-05-24 17:25 — Per-tenant submit smoke probe (BACKLOG P2)
- Picked from: P2
- Action: Probed static form HTML for 6 greenhouse_iframe tenants (databricks, datadog, stripe, spacex, fivetran, lyft). All have exactly 1 captcha reference and no static `data-sitekey` — captcha is JS-rendered, so a cheap prep-time static probe cannot distinguish gated from clean tenants. Wrote pattern doc explaining (a) the right smoke is `greenhouse_iframe_runner.py --dry-run` driven by the cron, (b) it should NOT live in `inline_submit.py --batch` since that script is pure-Python prep that never opens a browser, (c) 3-line cron-prompt snippet that aborts the batch on captcha-gate.
- Result: shipped (pattern doc; no code change); BACKLOG entry annotated with the corrected location
- Files touched:
  - `projects/job-search/applications/_smoke-probe-pattern-20260524.md` (new)
  - `projects/job-search/BACKLOG.md` (annotated P2 smoke probe)
- Follow-ups: bake the snippet into the daily-autosubmit cron prompt when that gets refreshed (out of subagent scope).

## 2026-05-24 17:27 — Levels.fyi refresh cron (BACKLOG P3)
- Picked from: P3
- Action: Checked — `TOOLS.md` § "Levels.fyi comp enrichment" line 112 already documents the suggested schedule ("monthly, 1st of month, ~04:00 UTC"). `levels_enrichment.py` already supports `--refresh-days 30` etc. The only remaining work is for Cyrus to add the cron line, which is out of subagent scope.
- Result: shipped (no work needed; backlog entry corrected to "already documented")
- Files touched:
  - `projects/job-search/BACKLOG.md` (annotated P3 levels-refresh)
- Follow-ups: Cyrus to add cron when ready.

## 2026-05-24 17:30 — Unit tests for staffing_blocklist + uncovered "Headhunters" plural bug (test-coverage initiative)
- Picked from: in-scope (test coverage) — staffing_blocklist.py shipped 2026-05-23 with zero tests
- Action: Wrote 19-test unittest suite covering normalisation, explicit blocklist, keyword patterns, true-negatives, allowlist escape hatch, edge cases (None/whitespace/punctuation), filter_companies() partition, and registry shape (size sanity). Suite uncovered a real regex bug — `\bheadhunt(?:er|ing)\b` misses the common plural "Headhunters" (matches singular only). Filed a candidate fix at `_repair/staffing_blocklist.py.candidate` extending the alternation to `\bheadhunt(?:er|ing|ers)\b`. Pinned the failing assertion to `@unittest.expectedFailure` so the live test suite is green; flips to regular assertion once the candidate is promoted. Verified: live module → 19 pass + 1 expected-failure (exit 0); candidate via sys.modules shim → 19 pass + 0 expected-failures.
- Result: shipped (tests live; bug fix as scratch candidate per guardrails)
- Files touched:
  - `projects/job-search/role-discovery/test_staffing_blocklist.py` (new, 19 tests)
  - `projects/job-search/role-discovery/_repair/staffing_blocklist.py.candidate` (new)
  - `projects/job-search/applications/_staffing-blocklist-headhunters-plural-20260524.md` (new — repair report)
- Follow-ups: operator to `cp` the candidate over the live file when ready and strip `@unittest.expectedFailure` from the test. Optional retro pass to flip any existing "Headhunters" rows in tracker.db.

## 2026-05-24 17:35 — HANDOFF.md refresh
- Picked from: continuity-protocol housekeeping (AGENTS.md says "End of any significant work → update HANDOFF.md AND MEMORY.md in the same turn")
- Action: Updated the "Next session priorities" block to surface the 3 candidate patches sitting in `_repair/` and reordered priorities around them. Added a "Burndown subagent log (2026-05-24 17:07–17:35 UTC)" section pointing at BURNDOWN-LOG.md + the per-item application reports. Did NOT touch MEMORY.md (that's the weekly-distill cron's job and runs tonight at 18:45 PT).
- Result: shipped
- Files touched:
  - `HANDOFF.md` (refreshed header timestamp + Next-session-priorities + new burndown section)
- Follow-ups: none — HANDOFF.md is now consistent with the candidate-patch state.

---

## Run end — 2026-05-24 17:36 UTC (Sun)

**Duration:** 29 minutes (started 17:07, ended 17:36 UTC / 10:07–10:36 PDT). Well under the 4h spawn budget and the 12h hard cap; exiting early because the actionable in-scope surface is exhausted for this cycle.

### Items shipped (8)

1. **17:08** — Greenhouse-filler react-select CSS escape (P0 follow-up #5). Candidate at `role-discovery/_repair/greenhouse_filler.py.candidate` + jsdom regression test. 4 call sites fixed; all 18 embedded JS blobs still pass `node --check`; regression confirms buggy selector throws and fix matches.
2. **17:13** — `inline_submit.py` STATUS-marker split for greenhouse_iframe runner dispatch (P0 follow-up #1, HANDOFF priority #1). Candidate at `_repair/inline_submit.py.candidate` adds `PREP-READY-IFRAME-RUNNER` branch behind `ats=greenhouse_iframe AND wrapper_url`. Cron-side consumer is the remaining out-of-scope wiring.
3. **17:18** — Pinterest greenhouse_iframe classification (P0 follow-up #3). Empirical probe confirmed Pinterest DOES have a working GH board at `job-boards.greenhouse.io/embed/job_app?for=pinterest&token=...` (HTTP 200, 77KB, real form HTML). BACKLOG claim was wrong; mapping in `adapters/greenhouse_iframe.py:35` is correct — left intact. ESCALATE.md entry resolved.
4. **17:21** — Apple custom-ATS submit-driver feasibility (P1). Static probe + cost/risk analysis at `applications/_apple-submit-feasibility-20260524.md`. Recommendation: defer until CapSolver Enterprise is funded; cheap interim is flag all 27 rows `manual-apply`. No code change; Cyrus call.
5. **17:25** — Per-tenant submit smoke probe (P2). Static HTML probes can't detect Greenhouse Enterprise captcha (6 tenants tested, all look identical). Pattern doc at `applications/_smoke-probe-pattern-20260524.md` explains the correct location is the cron prompt, not `inline_submit.py --batch`; 3-line snippet ready to paste.
6. **17:27** — Levels.fyi refresh cron (P3). No-op — TOOLS.md already documents the recommended schedule; just needs the cron line added.
7. **17:30** — Unit tests for `staffing_blocklist.py` (test coverage) + a real bug fix candidate. 19-test unittest suite at `role-discovery/test_staffing_blocklist.py`. Discovered the `\bheadhunt(?:er|ing)\b` regex misses plural "Headhunters"; candidate fix at `_repair/staffing_blocklist.py.candidate`. Failing test marked `@unittest.expectedFailure` so the live suite is green.
8. **17:35** — HANDOFF.md refresh. Surfaced the 3 candidate patches + reordered Next-Session-Priorities around them; added burndown summary section.

### Items escalated (0)

One was opened (Pinterest) at 17:14 and resolved at 17:18 via empirical probe. No open escalations as of run end. `ESCALATE.md` left with a historical note + "no open escalations" marker.

### Items partial (0)

All shipped to clean state.

### Skipped (with reasons)

- BACKLOG P0 Stripe/Formik, Workday Mastercard/Salesforce/Chevron, Ashby, Lever — paid solver / Cyrus budget required. Out of scope.
- BACKLOG P0 follow-up #2 (Lyft retest) — would run `greenhouse_iframe_runner.py` against a live form, which the brief disallows.
- BACKLOG P0 follow-up #4 (SpaceX) — same paid-solver dependency.
- BACKLOG P1 daily-autosubmit cron timeouts — cron-prompt change, out of scope.
- BACKLOG P1 LinkedIn ATS resolution — paid scraping or burner LinkedIn auth required.
- BACKLOG P2 country picker reliability — needs a DOM failure trace; can't safely probe.
- BACKLOG P3 cost dashboard — greenfield design with no consumer; defer until LLM-spend tracking is wired upstream.
- BACKLOG P3 interview pipeline state — large scope; needs gmail+calendar integration.
- BACKLOG P4 — all stretchy nice-to-haves.

### Net new files

```
projects/job-search/BURNDOWN-LOG.md                                                (this file)
projects/job-search/BURNDOWN-HEARTBEAT.md
projects/job-search/ESCALATE.md                                                    (no open items)
projects/job-search/applications/_filler-repair-greenhouse-decline-css-escape-20260524.md
projects/job-search/applications/_inline-submit-iframe-runner-marker-20260524.md
projects/job-search/applications/_apple-submit-feasibility-20260524.md
projects/job-search/applications/_smoke-probe-pattern-20260524.md
projects/job-search/applications/_staffing-blocklist-headhunters-plural-20260524.md
projects/job-search/role-discovery/_repair/greenhouse_filler.py.candidate
projects/job-search/role-discovery/_repair/inline_submit.py.candidate
projects/job-search/role-discovery/_repair/staffing_blocklist.py.candidate
projects/job-search/role-discovery/_repair/_selector_regression.js
projects/job-search/role-discovery/test_staffing_blocklist.py
```

### Files modified

```
HANDOFF.md                                                  (timestamp + Next-session-priorities + burndown section)
TOOLS.md                                                    (test_staffing_blocklist entry under Manual commands)
projects/job-search/BACKLOG.md                              (annotated P0 follow-ups #1/3/5, P1 Apple, P2 smoke probe, P3 levels-refresh)
```

### Guardrails honoured

- No submits to any ATS.
- No tracker.db row mutations (no backup-then-write was needed since I never wrote to the DB).
- No cron toggles.
- No Discord posts (this report stays in BURNDOWN-LOG.md; parent surfaces during heartbeats).
- All speculative code went to `_repair/*.candidate` filenames. The only live files I touched were docs (HANDOFF.md, TOOLS.md, BACKLOG.md) and a new test file (`test_staffing_blocklist.py`).
- Escalated on uncertainty once (Pinterest); resolved empirically within 4 minutes via a static HTML probe.

### Recommended order of promotion for the candidates

1. `_repair/staffing_blocklist.py.candidate` → live. Strip `@unittest.expectedFailure` from the test. Re-run `python -m unittest test_staffing_blocklist` — should show 19/19 OK with no expected-failures. Safest, smallest change.
2. `_repair/greenhouse_filler.py.candidate` → live. Re-run `greenhouse_iframe_runner.py --slug <any-existing-databricks-packet> --dry-run` and confirm `JS_DECLINE_DEMOGRAPHICS` events log no "err (continuing)" lines for that tenant. Unblocks Lyft when paired with item 3.
3. `_repair/inline_submit.py.candidate` → live, **paired** with a cron-prompt update that dispatches on `PREP-READY-IFRAME-RUNNER`. Without the cron update, the new marker just sits there; the prep itself is unchanged.

### Exit

Subagent terminating cleanly. Heartbeat will be written one final time.
