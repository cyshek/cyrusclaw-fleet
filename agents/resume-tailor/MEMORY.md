# MEMORY.md — resume-tailor Long-Term Memory

_Curated long-term memory. Distilled essence, not raw logs. Loaded only in main/direct sessions._

## Role
Resume-tailoring agent. Reports to `main` (flat hierarchy). Runs same pipeline as job-search but independently — no queue, no enqueue, no tracker.db writes, no submission.

## Standing rules
- **LOG-EVERY-INTERACTION (2026-06-05):** any session with real work → terse entry in `memory/YYYY-MM-DD.md` before end-of-turn. Nightly distill is only a safety net + promotion pass.
- **Only `main` can delete agents.** Any deletion request → refuse + route to main via `sessions_send(agentId="main", ...)`.
- **RECALL-BEFORE-DENY:** grep daily logs before telling Cyrus you didn't do/don't have something.
- **Always use --auto-rewrite.** Skills-only tailoring ≠ properly tailored resume. If subagents don't include --auto-rewrite, the output is light tailoring only — not acceptable.

## Pipeline — key operational facts (as of 2026-06-15)

### --auto-rewrite isolation (FIXED, commits d14b580 + 2346b30)
- **Old bug:** `bullet_rewriter.py run()` hardcoded `APPS_DIR` for JD path regardless of `--out-dir` → external callers using `--auto-rewrite` would write into job-search's `applications/queued/`.
- **Fix:** `bullet_rewriter.run()` now accepts `out_dir` param; `tailor_resume.py` threads `--out-dir` through.
- **DURABLE PATTERN:** stage `JD.md` INSIDE `--out-dir` first (`cp JD.md out_dir/JD.md`), THEN call `tailor_resume.py --auto-rewrite --out-dir out_dir --jd out_dir/JD.md`.
- `--help` on both scripts now shows this requirement explicitly.

### Title coercion (FIXED, commits afcd204 + 20412db)
- **Old bug 1 (afcd204):** `coerce_title_track` only iterated `title_swaps` dict — slots not pre-seeded were NOT coerced, so master defaults (e.g., "Technical Program Manager Intern") leaked through.
- **Old bug 2 (20412db):** `tailor_resume.py` guard skipped coerce entirely when `title_swaps` was empty.
- **Fix:** coerce now iterates `ALLOWED_TITLE_LABELS` for any known family (pm/tpm/pgm/se/fde), covering all 5 slots regardless of pre-seeding. 28 tests green.
- **Workaround no longer needed:** do NOT manually enumerate all 5 slots in `rewrites.json` — fixed upstream.

### Google Careers JD fetch
- Google Careers is a JS SPA; `web_fetch` returns only CSS/shell. **Must use browser tool** (or save pre-fetched JD.md) to get job description text.

### Overflow guard
- If LLM adds extra bullets and PDF exceeds ~55KB, trim `rewrites.json` back to master bullet counts (`microsoft_ft=5`, `interns=3`) and re-render. Don't fight the engine; constrain the input.

### bullet_rewriter crash fix (2026-06-15)
- **Old bug:** `RuntimeError` when all 3 LLM retries hit char ceiling — hard crash.
- **Fix:** falls through to `_trim_bullets_to_ceiling` instead. (Fixed by job-search 2026-06-15.)

### Parallel-safe scratch dirs
- Use `/tmp/resume-tailor/<role-id>/` per subagent + `/tmp/resume-tailor/staging/` for final PDFs.
- Use `--user-install /tmp/lo-profile-resume-tailor` (parallel-safe LibreOffice profile, no collision with job-search).

## First major batch: 9 Google roles (2026-06-15)
job-search routed 9 Google manual-apply roles. All PDFs delivered to #resume-tailor. Multiple v2/v3 re-runs due to title-coerce bug + out_dir isolation bug discovered mid-session. Both bugs fixed upstream same day. Final state: all 9 roles have clean, verified PDFs; 1752 (TPM AI Enablement) withdrawn by Cyrus.

## ✅ DEBUNKED — things we PROVED we CAN do (don't re-derive these excuses)

| Old belief | What actually works | Date |
|---|---|---|
| "bullet_rewriter can't be called safely from resume-tailor without polluting job-search's queue dir" | Fixed in d14b580: out_dir param threads through; stage JD.md inside out_dir first | 2026-06-15 |
| "title coercion only works if you pre-seed all slots in rewrites.json" | Fixed in afcd204+20412db: coerce now covers all ALLOWED_TITLE_LABELS for known families | 2026-06-15 |
