# Continuous Burndown V2 — 2026-05-24

## Mandate (from Cyrus, 2026-05-24)

Apply to **every open role** in `tracker.db` (currently 433). Order by `est_tc DESC NULLS MIDDLE`. Up to **3 hours per role** trying whatever it takes to submit. Quality bar: YOLO (LLM-tailored resume, no human review).

Last resort if no submit possible: write specific blocker into `agent_notes` column — what failed, what would unblock. Then move on. Never give up on a role until the full 3hr is spent.

## Behavior changes vs prior burndown

- **No more blanket Ashby/Lever skip.** Attempt every role. Captcha is not an automatic skip — only abandon if hard-blocked after a real effort (e.g. captcha challenge appears and we can't solve it on this attempt).
- **No more $-cost ceiling** (Cyrus has unlimited tokens). Time is the only budget.
- **Quiet Discord.** Worker subagents log to files, NOT Discord. Only escalations or batch summaries (every ~10 submits or ~2hr) go to channel.
- **Daily-autosubmit cron DISABLED** for duration of burndown to avoid race.
- **Main session stays responsive.** Orchestration runs as detached subagents.

## Architecture

### Orchestrator (this spawn)
Runs until queue empty OR Cyrus says stop. Picks next role by `est_tc DESC NULLS MIDDLE`, spawns one worker subagent for that role, waits for completion, picks next. Sequential, NOT parallel — avoids browser-instance and rate-limit contention.

Logs every dispatch + outcome to `applications/_burndown-v2-log.md` (append-only, one line per role).

### Worker (per-role subagent)
Receives one role-id. Has 3hr wall-clock budget. Mandate: do whatever it takes within reason to submit.

Tactics it may try in order:
1. `inline_submit.py --role-id <id>` (the standard pipeline)
2. If STATUS=PREP-READY → execute browser plan, watch for captcha. If captcha challenge appears, attempt anyway (e.g. checkbox click + wait; reCAPTCHA Enterprise may auto-pass).
3. If STATUS=PREP-READY-IFRAME-RUNNER → use `greenhouse_iframe_runner.py`.
4. If STATUS=PREP-READY-MANUAL (Workday) → run `workday_playwright.py --tenant <t> --url <u> --slug <s> --role-id <id>`.
5. If captcha fails the first time → retry once with: cleared cookies, longer humanization delays, no-headless mode if available.
6. If JD URL 404 / closed → mark `status='closed'`, agent_notes="role closed before apply".
7. If tenant requires sign-in-first → attempt account creation with `personal-info.json` + plus-aliased email.
8. If ALL tactics exhausted → write detailed blocker to `agent_notes` with what would unblock (e.g. "Ashby visible-challenge hCaptcha — needs CapSolver $20 funded").

On success: update tracker.db (`applied_by='auto'`, `applied_on=PT-today`), regenerate xlsx, write outcome to `applications/_burndown-v2-log.md`.

## Quality gates (still YOLO, but sanity)

- cover_answers.md has no AI-disclosure leak ("No" everywhere except Anthropic exception)
- Resume PDF is 1 page
- All cover-answer numbers appear in personal-info.json or resume
- Work auth: US citizen, authorized yes, sponsorship-now no, sponsorship-future no
- Demographics: decline first; if blocking, use `demographics_forced_fallbacks`
- Travel: 100%
- LinkedIn manual-apply rows NEVER auto-touched

## agent_notes blocker schema

When a role can't be applied to, write a one-line entry to `roles.agent_notes`:

```
BLOCKED 2026-05-24: <category> | <one-sentence why> | <unblock>
```

Categories: `captcha-hard`, `account-required`, `tenant-unsupported`, `jd-404`, `manual-apply-only`, `runtime-error`, `other`

## Logging

- `applications/_burndown-v2-log.md` — append-only. One line per role: `<ts> <role-id> <company> <title> <outcome> <runtime>`
- `applications/_burndown-v2-blockers.md` — categorized blocker rollup, regenerated periodically by orchestrator (so we can see patterns)
- Per-role detail still under `applications/submitted/<slug>/STATUS.md`
- `MEMORY.md` updates from orchestrator only after every 25 roles processed (not per role)

## Stop conditions

- Queue empty
- Cyrus says stop
- Orchestrator runtime > 60 hours uninterrupted (safety cap — orchestrator restarts itself if needed via a follow-on spawn)
- ≥10 consecutive workers fail with the same blocker category → orchestrator escalates to channel and pauses for human input

## Communication etiquette

- Per-role progress: file logs ONLY. No Discord.
- Batch summary: every 10 successful submits OR every 2hr (whichever first) → ONE Discord message to channel 1501827950474166332.
- Escalation: only if blocker pattern detected (≥10 same-category) or unrecoverable crash.
- Cyrus may interject anytime. He/main session can kill or steer the orchestrator via `subagents` tool.
