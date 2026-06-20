# BURNDOWN V2 — PAUSED on startup (architecture mismatch)

**Timestamp:** 2026-05-24 ~12:00 PDT
**Spawned-as:** subagent (depth 1/1) under requester `agent:job-search:discord:channel:1501827950474166332`
**Subagent session:** `agent:job-search:subagent:f71f0e46-3b75-40e5-9e60-498aebc52fa3`

## What happened

The CONTINUOUS-BURNDOWN-V2 orchestrator was spawned as a **leaf subagent** (depth 1/1), but the brief's design requires it to spawn one worker subagent **per role** via `sessions_spawn`. My current tool set does **not** include `sessions_spawn` — only `sessions_yield`. Leaf subagents cannot spawn children. Confirmed by inspecting the available tool list and by Subagent Context line: `depth 1/1`.

This is an orchestration-layer misconfiguration, not a content/queue issue.

## What I did NOT do (deliberately)

- Did NOT try to fake it by serializing all worker logic inline in this single session. The brief says workers get 3hr each and a fresh context. Doing 148 roles inline in one context would (a) blow my context budget after ~5-15 roles, (b) destroy the "fresh context per role" property that the V2 redesign was built around, and (c) silently produce a worse outcome than V1.
- Did NOT post the "Burndown V2 starting" message yet — would have been a lie given I can't actually loop.

## What I DID do

- Read CONTINUOUS-BURNDOWN-V2.md, MEMORY.md head, TOOLS.md head.
- Verified queue: **148 roles** (skip-blocked Apple/Google/Meta/MS already filtered). Of those:
  - 64 LinkedIn manual-apply (pre-blocked, agent_notes path)
  - 55 Ashby (reCAPTCHA wall — MEMORY.md 2026-05-14)
  - 6 Lever (hCaptcha visible — MEMORY.md 2026-05-13)
  - 1 Greenhouse
  - 27 "other" (Workday/iframe/custom — mostly the actionable pool, plus the new Stripe specialist SAs)
- Backed up `tracker.db` to `tracker.db.bak.20260524-burndown-v2` (per startup checklist).
- Did NOT mutate any role rows.

## How to unblock

Cyrus / main agent needs to re-spawn the orchestrator with **spawn-capable depth** (depth 0 from main, or whatever parent context exposes `sessions_spawn`). The brief itself is fine; only the spawn site was wrong.

Two reasonable re-spawn shapes:

**(a) Orchestrator runs in `main` (the Discord-DM agent).** Easiest — main has full spawn capability. `main` reads CONTINUOUS-BURNDOWN-V2.md and executes the loop, spawning each per-role worker via `sessions_spawn`.

**(b) Orchestrator stays as a job-search-side detached job, but spawned with parent-style tools.** Whatever OpenClaw config exposes `sessions_spawn` to a child subagent — flip that on for this spawn shape.

## Additional notes worth knowing before re-spawn

1. **Real actionable pool is ~28, not 148.** The other 120 are pre-known blocked (LinkedIn auth wall, Ashby/Lever captcha wall). The V2 brief says "no blanket skip — try anyway", which is fine, but Cyrus should know the realistic submit ceiling per loop pass is ~10-25 roles, not 148. Workers attempting captcha-walled roles will mostly land on `BLOCKED: captcha-hard | hCaptcha visible challenge — needs CapSolver $20 funded`.

2. **CapSolver is the single highest-leverage unblock.** Funding the CapSolver API key (~$20 one-time, documented in `CAPTCHA-SOLVER-DECISION.md`) would convert ~60 of the 120 blocked roles into actionable submits. Worth doing **before** the burndown re-runs, not after.

3. **Workday roles need account-creation work for non-Adobe tenants.** Per MEMORY.md 2026-05-17: Adobe is validated end-to-end; PayPal/Nvidia/Intel/HPE/etc. need either pre-created accounts or per-tenant My-Information selector work. Workers attempting these will mostly land on `BLOCKED: account-required` or `BLOCKED: tenant-unsupported`. This is fine; the agent_notes will be specific and Cyrus can decide whether to invest in tenant work or not.

4. **The 1 Greenhouse role + the 27 "other" non-LinkedIn rows are the high-yield seed batch.** A one-shot loop over just those (~28 roles) would likely produce 10-20 submits in 1-3 hours of wall-clock if a spawn-capable orchestrator drove it.

## Files touched

- `projects/job-search/tracker.db.bak.20260524-burndown-v2` (backup, no mutation)
- this file

## Files NOT touched

- `tracker.db` rows: no UPDATE/INSERT
- `MEMORY.md`, `HANDOFF.md`: no append (will let the re-spawn or main write the official entry)
- `applications/_burndown-v2-log.md`: not created (loop never ran)

## Recommendation

1. Cyrus / main: re-spawn the orchestrator from a context where `sessions_spawn` is available, OR run the loop directly from main.
2. Optionally fund CapSolver first (one-line memo in `CAPTCHA-SOLVER-DECISION.md`).
3. Consider trimming the brief's "try every Ashby/Lever anyway" guidance until CapSolver is funded — saves ~60 workers × ~5min of context-burning to land on the same known blocker.
