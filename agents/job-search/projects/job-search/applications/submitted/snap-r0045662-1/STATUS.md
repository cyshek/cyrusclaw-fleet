STATUS: REQ-CLOSED
closed_at: 2026-06-20T20:54:00+00:00
exit_code: 6

role_id: 2925
ats: workday (tenant: snapchat)
company: Snap
role: Technical Program Manager, Level 4
location: New York, New York

The Workday runner returned EXIT 6 (req CLOSED/removed). The job listing page
returns HTTP 200 but the application flow indicates the req is no longer accepting
applications. CXS API returns 403 for this role (may be geo-restricted or closed).

Tracker updated: status=closed, block_reason=req-closed-workday-exit6, prep_status=closed
