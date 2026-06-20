# inline_submit.py — STATUS-marker split for greenhouse_iframe captcha-runner

**Date:** 2026-05-24 17:13 UTC
**Origin:** HANDOFF.md "Next session priorities #1" / BACKLOG.md 2026-05-24 follow-up #1 ("Wire greenhouse_iframe_runner.py into inline_submit.py dispatch")
**Scope:** purely additive STATUS.md branch for `greenhouse_iframe` roles with a wrapper URL; no submit semantics changed.

## What this does

Today `inline_submit.py` writes the same `PREP-READY` STATUS marker for every prepped role. The daily-autosubmit cron / calling agent reads that marker and runs the generic browser-tool plan against the URL embedded in `plan.json`. For `greenhouse_iframe` packets that URL points at `https://job-boards.greenhouse.io/embed/job_app?...`, which is now silently reCAPTCHA-Enterprise gated. Every greenhouse_iframe submit fails.

The validated 2026-05-24 workaround is `role-discovery/greenhouse_iframe_runner.py`: load the company's careers-page wrapper URL (`https://www.databricks.com/.../?gh_jid=Y`), find the Greenhouse iframe Frame, replay the filler steps inside `frame.evaluate()`, click Submit. The runner already exists; the wiring step that was missing is "tell the calling cron to invoke the runner instead of the generic plan."

This candidate adds the minimal signal:

- When `ats == "greenhouse_iframe"` AND `role.wrapper_url` is set, the STATUS marker becomes `PREP-READY-IFRAME-RUNNER` and the body includes the runner command verbatim.
- All other ATSes (and any greenhouse_iframe role with no wrapper URL — would be an unusual case but handled defensively) get the existing `PREP-READY` marker unchanged.

Behaviour for currently-prepped packets and for native greenhouse/ashby/lever/workday is identical.

## Files

- `_repair/inline_submit.py.candidate` — proposed file; diff is a single if/else replacing one `write_text` call.

## Verification

- **AST parse:** `ast.parse()` on the candidate passes.
- **Diff is local:** `diff inline_submit.py _repair/inline_submit.py.candidate` shows only the intended block; no incidental changes.
- **Behavioural check (manual dry-run):** any role whose URL doesn't match `greenhouse_iframe` continues to hit the original branch (which is preserved verbatim, just indented under `else:`). The new branch only fires when `ats == "greenhouse_iframe"` AND `wrapper_url` is truthy — both conditions are already populated during `_resolve_role()` (see lines 197-199 and 326-328 of the live file).

## Promote / consumer wiring (what else must change before this matters)

This is **half** of P0 follow-up #1. After promoting the candidate, the daily-autosubmit cron prompt also needs an update so it dispatches on the new marker. Suggested cron-side logic:

```
for each applications/submitted/<slug>/STATUS.md whose first line starts with PREP-READY-IFRAME-RUNNER:
    run: .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug <slug>
    on success/abort: rewrite STATUS.md per INLINE-SUBMIT-PLAYBOOK.md
```

That cron prompt update is **out of scope for this candidate** (cron modification is excluded by the burndown brief). The runner is already idempotent — if the cron is updated later, packets prepped today are picked up automatically because the marker remains until something rewrites it.

## Recommend-merge

Yes, but conditioned on the operator wiring up a cron-side consumer for `PREP-READY-IFRAME-RUNNER`. Otherwise the new STATUS marker would just sit there until someone runs the runner manually — still strictly better than the current state (where the generic plan would silently fail on captcha), but not autonomous.

### Promotion command
```
cp projects/job-search/role-discovery/_repair/inline_submit.py.candidate \
   projects/job-search/role-discovery/inline_submit.py
```

### Quick smoke after promotion
- Re-run any greenhouse_iframe prep (e.g. `inline_submit.py --slug datadog-<jid>` against an existing packet) with `--dry-run` cleared and confirm the resulting STATUS.md begins `PREP-READY-IFRAME-RUNNER` and includes `wrapper:` + the runner command.
- For a native greenhouse role, confirm STATUS.md still begins plain `PREP-READY`.

## Follow-ups (not blocking)

- Document the new marker in `INLINE-SUBMIT-PLAYBOOK.md` under a `§ greenhouse_iframe runner` heading. (Out of scope here — the playbook is a Cyrus-facing doc and a copy edit needs the operator's review.)
- Add a corresponding `runner: "playwright-iframe"` field to the emitted plan JSON so a future generic dispatcher can switch on plan.runner instead of grep'ing STATUS.md. Not done here to keep the patch surgical.
- Once the cron is wired, retire the prep_status='manual_ready' Manual Ready xlsx tab for greenhouse_iframe rows (they're no longer manual).
