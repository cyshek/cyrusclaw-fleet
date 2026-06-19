You are an isolated subagent for the job-search project. RESUME an in-progress engine fix.

WORKSPACE: /home/azureuser/.openclaw/agents/job-search/workspace
ENGINE DIR: /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery
VENV: projects/job-search/role-discovery/.venv/bin/python

## Mission
Finish + LIVE-validate the Workday cross-nav WORK-EXPERIENCE persistence fix so the WD auto-apply cohort
(Nvidia 2829, PayPal 2891, Boeing 2546, Gates 2542, HPE 2830, Nordstrom 1456, etc.) stops hitting EXIT-5
loop-cap. Phase 1 (root-cause diagnosis) is ALREADY DONE — do NOT re-derive it.

## Read FIRST (ground yourself — Phase 1 is done, build on it)
- projects/job-search/role-discovery/STATUS-we-persist-fix.md  <-- THE root-cause + fix design. Read fully.
- MEMORY.md DEBUNKED ledger (the 2026-06-11 Workday entry): TRUE root cause = block-COUNT never plateaus
  (resume PARSER re-spawns empty blocks + resume RE-UPLOAD re-runs the parser). NOT a date-persistence bug.
  The `start_filled=False` log line is a FALSE-NEGATIVE; dates DO persist.
- TOOLS.md -> Workday runner section (EXIT-code map; _RESUME_UPLOADED/_MAX_RESUME_UPLOADS; prefill-guard convergence).
- AGENTS.md -> "Browser Submit Concurrency" (you are the SOLE browser-submit worker) + subagent practices.
- _workday_runner.py (the live runner) AND its backup _workday_runner.py.bak.run4-wepersist (pre-edit last-good).
- Read >=10 related files (populate_work_history, the converge loop, click_next, resume-upload path, tests) before editing.

## Goal (Phase 2 implement + Phase 3 validate — both already SPEC'd in STATUS doc)
Phase 2 — implement the 3 fixes from STATUS-we-persist-fix.md:
  1. Make the resume-upload cap ACTUALLY hold: increment the seen-uploaded counter on the SKIP path too; on a
     FRESH account NEVER re-upload after visit 1 (typed WORK_HISTORY already carries content; re-parsing = pure harm).
  2. Add `harden_my_experience_before_next(page)`: bounded loop that DELETES every empty WE block + re-measures
     until 0-empty AND total stable across 2 consecutive checks (settle waits), called right before click_next on
     My Experience. Fill a lone non-deletable permanent empty once as last resort.
  3. Replace the lying `start_filled` read with the probe-proven multi-source read (value || aria-valuetext ||
     hidden input) so logs stop false-negativing. Keep the working date-persist logic UNTOUCHED.
Phase 3 — validate:
  - Add test_workday_we_persist.py covering the count-plateau + cap-holds behavior; keep the FULL Workday suite green
    (pytest test_workday*.py from role-discovery/).
  - LIVE re-run on Nvidia 2829 (true fresh account) end-to-end: dryrun/review FIRST to confirm My-Experience now
    advances past the WE step, THEN one real submit attempt. Capture EXIT code + confirmation evidence.
  - If green on Nvidia, do NOT mass-run the cohort — STOP and report; the parent decides the batch.

## Constraints (load-bearing)
- You are the SOLE browser-submit worker for this run. Do not spawn parallel browser submitters.
- Edits go to the LIVE _workday_runner.py but: backup already exists (.bak.run4-wepersist); keep changes additive +
  minimal; suite MUST stay green; git -C <workspace> add/commit the change (scan diff for secrets first).
- tracker.db: before stamping any row applied, make tracker.db.bak.<stamp>-wepersist. Standard submit bookkeeping
  (STATUS.md under applications/submitted/<slug>/ -> UPDATE roles -> render_xlsx.py) ONLY for a confirmed live submit.
- Fresh-account Workday apply is the DEFAULT path (never reuse polluted saved-profile prefill).
- Do NOT re-enable any cron. Do NOT touch SOUL.md/USER.md/HEARTBEAT.md/heartbeat-state.json. Do NOT post to Discord.
- On unresolvable ambiguity -> write ESCALATE.md and stop that item.

## Checkpointing (every 15min / major step)
Update STATUS-we-persist-fix.md (phase / done / next / blockers). Parent reads it on timeout.

## Deliverables (SHORT summary back to parent)
- Files modified (path + one-line each) + the new test.
- Phase 3 result: the EXACT Nvidia 2829 outcome (EXIT code, advanced-past-WE? submitted? confirmation evidence).
- VERDICT: is the WD cross-nav WE wall fixed? yes/no/partial + confidence.
- If fixed: which other WD rows are now ready to batch (Nvidia/PayPal/Boeing/Gates/HPE/Nordstrom...).
- NO Discord posts — parent handles channel updates.

## Budget
runTimeoutSeconds: 14400 (4h)
