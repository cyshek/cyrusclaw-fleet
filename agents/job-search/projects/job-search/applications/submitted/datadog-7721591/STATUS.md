ABORT-CAPTCHA-FAIL — 2026-05-23T20:30Z

role_id: 622
slug: datadog-7721591
url: https://job-boards.greenhouse.io/embed/job_app?for=datadog&token=7721591

Same failure pattern as databricks-8243219002: form filled cleanly, resume committed, Submit button became permanently disabled after click. reCAPTCHA Enterprise score-based gate. No visible challenge, no error message — silent.

CONFIRMED: this is a NEW gate on `job-boards.greenhouse.io/embed/job_app?for=*&token=*` URLs. Today's earlier successful submits used canonical board URLs (job-boards.greenhouse.io/<org>/jobs/<jid>) which bypass it.

Tracker NOT updated. Resume/cover/plan preserved for retry.

submitted_by: auto (job-search subagent burndown 20:00 UTC) — ABORTED
