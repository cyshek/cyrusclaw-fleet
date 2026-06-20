# Overnight migration report — 2026-05-13

**Time:** ~05:42 UTC start → ~05:55 UTC report write.
**Subagent:** `migration-inline-pipeline-overnight`.
**Status:** Migration documentation + driver build complete. Smoke-test prep validated end-to-end on 1 role. Did NOT proceed to a real submit (rationale below).

---

## Phase 1: Documentation + memory updates — ✅ DONE

- `MEMORY.md` — added "Pipeline architecture (2026-05-13 evening)" section covering the new inline pipeline, screenshot policy, _stage_greenhouse retirement, and queued/ drain behavior.
- `TOOLS.md` — replaced the "Role discovery pipeline" section with the new inline-submit description (cover_answer_generator added, inline_submit driver, deprecation notice for `_stage_greenhouse.py`).
- `projects/job-search/INLINE-SUBMIT-PLAYBOOK.md` — NEW canonical playbook (~12 KB, ~280 lines). Covers:
  - Folder layout for `applications/submitted/<slug>/`
  - Greenhouse API endpoints and HTML→md helper origin
  - All Phase A (Python prep) phases with code sketches
  - All Phase B (browser execution) steps including the JS_* incantations from MEMORY.md
  - Phase C bookkeeping (STATUS.md, tracker UPDATE, render_xlsx)
  - Failure handling table (per-phase abort behavior)
  - Conservatism rules

## Phase 2: Inline submit driver — ✅ DONE

`projects/job-search/role-discovery/inline_submit.py` — 460 lines.

CLI:
- `--role-id <id>` — pull from tracker.db
- `--slug <slug>` — re-prep an existing slug (re-runs all phases)
- `--batch <N>` — auto-pick next N open Greenhouse roles not in queued/submitted
- `--dry-run` — skip the PREP-READY status marker

What it does per role (all five phases inline, serial):

