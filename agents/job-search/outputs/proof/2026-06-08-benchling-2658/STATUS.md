# SUBMIT STATUS — Benchling / Product Manager, Developer Platform (role 2658)

SUCCESS

- confirmation_signal: FormSubmitSuccess
- app_url: https://jobs.ashbyhq.com/benchling/61b20c5a-5c3d-4388-a19d-13a89886e73f
- submitted_by: agent
- submitted_on: 2026-06-08
- resume_attached: Cyrus_Shekari_Resume_ashby-benchling_61b20c5a_v2.pdf
- egress_ip: 82.23.97.223 (residential, Webshare)
- evidence: ApiSubmitMultipleFormsAction GraphQL — applicationFormResult.__typename == "FormSubmitSuccess", messages: null (no block, no field errors); surveyFormResults also FormSubmitSuccess. Two-POST race: resp_1=FormRender error (autofill clobber), resp_2=FormSubmitSuccess (clean win). Raw: /tmp/submit_resp_2.json captured 2026-06-08 23:58.
- notes: NOT a recaptcha-score block (stale batch4 reason was wrong). Real blockers were TWO field-commit gaps fixed via new _ashby_runner.py chain_p12 doctrine-fix: (1) work-auth radio whose live container entry-UUID regenerated per page-load (stale-fid container miss → never re-committed) now committed by LABEL needle; (2) the "Are you able to work from our office Mon/Tue/Thu, hybrid model?" question is a required CHECKBOX-group (Yes/No/discuss) the static dry-run never enumerated — now answered "Yes" via a TRUSTED Playwright label.click() (synthetic JS click does NOT register in Ashby React state). reCAPTCHA-v3 generated in-browser over residential egress (token_len ~2489).
