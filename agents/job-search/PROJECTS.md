# Projects

Index of active projects in this workspace. Read this on session startup if it isn't already in the provided context.

## Active

### `projects/job-search/`

Cyrus's active job search. Master resume, ~110 target companies grouped by
cluster, per-company research and application drafts, status tracker. Read
`projects/job-search/PROJECT.md` for the project brief and operating rules.
**Never submit an application without explicit approval from Cyrus.**

This agent (`job-search`) is dedicated to this project — it was split out from
the `main` agent on 2026-05-01 for context isolation. The `main` agent no
longer owns this project.

#### `projects/job-search/role-discovery/` (added 2026-05-06)

Automated daily crawler that hits Greenhouse / Ashby / Lever / Workday /
SmartRecruiters / Microsoft / Apple / Google / Meta job boards, filters for
PM / TPM / SE / SA / CE / FDE roles in the US (entry-to-mid level), and writes
JSON output. Originally built on Cyrus's Windows machine; migrated to the VM
on 2026-05-06 and now runs daily via cron.

Read `projects/job-search/role-discovery/OPERATIONS.md` for cron schedule,
venv layout, and how to invoke the tools manually. The auto-application
("apply-bot") side of the project was archived 2026-05-06 — only discovery
remains.

## Archived

_(none yet)_

## Future projects

Future OpenClaw projects should be registered as **separate agents**, not
nested in this workspace. To add a new agent:

1. Add an entry to `~/.openclaw/openclaw.json` under `agents.list` with a
   unique `id` and its own `workspace` and `agentDir` paths.
2. Create the matching directories under `~/.openclaw/agents/<NAME>/`.
3. Bootstrap the new workspace with its own `IDENTITY.md`, `SOUL.md`,
   `USER.md`, `PROJECTS.md`, `TOOLS.md`.

This keeps each project's context, auth profile, sessions, and memory
isolated from this one.
