SUBMITTED — 2026-05-26 chain_011 (unplanned-dropdown filler)

role_id: 716
slug:    lyft-8525086002
url:     https://app.careerpuck.com/job-board/lyft/job/8525086002?gh_jid=8525086002
title:   Product Manager, Driver Experience
tc:      $343K

Two-fix path to SUBMITTED:

1. **Resume gate** (chain_010): Option A React-onChange trigger already in place.
   Validated on Lyft 1343 + Hume 1379. Lyft 716's resume gate cleared in
   first chain_011 run.

2. **Custom proximity dropdown** (chain_011, NEW): The boards-api dryrun spec
   does NOT expose Lyft's required custom Q "Do you currently reside in
   commutable proximity to a Lyft Office located in New York City or San
   Francisco or are you open to relocating?". Without a planned dropdown
   entry, post-submit failed with `BLOCKED_FIELD_ERRORS`.

   FIX: New step `unplanned_dropdowns` in greenhouse_iframe_runner.py.
   - `JS_FILL_UNPLANNED_DROPDOWNS` (greenhouse_filler.py) scans rendered
     `.select__control` for unfilled non-demographic dropdowns, walks DOM
     for a label, matches against `DEFAULT_UNPLANNED_DROPDOWN_PATTERNS`.
   - Discovered patterns are then delegated to the proven `JS_PICK_DROPDOWNS`
     recipe (id + answer).
   - Demographic labels (gender/race/ethnicity/veteran/disability) are
     skipped unless explicitly patterned (safety net for decline-demographics).

   First pattern shipped: "commutable proximity" → "I am willing to relocate
   before starting employment." (Cyrus is in Kirkland WA; relocation_targets
   in personal-info.json includes SF + NYC; he is NOT near a Lyft on-site
   office today, so the "already reside near" option would be a false claim).

Runs:
- /tmp/lyft716-chain11-run1.json — BLOCKED (no pattern; baseline reproduces)
- /tmp/lyft716-chain11-run2.json — BLOCKED (scope-options bug; first-pass selector miss)
- /tmp/lyft716-chain11-run3.json — BLOCKED but retry-loop saw the right options
- /tmp/lyft716-chain11-run4.json — SUBMITTED ✅
  - conf=True, url=https://job-boards.greenhouse.io/embed/job_app/confirmation?for=lyft&token=8525086002
  - unplanned_dropdowns_retry got "I am willing to relocate before starting employment."

Tests:
- role-discovery/test_unplanned_dropdowns.py (10/10 green)

Tracker updated: status=applied, prep_status=submitted, applied_by=agent,
applied_on=2026-05-26. Backup: tracker.db.bak.20260526-r716-chain11.
