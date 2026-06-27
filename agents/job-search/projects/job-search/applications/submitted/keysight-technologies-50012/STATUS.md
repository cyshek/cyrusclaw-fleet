PREP-READY-ICIMS-RUNNER — 2026-06-26T19:39:42+00:00

role_id: 3789
slug:    keysight-technologies-50012
url:     https://careers-keysight.icims.com/jobs/50012/login
tenant:  careers-keysight  reqId: 50012

iCIMS apply is driven by the CDP runner (handles email-OTP via
Gmail IMAP, EXIT 10 on OTP timeout). Run:

    .venv/bin/python role-discovery/_icims_runner.py --url https://careers-keysight.icims.com/jobs/50012/login --apply --debug .icims-debug/keysight-technologies-50012

EXIT: 0=submitted/dryrun 2=auth/hcaptcha-wall 3=no-confirm
4=no-submit 5=cap 6=closed 7=already-applied 10=otp-timeout
