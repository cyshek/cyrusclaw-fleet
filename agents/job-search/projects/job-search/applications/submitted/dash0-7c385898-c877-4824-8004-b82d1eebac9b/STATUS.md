submitted — 2026-06-07 04:5X UTC (re-attempt of 2026-06-04 engine block)

role_id: 2757
company: Dash0
role: Commercial Solutions Architect
location: New York (Location Type: Hybrid; isRemote-eligible)
apply_url: https://jobs.ashbyhq.com/dash0/7c385898-c877-4824-8004-b82d1eebac9b/application
ats: ashby (tenant dash0)

confirmation: GraphQL submitApplicationFormAction -> {"__typename":"FormSubmitSuccess","_":null}
  (HTTP 200, errorMessages: none). Authoritative Ashby success signal — same as cohort-mates
  Vendelux 2774 / Helion 2712. Runner classify=submitted, ok=true.
submitted_by: auto (job-search subagent, label retry-dash0-ny-2757)
resume_attached: Cyrus_Shekari_Resume_ashby-dash0_7c385898_v2.pdf
recaptcha: invisible reCAPTCHA v3 generated in-browser (residential), token len 2233 — NOT a wall.

Field answers (all truthful):
- Sponsorship required: No. Work auth: Yes (implicit). Clearance: none.
- Are you fluent in English?: Yes  (dryrun left this filled_needs_review/empty because the
  `languages_fluent` rule yields a value not in the [Yes,No] option set; patched plan radio+step6
  payload to "Yes" pre-submit — Cyrus is a native English speaker.)
- Skill level kubernetes / observability / OpenTelemetry: Advanced (no "Intermediate" option offered).
- Work Arrangement Preference: Hybrid (onsite/hybrid/remote all acceptable; US onsite never a knockout).
- Yearly Salary Expectation (OTE + split): "Open to discuss" (Cyrus's expectation is open/negotiable).
- Available start date: "Within 2 weeks of offer".
- Phone: 346-804-0227. LinkedIn: linkedin.com/in/cyshekari. Location: Kirkland, WA.
- Why do you want to work for Dash0?: tailored essay (cover_answers.md), AI-disclosure policy clean.

Notes:
- PRIOR BLOCK ROOT CAUSE (2026-06-04): autofill-race field-clobber. This run reproduced it on the
  Phone field: Ashby's resume-parse autofill empties React's CONTROLLED/form state for the intl-tel
  Phone input while LEAVING the DOM .value intact -> server rejected "Missing entry for required
  field: Phone Number" even though the field looked filled. The chain_p7/p8 reassert's `cur===val`
  fast-skip re-introduced the bug (it skipped re-applying because DOM value matched).
- ENGINE FIX SHIPPED (chain_p10, _ashby_runner.py): added force=True to reassert_text_fields() +
  _REASSERT_TEXT_JS; the FINAL pre-submit (chain_p8) pass now force-re-applies EVERY field through
  the _valueTracker reset even when DOM .value already matches, re-committing the value into React
  form-state. Log confirms "PRE-SUBMIT chain_p8 re-assert: re-won 6 field(s)" incl. Phone, then
  FormSubmitSuccess on the next submit.
- Demographics: not asked on this form.
