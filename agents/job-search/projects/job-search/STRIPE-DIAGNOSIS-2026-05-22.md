# Stripe / Greenhouse-iframe v2 spike — 2026-05-22

**Verdict: UNBLOCKED for Stripe.** No Formik fiber-walk needed. The 2026-05-19 18:35 "MyGreenhouse v2 wrapper" diagnosis (memory/2026-05-19.md L249-270) was wrong; that subagent's report contradicted the 20:25-20:42 UTC subagent who actually submitted 3 of 5 Stripe roles end-to-end the same evening (878 / 879 / 950 confirmation URLs in STATUS.md files).

## Spike target

- Role 880 / `stripe-7680365` (Technical Program Manager, Internal Systems). PREP-READY, never submitted. Form URL `https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7680365`.

## What was actually tried

1. Loaded form, clicked the "Apply" pill button (label text is "Autofill with MyGreenhouse" but it reveals the same form).
2. Ran a single-shot ~150-line JS recipe (copy of `role-discovery/stripe_filler.js`) that:
   - Sets first/last/email/phone via `setNative` (HTMLInputElement value setter + input + change events).
   - Picks every react-select via `mousedown→mouseup→click` on `.select__control` then click on the matching `[id^=react-select-{id}-option]`.
   - Ticks `question_64112051[]` ("countries you anticipate working in") inside `<fieldset class=checkbox>` by label match.
   - Drives `#candidate-location` typeahead.
   - Declines 4/4 demographics.
3. Uploaded resume via `browser.upload` to `#resume`, then clicked "Attach".

## Result

All 16 fields landed. Resume attached. **Submit button: enabled, label "Submit application", `disabled=false`.** Only residual page error is one empty `<div>` element (no user-visible message). Per task brief this *is* the win — actual click-Submit not performed.

```
country chip:  "+1"             (standard JS_PICK_DROPDOWNS recipe — works)
countryReside: "US"             (2-letter labels, not full names — confirmed)
candidate-location: "Kirkland, Washington, United States"
demographics: all 4 declined
multi_checkbox question_64112051[]: US ticked
resume: attached, filename visible
submit: ENABLED ✅
```

## What the 2026-05-19 18:35 diagnosis got wrong

- Claimed the standard `JS_PICK_DROPDOWNS` recipe leaves `aria-invalid=true` on `#country`. **False.** `aria-invalid=false` after pick, chip text is `+1` which IS the correct rendered state for the new phone-country combobox.
- Claimed `JS_DECLINE_DEMOGRAPHICS` SingleValue doesn't survive re-render. **False on Stripe today** — chips stayed after fill and submit was enabled.
- Theory of a new Formik wrapper shape requiring fiber-walk: never verified — and irrelevant because the existing recipe already works.

The 20:25 UTC sibling subagent already documented the correct flow in stripe-7206336/STATUS.md ("MyGreenhouse v2 wrapper diagnosis was WRONG"). I'm restating + locking it in.

## Code changes (one-line summary)

- `role-discovery/greenhouse_filler.py`: add `multi_value_multi_select` handling — new `JS_TICK_MULTI_CHECKBOXES` recipe + `multi_checkboxes` plan bucket + alias expansion ("United States" → also try "US"/"USA") + emit_steps wiring. Short-token (≤3 chars) substring match disabled to avoid "australia" matching "us".

No changes to `stripe_filler.js`, `tracker.db`, `inline_submit.py`, or dryrun specs.

## Verification

- `greenhouse_filler.build_plan(spec_for_stripe-7680365)` now emits `multi_checkboxes: [{id: 'question_64112051[]', legend_re: 'Please select the country...', values: ['United States','US','USA']}]` and `question_64112051[]` is no longer in `unknown`/`skipped`.
- `emit_steps` adds a `JS_TICK_MULTI_CHECKBOXES` step right after country dropdowns.
- Live-tested the recipe on stripe-7680365 — ticked the "US" checkbox correctly after the alias fallback (full name missing → 2-letter exact match found).

## reCAPTCHA Enterprise

Confirmed loaded on Stripe iframe (`recaptcha/enterprise.js?render=6LfmcbcpAAAAAChNTbhUShzUOAMj_wY9LQIvLFX0`, `window.grecaptcha.enterprise` defined). **But it is NOT the blocker.** It's running in `render=` invisible-score mode, not a visible-challenge mode. The 2026-05-19 20:25/20:35/20:42 UTC sibling submitted 3 Stripe roles end-to-end without any captcha solver — score-based reCAPTCHA Enterprise lets the form through automatically for normal browser fingerprints.

If Stripe ever escalates this sitekey to visible-challenge or score-rejects us in the future, CapSolver SKU = **`ReCaptchaV3EnterpriseTaskProxyless`** at ~$2.99 / 1000 solves. At 50 Stripe submits/month that's ~$0.15/mo — rounding error.

## Next-step recommendation

1. **Don't spend any more time on a "Formik wrapper" theory.** It's a dead end / false trail.
2. The `greenhouse_filler.py` multi_value_multi_select patch makes the generic filler match what `stripe_filler.js` already does manually. Next thing to do is verify the patched generic filler end-to-end on `stripe-7680365` via `inline_submit.py --role-id 880` actually-driven (the spike confirmed the recipe works in isolation, not via the full driver loop).
3. Email verification is still the final ~10-second wait, but `gmail_imap.wait_for_verification_code` already handles that — confirmed working on the 3 May-19 submits.
4. **The actual P0 work now**: turn the daily-autosubmit cron back on (still disabled since 2026-05-19 04:42) and let it drain the 2 remaining Stripe PREP-READY roles (877 and 880). Role 877 must be skipped (NYC-only).

## Time spent

~35 min of 90 budget. Stopped after Submit-enabled + emit_steps patched + verified.
