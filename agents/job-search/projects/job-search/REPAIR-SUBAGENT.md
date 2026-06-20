# REPAIR-SUBAGENT.md — Adapter auto-repair brief

You are an **isolated subagent** spawned by the `job-search adapter smoke test` cron to attempt repairs on newly-broken role-discovery adapters. **Do not auto-merge.** Your job is **DETECT → DIAGNOSE → PROPOSE** only.

## Workspace
- Project root: `/home/azureuser/.openclaw/agents/job-search/workspace`
- Role discovery dir: `projects/job-search/role-discovery/`
- Venv: `projects/job-search/role-discovery/.venv/bin/python`
- Live adapters: `projects/job-search/role-discovery/adapters/<name>.py` — **NEVER overwrite these directly.**
- Candidate scratch dir: `projects/job-search/role-discovery/adapters/_repair/` — **safe to write into.** Nothing in prod imports from this directory (verified: `run.py` and `adapters/__init__.py` only import top-level adapter modules).

## Inputs
- `projects/job-search/role-discovery/_smoke-results.json` — current run (just produced by the cron).
- `projects/job-search/role-discovery/_smoke-baseline.json` — last-known-good shape per adapter (the `sample_role` field is your reference contract).
- Live adapter source files (one per ATS).

## Scope (HARD LIMITS)
- **Max 2 adapters per run** (pick the first 2 from `newly_broken[]` in `_smoke-results.json`).
- **~30 min budget per adapter.** If you can't get green in 30 min, write a diagnosis-only file and move on.
- **Microsoft is permanently scan-blocked.** Its baseline status is `fail-expected`; the smoke test will never classify it as `newly_broken`. If you somehow see it in the list, skip it.
- **DO NOT touch:** submit pipeline, tracker.db, `companies.yaml`, cron prompts, anything outside `adapters/_repair/` and the repair report file.

## Procedure (per newly-broken adapter)

1. **Identify.** Read `_smoke-results.json` → `adapters.<name>`. Capture `error`, `traceback` (if present), and the **last-known-good** `sample_role` from `_smoke-baseline.json` (this is your contract — fields that must still appear).

2. **Reproduce.** Run the single probe:
   ```bash
   .venv/bin/python -c "
   import sys; sys.path.insert(0,'.')
   from adapters import <name>
   roles = <name>.fetch(...)  # see PROBES in smoke_test_adapters.py for args
   print(len(roles)); print(roles[:2])
   "
   ```
   If the script raises, capture the full traceback. If it returns 0 roles, fetch the raw endpoint with `curl -sS` (or `requests.get` from a one-liner) and inspect the body — has the JSON shape changed? Did the URL move? Is it a 404?

3. **Diagnose.** Compare the live API response shape to `sample_role` in the baseline:
   - If keys moved (e.g. `posted_at` is now nested under `meta.created_at`) → it's a shape change.
   - If the endpoint 404s → URL/path changed (most common for Workday tenant moves).
   - If the response is HTML/captcha → anti-bot wall went up. **Stop and escalate**; do not try to bypass.

4. **Patch in a scratch branch.** Copy the live adapter to a candidate path:
   ```
   cp adapters/<name>.py adapters/_repair/<name>.py.candidate
   ```
   Edit ONLY the candidate file. Keep the patch minimal — fix the broken extraction; do not refactor.

5. **Verify.** Run the candidate against the same probe by temporarily importing from `_repair`. Use a small driver script in `_repair/` (e.g. `_repair/_verify_<name>.py`) that loads the candidate module via `importlib.util.spec_from_file_location`, calls `.fetch(...)` with the same args as `smoke_test_adapters.PROBES`, and applies the same OK/FAIL checks (count > 0, company/title/url present, posted_at where required). **Do not** modify `smoke_test_adapters.py` or anything in the live `adapters/` package to test the candidate.

6. **Report.**

   **If candidate is GREEN:**
   - Write `projects/job-search/applications/_adapter-repair-<name>-<YYYYMMDD-HHMM>.md` containing:
     - `## Summary` — one-line: what broke, what you changed.
     - `## Diff` — unified diff of live vs candidate (use `diff -u adapters/<name>.py adapters/_repair/<name>.py.candidate`).
     - `## Smoke output` — paste the candidate's probe output (role count, first 2 roles).
     - `## Candidate path` — absolute path to `_repair/<name>.py.candidate`.
     - `## Recommend merge` — bullet starting with `RECOMMEND MERGE:` and the exact `cp` command Cyrus would run to promote it.
   - Post **ONE** Discord message to the agent channel: a 3-line summary (adapter name, root cause, "patch ready at <path> — approve merge?"). Reference the full report path. **Do not** run the `cp` yourself.

   **If candidate is RED (or you can't produce a candidate):**
   - Write `projects/job-search/applications/_adapter-repair-<name>-<YYYYMMDD-HHMM>.md` with:
     - `## Summary` — what broke, best guess at why.
     - `## Reproduction` — exact command + output that demonstrates the failure.
     - `## Suspected root cause` — shape change / 404 / anti-bot / unknown.
     - `## Next steps` — what a human should investigate.
   - Post ONE Discord escalation message with adapter name + suspected cause + "see <report path>".

## Output discipline
- ONE Discord message per adapter. No spam.
- Always reference report files by absolute path.
- Never claim a merge happened — you don't have authority to write to live adapters.
- If the candidate path already exists from a prior run, overwrite it (newest wins).

## Done condition
You're done when:
- Both target adapters have either a green candidate + recommend-merge report, OR a diagnosis report + escalation.
- Each report file exists on disk.
- One Discord message per adapter has been sent.
- Final message to parent summarizes: adapters touched, candidate paths (if any), report paths.
