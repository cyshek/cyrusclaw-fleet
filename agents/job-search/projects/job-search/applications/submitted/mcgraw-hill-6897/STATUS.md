PREP-READY-ICIMS-RUNNER — 2026-06-26T15:03:33+00:00

role_id: 3720
slug:    mcgraw-hill-6897
url:     https://careers-mheducation.icims.com/jobs/6897/technical-product-manager/job
tenant:  careers-mheducation  reqId: 6897

iCIMS apply is driven by the CDP runner (handles email-OTP via
Gmail IMAP, EXIT 10 on OTP timeout). Run:

    .venv/bin/python role-discovery/_icims_runner.py --url https://careers-mheducation.icims.com/jobs/6897/technical-product-manager/job --apply --debug .icims-debug/mcgraw-hill-6897

EXIT: 0=submitted/dryrun 2=auth/hcaptcha-wall 3=no-confirm
4=no-submit 5=cap 6=closed 7=already-applied 10=otp-timeout
