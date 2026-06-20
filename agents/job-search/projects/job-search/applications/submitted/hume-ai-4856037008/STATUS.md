SUBMITTED — 2026-05-26 chain_011 (Option A React-trigger validation)

role_id: 1379
slug:    hume-ai-4856037008
url:     https://job-boards.greenhouse.io/humeai/jobs/4856037008
title:   Product Manager, Growth

Re-attempted with chain_010 USE_REACT_RESUME_TRIGGER=True (no code changes
from chain_010 — just first live verify on a non-Lyft tenant).

Run: `greenhouse_iframe_runner.py --slug hume-ai-4856037008 --debug-filestack`
Artifacts: /tmp/hume1379-chain11-run1.{json,stderr}

Outcome: SUBMITTED
- conf=True, url=https://job-boards.greenhouse.io/humeai/jobs/4856037008/confirmation
- react_trigger: native_setter_used=true, change_dispatched=true
- verification_code_used: jii60WeU (Hume sends email-code interstitial like Lyft;
  auto-handled via Gmail IMAP fetch)
- fieldErrs: [] (the chain_009 "Resume/CV is required" gate cleared cleanly)

Validates chain_010 Option A pattern is GENERIC across newer GH+Filestack tenants,
not just Lyft. Same React-onChange trigger works on Hume.

Tracker updated: status=applied, prep_status=submitted, applied_by=agent,
applied_on=2026-05-26. Backup: tracker.db.bak.20260526-r1379-chain11.
