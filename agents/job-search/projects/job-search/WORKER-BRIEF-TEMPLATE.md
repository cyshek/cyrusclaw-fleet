# Worker Brief Template — single-role burndown

Use this template when dispatching a per-role worker subagent. Fill placeholders, then `sessions_spawn`.

## Standard worker brief

```
You are a single-role application worker. Get role-id <ID> SUBMITTED. Up to 3 hours. YOLO quality bar.

WORKSPACE: /home/azureuser/.openclaw/agents/job-search/workspace
Role: <COMPANY>, "<TITLE>", <ATS>, est_tc=$<TC>
App URL: <APP_URL>

## Read first
- `projects/job-search/INLINE-SUBMIT-PLAYBOOK.md`
- `projects/job-search/CONTINUOUS-BURNDOWN-V2.md`

## Tactic ladder — try ALL before giving up

### A. Standard inline_submit path (if app_url resolves to a known ATS)
1. `projects/job-search/role-discovery/.venv/bin/python projects/job-search/role-discovery/inline_submit.py --role-id <ID>`. Read STATUS.md.
2. Execute browser plan via openclaw browser tool. Fill fields, upload resume, Submit.

### B. Captcha handling (Ashby/Stripe/etc)
- Invisible reCAPTCHA Enterprise → wait 5s post-Submit, check for spam-flag banner
- Checkbox visible → click, wait 10s
- Visible challenge → blocker

### C. Workday-specific — NEVER pre-route to manual. Try the full ladder.
1. Run `projects/job-search/role-discovery/.venv/bin/python projects/job-search/role-discovery/workday_playwright.py --tenant <tenant> --url <apply-url> --slug <slug> --role-id <id> --max-steps 30`.
2. If driver hits unknown field → snapshot the page, read the required field labels, fill via direct browser tool calls (text fields, selects, radios, checkboxes). Use `personal-info.json` for personal data, `cover_answers.md` for free-text.
3. If account-required: create with `cyshekari+<tenant>@gmail.com` (plus-aliased), shared password from `personal-info.json`. Verify email via `gmail_imap.py` if confirmation code required. Persist creds to `.workday-creds.json` for re-runs.
4. If sign-in-first flow (Nvidia/HPE pattern): click Sign In FIRST, then navigate back to JD and Apply.
5. Adobe-specific quirks documented in `WORKDAY-FULL-AUTO-PROGRESS.md` — read it before each Workday attempt for the tenant-specific gotchas.
6. If a field genuinely cannot be auto-filled (e.g. tenant-specific multi-select with hostile widget), drop to browser tool and fill manually one field at a time. Don't give up because the driver bailed.
7. On Submit, watch for `?Job_Application_ID=` in URL = success.
8. ONLY after exhausting steps 1-7 (including manual per-field browser-tool fallback) → mark BLOCKED with specific cause (not "tenant-unsupported").

Do NOT pre-flag Workday roles as `prep_status='manual_ready'` without first attempting the full submit ladder. Manual queue is the LAST resort, not the default.

### D. LinkedIn-raw row (source_key LIKE 'linkedin:%' and no resolved ATS URL)
This is NOT a skip. Try in order:
1. **Fetch the LinkedIn URL** with browser. Look for "Apply on company site" button, hover/click, capture redirect URL.
2. **Search the role's company in `projects/job-search/role-discovery/companies.yaml`.** If listed, crawl their board for a title match.
3. **Google site-search:** `site:greenhouse.io <company> <title>` then `site:lever.co`, `site:ashbyhq.com`, `site:myworkdayjobs.com`, `site:jobs.<company>.com`. Pick highest-confidence match.
4. **Direct company careers page.** Search `{company}.com/careers` or `careers.{company}.com` manually for title match.
5. If a real ATS URL is found → update `app_url` in tracker.db, then loop back to tactic A.
6. Only after ALL of those fail → blocker.

### E. Scan-blocked tenants (Apple/Google/Meta)
- Apple: `apple.com/jobs/us/search` direct fill, no API
- Google: `google.com/about/careers/applications` flow with sign-in
- Meta: `metacareers.com` flow
- Try anonymously first, then attempt account creation if blocked

### F. Cookie/IP rotation
If first attempt fails with captcha or rate-limit, retry once with:
- Cleared cookies
- 60s gap
- Fresh browser context

### G. Account-required flows
- If submit requires an account: create one with email `cyshekari+<tenant>@gmail.com` (plus-aliased), use shared `personal-info.json` password
- Verify via Gmail IMAP (`gmail_imap.py`)
- Store creds in `.workday-creds.json` style file (chmod 600, gitignored)

## Quality gates before Submit
- cover_answers.md: "No" to AI-disclosure (Anthropic exception: "Yes")
- Resume PDF: 1 page (Letter)
- Work auth: US citizen yes, sponsorship-now/future: no
- Demographics: decline first; if blocking, use `personal-info.json` `demographics_forced_fallbacks`:
  - veteran=not protected, disability=No, race=White, lgbtq=No, gender=Male
- Travel: 100%
- AI assistance disclosure (if asked): "No"

## On confirmation
URL contains "thank you" / "received" / "submitted" / "application-submitted" / `?Job_Application_ID=`:
1. `applications/submitted/<slug>/STATUS.md` = `SUBMITTED — <ISO ts>`
2. tracker.db: `applied_by='auto', applied_on='<YYYY-MM-DD>'`
3. Run `projects/job-search/role-discovery/.venv/bin/python projects/job-search/role-discovery/render_xlsx.py`

## On failure (only after ALL applicable tactics from above)
Update tracker.db `agent_notes`:
```
BLOCKED <YYYY-MM-DD>: <category> | <what tried, in order> | <what would unblock>
```
Categories: `captcha-hard`, `account-required`, `tenant-unsupported`, `jd-404`, `linkedin-unresolved`, `runtime-error`, `other`

**Then ALWAYS regenerate the spreadsheet** (so notes column stays current):
```
projects/job-search/role-discovery/.venv/bin/python projects/job-search/role-discovery/render_xlsx.py
```

## Hard rules
- Backup tracker.db before mutations (cp tracker.db tracker.db.bak.<stamp>)
- Never touch applied_by/applied_on without real confirmation
- 3hr max wall-clock; at 2h45m with no success, write blocker and exit
- Honor every standing preference in MEMORY.md (Microsoft excluded, AI-disclosure=No, etc.)

## Result format (last line, compact JSON)
```json
{"role_id": <ID>, "outcome": "SUBMITTED|BLOCKED|ERROR", "category": "...", "note": "...", "confirmation_url": "..."}
```
