PREP-READY-ICIMS-RUNNER — 2026-07-01T01:12:38+00:00

role_id: 3760
slug:    siriusxm-17393
url:     https://uscareers-siriusxmradio.icims.com/jobs/17393/login
tenant:  uscareers-siriusxmradio  reqId: 17393

iCIMS apply is driven by the CDP runner (handles email-OTP via
Gmail IMAP, EXIT 10 on OTP timeout). Run:

    .venv/bin/python role-discovery/_icims_runner.py --url https://uscareers-siriusxmradio.icims.com/jobs/17393/login --apply --debug .icims-debug/siriusxm-17393

EXIT: 0=submitted/dryrun 2=auth/hcaptcha-wall 3=no-confirm
4=no-submit 5=cap 6=closed 7=already-applied 10=otp-timeout
