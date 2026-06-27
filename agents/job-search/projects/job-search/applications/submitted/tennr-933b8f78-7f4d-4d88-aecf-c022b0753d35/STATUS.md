# STATUS: BLOCKED
role_id: 3730
company: Tennr
role: Associate Solutions Architect
ats: ashby
url: https://jobs.ashbyhq.com/tennr/933b8f78-7f4d-4d88-aecf-c022b0753d35

block_reason: RECAPTCHA_SCORE_BELOW_THRESHOLD (hard cohort — both datacenter and residential proxy flagged as spam)
attempts:
  1. Datacenter (http://[::1]:18900) — RECAPTCHA_SCORE_BELOW_THRESHOLD
  2. Residential (http://127.0.0.1:19223) — RECAPTCHA_SCORE_BELOW_THRESHOLD
  
notes: Tennr uses Ashby hard-cohort reCAPTCHA v3 that blocks even residential IPs. Needs real aged Google account + dedicated residential IP (Cyrus-side).
blocked_at: 2026-06-26
