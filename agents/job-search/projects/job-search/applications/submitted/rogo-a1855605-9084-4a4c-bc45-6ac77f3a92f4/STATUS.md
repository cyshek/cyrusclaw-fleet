SUBMITTED — 2026-06-08T19:02:19+00:00

role_id: 2904
company: Rogo
role: Product Manager | Enterprise (Ashby)
ats: ashby
applied_by: agent
applied_on: 2026-06-08

verification: HONEST — Ashby returned applicationFormResult.__typename=
"FormSubmitSuccess" on the SECOND submit POST (POST #1 was the autofill-clobber
FormRender "Missing entry: Location"; the chain_p11 guard reasserted Location +
work-auth and the re-submit was ACCEPTED). FormSubmitSuccess is Ashby's
definitive accept token. Page body confirmed the "Product Manager | Enterprise"
role. NOTE: the runner initially exited 1 due to a classifier race (it read the
early error POST before the trailing success POST landed) -- that classifier
false-negative is now FIXED via scan_form_submit_success() (success-anywhere-wins
+ wait-for-trailing-POST). NOT re-submitted, to avoid a duplicate application.
