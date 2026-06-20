# REPROBE FINDINGS — 2026-06-13

Probed at: 2026-06-13 ~00:20–00:45 PDT

---

## ROW 1: Snowflake 2527 — Senior Technical Program Manager (Ashby)

**VERDICT: LIKELY-FIXABLE (technically) — but POLICY-BLOCKED (senior title)**

### Technical verdict
- Ran `inline_submit.py --role-id 2527 --dry-run` (Ashby dryrun fresh fetch 2026-06-13)
- Dryrun result: **`ready_to_submit: True`, `blockers: 0`**, 17 fields, 15 filled, 0 needs_review_dropdowns, 1 needs_essay (cover Q answered in cover_answers.md), 1 unresolved (optional "Additional Attachments" file — not a blocker)
- The old ASHBY-AUTOFILL-NONDETERMINISTIC block is **GONE** — the dryrun produces a clean plan with 0 blockers. The `final_clobber_guard` fix (shipped 2026-06-08) resolves the race condition that was failing 8 of 8 prior attempts.
- Prep aborted at bullet-rewriter phase due to a symlink-shim path issue (QUEUED_DIR shim cleanup race in `--dry-run` mode), but the dryrun spec itself is sound.

### Policy verdict
- Title is "Senior Technical Program Manager" — `\bsenior\b` hits HARD_BLOCKLIST (no carve-out for TPM roles)
- The pipeline already tried and banked `TRIED 2026-06-09: BATCH: senior-title-out-of-scope`
- **Not a technical wall — a policy wall.** A fresh live-submit attempt would likely succeed IF the classifier gate were bypassed.

### What needs to happen
- If Cyrus explicitly wants to apply despite Senior title: `inline_submit.py --role-id 2527` (no --dry-run) — the engine will reach the submit gate cleanly.
- If classifier policy stands: leave as TRIED/blocked.

---

## ROW 2: Starbucks 2044 — digital product manager, Delivery (LinkedIn → Workday)

**VERDICT: STILL-WALLED — Starbucks Workday tenant is in active maintenance mode**

### What we found
- Old block (2026-06-11): `LINKEDIN-BRUTE: ERRORED | ATS=workday error=network-error` — this was initially a transient-looking SSL error
- The June 4 SSL error (`SSLEOFError: UNEXPECTED_EOF_WHILE_READING`) was the FIRST sign of the tenant being unstable
- **Today's probe (2026-06-13):** Browser navigation to `starbucks.wd5.myworkdayjobs.com/en-US/starbuckscareers` redirects to `community.workday.com/maintenance-page` with message: **"Workday is currently unavailable. We are experiencing a service interruption."**
- All CXS API calls (job search, job detail) return HTTP 422 — consistent with the maintenance intercept layer blocking API requests
- Pattern: Starbucks Workday has been failing EVERY crawl since 2026-06-04 (confirmed in daily_runs.log — every search term returning 422)

### Workday URL status
- We could NOT resolve the specific WD job URL (req ID unknown — role only ever saw a LinkedIn URL, never a direct WD apply URL)
- The Starbucks Workday tenant doesn't expose its jobs API without a PLAY_SESSION cookie (requires JS execution), AND is currently in maintenance mode
- Cannot run `workday_dryrun.py` on a real req URL because we don't have the actual req ID

### What needs to happen
- Wait for maintenance window to end, then re-run the LinkedIn brute resolver on this row
- Command: `role-discovery/.venv/bin/python role-discovery/linkedin_stranded_brute_resolver.py --limit 1` (row is still eligible — agent_notes LIKE 'LINKEDIN-BRUTE' but NOT 'LINKEDIN-BRUTE-DONE')
- Expected outcome once maintenance ends: resolver will fetch the jobs list, match "digital product manager, Delivery" by title, and set a real Workday apply URL
- Role itself appears to still be live (TealHQ showed it posted "4 days ago" as of 2026-06-13)
- Note: even after URL resolution, Workday auto-submit is not implemented — would land in PREP-READY-MANUAL

---

## Summary

| Row | Status | Action |
|-----|--------|--------|
| Snowflake 2527 (Ashby TPM) | LIKELY-FIXABLE technically / POLICY-BLOCKED (senior title) | Cyrus decision: bypass senior-title gate or leave banked |
| Starbucks 2044 (WD Digital PM) | STILL-WALLED (Workday maintenance + unknown req URL) | Re-run brute resolver after maintenance ends |
