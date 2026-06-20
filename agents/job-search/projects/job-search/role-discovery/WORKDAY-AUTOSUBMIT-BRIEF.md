# WORKDAY AUTO-SUBMIT WIRE-UP + LIVE VALIDATION — Subagent Brief

**Goal (Cyrus directive 2026-06-09):** "I want to autosubmit Workday roles correctly." Make `inline_submit.py` actually SUBMIT Workday roles via the existing `_workday_runner.py` (fresh-account path → fills every field FRESH from the tailored resume, never trusts Workday saved-profile autofill), instead of short-circuiting to prep-only. Then PROVE it on live roles.

## What already exists (do NOT rebuild)
- `_workday_runner.py` (~2300 lines, MATURE): CLI `python3 _workday_runner.py --url <url> --tenant <t> --role-id <id> --resume <pdf> [--fresh-account] [--dryrun]`.
  - `resolve_account_for_tenant()` already defaults to **create_fresh** for ANY tenant (Cyrus 2026-06-08 global-fresh rule) → My Experience starts EMPTY, filled only from the tailored resume.
  - Exit-code map: 0=submitted/dryrun-review · 2=sign-in/account block · 3=submit-no-confirm · 4=can't-click-submit · 5=loop-cap · 6=req CLOSED · 7=ALREADY_APPLIED · 8=My-Info dropdown won't commit · 9=profile-prefill uncommittable date.
  - Account creation works in-flow, no email-verify (Nordstrom proof). Creds persist to `.workday-creds.json` (per-tenant fresh_alias).
- 9 workday test files (~66 tests incl. `test_workday_fresh_account.py`=21). KEEP THEM GREEN.
- `inline_submit.py` ALREADY tailors the resume for Workday rows (prep_role_workday builds JD files + would produce a tailored PDF). Reuse that tailored PDF as the runner's `--resume` arg.

## THE GAP (your core task)
`inline_submit.py` line ~1894: `if role.get("ats") == "workday": return prep_role_workday(...)` — this short-circuits to PREP-ONLY and NEVER calls `_workday_runner.py`. Wire it so Workday rows actually attempt a submit via the runner.

## Phase 1 — WIRE (engine edit, test-gated)
1. Read `prep_role_workday()` + the Workday tailoring path in `inline_submit.py` fully first (how it builds the tailored PDF + resolves tenant/url/reqid). Read `_workday_runner.py` `run()` + `__main__` to learn its exact arg contract + return semantics.
2. Add a real submit path: after Workday prep produces the tailored PDF, invoke `_workday_runner.py` via subprocess (mirror how Rippling/other runners are dispatched in inline_submit — there's a `prep_role_rippling` + runner-CLI pattern at lines ~803-1043). Pass `--url --tenant --role-id --resume <tailored.pdf> --fresh-account`. Respect a `--dryrun`/`--no-submit` passthrough so dryrun stays prep-only.
3. Map the runner exit code → tracker bookkeeping, REUSING the existing convention:
   - 0 → verify confirmation on DISK + DB + confirmation route (NOT a text-match), then `applied_by='auto', applied_on=today`, write `applications/submitted/<slug>/STATUS.md`.
   - 6 → status='closed'. 7 → already-applied (mark applied, note it). 2/3/4/5/8/9 → leave actionable + write `agent_notes` BATCH tag with the exit reason (e.g. `BATCH workday-exit9-prefill-uncommittable`). Prep-only fallback (PREP-READY-MANUAL) stays as the path when the runner can't proceed (CSP-captcha class, maintenance).
4. Keep prep-only reachable behind a flag (e.g. `--workday-prep-only`) for debugging / known-walled tenants.
5. **Add a regression test** (`test_workday_inline_submit_wire.py` or extend an existing one): assert that an `ats=='workday'` role with submit enabled CALLS the runner (mock subprocess) and that exit-code→DB-status mapping is correct (0→applied, 6→closed, 9→actionable+BATCH-tag). Mock the subprocess — do NOT hit a live browser in the unit test.
6. `pytest -q` MUST stay green (~945 baseline). COMMIT the engine edit to git (content-scan the diff for secrets FIRST — no creds/cookies/keys). The workspace root is a git repo; `git -C <workspace> add <files> && commit`.

## Phase 2 — LIVE VALIDATION (you own the SINGLE browser slot)
Validate on the 3 live actionable rows, ONE AT A TIME, bank-and-stop after each:
- **2891 PayPal** (Product Manager 2 - Technical) — currently prep-only/manual_ready, best first candidate.
- **2265 Thomson Reuters** (Product Manager) — currently 'blocked'.
- **2358 GEICO** (Technical Program Manager) — currently 'blocked'.
For each: `inline_submit.py --role-id <id>` (now routing through the runner). Watch it create a fresh account → fill My Info + Work Experience FRESH from the tailored resume → submit. **VERIFY the submit landed on the real confirmation route (URL contains /confirmation or an explicit "application submitted" + form gone), NOT a "Thank you" text-match** (a text-match false-positive cost a bogus applied before). On success: bookkeeping as above + regen `render_xlsx.py`. On a runner wall: capture the exact exit code + a BATCH `agent_notes` tag, move on. Update `STATUS-WORKDAY-AUTOSUBMIT.md` after EVERY row.

## Phase 3 — wrap
- If wiring + at least one live submit works: update `MEMORY.md`/`TOOLS.md` (flip the "Workday = prep-only" standing note to "Workday auto-submits via `_workday_runner.py` fresh-account path"; keep the prep-only fallback note). Update `BACKLOG.md` (move to Recently-shipped). Append a summary to `memory/2026-06-09.md`. Terse Discord one-liner to channel `1501827950474166332` on each shipped milestone + final.

## RULES
- ONE browser-submit at a time (you own it). cwd=role-discovery/, venv `.venv/bin/python`, DB `../tracker.db`.
- Truthful knockouts always (work-auth/clearance/citizenship) even if it costs the submit. Essays/motivation may be auto-generated.
- DB backup + `PRAGMA integrity_check` before any bulk write.
- Self-preservation: SMALL bank-and-stop increments, run each live submit under a `timeout` wrapper, update STATUS after every row, do NOT hold a long open DOM/poll tail — if you feel context getting large, write a crisp RESUME-FROM note into STATUS and stop cleanly; a fresh session finishes.
- If you hit a genuine wall needing spend/credential/irreversible action, LOG it for triage and continue — don't block the whole task on one row.
