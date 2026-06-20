# STATUS-apple.md — Apple custom-ATS spike (FINAL)

**Started:** 2026-05-27 12:25 PDT
**Finished:** 2026-05-27 12:30 PDT (~5min — diagnosis was crisp)
**Subagent:** apple-driver-spike

## Phase
DONE.

## Verdict
**GENUINELY BLOCKED — not fillable.** The "needs custom driver" tag was *partially* wrong (it framed this as missing engineering) but the underlying reality is still a hard wall: every Apple JD apply CTA → `idmsa.apple.com` Apple ID OAuth (shared `appIdKey=967e0c9e…`), full 2FA, no guest path, no recruiter mailto, no Easy-Apply fallback. Falsification attempt FAILED — the SSO wall is real and universal across HRDWR + SFTWR roles.

## Per-role diagnosis (all 10 → same class)
| id | role | blocker class |
|---|---|---|
| 34 | BizOps EPM PACE | SSO-as-captcha (Apple ID OAuth) |
| 37 | CPU Pre-Si EPM | SSO-as-captcha |
| 52 | HW EPM VPG | SSO-as-captcha |
| 68 | PM Manufacturing | SSO-as-captcha |
| 83 | TPM Services Pricing | SSO-as-captcha (browser-verified) |
| 85 | TPM iPad | SSO-as-captcha |
| 964 | Safety EPM PACE | SSO-as-captcha |
| 1340 | DRAM NPI PM | SSO-as-captcha |
| 1634 | EPM iCloud Mail | SSO-as-captcha (browser-verified) |
| 1637 | Hardware EPM | SSO-as-captcha (browser-verified) |

3 verified live (1637/83/1634). The other 7 share the identical `/app/en-us/apply/<reqid>` URL shape — same redirect by code path (all hit `idmsa.apple.com/IDMSWebAuth/signin?appIdKey=967e0c9e…`).

## Done
- Enumerated 10 stranded roles.
- Browser-walked 3 (HRDWR EPM, SFTWR TPM, SFTWR EPM iCloud) — all → same Apple ID OAuth iframe.
- Inspected SSO form: client_id, response_type=code, response_mode=web_message, `scnt`+`grantCode` server-issued CSRF, full Apple ID 2FA flow.
- DOM scan of JD: only one "Submit Resume" CTA, zero mailto, zero alt apply paths.
- Wrote `projects/job-search/APPLE-BLOCKER.md` (evidence + unblock-path).
- Backed up `tracker.db` → `tracker.db.bak.20260527-apple-driver-spike`.
- Stamped all 10 rows: `agent_notes` prepended with `APPLE-DIAGNOSED 2026-05-27: SSO-as-captcha…See APPLE-BLOCKER.md`.

## Deliverables
- ✅ Per-role diagnosis: all 10 → SSO-as-captcha.
- ✅ Verdict: genuinely-blocked.
- ✅ APPLE-BLOCKER.md (7KB, includes evidence + unblock infra ask).
- ❌ No candidate driver (would be wasted code; nothing to fill until cookies provisioned).
- ❌ No test file (no driver to test).
- ✅ Open-queue impact: removes "Apple custom-ATS driver: build vs defer?" from HANDOFF "open questions" — **confirmed defer.** 10 rows stay open in tracker (not skip-flipped) so they remain visible if cookie infra ever lands; agent_notes annotation prevents re-spawn of this spike.

## Blockers (for unblock if/when prioritized)
- Apple ID cookie injection on OpenClaw browser profile (analogous to the LinkedIn `li_at` escalation already pending).
- Once cookies land, ~1 day to build `apple_playwright.py` mirroring `workday_playwright.py` (SPA section-by-section).
- ROI low: EPM/PM TC band + Apple's slow recruiter pipeline vs. 184 already-open queue → de-prioritize behind CapSolver decision and LinkedIn cookie escalation.

## Cross-references updated
- `APPLE-BLOCKER.md` (new) — full evidence and ask.
- `tracker.db` rows 34/37/52/68/83/85/964/1340/1634/1637 — agent_notes stamped.
- Backup: `tracker.db.bak.20260527-apple-driver-spike` (1499136 bytes, 2026-05-27 19:22 UTC).

## Recommended HANDOFF.md edit (for parent agent)
Replace the open question "Apple custom-ATS driver: build vs defer? (recommendation: defer.)" with:
> "Apple custom-ATS driver: **DEFERRED** (apple-driver-spike 2026-05-27 confirmed SSO-as-captcha; see APPLE-BLOCKER.md). Unblock requires Apple ID cookie injection — bundle with LinkedIn `li_at` escalation."
