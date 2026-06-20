# CSP-probe-at-prep — task aborted before shipping

**Date:** 2026-05-24
**Subagent:** csp-probe-fix
**Outcome:** BLOCKED — spec hypothesis empirically invalidated, no code changes shipped.

## What I did

1. Read `inline_submit.py` (1368 lines) and `tracker_db.py` to confirm interfaces (`prep_role`, `agent_notes`, `prep_status`, `STATUS.md` writers — all present as expected).
2. Verified the 3 BLOCKED roles in tracker (1125 Ascend, 1140 HackerRank, 1155 Similarweb). Confirmed identical failure-mode notes in `agent_notes`.
3. **Captured live CSP headers** via `curl -sIL` against:
   - 3 confirmed-blocked tenants: similarweb, hackerrank, ascend21
   - 3 known-working tenants: airtable, discord, anthropic
4. Diffed them. **Result: all 6 boards return BIT-IDENTICAL `Content-Security-Policy` headers.** No `<meta http-equiv>` CSP override in the HTML either.

## Why the spec doesn't work

The task assumes per-tenant CSP variation: "GH board's tenant CSP `connect-src` only allows `www.google.com` … but other tenants whitelist `recaptcha.net`." This is **not true**. Greenhouse's edge ships one CSP for the entire `*.greenhouse.io` surface. Specifically, **every** tenant has:

- `script-src` includes `www.recaptcha.net`, `www.google.com/recaptcha/`, `www.gstatic.com/recaptcha/` (loads OK on all).
- `connect-src` includes `www.google.com` and `boards.greenhouse.io` but **NEVER `recaptcha.net`** — on every single tenant probed, blocked AND working.

So the proposed probe has two failure modes, both bad:

| Probe rule (as written) | Behavior on real data |
|---|---|
| "Flag if `connect-src` missing `recaptcha.net` AND `script-src` references enterprise" | Flags **100% of Greenhouse roles**, including Discord/Anthropic/Airtable that submit fine → blocks the entire GH pipeline. |
| Tightened to "flag only if tenant uses Enterprise reCAPTCHA" | The CSP header carries no Enterprise vs v3 signal — that's a runtime JS decision baked into the board config, not visible in HTTP headers. |

The real per-tenant variation lives in `init` JS responses or board config that Greenhouse swaps in client-side (Enterprise reCAPTCHA emits XHRs to `www.recaptcha.net/recaptcha/enterprise/clr`; legacy v3 emits to `www.google.com/recaptcha/api2/anchor` which the shared CSP happily allows). A static HTTP probe at prep time cannot distinguish them.

## Evidence (header diff)

```
$ curl -sIL https://job-boards.greenhouse.io/similarweb/jobs/7743380 | grep -i content-security
content-security-policy: …; connect-src 'self' api.mapbox.com … www.google.com auth.seek.com … boards.greenhouse.io job-boards.cdn.greenhouse.io … c.spl.greenhouse.io

$ curl -sIL https://job-boards.greenhouse.io/airtable | grep -i content-security
content-security-policy: …; connect-src 'self' api.mapbox.com … www.google.com auth.seek.com … boards.greenhouse.io job-boards.cdn.greenhouse.io … c.spl.greenhouse.io
```

(Identical to the byte. Full payloads captured in subagent transcript.)

## Files NOT changed

- `inline_submit.py` — untouched
- `tracker.db` — no backup created, no rows mutated
- No new `test_csp_captcha_probe.py`

## Recommended next steps (pick one; each addresses the real signal)

1. **Runtime-tag, not prep-time-tag.** Have the browser plan instrument `page.on("response")` and bail out if it sees a 4xx on `www.recaptcha.net/recaptcha/enterprise/*` BEFORE clicking Submit (saves ~30s of polling-the-disabled-button time, not 10–15min but real). Cleanest implementation: add a 5-second probe right after the iframe loads — open the page headlessly, check for the enterprise script tag in the rendered DOM (`grecaptcha.enterprise.execute` or `enterprise.js` in network log), and if present flag the tenant.
2. **Per-tenant blocklist.** Maintain `projects/job-search/role-discovery/greenhouse_csp_blocklist.yaml` of confirmed-bad tenant slugs (today: `similarweb`, `hackerrank`, `ascend21`). On prep, if `gh_org` is in the list, write `PREP-READY-MANUAL-CSP-CAPTCHA` immediately. Grow the list when failures recur. Low engineering cost, high precision, manual maintenance — but for a list of ~3 today this beats a wrong probe. Reuses the same `agent_notes` schema.
3. **Active probe.** Use Playwright (already in venv) to fetch the apply page, evaluate `document.documentElement.outerHTML.includes('recaptcha/enterprise')` or scan loaded scripts for `enterprise.js`. ~3s/role at prep — fits prep budget. Most accurate but adds a Playwright launch to a step that's currently pure HTTP.

