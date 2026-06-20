# [Subagent Task] Resolve + submit the `(none)`-block LinkedIn-discovery cohort

You are a focused job-application worker for `job-search`. Workdir:
`/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search`
venv: `role-discovery/.venv/bin/python`

## Mission
8 tracker rows are `status='manual-apply'`, `block_reason` EMPTY. They came from LinkedIn
discovery and were tagged NO-ATS by a 2026-06-08 brute pass that ONLY checked public ATS
boards by company slug. That pass MISSED the real apply path: the COMPANY CAREERS SITE →
real ATS. Proven already: Expedia→Workday, WWT→ADP. Your job: for EACH row, resolve the real
apply URL via OPEN WEB (web_search/web_fetch — **never** linkedin.com, it is IP-dead from this
VM), then attempt to SUBMIT the application end-to-end, then COMMIT the outcome to tracker.db.

TARGET ROWS (work in this order):
- 2525 Expedia Group — Program Manager III (Workday: expedia.wd108.myworkdayjobs.com)
- 2526 Nintendo — IT Project Manager (ERPs)
- 2528 UST — Technical Program Manager
- 2537 Iceberg — Technical Account Manager
- 2538 World Wide Technology — Consulting Systems Engineer (Seattle) (ADP: myjobs.adp.com/wwtexternalcareersite)
- 2539 Sager Electronics — Sales Engineer (Power Supply Expert)
- 2540 Averro — Senior Sales Engineer
- 2547 Synectics Inc. — Program Manager

## HARD RULES
1. **10 MINUTES MAX per role.** No meaningful progress after 10 min → log + move on. Do NOT
   sink the whole run into one wall. Track wall-clock per role.
2. **COMMIT per role IMMEDIATELY** after finishing it (see SQL below) — fully resumable.
3. **UNSEEN screening questions → BEST JUDGMENT, lean toward advancing, SUBMIT.** Cyrus: "I'd
   rather it be wrong than do nothing." Applying != committing. BUT knockout FACTS stay truthful:
   - Work auth: authorized to work in US, **no sponsorship needed**, US citizen.
   - Clearance: none / "never held a clearance". Export/ITAR: cleared (US citizen).
   - Location: Kirkland, WA 98033. Relocation/onsite/travel/notice-period → answer YES/open.
   - Education: University of Houston, BS Computer Science, GPA 3.8, Aug 2021–Dec 2024.
   - Personal info source of truth: `personal-info.json` (root) + `role-discovery/personal-info.json`.
   - Resume to attach: `resume/Cyrus_Shekari_Resume.pdf`.
4. **Provisioning walls = log + move FAST (don't burn 10 min):** if a row resolves to a known
   dead wall — authed-LinkedIn, Lever hCaptcha-Enterprise, Ashby score-gate (Tessera/Atticus/
   Baseten/Tavus/Mercor/Klarity/Anrok class), DataDome/Akamai IP-bound, Eightfold Filestack
   resume-wall, Google-SSO — log it as provisioning-blocked with the SPECIFIC reason + move on.
5. **One browser submit at a time** — you ARE the only browser worker; don't spawn parallels.
6. Read `TOOLS.md` (esp. ATS runner facts + EXIT-code maps) and `MEMORY.md` DEBUNKED ledger
   BEFORE touching a runner, so you reuse known fixes/gotchas.

## HOW TO RESOLVE + SUBMIT each row
1. `web_search` "<company> <role> careers apply" and "<company> careers <ATS hint>". Identify the
   real ATS (Workday/Greenhouse/Ashby/Lever/ADP/iCIMS/SuccessFactors/etc.) + the direct job URL.
   Confirm the req is OPEN and matches the title. If you can't find a live matching req in ~4 min,
   treat as `closed/not-found` and move on.
2. Dispatch by ATS:
   - **Greenhouse / Ashby / Lever / Workday**: prefer `role-discovery/inline_submit.py` — but it
     keys off tracker `app_url`. First UPDATE the row's `app_url` to the resolved direct ATS URL,
     then run `inline_submit.py --role-id <id>` (it preps + dispatches). For GH/Ashby permissive
     tenants this can submit; Workday rows go PREP-READY-MANUAL (that's expected, log as such).
     Inspect the runner/dryrun helpers (`greenhouse_dryrun.py`, `ashby_dryrun.py`, `_gh_submit.py`,
     `_ashby_runner.py`, `_workday_runner.py`) and the EXIT-code maps in TOOLS.md.
   - **ADP / iCIMS / SuccessFactors / Oracle / custom**: no turnkey runner — drive via the
     `browser` tool (use the browser-automation skill at ~/.openclaw/plugin-skills/browser-automation/SKILL.md).
     Fill the whole form with the facts above, answer screening Qs per rule 3, attach the resume
     PDF, SUBMIT. Confirm on the ATS's own success route/text (NOT a generic "Thank you").
3. **Verify before claiming applied.** Only set status to a submit state when you OBSERVE a real
   confirmation (success URL/route, confirmation number, or a server success response). On success
   write `applications/submitted/<slug>/STATUS.md` (confirmation_url/text, submitted_by=auto,
   resume_attached=yes, what you answered for any novel screening Q).

## COMMIT SQL (run after EACH role)
SUBMITTED:
```
sqlite3 tracker.db "UPDATE roles SET status='applied', applied_by='auto', applied_on='2026-06-10',
  app_url='<resolved_url>', block_reason=NULL,
  agent_notes=COALESCE(agent_notes,'')||' | GRIND 2026-06-10: resolved <ATS> via open-web, SUBMITTED end-to-end. Answered <novel Qs>. Confirmation: <url/text>.'
  WHERE id=<id>;"
```
(the guard trigger requires status IN applied/submitted for applied_by — use 'applied'.)

BLOCKED / provisioning / closed:
```
sqlite3 tracker.db "UPDATE roles SET status='<blocked|closed>', block_reason='<specific-reason>',
  app_url='<resolved_url_if_any>',
  agent_notes=COALESCE(agent_notes,'')||' | GRIND 2026-06-10: resolved <ATS>=<url>; <what was attempted + exact wall>.'
  WHERE id=<id>;"
```
Keep `manual-apply` ONLY if it genuinely needs a human (e.g. account/SSO Cyrus must own) — and
say exactly why in the note.

## CHECKPOINT
Maintain `STATUS-grind-cohort.md` in the project dir: phase, role currently on, done list with
outcomes, next, blockers. Update every role or ~10 min so the parent can recover on timeout.

## REPORT
Append every blocked/manual row, GROUPED BY REASON (most-common first → one-offs), to
`BLOCKED-REPORT-2026-06-10.md`, clearly separating PROVISIONING-walled from genuinely-AI-exhausted.

## WHEN DONE
Reply with a terse summary: per-row outcome (id → SUBMITTED / BLOCKED:<reason> / CLOSED), count
submitted, count moved-on. That's it. Do NOT post to Discord (the parent will).
