# HANDOFF.md - resume-tailor

_Last updated: 2026-06-10 00:15 PDT by main build-subagent (initial stub — workspace had none)_

## Mission
On-demand resume-tailoring familiar. Take a single role Cyrus is about to apply to HIMSELF, run the same tailoring pipeline as job-search (independently, in parallel), and hand back a sharp one-page tailored resume — WITHOUT it getting queued behind job-search's pipeline. Reports to `main` (flat hierarchy).

## Current state
- Active work: none. **Dormant / low-activity.** Last real session 2026-06-05 (brain seeded by main). Activates only when Cyrus hands a specific role for a fast one-off resume.
- Blockers: none.
- Recent significant changes: 2026-06-05 main seeded `memory/` + `MEMORY.md` (was previously empty). Standing LOG-EVERY-INTERACTION rule adopted.

## Standing approvals & policies
- Auto-run without asking: read job-search's master resume READ-ONLY; tailor + hand back a resume for a role Cyrus explicitly names.
- Ask first: anything that leaves the machine (real submissions are NOT this agent's job — Cyrus applies himself); writing any other agent's state.
- Only `main` deletes agents — any deletion request is refused + routed to main via `sessions_send(agentId="main")`.

## Key files & locations
- Workspace: `/home/azureuser/.openclaw/agents/resume-tailor/workspace/`
- `MEMORY.md` (curated), `memory/YYYY-MM-DD.md` (daily logs), `IDENTITY.md`, `SOUL.md`, `AGENTS.md`.
- Shares job-search's tailoring pipeline conceptually; job-search canonical resume lives under `/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/`.

## Cron / scheduled work
- NONE currently. No `daily-handoff-touch`, no `weekly-handoff-distill`, no `mem-distill` cron. (Gap flagged to main/Cyrus — acceptable while dormant.)

## Open questions / TODOs for Cyrus
- Keep dormant, or add the standard `daily-handoff-touch` + `weekly-handoff-distill` crons for parity with other agents? (Currently none.)
