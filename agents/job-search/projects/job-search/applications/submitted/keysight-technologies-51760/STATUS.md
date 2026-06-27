PREP-READY-ICIMS-RUNNER — 2026-06-26T19:39:30+00:00

role_id: 3788
slug:    keysight-technologies-51760
url:     https://careers-keysight.icims.com/jobs/51760/login
tenant:  careers-keysight  reqId: 51760

iCIMS apply is driven by the CDP runner (handles email-OTP via
Gmail IMAP, EXIT 10 on OTP timeout). Run:

    .venv/bin/python role-discovery/_icims_runner.py --url https://careers-keysight.icims.com/jobs/51760/login --apply --debug .icims-debug/keysight-technologies-51760

EXIT: 0=submitted/dryrun 2=auth/hcaptcha-wall 3=no-confirm
4=no-submit 5=cap 6=closed 7=already-applied 10=otp-timeout
