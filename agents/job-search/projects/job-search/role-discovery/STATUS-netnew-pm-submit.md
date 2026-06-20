# STATUS — netnew_pm_submit subagent

**Updated:** 2026-06-08 ~14:32 PDT — RUN COMPLETE

## Phase
DONE — all 4 net-new GH PM roles SUBMITTED + DB-stamped + STATUS.md written. Final integrity_check=ok.

## Roles (all confirmed on-page)
- 2675 FanDuel — Product Manager - Poker — gh_jid=7954862 — ✅ SUBMITTED
- 2676 FanDuel — Product Manager, Sportsbook — gh_jid=7952051 — ✅ SUBMITTED
- 2893 Datadog — Product Manager II, AI & Data Security — gh_jid=7982288 — ✅ SUBMITTED
- 2894 Okta — Product Manager - Agentic AI — gh_jid=7982658 — ✅ SUBMITTED

## Real submits this run
- 4 / 4

## DB backups created (before each write)
- tracker.db.bak.netnew-pm-submit-1780953098
- tracker.db.bak.netnew-pm-submit-1780953507
- tracker.db.bak.netnew-pm-submit-1780953887
- tracker.db.bak.netnew-pm-submit-1780954293

## Blockers
- None.

## Engine/data notes (for parent → TOOLS.md / LABEL_RULES candidates)
- **FanDuel GH embed (for=fanduel)**: the two location/relocation needs-review dropdowns MIS-RESOLVE to the candidate's home city ("Kirkland"/"Kirkland, WA"), which matches NO option → field stays empty → emptyRequired bounce. Correct pattern: within-120mi="None", willing-to-relocate="Yes". Cohort-wide for FanDuel (identical on 7954862 + 7952051). Good LABEL_RULES candidate so future FanDuel rows don't need a hand-fed --answers.
- **Datadog GH embed**: required "In what cities are you available to work?" multi_value_multi_select is NOT placed in plan['dropdowns'] nor needs_review_dropdowns → stays empty → would bounce. Had to force via --answers multiselect (all 10 US-hub tags landed incl. New York City). Possible general gap: required multi_value_multi_select fields aren't auto-committed by _gh_submit's main passes (only the Raft multiUnset live-scan catches some).
- **Okta GH embed**: dryrun "3 unresolved" was a red herring — cover_letter file (engine generated+uploaded), hidden lat/long (location typeahead), and 2 conditional follow-ups (required:false). Required acknowledgment + optional consent are CHECKBOXES (not react-select) → CONSENT step auto-ticked both (verified live).
- **No fanduel.careers wrapper bounce**: submitting via the canonical `job-boards.greenhouse.io/embed/job_app?for=<org>&token=<jid>` URL (NOT the fanduel.careers wrapper) worked cleanly. The earlier ~75–109s "hang" is just slow JD prep, not a wrapper problem.
