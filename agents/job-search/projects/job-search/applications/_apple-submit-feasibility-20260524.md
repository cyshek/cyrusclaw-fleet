# Apple custom-ATS submit-driver feasibility — 2026-05-24

**Origin:** BACKLOG.md P1 → "Apple custom ATS — 27 open Apple roles. Apple is `scan-blocked` (no public API). Would need their own driver."
**Probed by:** burndown subagent 2026-05-24 17:21 UTC
**Scope:** static analysis only; no submit attempted; no Apple ID account touched

## Discovery vs submit

Discovery already works fine. `role-discovery/adapters/apple.py` scrapes `https://jobs.apple.com/en-us/search` HTML, extracts pid/discriminator/slug/team, hits the public JD pages and builds Role records. Today's tracker has 27 open Apple roles (all `status=''`, all with `app_url=https://jobs.apple.com/en-us/details/<pid>-<disc>/<slug>?team=<team>`).

**Submit** is the BACKLOG-flagged blocker.

## What the JD page reveals (HTTP 200, 187 KB)

- The JD page renders a single-page-app shell. No inline form HTML; the apply button is rendered by `jobsite.main.<hash>.js` after hydration.
- No `apply.apple.com` link, no plain `href="apply..."` link, no iframe, no plain anchor to an external ATS.
- The page mentions `applyFilters`, `applyNoProfileThanks`, `applyParsingOptions` — these are SPA action labels for resume-parsing options and the post-apply confirmation screen, suggesting the apply UI is multi-step and entirely client-rendered.
- No CSRF token in the JD HTML, no `requisitionId` / `applyUrl` JSON blob in `<script type="application/ld+json">`.
- Globalnav references Apple ID sign-in (`appleid.apple.com` is invoked by `ac-globalfooter`). The apply step almost certainly requires an Apple ID.

## Cost / risk to build a driver

**Required components:**
1. Apple ID account (Cyrus's, or a burner). 2FA every time the cookie expires.
2. Playwright headless driver that loads the JD page, waits for hydration, clicks Apply, handles the SSO redirect, walks the multi-step apply wizard (Personal Info → Education → Work Experience → Self-ID / EEO → Resume upload → Review), then Submit.
3. Form-field extractor + filler with per-field-type handlers (Apple's form widgets are custom React components, not the Greenhouse react-select we already know how to drive). At least a week of fiber-walking the DOM to figure out which event handlers latch state.
4. Anti-bot handling. Apple is Cupertino-tier sophisticated; same datacenter-IP risk as we just hit on Greenhouse Enterprise, but on Apple ID's own risk model. A signed-in account doing programmatic apply could trigger account lockout — and that's *Cyrus's* Apple ID.
5. Maintenance burden: any Apple UI revamp breaks the driver. The Greenhouse pipeline has 6 dependent ATSes; an Apple-only driver supports just one source.

**Engineering estimate (one human-week of focused work):** 30-50 hours to MVP, then ongoing maintenance after every Apple UI change.

**Yield:** 27 roles today, +/- weekly delta. Apple typically has 50-150 PM-eligible postings live at any time, so the long-term yield is bounded by Apple's hiring volume in PM-adjacent SF/Cupertino roles, of which Cyrus's overreach filter would keep maybe 10-30 per crawl.

## Comparable options Cyrus might prefer

1. **Manual-apply for Apple, like we do for LinkedIn.** Flag every Apple row `manual-apply`, surface them in the xlsx, Cyrus pastes from `cover_answers.md` at his pace. Zero engineering cost. Loses on volume.
2. **Build the driver only after CapSolver Enterprise is paid for.** The Apple submit flow likely has its own anti-bot challenge; without solver budget there's no clean answer to step 4 anyway.
3. **Skip Apple entirely.** Status quo in tracker is `status=''` (open). Could flip all 27 to `manual-apply` and revisit once a quarter.

## Recommendation

**Defer.** The capability is technically buildable but the cost/yield + risk-to-Apple-ID combination is bad relative to other backlog work. Until CapSolver Enterprise is funded (which would address the bigger Ashby+Lever+SpaceX backlog of ~70 roles), Apple shouldn't be the next milestone.

**Cheap interim:** flag all 27 open Apple rows `manual-apply` so they surface in the xlsx like LinkedIn rows do. This is a one-line tracker.db migration (`UPDATE roles SET flags = flags || ',manual-apply' WHERE company='Apple' AND ...`) but per burndown guardrails it requires a backup-then-write idempotent migration and is a row-touch that I'd rather have Cyrus greenlight. Capturing here so it's a one-step ask, not a research task.

## No code changes made

The candidate file `_repair/` directory is unchanged. This is a feasibility note only.