My recommendation: **#2 today (one-line YAML, ships in 10min) + #3 as the proper fix this week**. #1 is fine if the runtime layer is being touched anyway.

## Compact JSON

`{"task": "csp-probe-fix", "outcome": "blocked", "tests_pass": "0/0", "backfilled_count": 0, "files_changed": []}`

---

## Follow-up — 2026-05-24 PM — blocklist option SHIPPED

Second spawn (subagent ba1e7cb3) implemented Option #2 from the recommendations
above. Tiny per-tenant blocklist; no probe, no Playwright, no false positives.

### Changes shipped

- **NEW** `projects/job-search/role-discovery/greenhouse_csp_blocklist.yaml`
  — 3 entries: `similarweb`, `hackerrank`, `ascend21`. Schema documented inline
  (slug / observed / symptom).
- **EDIT** `projects/job-search/role-discovery/inline_submit.py`
  - Added `GH_CSP_BLOCKLIST_PATH` + `load_gh_csp_blocklist()` (lazy YAML load,
    never raises, returns empty set if YAML missing).
  - In `prep_role`, after the Workday dispatch, added a CSP-blocklist short-
    circuit for `ats in (greenhouse, greenhouse_iframe)`. When `gh_org` is in
    the blocklist: writes `STATUS.md = PREP-READY-MANUAL-CSP-CAPTCHA`, updates
    tracker (`prep_status='manual_ready', prep_path=<workdir>, agent_notes +=
    "CSP-CAPTCHA-BLOCK-BLOCKLIST 2026-05-24: tenant <slug>"`). No
    bullet_rewriter / cover_answers / dryrun / browser plan generated.
  - Added `--ignore-csp-block` CLI flag (passes through to `prep_role`).
- **NEW** `projects/job-search/role-discovery/test_greenhouse_csp_blocklist.py`
  — 3 unit tests. Run:
  ```
  $ .venv/bin/python -m unittest test_greenhouse_csp_blocklist -v
  test_slug_derivable_from_app_url ... ok
  test_slug_in_blocklist_short_circuits ... ok
  test_slug_not_in_blocklist ... ok
  ----------------------------------------------------------------------
  Ran 3 tests in 0.088s
  OK
  ```
- **Backfill**: 3 GH open roles in blocklist (1125 Ascend, 1140 HackerRank,
  1155 Similarweb) updated to `prep_status='manual_ready'` with the
  `CSP-CAPTCHA-BLOCK-BLOCKLIST` tag appended to `agent_notes` (preserving
  pre-existing notes). They will now show up on the Manual Ready tab of the
  xlsx and stop being picked by future `--batch` runs.

### Safety

- `tracker.db` backed up to `tracker.db.bak.20260524-csp-blocklist` BEFORE
  backfill.
- Test isolation: unit tests use a tempfile sqlite DB + sandboxed
  SUBMITTED_DIR, real tracker untouched during testing.
- Short-circuit doesn't fire on `greenhouse_iframe` tenants by default unless
  the iframe wrapper resolves to a blocklisted `gh_org` — same precision as
  native greenhouse.

### Recurring-pipeline fit (per AGENTS.md checklist)

- **Source of bad data:** ATS-level CSP/captcha mismatch. Not introduced by
  any of our adapters; it's an upstream Greenhouse-tenant config quirk.
- **Recurrence:** YES — the next weekly crawl will re-pick the same 3
  tenants if/when they post new roles. The short-circuit in `inline_submit`
  is the permanent fix; the backfill above caught up existing open rows.
- **Permanent home:** `inline_submit.prep_role()`. Done.
- **Migration:** done (catch-up via backfill block in this report's script,
  permanent logic merged into prep_role).

### Open work (Option #3 from above)

Active Playwright probe for unknown tenants is still the proper long-term fix
(detects new offenders automatically instead of requiring a failed submit + a
human to add a YAML line). Not in scope today.

`{"task": "csp-blocklist-fix", "outcome": "shipped", "tests_pass": "3/3", "backfilled_count": 3, "files_changed": ["projects/job-search/role-discovery/greenhouse_csp_blocklist.yaml", "projects/job-search/role-discovery/inline_submit.py", "projects/job-search/role-discovery/test_greenhouse_csp_blocklist.py", "projects/job-search/tracker.db"]}`
