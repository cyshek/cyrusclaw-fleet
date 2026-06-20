# INLINE-SUBMIT-PLAYBOOK.md

Canonical reference for any submit subagent run after **2026-05-13**. The pipeline collapsed: there is no longer a separate "stage to queued/" step. A submit subagent prepares, fills, submits, and records — all in one pass — and writes its audit trail directly into `applications/submitted/<slug>/`.

**Multi-ATS dispatch (added 2026-05-13):** `inline_submit.py` detects the ATS from the role URL and dispatches to the right adapters automatically. Supported: Greenhouse, **Greenhouse-iframe (NEW)**, Ashby, Lever. The calling agent's job stays the same: read the emitted plan, execute it via the browser tool, click Submit, verify, and bookkeep.

## ATS-specific gotchas

- **Greenhouse:** react-select dropdowns; Filestack file picker for resume; phone iti widget. See `greenhouse_filler.py:emit_steps`.
- **Greenhouse-iframe (NEW 2026-05-13):** 13 hosts that embed the standard GH `/embed/job_app` form on a branded careers page (Datadog, Databricks, Stripe, CoreWeave, Abnormal, Dropbox, Elastic, Okta, MongoDB, Salesloft, Pinterest, Orca, Lyft/careerpuck). Detected by `?gh_jid=<jid>` query param + known host. Adapter shim: `adapters/greenhouse_iframe.py` maps `host -> gh_slug`. **Pipeline shortcut:** instead of opening the company page and scraping the iframe `src`, the plan navigates directly to `https://job-boards.greenhouse.io/embed/job_app?for=<slug>&token=<jid>` — every tenant accepts this without a `validityToken` on first render (verified across all 13 hosts in the 2026-05-13 scout). The DOM inside is identical to a native GH board, so all `greenhouse_filler` selectors work unchanged. **Caveat:** some tenants ship a `gdpr_demographic_data_consent_given` checkbox that's required but not in the boards-api schema — currently must be ticked manually until added to filler. Demographic dropdowns may use bare numeric ids (`1653`, `1654`, …) instead of `demographic_question_<n>` — `JS_DECLINE_DEMOGRAPHICS` matches by label text so this still works.
- **Ashby:** custom React form; uses gh_org/gh_jid aliases internally for compat with `bullet_rewriter`.
- **Lever:** native HTML form (input/select/radio/checkbox), simpler. **GOTCHA:** hCaptcha or invisible recaptcha appears on most apply pages — the browser plan does NOT click Submit, the calling agent must verify no captcha challenge is shown before clicking. Resume is a standard `<input type=file name=resume>`. Custom Q&A is in `cards[<uuid>][field<idx>]` named inputs (schemas in hidden `cards[<uuid>][baseTemplate]` JSON). EEO scan-pass via `JS_DECLINE_EEO` covers all `eeo[*]` fields automatically.

## TL;DR

For each role:

```
1. inline_submit.py --role-id <id>      # prepares packet (folder, JD, dryrun, resume, cover answers, plan)
2. (agent) read role-discovery/output/inline-plan.json + execute browser steps
3. Click Submit → verify confirmation page
4. Write STATUS.md
5. UPDATE roles SET applied_by='auto', applied_on='YYYY-MM-DD' WHERE id=<role_id>
6. python role-discovery/render_xlsx.py
```

---

## Architecture

The OpenClaw browser tool belongs to the agent, not to Python scripts. So the work splits cleanly:

- **`role-discovery/inline_submit.py`** — pure-Python prep (no browser): folder, JD fetch, dryrun spec, resume tailoring, cover answers, browser plan emission.
- **The submit subagent** — uses the `browser` tool to execute the emitted plan, observe the confirmation, then writes STATUS.md and updates tracker.db.

`greenhouse_filler.py:emit_steps()` produces the ordered browser-call plan. `inline_submit.py` calls into it.

## Folder layout (after a successful submit)

```
applications/submitted/<org>-<jid>/
  meta.json                                  # company, role, location, gh_org, gh_jid, apply_url, fetched_at
  prefill.json                               # full personal-info.json snapshot
  JD.md                                      # title + location + apply URL + JD body (markdown)
  rewrites.json                              # bullet_rewriter output
  tailoring-notes.md                         # bullet_rewriter notes
  Cyrus_Shekari_Resume_<org>_<jid>_v2.docx
  Cyrus_Shekari_Resume_<org>_<jid>_v2.pdf
  cover_answers.md                           # cover_answer_generator output
  STATUS.md                                  # written AFTER submit
  screenshots/                               # ONLY if a step failed (debugging) or asked for
```

