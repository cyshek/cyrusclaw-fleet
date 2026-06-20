# Per-tenant submit smoke probe — pattern doc

**Origin:** BACKLOG.md P2 → "Before queuing 5 packets that all hit same blocker, probe 1 first. Add to `inline_submit.py --batch`."
**Author:** burndown subagent, 2026-05-24 17:25 UTC
**Status:** pattern only; no code change. The "add to `inline_submit.py --batch`" framing is misleading — see "Why not inside --batch" below.

## What we want

Today the daily-autosubmit cron preps N packets, then drives N browser submits. If the first packet hits a captcha gate or a tenant-specific Formik wall, the next N-1 will too — but we burn LLM credits + cron time prepping them anyway. We want a cheap signal to abort the batch after one failure of a class we know is sticky.

## What's already cheap

`greenhouse_iframe_runner.py --slug <slug> --dry-run` already does the **field-fill-then-stop-before-Submit** dance and returns a JSON report including `pre_submit.grecapErrText`. For greenhouse_iframe packets, this is the right smoke.

For other ATSes (greenhouse native, ashby, lever, workday, lever-via-careerpuck) there's no equivalent dry-run runner today. They could be added as separate helpers, but the highest-impact tenant family right now is greenhouse_iframe.

## What can't easily be done at prep time

A static HTML fetch of the embed form does NOT distinguish captcha-gated tenants from clean tenants — every tenant ships exactly 1 captcha reference in the form HTML and no static `data-sitekey` attribute (captcha is JS-rendered after hydration). Smoke-probing without a headless browser is therefore not viable for the captcha question.

Empirical verification (2026-05-24 17:24 UTC):
- databricks form HTML: 1 grecaptcha hit, no sitekey
- datadog form HTML: 1 grecaptcha hit, no sitekey
- stripe form HTML: 1 grecaptcha hit, no sitekey
- spacex form HTML: 1 grecaptcha hit, no sitekey
- fivetran (works) form HTML: 1 grecaptcha hit, no sitekey
- lyft form HTML: 1 grecaptcha hit, no sitekey

Same signal everywhere. Need DOM-level inspection or a real submit attempt.

## Recommended consumer pattern (for the cron prompt, NOT inline_submit.py)

When the cron iterates over `applications/submitted/<slug>/STATUS.md` markers and finds the first `PREP-READY-IFRAME-RUNNER` (or `PREP-READY` for native greenhouse), run a smoke:

```
.venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug <first-slug> --dry-run > /tmp/smoke.json
python3 -c "import json,sys; r=json.load(open('/tmp/smoke.json')); g=r.get('pre_submit',{}).get('grecapErrText',''); sys.exit(2 if g else 0)"
```

- Exit 0 → form filled cleanly, no captcha error text, proceed with real submit.
- Exit 2 → captcha gate detected pre-submit. ABORT-CAPTCHA-GATE for the entire batch of this tenant; mark every packet's STATUS.md `ABORT-CAPTCHA-SMOKE` so the next batch run picks them up fresh after a wait / workaround.

This adds ~30-60s of headless-Chromium time per batch (one smoke), saves ~20-30 min of cron + LLM-credit waste when the gate is up.

## Why not inside `--batch`

`inline_submit.py --batch` is pure-Python prep — it never launches a browser, never hits any login wall, never sees a captcha. Adding a headless Chromium probe inside `prep_role()` would:
1. Break the clean prep/submit separation (`inline_submit` would become a partial submit driver).
2. Quadruple the wall time of `--batch` runs even on cron runs where every packet succeeds.
3. Require the prep script to know about captcha-state, which it currently doesn't (it just emits a plan).

The right home is the cron's driver loop. Once the cron prompt is updated to dispatch on `PREP-READY-IFRAME-RUNNER`, adding the smoke gate is a 3-line addition to that prompt.

## No code change made

This is a pattern doc only. The candidate dir is unchanged.

## Action for Cyrus / future operator

When updating the daily-autosubmit cron prompt to handle the new `PREP-READY-IFRAME-RUNNER` marker (HANDOFF "Next session priorities #1"), include the smoke-gate snippet above.
