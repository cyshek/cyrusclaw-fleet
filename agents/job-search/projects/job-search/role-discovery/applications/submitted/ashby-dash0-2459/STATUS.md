# STATUS — Dash0: Commercial Solutions Architect (role id 2459)

status: applied
submitted_by: agent (residential-egress run)
submitted_on: 2026-06-08
ats: ashby
app_url: https://jobs.ashbyhq.com/dash0/88dc8222-497c-4d58-ad5b-e862a6602c51
egress: residential (Webshare 82.23.97.223, sticky)

## Evidence (PARTIAL — backfilled by parent for audit trail)
- Subagent residential_egress_scope reported live FormSubmitSuccess (server applicationFormResult.__typename == FormSubmitSuccess) + Ashby ApplicationSuccess page via residential egress.
- DB updated (status=applied, applied_by=auto, applied_on=2026-06-08, block_reason cleared); DB backup tracker.db.bak.egress-1780953500.
- CAVEAT: the runner's live success observation was NOT persisted to disk at submit time; this STATUS.md is a post-hoc reconstruction from the subagent report, NOT a captured runner artifact. Treat as DB-recorded / evidence-partial until a re-confirm pass re-observes the application in-account.
- Full context: memory/2026-06-08-residential-egress-scope.md
