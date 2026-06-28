PREP-READY-ICIMS-RUNNER — 2026-06-28T08:36:37+00:00

role_id: 3624
slug:    foot-locker-70866
url:     https://us-corp-footlocker.icims.com/jobs/70866/product-manager,-point-of-sale-(pos)/job
tenant:  us-corp-footlocker  reqId: 70866

iCIMS apply is driven by the CDP runner (handles email-OTP via
Gmail IMAP, EXIT 10 on OTP timeout). Run:

    .venv/bin/python role-discovery/_icims_runner.py --url https://us-corp-footlocker.icims.com/jobs/70866/product-manager,-point-of-sale-(pos)/job --apply --debug .icims-debug/foot-locker-70866

EXIT: 0=submitted/dryrun 2=auth/hcaptcha-wall 3=no-confirm
4=no-submit 5=cap 6=closed 7=already-applied 10=otp-timeout
