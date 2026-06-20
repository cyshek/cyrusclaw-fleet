# STATUS — Notion: Employee Experience Program Manager (role id 2888)

status: applied
submitted_by: agent (residential-egress run)
submitted_on: 2026-06-08
ats: ashby
app_url: https://jobs.ashbyhq.com/notion/c2299d80-c3a5-45fa-bf49-29372a4d9aec
egress: residential (Webshare 82.23.97.223, sticky)

## Evidence (PARTIAL — backfilled by parent for audit trail)
- Subagent residential_egress_scope reported live FormSubmitSuccess (server applicationFormResult.__typename == FormSubmitSuccess) + Ashby ApplicationSuccess page via residential egress.
- DB updated (status=applied, applied_by=auto, applied_on=2026-06-08, block_reason cleared); DB backup tracker.db.bak.egress-1780953500.
- CAVEAT: the runner's live success observation was NOT persisted to disk at submit time; this STATUS.md is a post-hoc reconstruction from the subagent report, NOT a captured runner artifact. Treat as DB-recorded / evidence-partial until a re-confirm pass re-observes the application in-account.
- Full context: memory/2026-06-08-residential-egress-scope.md
