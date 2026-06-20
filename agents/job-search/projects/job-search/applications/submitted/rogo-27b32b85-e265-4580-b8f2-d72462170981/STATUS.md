SUBMITTED — 2026-06-08T18:53:44+00:00

role_id: 2475
company: Rogo
role: Solutions Architect (Ashby)
ats: ashby
applied_by: agent
applied_on: 2026-06-08

verification: HONEST — Ashby ApiSubmitMultipleFormsAction GraphQL final response
returned NO errorMessages, NO blockMessage, NO spam-flag (classify=submitted,
"server: no errors, no block"). First POST hit the autofill-clobber ("Missing
entry for required field: Location"); the new chain_p11 final_clobber_guard then
settle-refilled Location (picked option "Kirkland, Washington, United States")
and re-asserted work-auth, and the SECOND POST was accepted clean.
fix: chain_p11 final_clobber_guard in _ashby_runner.py.
