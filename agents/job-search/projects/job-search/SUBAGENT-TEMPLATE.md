# SUBAGENT-TEMPLATE.md

Canonical brief template for job-search subagent spawns. Copy this file, fill the placeholders, paste into the spawn body. Don't free-form — the constraints below are load-bearing.

Companion policy: `AGENTS.md` → "## Subagent operating practices".

---

## Spawn snippet (copy this)

```
sessions_spawn(
  agentId="job-search",
  body="<paste the filled-in brief below>",
  runTimeoutSeconds=<3600|7200|14400>,
  # Resume from: <path-to-RESUME-FROM.md>   # include only if applicable
)
```

Budget guidance:
- Small (one focused edit / single diagnostic pass): **3600** (1h)
- Medium (multi-file change, single-adapter repair, doc+code combo): **7200** (2h, default)
- Large (cross-cutting refactor, multi-adapter sweep, new component): **14400** (4h)

When unsure, pick the next tier up. Oversize is free; timeout mid-edit is expensive.

---

## Brief body template

```
You are an isolated subagent for the job-search project.

WORKSPACE: /home/azureuser/.openclaw/agents/job-search/workspace

## Mission
<one line — what's the end state?>

## Read first
- AGENTS.md
- HANDOFF.md
- TOOLS.md → <relevant section>
- <other paths the subagent needs to ground in>
<For diagnosis tasks add: "Read ≥10 related files before patching.">

## Goal
1. <numbered step>
2. <numbered step>
3. ...

## Phase structure (for multi-phase work)
- Phase 1: <name + exit criterion>
- Phase 2: <name + exit criterion>
- ...

If you hit a logical break (end of phase, blocker needing human input, scope expansion),
write `RESUME-FROM.md` (in your working area) containing the next-phase prompt verbatim
so a follow-up subagent can resume cleanly.

## Constraints (always include)
- DO NOT submit to any ATS (no inline_submit, no greenhouse_iframe_runner submits, no workday_playwright submits).
- DO NOT re-enable any cron job.
- DO NOT destructively modify tracker.db without first creating a `tracker.db.bak.<stamp>-<reason>` backup.
- DO NOT post to Discord unless this brief explicitly instructs you to (with a specific channel/recipient).
- DO NOT touch SOUL.md or USER.md.
- DO NOT modify HEARTBEAT.md or heartbeat-state.json.
- Code changes that are speculative go to scratch (`*.candidate`, `_repair/`, or a clearly-marked draft path) — never overwrite live adapters or pipeline scripts without a passing smoke test.
- On any unresolvable ambiguity → write `ESCALATE.md` describing the choice and stop that item.

## Checkpointing rule (always include)
Every 15min or after every major step, write/update `STATUS.md` with:
- **phase** — which phase you're in
- **what's done** — bulleted, concrete
- **what's next** — the very next concrete action
- **blockers** — anything you need from the parent / Cyrus

If you time out, the parent reads STATUS.md to recover.

## Deliverables (final summary back to parent)
- Files added/modified (path + one-line description each)
- Outcome vs goal (what shipped, what didn't, why)
- Any open follow-ups for the parent to track
- NO Discord posts unless this brief specifically instructed a post with a target channel.

## Budget
runTimeoutSeconds: <3600 | 7200 | 14400>   <!-- match to mission size -->
```

---

## Parallel-exploration variant (Pattern 5)

When the parent has ≥2 plausible hypotheses for a diagnosis, spawn 2-3 subagents in parallel using the template above, but in each one's `## Mission` line, pin a single hypothesis:

> Mission: Investigate **only** hypothesis <A|B|C>: "<one-line hypothesis>". Do not pivot to other hypotheses; another subagent owns those. Time-box to 60min. Output a one-page diagnosis with evidence + confidence level (low/med/high).

Set `runTimeoutSeconds: 3600` on each. Merge the winning diagnosis into one follow-up shipping subagent.

---

## Anti-patterns (don't do these)

- Spawning a subagent for something <5min of parent work.
- Spawning without specifying constraints (the boilerplate above isn't optional).
- Spawning to reply to Cyrus — subagents don't carry the parent's channel.
- Spawning without a STATUS.md/RESUME-FROM.md requirement.
- Setting `runTimeoutSeconds < 3600` "to be safe" — that's how mid-edit timeouts happen.
- Including a `thinking` parameter — current model `github-copilot/claude-opus-4.7` only supports `"off"`. Revisit when a future model adds higher levels.
