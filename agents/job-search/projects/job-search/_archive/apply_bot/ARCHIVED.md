# Archived apply-bot (auto-application tool)

**Status:** Pivoted away from. **Date archived:** 2026-05-06

## Why archived
We tried to auto-fill and submit job applications across Greenhouse, Ashby, and Lever.
After repeated spam-flagging (most recently on Modal — see plan history), we concluded
that auto-submitting applications is too risky for the user's reputation and the
ROI doesn't justify the engineering cost. The project pivoted to **discovery-only**
(see ../role-discovery/).

## What's here
- ATS adapters (greenhouse.py, ashby.py, lever.py) — captured a lot of learnings about
  each ATS's quirks (Greenhouse checkbox-groups, Ashby radio-groups, Lever React-form
  click rejection, etc.)
- packet.py — orchestration
- batch_ashby*.py / sweep_dryrun*.py — batch runners
- gmail_otp.py — OTP retrieval helper
- tenant_caps.json — per-tenant rate limits learned the hard way

## When to revisit
- If you want a "fill all the fields, you submit" middle-ground tool, the form-filling
  logic in greenhouse.py / ashby.py / lever.py is a head-start. Strip the submit step.
- If a specific company has a tedious application and you'd rather automate it,
  pull the relevant adapter and run packet.py manually.

## Don't touch
- This directory is not wired into daily_run.ps1 anymore.
- The ./runs/ subdirectory was deleted (214 MB of forensic screenshots/traces) — they
  were debugging artifacts, not production output.
