# BlackRock - AI Product Manager, Associate - Aladdin AI (id=3670)

## Status: SUBMITTED ✅

| Field | Value |
|-------|-------|
| Company | BlackRock |
| Role | AI Product Manager, Associate - Aladdin AI |
| Role ID | 3670 |
| Req ID | R263783 |
| URL | https://blackrock.wd1.myworkdayjobs.com/BlackRock_Professional/job/New-York-NY/AI-Product-Manager--Associate---Aladdin-AI_R263783 |
| Applied | 2026-06-28 (confirmed) |
| Applied By | auto (_workday_runner.py) |
| Resume | Yes |

## Confirmation Evidence

Screenshot confirms successful submission on **2026-06-28** (file: `BlackRock_Professional-after-submit.png`) AND **2026-06-30** (file: `blackrock-after-submit.png`).

Both screenshots show:
- Green circular checkmark icon
- **"Congratulations!"** heading
- **"Your application has been submitted."** text
- BlackRock jobs listing in background (confirmation modal overlay pattern)

## Root Cause of Runner Exit-3

BlackRock WD tenant displays the confirmation in a **MODAL OVERLAY** over the jobs listing page (not a standalone confirmation page). The runner's confirm-text search scanned the main page DOM but missed the modal. The redirect-to-jobs-listing was then parsed as EXIT-3 ("no confirmation text").

**Fix needed:** Detect `[data-automation-id=confirmationMessage]` or `"Congratulations"` text in modal/dialog containers on all WD tenants, not just the main page body. This same pattern may affect other WD tenants.

## Note: Possible Double-Submission
The runner ran again on 2026-06-30 (after EXIT-3 was logged) and also shows a confirmation screenshot. BlackRock likely only records one application per person (subsequent submissions may be ignored or flagged as duplicate).
