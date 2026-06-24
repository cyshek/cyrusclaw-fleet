STATUS: PREP-READY-MANUAL-CSP-CAPTCHA
observed_at: 2026-06-24T05:03:36+00:00
role_id: 2940
slug: hackerrank-7482137
gh_org: hackerrank
company: HackerRank
role: Forward Deployed Engineer
url: https://job-boards.greenhouse.io/hackerrank/jobs/7482137

Tenant is on greenhouse_csp_blocklist.yaml: reCAPTCHA Enterprise
calls www.recaptcha.net which the Greenhouse CSP blocks ->
submit button stays permanent-disabled / POST /v1/post 428.

Apply manually via the Apply URL. Override: pass --ignore-csp-block
if you want to attempt prep+submit anyway (e.g. to re-confirm the
block is still in place).
