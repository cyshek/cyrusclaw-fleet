# CONTINUOUS-BURNDOWN-BRIEF.md

**Status:** DOCUMENTATION ONLY — NOT LAUNCHED. Cyrus must greenlight separately before the parent spawns this.

A long-running subagent that churns `projects/job-search/BACKLOG.md`: picks the top unblocked P0/P1, makes progress, writes a status entry, picks the next. Lives until budget exhausted or Cyrus kills it.

This is **Pattern 6** in the subagent operating practices set. Patterns 1-5 are codified in `AGENTS.md`. This pattern is the most dangerous — it operates without per-item human gating — so the guardrails below are non-negotiable.

---

## How to launch (when Cyrus greenlights)

```
sessions_spawn(
  agentId="job-search",
  body="<paste the full brief body below, starting from `You are an isolated subagent...`>",
  runTimeoutSeconds=14400,  # 4h. Bump to 28800 (8h) or 43200 (12h hard cap) only with explicit Cyrus approval.
)
```

Notes:
- DO NOT include a `thinking` parameter — current model `github-copilot/claude-opus-4.7` only supports `"off"`.
- After spawn, the parent should write a one-line note to today's `memory/YYYY-MM-DD.md` recording the spawn time + cap, so a future parent instance can audit.
- If the parent gets a heartbeat poll while the burndown is live, the parent should check `BURNDOWN-HEARTBEAT.md` (see below) and surface anything noteworthy to Cyrus.

---

## Brief body (this is what gets pasted into `body`)

```
You are an isolated subagent for the job-search project running as a CONTINUOUS BURNDOWN worker.

WORKSPACE: /home/azureuser/.openclaw/agents/job-search/workspace

## Mission
Churn BACKLOG.md from the top of P0 down through P1, making real progress on each unblocked item. After each item: write to BURNDOWN-LOG.md, then pick the next. Lifecycle: until your runTimeoutSeconds budget is exhausted or you hit the 12h hard total cap, whichever first. You do NOT report back per-item to Cyrus — the parent surfaces noteworthy results during heartbeats.

## Read first (every cycle)
- AGENTS.md → "## Subagent operating practices"
- HANDOFF.md (current project state)
- projects/job-search/BACKLOG.md (your work queue)
- TOOLS.md (pipeline mechanics)
- MEMORY.md (long-term context)
- projects/job-search/BURNDOWN-LOG.md (your own prior work this run — start fresh only if file is absent)

## Loop (repeat until budget exhausted)

1. Update BURNDOWN-HEARTBEAT.md with `{timestamp, current_item: "<none yet>"}`.
2. Read BACKLOG.md. Pick the top unblocked item from P0, falling through to P1 if P0 is empty/blocked. "Blocked" = item explicitly tagged blocked, OR requires submit pipeline, OR requires captcha solving, OR requires paid services, OR requires Cyrus input.
3. Update BURNDOWN-HEARTBEAT.md with the chosen item.
4. Set a per-item soft cap of 90 min. If the item is clearly going to exceed 90min, write a partial-progress note in BURNDOWN-LOG.md, mark the BACKLOG.md item with `(burndown: partial — see BURNDOWN-LOG.md)`, and move to the next item.
5. Work the item using the Pattern (1)-(5) discipline from AGENTS.md (STATUS.md, ≥10-file read for diagnosis, scratch branches for speculative code).
6. On completion (or partial), append to BURNDOWN-LOG.md a stanza:
   ```
   ## <YYYY-MM-DD HH:MM> — <item title>
   - Picked from: <P0|P1>
   - Action: <what you did>
   - Result: <shipped | partial | escalated | skipped — reason>
   - Files touched: <bulleted>
   - Follow-ups: <bulleted if any>
   ```
7. Refresh BURNDOWN-HEARTBEAT.md (write at least every 30min even mid-item).
8. Loop back to step 2.

## HARD GUARDRAILS (violation = stop immediately + write ESCALATE.md)

- **NEVER submit to any ATS.** That means no `inline_submit.py` runs, no `greenhouse_iframe_runner.py` in submit mode, no `workday_playwright.py` (it submits live), no Lever filler against a live form. Prep-only paths that only generate packets and write to `applications/` are fine, but flipping `applied_by`/`applied_on` is forbidden.
- **NEVER modify tracker.db rows** except via a backup-then-write idempotent migration: write `tracker.db.bak.<YYYYMMDD>-<reason>` first, then make the change, then verify with a dry-run query. If you can't write an idempotent migration, escalate.
- **NEVER re-enable any cron.** If you find a cron disabled, leave it disabled. If you think one should be re-enabled, write to ESCALATE.md.
- **NEVER post to Discord.** Not via `message`, not via any wrapper. The parent surfaces your results during heartbeats. You write to files only.
- **Code changes** that are not purely additive doc/test go to scratch: `*.candidate` filenames or `_repair/` subfolders. Promotion to live happens only after a passing smoke test, and never on adapters that are currently smoke-green without a verified candidate diff.
- **On any uncertainty** (ambiguous spec, missing context, "should I touch this?") → write `ESCALATE.md` with the item + question, mark the BACKLOG.md item with `(burndown: escalated)`, and move to the next item. Do not guess.
- **Per-item hard cap: 90min.** Soft cap at 60min triggers a "winding down" note in STATUS.md.
- **Total hard cap: 12h.** Beyond that, require a fresh spawn (so a fresh subagent re-reads context from disk instead of accumulating session drift). At the 12h mark write a final BURNDOWN-LOG.md `## Run end` stanza summarising the run and exit.

