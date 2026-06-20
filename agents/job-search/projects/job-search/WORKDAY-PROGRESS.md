# WORKDAY-PROGRESS.md — Workday integration workstream

## STATUS — 2026-05-16

**Option B shipped.** Prep-only Workday pipeline is in place. Auto-submit is
not implemented (and won't be unless the role count materially grows — see
"Why not full auto" below).

## What's running

- `role-discovery/workday_dryrun.py` — JD-fetch via Workday CXS detail
  endpoint. Emits prep-only spec with `ready_to_submit: false, blockers:
  ["workday-form-fill-not-implemented", ...]`. Maintenance-mode aware.
- `role-discovery/migrate_prep_status_column.py` — added `prep_status` +
  `prep_path` columns to `roles`. Already applied.
- `role-discovery/inline_submit.py` — extended to dispatch `*.myworkdayjobs.com`
  URLs into `prep_role_workday()`. No browser plan; writes
  `applications/submitted/<slug>/STATUS.md` (`PREP-READY-MANUAL` or
  `MAINTENANCE_RETRY`) and flips `tracker.roles.prep_status='manual_ready'`
  on success.
- `role-discovery/render_xlsx.py` — new **Manual Ready** sheet (amber-900
  header) listing prepped-but-unsubmitted Workday packets.

See `TOOLS.md > "Workday (prep-only — 2026-05-16)"` for the command summary
and the manual-submit bookkeeping flow.

## Smoke test 2026-05-16 06:51 UTC

Workday is **still in maintenance mode** at smoke-test time — every CXS
endpoint 303-redirects to `https://community.workday.com/maintenance-page`
(reproduced against adobe, nvidia tenants).

Smoke result on Adobe role id 9 (Engineering Product Manager):
- `inline_submit.py --role-id 9` → ABORT(maintenance-retry) in 0.3 s
- `applications/submitted/adobe-r163295/`: JD.md (placeholder body),
  meta.json, prefill.json, STATUS.md = `MAINTENANCE_RETRY` (full reason
  + http_status + final_url).
- `tracker.db`: `prep_status` left NULL (correctly — packet is incomplete,
  next run will retry).
- Zero LLM credits burned.

End-to-end LLM-tailoring path (bullet_rewriter + cover_answer_generator)
will validate on the next cron run after Workday is restored. Code is
written; only the live JD body is missing to exercise it.

## Why not full auto-submit (Option C rejected)

- ~15 open Workday roles across 5 tenants → ~30 min engineering effort
  saved per role would need ~25 h initial build = bad ROI.
- Workday's per-tenant variability (different widget versions, different
  account flows, MFA, file upload mechanics) means the build is fragile
  and per-tenant maintenance burden is real.
- Workday is also outage-prone (current global maintenance window is a
  representative example).

If the Workday role count ever crosses ~50 or a top-tier strategic role
appears, revisit. Threshold for re-evaluation: 50 open Workday roles or
3 Anthropic-tier roles on a single tenant.

## Backward compat / semantics

`applied_by` / `applied_on` semantics are unchanged — they still mean
"submitted" (auto or manual). `prep_status` is orthogonal:

| prep_status     | applied_by | meaning                                 |
|-----------------|------------|-----------------------------------------|
| NULL            | NULL       | open, never touched                     |
| `manual_ready`  | NULL       | Workday packet ready, Cyrus to submit   |
| `submitted`     | `manual`   | Cyrus submitted, packet existed         |
| NULL            | `auto`     | auto-submitted (Greenhouse/Ashby/etc.)  |
| NULL            | `manual`   | Cyrus submitted by hand (no packet)     |

Manual-submit bookkeeping after Cyrus clicks Submit on a Workday role:

```sh
sqlite3 projects/job-search/tracker.db \
  "UPDATE roles SET applied_by='manual', applied_on='YYYY-MM-DD', \
   prep_status='submitted' WHERE id=<id>"
projects/job-search/role-discovery/.venv/bin/python \
  projects/job-search/role-discovery/render_xlsx.py
```

Row drops off Manual Ready, appears on Applied.