The slug is `{company-slug}-{gh_jid}`. Example: `anthropic-4989788008`.

---

## Phase A: Prep (Python, no browser)

### 1. Resolve role

From `--role-id <id>`:

```python
import sqlite3, re
c = sqlite3.connect('projects/job-search/tracker.db')
row = c.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
url = row['app_url'] or row['jd_url']
m = re.search(r'/jobs/(\d+)', url)        # also matches ?gh_jid=...
jid = m.group(1)
gh_org = re.search(r'(?:job-boards|boards)\.greenhouse\.io/([^/]+)', url).group(1)
slug = re.sub(r'[^a-z0-9]+', '-', row['company'].lower()).strip('-') + '-' + jid
```

Refuse if `applied_on IS NOT NULL` (already submitted).

### 2. Fetch JD via Greenhouse API

```python
api = f"https://boards-api.greenhouse.io/v1/boards/{gh_org}/jobs/{jid}"
data = requests.get(api, timeout=20).json()
title = data['title']
loc   = (data.get('location') or {}).get('name', '')
absolute_url = data['absolute_url']
content_html = data['content']                    # HTML-entity-encoded HTML
jd_md = html_to_md(content_html)                  # see _stage_greenhouse.py
```

Write `<workdir>/JD.md`. If the API 404s, **abort that role** — do not screen-scrape; it's not worth the failure mode overnight.

### 3. Build meta.json + prefill.json

```python
meta = { "company": row['company'], "role": title, "location": loc,
         "exp_required": row['exp_req'], "apply_url": absolute_url,
         "jd_url": absolute_url, "fetched_at": iso_now,
         "ats": "greenhouse", "gh_org": gh_org, "gh_jid": jid,
         "flags": row['flags'] or "" }
prefill = json.loads(open('projects/job-search/personal-info.json').read())
```

### 4. Generate dryrun spec

```bash
.venv/bin/python role-discovery/greenhouse_dryrun.py "https://job-boards.greenhouse.io/<org>/jobs/<jid>"
# writes applications/dryrun/<org>-<jid>.json
```

If `report['ready_to_submit'] == False` AND blockers contain unrecoverable issues → **abort, document, continue batch**.

### 5. Tailor the resume

```bash
.venv/bin/python role-discovery/bullet_rewriter.py \
    --org <gh_org> --job-id <jid> --render --max-loops 3
```

`bullet_rewriter` writes `rewrites.json`, `tailoring-notes.md`, the `_v2.docx`, the `_v2.pdf` directly into `applications/queued/<slug>/` by default. If we're writing to `submitted/<slug>/` instead, run from a temp queued/ symlink OR move files after.

**Workaround used by inline_submit.py:** symlink `applications/queued/<slug>` → `applications/submitted/<slug>` for the duration of the bullet_rewriter run, then unlink. (See bullet_rewriter for path conventions; `_OUT_DIR_TMPL` in `tailor_resume.py`.)

If bullet_rewriter exits non-zero or the page-fit loop exhausts retries without producing a 1-page PDF, **abort, document, continue.** Never submit with the master resume.

### 6. Generate cover answers

```bash
.venv/bin/python role-discovery/cover_answer_generator.py --slug <slug>
# writes applications/submitted/<slug>/cover_answers.md
```

If validation fails twice (banned-phrase leak, AI-disclosure leak, missing answer), **abort, leave partial file for human review, continue.**

### 7. Emit browser plan

`inline_submit.py` calls `greenhouse_filler.build_plan(spec, resume_path)` and `emit_steps(plan, label=slug)`, then writes the ordered list of browser tool invocations to `role-discovery/output/inline-plan-<slug>.json`. Each step is `{"tool": "browser.<verb>", "args": {...}}`.

