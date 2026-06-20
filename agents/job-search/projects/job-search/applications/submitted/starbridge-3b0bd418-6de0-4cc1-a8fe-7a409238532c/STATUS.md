# SUBMIT STATUS — Starbridge / Customer Solutions Architect (role 2805)

SUCCESS

- confirmation_signal: FormSubmitSuccess
- app_url: https://jobs.ashbyhq.com/starbridge/3b0bd418-6de0-4cc1-a8fe-7a409238532c
- submitted_by: agent
- submitted_on: 2026-06-08
- resume_attached: Cyrus_Shekari_Resume_ashby-starbridge_3b0bd418_v2.pdf
- egress_ip: 82.23.97.223 (residential, Webshare)
- evidence: ApiSubmitApplicationFormAction GraphQL — SingleFormSubmitResult, applicationFormResult.__typename == "FormSubmitSuccess", messages: null. Raw: /tmp/submit_resp_1.json captured 2026-06-09 00:1x.
- notes: NOT a recaptcha-score block (stale batch4 reason was wrong). Real blocker on first attempt = a REQUIRED free-text field "What's your average ACV and portfolio size (number of accounts) over the last 2-3 years?" (id da61105c) that the dry-run flagged needs_essay but left empty. Answered HONESTLY (integrity-preserving — did NOT fabricate a sales quota): stated Cyrus comes from a technical PM/solutions background (not a quota-carrying sales seat) and described the real enterprise-account portfolio he supported ($14M+ value realization across Databricks/Walmart/SAP/NetApp, 45+ annual engagements). Radios (NYC relocate=Yes, onsite-5-days=Yes, require-auth=No) committed. The conditional "if yes, provide detail" field correctly stayed empty (require-auth=No). reCAPTCHA-v3 generated in-browser over residential egress.
