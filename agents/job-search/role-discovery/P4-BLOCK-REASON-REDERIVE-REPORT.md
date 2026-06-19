# P4 — Vague/Stale block_reason Re-Derivation (READ-ONLY triage)

**Run:** 2026-06-09 ~08:05 UTC · backlog-build subagent (non-submit lane)
**Mode:** READ-ONLY. No DB writes — the submit subagent is concurrently submitting + Phase-F BATCH-tagging the blocked table, so writing block_reason here would race it. This is a morning-triage report; apply after the submit run settles.
**DB state at audit:** 137 blocked rows. **0 had truly vague (`OTHER`/`HARD-WALL`/empty) block_reasons** — the concurrent submit agent's Phase-F tagging already cleared the 13 vague rows a prior tick flagged. So P4's original target (vague→specific) is effectively already done. What remains is **STALE/INACCURATE specific labels**, surfaced below.

## Finding: the `linkedin-stranded` bucket (20 rows) is 3 different realities

Re-derived each from its actual `app_url` (evidence), not the banked label:

### A. block_reason STALE/WRONG — app_url is a REAL ATS posting (3 rows) → RE-PROBE, likely submittable
These are NOT stranded; a prior resolver already found a real posting URL. They were (mis)labeled `linkedin-stranded` but should be re-evaluated as live candidates:
- **1280 San Jose Boiler Works** — `jobs.dayforcehcm.com/en-US/legence/SJBOILERSPORTAL/job/...` (Dayforce — Ant-Design combobox runner exists)
- **2019 Adaptive Machines** — `jobs.ashbyhq.com/adaptive/e90de15c-...` (Ashby — auto-submittable if permissive tenant)
- **2113 Cloudforce** — `jobs.lever.co/go-cloudforce/56bdc9dd-...` (Lever — but Lever auto-submit is hCaptcha-walled; discovery URL is valid for manual)

**Action:** clear `linkedin-stranded`, run a fresh dryrun on each; 2019 is the best auto-submit shot.

### B. Resolved to a GENERIC/junk URL — real issue is "bad resolve", not "stranded" (5 rows)
A previous resolver wrote a non-posting URL. The label hides the real problem (the brute/careers resolver matched a marketing/alerts/wrong-role page):
- **1567 BioCatch** — `comeet.com/jobs/biocatch/03.00E/solutions-engine...` (Comeet — may be a real posting, verify)
- **2002 Sapio Sciences** — `jobs.lever.co/sapiosciences` (bare board root, no job id — bad resolve)
- **2115 Windward** — `jobs.jobvite.com/windward/jobAlerts` (job-ALERTS page, not a posting)
- **2118 ChapsVision** — `teamtailor.com/?utm_campaign=poweredby` (generic "powered by Teamtailor" link)
- **2126 Zensai** — `zensai.recruitee.com/o/full-stack-engineer-net` (WRONG role — full-stack-eng matched to a Solutions Engineer row)

**Action:** these resolved to garbage. Re-label `linkedin-resolved-to-generic-url` (truthful) and either re-resolve to the real posting or drop. NOTE for pipeline: the careers/brute resolvers can emit a board-root / jobAlerts / poweredby URL as a false "resolve" — worth a guard that rejects non-posting URLs (no job-id path segment) so they don't masquerade as resolved.

### C. Genuinely still `linkedin.com` — label ACCURATE (12 rows)
1020 Paramount+, 1111 Checkmarx, 2006 TrueLearn, 2007 adly, 2101 Productboard, 2102 ChargeAfter, 2122 NeuReality, 2132 Epic, 2153 Alignerr, 2169 EDMO, 2170 CapTech, 2254 Vsimple. These are correctly stranded (no direct-ATS crosslink match exists; HTTP resolvers couldn't crack them). Label is honest — leave as-is.

## Cross-link note (P3 interaction)
My P3 `linkedin_db_crosslink_resolver` did NOT touch any of these 20 — correct, because their app_url is no longer `linkedin.com` for buckets A/B (already off-LinkedIn), and bucket C has no direct-ATS twin in the DB. The 5 that showed as "crosslinkable" in a probe were **self-matches** (the row matching its own already-resolved direct row), not real new links.

## Other blocked buckets spot-checked (labels look ACCURATE — no action)
- `openai-applimit-180d` (33) — OpenAI 180-day application limit; accurate batch reason.
- `need-runner-eightfold-RESUMEWALL` (12) — Netflix/Eightfold resume-wall; matches P1 finding.
- `lever-hcaptcha-enterprise-wall` (11) + `lever-hcaptcha-score-wall` (4) — matches TOOLS.md Lever-hCaptcha VERDICT (no vendor on account).
- `proxy-ip-walled` (10) — DataDome/Akamai IP-bound; needs residential proxy (provisioning, not retry).
- `ashby-score-gate-warmed-profile-required` (5) — matches the DEBUNKED-ledger Ashby fingerprint verdict.

## Net P4 verdict
- **0 truly-vague reasons remain** (submit agent already cleared them).
- **8 of 20 `linkedin-stranded` rows carry an INACCURATE label** (3 stale-real-posting + 5 resolved-to-junk). Documented above for morning re-label; not written to avoid racing the live submit agent.
- **1 pipeline hardening candidate:** add a "reject non-posting URL" guard to the careers/brute resolvers (bucket B class).
