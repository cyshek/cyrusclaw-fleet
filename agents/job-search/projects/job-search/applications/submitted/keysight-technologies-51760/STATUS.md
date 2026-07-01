BLOCKED — 2026-07-01

role_id: 3788
slug:    keysight-technologies-51760
url:     https://careers-keysight.icims.com/jobs/51760/login
company: Keysight Technologies
role:    Solutions Engineer - EDA

## Block Reason
`icims-auth0-locked` — same as role 3787: cyshekari@gmail.com locked on login.icims.com
Auth0 tenant (same org hs-13178, same lockout).

## What Was Tried
Same flow as 3787. All Keysight iCIMS roles share Auth0 org hs-13178.
(Only 3787 was attempted in detail; 3788 would have same outcome.)

## What's Needed to Unblock
Same as 3787 — wait for lockout to expire or Cyrus resets password.
After unblocking, run:
    .venv/bin/python role-discovery/_icims_runner.py --url https://careers-keysight.icims.com/jobs/51760/login --apply

## ATS Details
ATS: iCIMS
Auth0 org: hs-13178 (Keysight)
Gate hCaptcha sitekey: 94fee806-5cac-4582-9738-384a0f4ea6f8 (invisible)
Auth0 hCaptcha sitekey: ccfa5854-6bd6-4dd4-8d86-709a062e61ee (visible)
