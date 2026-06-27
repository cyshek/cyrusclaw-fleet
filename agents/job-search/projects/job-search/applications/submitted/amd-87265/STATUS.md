PREP-READY-ICIMS-RUNNER — 2026-06-26T19:38:53+00:00

role_id: 3762
slug:    amd-87265
url:     https://careers-amd.icims.com/jobs/87265/login
tenant:  careers-amd  reqId: 87265

iCIMS apply is driven by the CDP runner (handles email-OTP via
Gmail IMAP, EXIT 10 on OTP timeout). Run:

    .venv/bin/python role-discovery/_icims_runner.py --url https://careers-amd.icims.com/jobs/87265/login --apply --debug .icims-debug/amd-87265

EXIT: 0=submitted/dryrun 2=auth/hcaptcha-wall 3=no-confirm
4=no-submit 5=cap 6=closed 7=already-applied 10=otp-timeout
