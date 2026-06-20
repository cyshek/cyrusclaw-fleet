ABORT-CAPTCHA-FAIL — 2026-05-23T20:32Z

slug: stripe-7815794

Not attempted in 20:00 UTC burndown — batch-aborted after databricks-8243219002 and datadog-7721591 both failed the same way.

Pattern: `job-boards.greenhouse.io/embed/job_app?for=*&token=*` URLs now have hardened reCAPTCHA Enterprise score-based gate. Form fills successfully, resume commits, but Submit button stays disabled after click. No visible challenge to solve. Headless Chrome from Azure datacenter IP scores too low.

Today's earlier successful submits (id 609 databricks-6328361002 via databricks.com/company/careers, id 615 datadog-7452669 via careers.datadoghq.com/detail/) used canonical careers-page URLs, not the embed shortcut.

Hypothesis: the parent careers page provides a validityToken (or warm cookie/referrer) that the embed URL alone doesn't get. Worth experimenting: navigate to parent page, wait for iframe to load, then submit from within. NOT attempted this run due to budget.

Tracker NOT updated. Resume/cover/plan preserved.

submitted_by: auto (job-search subagent burndown 20:00 UTC) — ABORTED (not attempted)