Also copies the rendered PDF to `/tmp/openclaw/uploads/` (the only directory the browser tool's upload action accepts).

---

## Phase B: Browser execution (agent)

The submit subagent reads the plan and dispatches browser calls in order. Per-role time budget: **8 minutes**.

### Browser plan steps (canonical for greenhouse forms)

1. `browser.navigate { url: <absolute_url> }`
2. `browser.act { kind: "evaluate", fn: JS_OPEN_APPLY }` — clicks the visible Apply button.
3. wait 600ms.
4. `browser.act { kind: "evaluate", fn: JS_FILL_TEXT_FIELDS, args: <text_fields_map> }` — native value setter for every text/textarea (`act:fill` no-ops on React).
5. `browser.act { kind: "evaluate", fn: JS_PICK_DROPDOWNS, args: <dropdowns> }` — react-select via `mousedown+mouseup+click` on `.select__control`, then on the matching option div. Match priority: exact → ci → startsWith → includes.
6. (If country dropdowns) `JS_PICK_DROPDOWN_TYPEAHEAD` — typeahead variant for large country lists.
7. (If iti phone widget present) `JS_FILL_PHONE_ITI` — flag click → United States → setNative digits-only.
8. `JS_DECLINE_DEMOGRAPHICS` — auto-pick "decline" option for any unset gender/race/ethnicity/veteran/disability react-select.
9. (Per `needs_review_dropdowns`) `JS_INSPECT_OPTIONS` then re-issue `JS_PICK_DROPDOWNS` with the corrected label from rendered alternates.
10. (If resume) `JS_CLICK_ATTACH` (Filestack — retry click 3× with sleeps), then `browser.act { kind: "upload", selector: "#resume", paths: [<pdf>] }`.
11. **Fill cover answers** — for each open-essay field (id matched by `cover_answers.md`'s headings), use native value setter to write the answer into the corresponding `<textarea id="...">` or `<input id="...">`. cover_answer_generator already enforces AI-disclosure policy.
12. `JS_VERIFY` — read back form state. Check that all required fields are populated.
13. **Click Submit.** Use `JS_SUBMIT` — bails if a visible captcha frame is present (set `allowVisibleCaptcha:true` only if you've confirmed the captcha is harmless).
14. Wait for `/confirmation` URL or for the confirmation page text. Use `JS_VERIFY_CONFIRMATION`.
15. **Email verification gate (Anthropic + a few others):** if `JS_DETECT_VERIFICATION` returns true, call `gmail_imap.wait_for_verification_code()` and submit it via `JS_SUBMIT_VERIFICATION_CODE`.
16. Capture the confirmation URL + body text.

### Form-fill incantations (distilled from MEMORY.md 2026-05-08)

- **react-select dropdowns:** `mousedown+mouseup+click` on `.select__control` (NOT the chevron button), wait ~300ms, then dispatch the same trio on `[id^=react-select-{id}-option]` whose textContent matches.
- **Filestack `#resume`:** UPLOAD FIRST, THEN CLICK ATTACH. (Updated 2026-05-13 PM after debugging the silent-failure problem.) The visually-hidden `<input id=resume>` is in the DOM from page load. Sequence: `browser.upload selector="#resume"` → wait 300ms → click the visible `<button>Attach</button>` sibling → wait 1s → verify the filename appears in `document.body.innerText` (Filestack swaps the input out for a 'filename + Remove' chip). If verification fails, retry the same sequence once. The OLD order (click-then-upload) silently no-op'd on most boards because Filestack hijacks the file chooser after the click, so CDP `setInputFiles` lands in a stale input. See `greenhouse_filler.py:JS_CLICK_ATTACH` docstring for the full writeup.
- **Plain text/textarea:** native value setter via `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, val)` + dispatch `input` event. `act:fill` no-ops on React.
- **Multiple greenhouse.io tabs:** the browser tool's targetId routing in `act` responses can lie. Always pass raw target id and verify via `location.href` inside the JS.

---

## Phase C: Bookkeeping (after browser confirms submission)

### 1. Write STATUS.md

```
submitted — YYYY-MM-DD HH:MM UTC

confirmation_url: <url>
confirmation_text: <first ~200 chars of confirmation page>
verification_code_used: <code if anthropic / gmail_imap was used>
submitted_by: auto (job-search subagent)
resume_attached: Cyrus_Shekari_Resume_<org>_<jid>_v2.pdf

Notes:
- AI-use questions answered "No." per 2026-05-13 policy.
- Demographics declined.
- (any role-specific notes worth flagging)
```

### 2. Update tracker.db

```python
conn = sqlite3.connect('projects/job-search/tracker.db')
conn.execute("UPDATE roles SET applied_by='auto', applied_on=? WHERE id=?",
             (datetime.utcnow().strftime('%Y-%m-%d'), role_id))
conn.commit()
```

### 3. Re-render xlsx

```bash
projects/job-search/role-discovery/.venv/bin/python projects/job-search/role-discovery/render_xlsx.py
```

(Cyrus signed off 2026-05-13 — this MUST run after every successful submit so the xlsx doesn't lag.)

---

## Failure handling

When something goes wrong, **abort and document — never recover at the cost of a bad submission.**

| Failure                                 | Action                                                                                              |
|----------------------------------------|------------------------------------------------------------------------------------------------------|
| Greenhouse API 404 on JD fetch         | Skip role. Append to batch log: "<slug>: JD fetch 404."                                              |
| dryrun spec has unrecoverable blockers | Skip role. Log blockers. Don't try to brute-force.                                                   |
| bullet_rewriter exhausts retries       | Skip role. Leave partial files in `submitted/<slug>/` flagged. Do NOT submit with master resume.    |
| cover_answer_generator validation fail × 2 | Skip role. Leave whatever was generated for human review with `STATUS.md = ABORT-REVIEW-NEEDED`. |
| Browser misbehaving (stale refs, hangs) | Restart browser session, retry once, then move on.                                                  |
| Submit button missing / unknown required | Take ONE screenshot to `submitted/<slug>/screenshots/`, write `STATUS.md` with reason, leave tracker row untouched, continue. |
| Captcha appears                         | Bail. Leave for human.                                                                              |

## Lever (UNBLOCKING via CapSolver — 2026-05-13)

Lever pipeline files exist (`role-discovery/lever_dryrun.py`, `lever_filler.py`, `adapters/lever.py`, dispatch in `inline_submit.py`). Prep half (JD, dryrun, resume, cover answers, plan) works end-to-end. Auto-submit was previously blocked because most Lever boards (Outreach, Spotify, Shield AI, Palantir TPM — sampled 2026-05-13) ship visible-challenge hCaptcha, not the invisible variant. Greenhouse uses invisible reCAPTCHA v3 which is why it works headless.

**Now wired (stub, awaiting key):** see captcha-solver section below.

- `inline_submit.py --role-id <id>` for a Lever role still does prep correctly.
- Manual hand-fill is possible: open the apply URL, the form is mostly pre-resolved by lever_dryrun, then a human solves the captcha.
- Open follow-ups (independent of captcha):
  - `lever_filler.emit_steps()` emits `args.arg` for evaluate, but the OpenClaw browser tool doesn't support a separate arg — inline data into the `fn` IIFE.
  - Resume upload: `setInputFiles` to `#resume-upload-input` doesn't trigger Uppy. May need `a.visible-resume-upload` click first or a direct POST to Lever's `/parse-resume` endpoint.

### Captcha solver (NopeCHA-first, CapSolver-fallback — 2026-05-13)

Vendor selection rationale: `CAPTCHA-SOLVER-DECISION.md`. Stealth-bypass result: `STEALTH-TEST-RESULT.md` (does NOT work — paid solver is the path).

**Code (in place, awaiting API key):**
- `role-discovery/captcha_solver.py` — vendor-agnostic class. `CaptchaSolver()` defaults to `vendor='nopecha'`; pass `vendor='capsolver'` (or set `CAPTCHA_VENDOR=capsolver`) for fallback. Methods: `.solve_hcaptcha(sitekey, page_url) -> token`, `.solve_recaptcha_v2`, `.solve_turnstile`, `.get_balance()`. Exceptions: `SolverNotConfigured` (no key), `SolverQuotaExceeded` (out of credits / rate-limited / IP-blocked — DON'T retry), `SolverError`, `SolverTimeout` (90s default, retries=2).
- `role-discovery/captcha_inject.py` — JS payloads for detect/inject (hCaptcha, reCAPTCHA v2, Turnstile). Unchanged.
- `lever_filler.emit_steps()` emits the same `captcha.handle` step. Runner contract is vendor-agnostic.
- Visible-Submit selector pinned to `button:has-text('Submit application'):visible`.

**Vendor selection (first match wins):** explicit `vendor=` arg → `CAPTCHA_VENDOR` env ("nopecha"|"capsolver") → default `nopecha`.

**Key resolution per vendor:**
- NopeCHA: explicit `api_key=` → `NOPECHA_API_KEY` env → `<project>/.nopecha-key` file.
- CapSolver: explicit `api_key=` → `CAPSOLVER_API_KEY` env → `<project>/.capsolver-key` file.

**Activation paths:**

*NopeCHA (preferred for cost):*
1. Sign in at https://nopecha.com (Google or GitHub OAuth — no email/password). Free tier auto-applies; paid subscription gets you a Token API key on /manage.
2. Free-tier caveats (per https://developers.nopecha.com/):
   - 100 credits/24h. **hCaptcha token = 10 credits → only ~10 hCaptcha solves/day on free.**
   - **Free tier excludes non-residential IP addresses.** Azure VM is datacenter — free tier will return HTTP 402/403 (`SolverQuotaExceeded`). The Token API requires a paid subscription for server-side use; the free tier is delivered via the browser extension only.
   - Sub plans: Basic ~$10/mo (≈500 hCaptcha/day), Pro ~$25/mo (≈5k/day). Predictable flat rate.
3. `echo '<key>' > projects/job-search/.nopecha-key && chmod 600 projects/job-search/.nopecha-key`.
4. Sanity: `role-discovery/.venv/bin/python role-discovery/captcha_solver.py --check` → `{"configured": true, "vendor": "nopecha", "credits": <int>}`.

*CapSolver (fallback — works from datacenter IPs, no daily cap):*
1. Sign up at https://capsolver.com, deposit ~$20 (~25k hCaptcha solves at $0.80/1k).
2. `echo '<key>' > projects/job-search/.capsolver-key && chmod 600 projects/job-search/.capsolver-key && export CAPTCHA_VENDOR=capsolver`.
3. Sanity: `CAPTCHA_VENDOR=capsolver role-discovery/.venv/bin/python role-discovery/captcha_solver.py --check` → `{"configured": true, "vendor": "capsolver", "balance_usd": <float>}`.

**Quota-exceeded behavior:** `SolverQuotaExceeded` is raised on HTTP 402/403/429 from NopeCHA or `balance`/`credit` errors from CapSolver. The class does NOT auto-retry these (won't recover in 2s). The runner should:
  - Treat as ABORT-CAPTCHA-FAIL for that role (write STATUS.md, leave tracker row untouched).
  - **Continue the batch** — other roles in the run may be Greenhouse (no captcha needed).
  - If quota-exceeded persists across multiple roles in one run, switch vendor: `export CAPTCHA_VENDOR=capsolver` and re-run.

**Stop-loss (per decision doc):** if monthly CapSolver spend exceeds **$15** (~5,000 solves, 100x expected), pause Lever auto-submit and investigate.

**Runner contract for the `captcha.handle` step (the only thing left to implement on the agent side):**

```
1. Run detect_fn → {sitekey, page_url, visible_challenge}.
2. If !visible_challenge: skip block (assume Submit went through; verify confirmation).
3. Try CaptchaSolver(); on SolverNotConfigured → log failure_reason and return failed-role.
4. solver.solve_hcaptcha(sitekey, page_url) → token (90s timeout, 2 retries inside the class).
5. Run inject_fn(token) → expect {found>=1}.
6. Click resubmit_selector. Wait. Verify confirmation page or error banner.
7. On any SolverError: take a screenshot, write STATUS.md=ABORT-CAPTCHA-FAIL, leave tracker row untouched, continue batch.
```

## Ashby

Files exist but smoke-test status uncertain as of 2026-05-13. Cohere apply page showed reCAPTCHA on inspection — likely the same captcha problem. See whatever the build-ashby-resume-and-finish subagent left in `applications/submitted/cohere-929b6c8e-...`.


**Never** flip `applied_by`/`applied_on` on a failed role.

---

## Conservatism rules

- Hard cap on overnight unsupervised submissions: **10**.
- Serial only — no parallel browser automation.
- Per-role time budget: 8 min.
- Don't restart the gateway. Don't change config. Don't touch crontab.
- When in doubt, ABORT and document over RECOVER and risk a bad submission.

---

## Related

- `role-discovery/inline_submit.py` — entry point
- `role-discovery/greenhouse_dryrun.py` — form schema fetcher
- `role-discovery/greenhouse_filler.py` — plan emitter (text fields, dropdowns, file upload, JS_*)
- `role-discovery/bullet_rewriter.py` — resume tailoring
- `role-discovery/cover_answer_generator.py` — essay answers
- `role-discovery/render_xlsx.py` — xlsx renderer
- `MEMORY.md` — pipeline architecture (2026-05-13 evening), AI-disclosure policy, greenhouse autofill recipes

## 2026-05-25 — Anduril legacy `boards.greenhouse.io` findings (1374 submit)

1. **8-char post-submit security code IS USED on Anduril.** Earlier playbook entries said only new-template `job-boards.greenhouse.io` mails the 8-char code; that's wrong. Anduril on legacy `boards.greenhouse.io` also mails it. `fetch_company_code.py anduril <since>` worked first try; 8 `security-input-N` slots filled via native setter + InputEvent.

2. **Anduril extra required `#country` react-select** (phone-input country code, "United States +1") NOT surfaced by GH boards-api dryrun. First submit failed with "Select a country". Resolved via mousedown/mouseup/click on `.select__control`. Worth adding PhoneInput country-code introspection to GH dryrun.
