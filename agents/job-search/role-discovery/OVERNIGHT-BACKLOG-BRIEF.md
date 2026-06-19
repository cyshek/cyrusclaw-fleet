# OVERNIGHT BACKLOG-BUILD BRIEF (2026-06-09 → wake +12h)

**Owner:** Cyrus (asleep 12h). **Mandate:** build the actionable engine/discovery items from BACKLOG.md while he's gone. NON-browser-submit work only (the submit-grind subagent owns the single browser-submit slot — do NOT run browser submits here; you may run `--no-submit` dryruns and HTTP-only probes).

## Priority order (highest leverage first)

### 1. 9 Netflix unclassified rows → classify + route (cheap, fast)
9 Netflix rows sit `status=''` with no `llm_*` verdict (crawled, never classified): 2870, 2874, 2875, 2879, 2880, 2882, 2883, 2885, 1539. Run `jd_llm_classifier.py` over just `company='Netflix' AND status=''` (or confirm the next classifier pass sweeps them). They have real `explore.jobs.netflix.net` ATS URLs. Routes a stranded megacap-adjacent cohort into the queue. Netflix is NOT blocklisted.

### 2. Discovery breadth — keyword crawl on non-LinkedIn boards (P1, durable)
BACKLOG "Options to ADD #1": same keyword-matrix pattern (product manager / TPM / SE / etc. × US locations) against Wellfound/AngelList, YC Work-at-a-Startup, Indeed. Net-new companies, NOT IP-walled like LinkedIn. Best ROI. If a full adapter is too big for one night, prototype ONE source (Wellfound or YC WaaS) end-to-end (fetch → parse → dedup vs companies.yaml → emit merge-ready rows), test it, and leave it runnable + documented for review. Do NOT merge thousands of unverified rows blind — probe through the ATS slug-resolver first like `yc_discover.py`/`li_company_slug_resolver.py` do.

### 3. LinkedIn offsite-link resolution improvement (P1)
888 LinkedIn-source rows still hold the LinkedIn URL though most `manual-apply` ones point at a real company ATS. Improve offsite-URL extraction from the LinkedIn job page (the company-site Apply target). This is HTTP/parse work, NOT the authed li_at browser path (that's separately blocked on residential egress). Convert discovered leads → submittable ATS links. Add tests.

### 4. If time: re-derive the vague blocked reasons from evidence (overlaps submit brief #4)
Coordinate with the submit subagent via STATUS files so you don't both grab the same row. You take the pure-diagnosis (dryrun-only) re-derivation; it takes the actual submit if a row preps clean.

## Discipline / guardrails
- **NO browser submits here.** Dryruns (`--no-submit`), HTTP probes, classifier, parsers, adapters, tests only.
- Engine code edits: this agent is the SOLE writer of the tailoring/engine pipeline. Snapshot before edits where a guard exists; keep the test suite GREEN (`pytest` in role-discovery, currently ~918 passing). Add a regression test for any behavior change. COMMIT engine edits to git (`git -C <workspace> add <file> && git commit`) — a tick that edits code and errors before committing loses the fix otherwise. Content-scan diffs for secrets before `git add`.
- DB backup before any bulk write; `PRAGMA integrity_check` before+after.
- Every ~15 min or major step: update `STATUS-OVERNIGHT-BACKLOG.md` (phase, done, next, blockers).
- Post a terse Discord one-liner (channel 1501827950474166332) on start, each shipped item, and final summary.
- Final: append a build summary to `memory/2026-06-09.md` + update BACKLOG.md (move shipped items to "Recently shipped", mark progress).
- If you hit a genuine wall (needs spend / needs a credential that's Cyrus's to type / irreversible), LOG it clearly for morning triage and move to the next item — do NOT block the whole run on one item.
