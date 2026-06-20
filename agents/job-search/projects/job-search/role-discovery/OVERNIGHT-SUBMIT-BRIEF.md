# OVERNIGHT SUBMIT-GRIND BRIEF (2026-06-09 → wake +12h)

**Owner:** Cyrus (asleep 12h). **Mandate:** final audit — try ONE LAST submit on every actionable row; on failure log a CLEAR reason in `agent_notes` tagged `BATCH:` or `ONEOFF:` so tomorrow's triage is a sort, not a re-investigation.

## Scope (ATTEMPT these)
Work strictly from the tracker DB `../tracker.db` (table `roles`). Driver: `.venv/bin/python inline_submit.py --role-id <id>` (auto-detects ATS, preps + submits). Verify success the canonical way (browser confirmation/route + write `applications/submitted/<slug>/STATUS.md` + `UPDATE roles SET applied_by='auto', applied_on=date`).

Queue (work in this order, SERIAL — only ONE browser-submit at a time, that's a hard rule):
1. **16 open/empty unapplied:** `WHERE (status='' OR status='open') AND applied_by IS NULL ORDER BY id`
2. **13 manual_ready not applied/skip:** `WHERE prep_status='manual_ready' AND status NOT IN ('applied','skip') ORDER BY id`
3. **Recoverable blocked — Ashby score-gate (4):** `WHERE status='blocked' AND block_reason LIKE '%ashby-score-gate%'` → use the RESIDENTIAL path: `./_residential_browser.sh` then run `_ashby_runner.py` via `JOBSEARCH_CDP` pointed at the proxied Chrome. ~$0.07 total pre-approved. Includes Mercor 1237.
4. **Re-probe vague blocked reasons** (re-derive from EVIDENCE, not the stale string): the ~13 rows tagged OTHER/HARD-WALL/label-gap/gh-blank-label (Ambient 2563, Anara 2606, Antithesis 2781, Cartesia 1384, Curri 2557, Drata 2548, Knowtex 2593, Ready 2605, Snowflake 2527, Nintendo 2748, Paystand 2799, Pure Storage 2688, + any new). Run a live `greenhouse_dryrun.py --no-submit` (or ashby equiv); if it preps clean → submit; if genuinely walled → re-log honest reason.

## Honest NO-ATTEMPT (do NOT fake-attempt — just ensure agent_notes has the known reason, tagged BATCH:)
These are documented dead-ends; a fake attempt wastes time + money. Just confirm each carries a clear BATCH-tagged reason:
- 33 `openai-applimit-180d` → `BATCH: OpenAI 180-day apply cooldown, time-gated, not retryable`
- 20 `linkedin-stranded` → `BATCH: LinkedIn offsite URL unresolved; datacenter IP burns li_at in-browser; needs residential-egress-end-to-end + fresh cookie`
- 11 `eightfold RESUMEWALL` → `BATCH: Eightfold Filestack resume-upload wall, no XHR-intercept built`
- 15 `lever-hcaptcha-enterprise/score` → `BATCH: Lever hCaptcha Enterprise rqdata, platform-wide score-gate, no vendor token defeats it`
- 10 `proxy-ip-walled` / DataDome → `BATCH: solve-IP-bound challenge (DataDome/Akamai), needs residential proxy provisioning`

## Failure-logging FORMAT (mandatory on every failed attempt)
`UPDATE roles SET agent_notes = COALESCE(agent_notes,'') || ' | TRIED 2026-06-09: <BATCH|ONEOFF>: <specific reason + exit code/field>' WHERE id=<id>`
- **BATCH** = shared root cause hitting many rows (captcha class, ATS-wide upload wall, IP binding, applimit).
- **ONEOFF** = row-specific (one missing field, one closed req, one weird label, one knockout answer).
- Always include the concrete signal: exit code, the missing field name, the confirmation-route check that failed, the captcha verdict string.

## Discipline / guardrails
- ONE browser-submit subagent worth of concurrency. Non-browser probes (dryruns, DB) can parallelize.
- DB backup before any bulk status write: `cp ../tracker.db ../tracker.db.bak.overnight-<ts>`. `PRAGMA integrity_check` before+after.
- Bank-and-stop per row; NEVER giant DOM snapshot/scroll loops (they context-overflow). Small probe scripts, write STATUS.md per row, move on.
- Verify submits on DISK+DB+route — a "Thank you"/text-match is NOT proof (cost a false Uber applied before).
- Truthful knockouts always (location/work-auth/clearance/citizenship) even when it costs the submit. Essays/motivation may be auto-generated.
- Every ~15 min or major step: update `STATUS-OVERNIGHT-SUBMIT.md` (phase, done count, submitted ids, failed+reason, next, blockers).
- Post a terse one-liner to Discord channel 1501827950474166332 on: start, every ~10 submits or major milestone, and final summary.
- Final: regenerate `render_xlsx.py`, write a tally (attempted/submitted/failed-BATCH/failed-ONEOFF) to STATUS + Discord + append to `memory/2026-06-09.md`.