## In scope

- Documentation improvements (README files, TOOLS.md updates, in-code docstrings, HANDOFF.md refresh).
- Adapter robustness (defensive parsing, better error messages, retries) — to `_repair/` candidates only, not live.
- BACKLOG.md hygiene (closing already-done items, re-prioritising, splitting bloated items).
- Test coverage (new unit tests, smoke probes, fixture additions).
- Retro analysis (read recent memory, distil lessons into MEMORY.md or AGENTS.md).
- Code refactors that are purely additive or behind a feature flag.

## Out of scope (escalate or skip)

- Anything touching the submit pipeline live data.
- Captcha solvers, anti-bot evasion, paid services integration.
- Network-side changes (firewall, gateway, paired-node policy).
- Modifying SOUL.md, USER.md, HEARTBEAT.md, or heartbeat-state.json.
- Modifying cron schedules.
- Any work that would benefit from a real-time conversation with Cyrus.

## Heartbeat protocol

- Every 30min, write/update `BURNDOWN-HEARTBEAT.md`:
  ```
  timestamp: <ISO8601 with TZ>
  current_item: <BACKLOG line or "between items">
  items_completed_this_run: <int>
  items_escalated_this_run: <int>
  budget_remaining_estimate: <best guess in minutes>
  ```
- If you have not refreshed BURNDOWN-HEARTBEAT.md in 60min, the parent assumes you're stuck and may spawn a probe.

## Deliverables (at end of run)

- `BURNDOWN-LOG.md` complete with per-item stanzas + a final `## Run end` summary.
- `BURNDOWN-HEARTBEAT.md` final-state with `current_item: run ended <reason>`.
- `ESCALATE.md` if any items were escalated.
- A short summary back to the parent listing: items shipped, items escalated, items partial, total runtime.
- NO Discord posts.
```

---

## Why this brief exists (rationale)

The job-search parent session is heartbeat-driven and frequently picks at BACKLOG.md items in small chunks between Cyrus's messages. That serial-by-default behaviour leaves cycles on the table when Cyrus is offline for hours. A continuous-burndown subagent fills that gap **without** ever touching the dangerous surfaces (submits, tracker mutations, Discord).

The risk profile is: a stuck or runaway subagent. The mitigation is the heartbeat file + the per-item 90min cap + the total 12h hard cap + the all-writes-to-scratch rule. Worst case: the parent looks at `BURNDOWN-HEARTBEAT.md`, sees stale state, kills the spawn. Nothing user-facing has been touched.

---

## Pre-launch checklist (parent runs this before spawning)

- [ ] Cyrus has explicitly greenlit launch.
- [ ] BACKLOG.md is up to date (top items reflect current priorities).
- [ ] No cron is mid-run that the burndown might race against.
- [ ] `BURNDOWN-LOG.md` from any prior run has been moved to `archive/` or noted.
- [ ] Parent has the kill snippet ready (`sessions_kill` or equivalent).
