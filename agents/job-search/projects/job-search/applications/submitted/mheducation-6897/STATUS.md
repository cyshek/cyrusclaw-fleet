BLOCKED — 2026-07-01

role_id: 3720
slug:    mheducation-6897
url:     https://careers-mheducation.icims.com/jobs/6897/login
company: McGraw Hill
role:    Technical Product Manager

## Block Reason
`icims-auth0-no-account` — cyshekari@gmail.com is NOT registered in McGraw Hill's
Auth0 org. Returns "Wrong username or password" (not "blocked"). Self-registration
is DISABLED on the McGraw Hill Auth0 org (fresh aliases also rejected).

## What Was Tried (2026-07-01)
1. cyshekari@gmail.com / JobSearch2026!amd → "Wrong username or password" (no account)
2. cyshekari+mh2026a@gmail.com (fresh alias) → same "Wrong username or password"
   (confirms: McGraw Hill Auth0 org does not allow self-registration)

## What's Needed to Unblock
Cyrus needs to manually create an account at:
https://careers-mheducation.icims.com/jobs/6897/login

Steps:
1. Navigate to the URL above
2. Enter cyshekari@gmail.com as the email
3. Complete the registration/OTP flow (if MH uses OTP instead of Auth0 password)
   OR register via Auth0 if that path becomes available
4. Set password to JobSearch2026!amd
5. Then re-run:
    .venv/bin/python role-discovery/_icims_runner.py --url https://careers-mheducation.icims.com/jobs/6897/login --apply

Note: It's possible McGraw Hill uses OTP email flow (not Auth0) for new accounts — 
the iCIMS runner's `CANONICAL_EMAIL` was `cyshekari@gmail.com` which has an existing
account in AMD's org. McGraw Hill may route to Auth0 OR OTP depending on whether 
the email is recognized. Manual verification needed.

## ATS Details
ATS: iCIMS  
Auth0 org: separate from Keysight's hs-13178
Gate hCaptcha sitekey: 94fee806-5cac-4582-9738-384a0f4ea6f8 (invisible)
Auth0 hCaptcha sitekey: ccfa5854-6bd6-4dd4-8d86-709a062e61ee (visible)