1. Resolve role from tracker.db; refuse if `applied_on IS NOT NULL`.
2. Create `applications/submitted/<slug>/` and write `JD.md`, `meta.json`, `prefill.json` from the Greenhouse `/v1/boards/<org>/jobs/<jid>` API response.
3. Run `greenhouse_dryrun.py` to produce `applications/dryrun/<org>-<jid>.json`. Abort if `blockers > 0`.
4. Run `bullet_rewriter.py --render --max-loops 3` for tailored docx + 1-page PDF. Uses a transient `applications/queued/<slug>` symlink → `submitted/<slug>` because bullet_rewriter currently hardcodes `APPS_DIR=applications/queued`. Symlink is removed after.
5. Run `cover_answer_generator.py --slug <slug>` for `cover_answers.md`.
6. Build the browser plan via `greenhouse_filler.build_plan + emit_steps`, **inject cover_answers.md text into matching essay textareas** (overrides dryrun's why-company-template default), copy PDF into `/tmp/openclaw/uploads/`, write plan to `role-discovery/output/inline-plan-<slug>.json`.
7. Write `STATUS.md = "PREP-READY — ..."` (or skip with `--dry-run`).

Key design choices:
- **Aborts always document.** Each phase has its own try/except that writes `STATUS.md = "ABORT-<PHASE>"` with the error before bailing. The role's tracker row is left untouched.
- **Cover-answer injection.** Discovered during smoke test that the dryrun spec puts a *generic* "Why Anthropic" template into the form, which would clobber the JD-specific essay. Added `merge_cover_answers_into_plan()` that parses cover_answers.md `## <question>` blocks and overrides matching `text_fields[id]` by label match (exact → substring).
- **Resume PDF override.** The dryrun spec records the master PDF path. Inline pipeline ignores that and points the plan at the freshly tailored PDF.
- **Per-phase subprocess timeouts:** dryrun 60s, bullet_rewriter 360s, cover_answer 240s.
- **No browser automation in the script.** The script's job ends at "plan ready". The *agent* executes the plan via the `browser` tool. (See "What I did NOT do" below.)

## Phase 3: Smoke test — ⚠️ PARTIAL (prep validated; no real submit)

Ran prep on **Anthropic role 924, Technical Program Manager, Discovery (jid 5215124008)** end-to-end:

- Elapsed: **54.7 s** total (JD fetch + dryrun + bullet_rewriter render with page-fit loop + cover_answers + plan emit).
- All 5 phases OK. Artifacts written to `applications/submitted/anthropic-5215124008/`:
  - `JD.md` (8 KB), `meta.json`, `prefill.json`
  - `Cyrus_Shekari_Resume_anthropic_5215124008_v2.pdf` — **1 page, 55 KB, clean tailoring** (reads correctly via pdftotext, role headers + bullets all present, JD-aligned).
  - `cover_answers.md` — 2 questions answered (Earliest start + Why Anthropic). Voice is conversational, JD-grounded, no AI-disclosure leaks. Sample of "Why Anthropic" opens: *"The Discovery role lines up almost exactly with what I do today. At Microsoft I own compute planning and allocation for Azure's resilience validation program, forecasting capacity across 45+ annual large-scale drills..."*
  - `rewrites.json`, `tailoring-notes.md`
- Browser plan: `role-discovery/output/inline-plan-anthropic-5215124008.json`. 10 steps (open → click Apply → fill text → react-select dropdowns → phone iti → demographics decline → Filestack attach → upload → verify). 8 text fields, 6 dropdowns, no needs-review, no unknowns. Cover override audit: 2 fields overridden (lengths went 20→121 and 1519→1139 — the second being the dryrun template being replaced with the real essay).

**Did NOT proceed to actually submit this role**, for two reasons:

1. **The other subagent (`submit-only-batch6-retry`) is actively driving the same OpenClaw browser** (it submitted `chime-8382253002` at 05:42 and was still working as of 05:50). MEMORY.md explicitly warns about target-id collision when multiple greenhouse.io tabs are open. Concurrent browser drivers = footgun, and the brief said "DO NOT interfere with it."
2. The actual **browser-execution half of the playbook is heavy** (10+ tool calls per role, plus an email-verification gate for Anthropic via `gmail_imap.wait_for_verification_code()`). With the other subagent already burning through the queued backlog, the marginal value of me submitting one more was lower than the risk of a botched concurrent submission contaminating Cyrus's inbox or the tracker.

The prepped packet is sitting at `STATUS.md = "PREP-READY — 2026-05-13T05:51:05+00:00"`. Cyrus can either (a) inspect the artifacts and approve a manual submit, or (b) hand it to a fresh submit subagent that runs solo (no concurrent browser work).

## Phase 4: Other subagent's progress

The `submit-only-batch6-retry` subagent ran in parallel. Visible results between 05:25-05:50 UTC:

| time (UTC) | submitted slug | role |
|---|---|---|
| 03:25 | anthropic-4985877008 | Forward Deployed Engineer, Applied AI |
| 03:41 | glean-4651990005 | Founding Forward Deployed Engineer |
| 03:42 | dbt-labs-4664399005 | Customer Solutions Architect (Austin) |
| 05:32 | anthropic-4989788008 | Technical Program Manager, Security |
| 05:42 | chime-8382253002 | Product Manager, Data Platform |

Plus 3 earlier today (Anthropic Human Data Platform, Arize AI, Scale AI Robotics, Vercel v0) were already submitted by the time I started.

It's still running as of report write. Queued pile: 47 (down from 48 — `chime-8382253002` was the only one drained tonight that started in queued/; the others were direct submits).

## Final tracker stats

```
Total applied: 15
  prior to today: 6
  today (2026-05-13): 9 (all applied_by=auto)
```

Today's 9 auto-submits: 3 Anthropic, 1 Arize, 1 Chime, 1 Glean, 1 Scale AI, 1 Vercel, 1 dbt Labs.

## Decisions for Cyrus in the morning

1. **Approve and submit the prepped Anthropic Discovery TPM packet?** It's at `applications/submitted/anthropic-5215124008/` PREP-READY. Resume + cover are validated. If yes, just spawn a single-role submit subagent pointing at the slug + plan path; it should take <10 min including the gmail verification gate.
2. **Sign-off to retire `applications/_stage_greenhouse.py`?** The new inline pipeline replaces it. Recommend trash to `~/.local/trash/` once the queued/ backlog is fully drained (47 packets remaining; at the other subagent's pace that's ~1-2 more nights of work).
3. **Cover-answer voice on small companies — recommend gut-check.** I only sampled it on Anthropic (large, opinionated company; the model has plenty to ground on). Recommend Cyrus eyeball the next Modal Labs / Cursor / Baseten cover_answers.md when one is generated, since the model may produce something stiffer when the JD is sparser. The voice prompt in `cover_answer_generator.py` is good but worth verifying on smaller-co.
4. **Symlink shim hack for bullet_rewriter** — works fine but is ugly. Future cleanup: add `--out-dir` to bullet_rewriter.py and remove the shim from inline_submit.py. Not blocking.

## What I did NOT do that you might expect

- **No real overnight submissions via the new inline driver** (rationale above — concurrent-browser footgun + diminishing returns vs the other subagent's in-flight work). Hard cap of 10 was not approached; today's 9 came entirely from the other agent and earlier-day submits.
- **Did NOT trash `_stage_greenhouse.py`** — leaving for your sign-off (item 2 above).
- **Did NOT touch `applications/queued/INDEX.md`** — that's still the old file from the prior pipeline. Will rot naturally as queued/ drains; can clean up later.
- **Did NOT update `weekly_run.sh`** to reference inline_submit. The new pipeline is *on-demand* (per-role / per-batch via subagent), not weekly. Weekly run is still: crawl → merge → render → digest. No change needed.
- **Did NOT add a cron entry** for inline_submit. Per the brief: don't touch crontab.
- **Did NOT add `--out-dir` to bullet_rewriter** — used the symlink shim instead to minimize blast radius on working code overnight.

---

## Files added/modified

- `MEMORY.md` — 1 new section
- `TOOLS.md` — replaced "Role discovery pipeline" section
- `projects/job-search/INLINE-SUBMIT-PLAYBOOK.md` — NEW (12 KB)
- `projects/job-search/role-discovery/inline_submit.py` — NEW (~460 lines, 19 KB)
- `projects/job-search/applications/submitted/anthropic-5215124008/` — NEW (prep-ready, not yet submitted)
- `projects/job-search/role-discovery/output/inline-plan-anthropic-5215124008.json` — NEW (browser plan ready to execute)
- `/tmp/openclaw/uploads/Cyrus_Shekari_Resume_anthropic_5215124008_v2.pdf` — staged for browser upload
