# ESCALATE — LinkedIn auth missing on the OpenClaw browser

Filed: 2026-05-27 09:55 PDT
Filer: subagent (linkedin_authed_resolver build)
Routes to: main → Cyrus

## What's blocked
121 stranded LinkedIn rows in `projects/job-search/tracker.db` (highest-TC ones: Rivian TPM $264K, 4 Tesla PMs $221K each). The anonymous v3 pipeline-port resolver (`linkedin_resolver_pipeline.py`) cannot resolve them because LinkedIn's public JD pages do not inline the off-site Apply URL.

The new `linkedin_authed_resolver.py` (built today) is the right next layer — it walks each JD in a real Chromium browser and clicks the "Apply on company website" button to capture the off-site redirect. **But that button only appears for visitors with a valid `li_at` LinkedIn auth cookie.** Anonymous browser visitors only see a sign-up modal.

## What's broken
1. **`profile="user"` is not actually attached to a running browser.** The chrome-mcp wrapper (pid 184848) is alive but no Chrome process has been launched under it. `browser action=open profile=user` fails with:
   > `Could not find DevToolsActivePort for chrome at /home/azureuser/.config/google-chrome/DevToolsActivePort`
   The OS Chrome at `~/.config/google-chrome/` has never been started in remote-debug mode (no `DevToolsActivePort` file, only a `Crash Reports/` dir from May 3).
2. **`profile="openclaw"` is running fine** but its cookie jar (`~/.openclaw/browser/openclaw/user-data/Default/Cookies`) carries only anonymous LinkedIn cookies (`bcookie`, `bscookie`, `JSESSIONID`, `lang`, `lidc`, `__cf_bm`). **No `li_at`.** I verified by querying the cookies DB directly.
3. **Public JD pages confirmed unresolvable anonymously**, even with a real JS-rendered browser:
   - Rendered DOM of Rivian 4407094249 has 0 off-site ATS URLs (`linksFound: 0` across 318KB of rendered HTML).
   - The visible "Apply" buttons are `sign-up-modal__outlet` shims that open LinkedIn's sign-up modal, not an off-site redirect.

## What I need from you
Pick ONE:

**Option A (lowest friction) — drop a fresh `li_at` cookie into the openclaw browser profile.**
1. On a machine where you're logged into LinkedIn (any browser), open DevTools → Application → Cookies → linkedin.com.
2. Copy the value of the `li_at` cookie.
3. Tell me the value (or paste it into a file like `projects/job-search/.linkedin-li-at` with `chmod 600`).
4. I'll inject it into `~/.openclaw/browser/openclaw/user-data/Default/Cookies` (Chrome cookie DB) and re-run the resolver with `--profile openclaw`.
5. Re-rotate every ~30 days (LinkedIn `li_at` typically lasts ~1y but rate-limit-rotates can shorten it).

**Option B — set up the existing-session `profile="user"` properly.**
1. Launch Chrome on the VM with remote debugging on a known port and a user-data-dir that already has a LinkedIn session.
2. Provide me the launch command / path so the chrome-mcp wrapper can attach.
3. I'll re-run with `--profile user`.

**Option C — confirm we're abandoning the 121 LinkedIn-stranded rows** and I'll mark them all `status='blocked'` + `flags+='linkedin-only'` and stop trying.

## What's ready to go the moment auth lands
- `role-discovery/linkedin_authed_resolver.py` — full tactic ladder (apply-button capture + DOM scrape + company-careers + anonymous fallback). CLI mirrors the pipeline-port resolver.
- `role-discovery/test_linkedin_authed_resolver.py` — 23 unit tests, all green.
- DB never touched in dry-run; backup auto-created on first `--apply` write.
- Idempotent (re-runs skip already-tagged rows).
- **NOT yet wired into `weekly_run.sh`** — intentionally. I want a successful live sweep before adding it to the Monday cron. The anonymous step 3a stays in place as-is until then.

## Resume command (after auth is provisioned)
From `projects/job-search/role-discovery/`:
```bash
# Single-row smoke test against the highest-TC row
.venv/bin/python linkedin_authed_resolver.py --apply --role-id 829 --profile openclaw

# If that works, small batch
.venv/bin/python linkedin_authed_resolver.py --apply --limit 5 --profile openclaw

# Full sweep
.venv/bin/python linkedin_authed_resolver.py --apply --max-seconds 10800 --profile openclaw
```

## Why I'm stopping rather than pushing through
The subagent brief is explicit: "If LinkedIn shows a 'please log in' wall when using `profile='user'` → STOP, write `ESCALATE.md` describing the auth gap (cookie expired? wrong profile?), do NOT continue. Cyrus will refresh the auth and resume you." The anonymous-tactic-only path is already exercised by the existing weekly pipeline and is known to return UNRESOLVED for these 121 rows. Burning the browser + LinkedIn IP on a sweep that will write 121 × UNRESOLVED rows is destructive (it stamps `agent_notes` and the SELECT filter then skips them on the next attempt). I'd rather wait for auth than poison the queue.
