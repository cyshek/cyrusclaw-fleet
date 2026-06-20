# STATUS — chain_028: Speak 1015 Ashby Location-typeahead defensive guard

**Date:** 2026-05-29
**Subagent:** speak-1015-typeahead-guard
**Outcome:** Code: SHIPPED. Live: BLOCKED-SPAM-GATE (CapSolver-gated, not chain_028's fault)

---

## Diagnosis (actual chain_013 root cause)

The "Speak 1015 typeahead crash" was two collapsed problems:

1. **Fid mismatch (real bug, fixed):** Speak's spec field
   `fb17ef15-d0cf-4297-8cc8-9f9af8f3ef53__systemfield_location` doesn't
   match any DOM element. Ashby's Location combobox renders as
   `<input role="combobox" placeholder="Start typing...">` — NO `id`, NO
   `name`. The existing `JS_RESOLVE_LOCATION_INPUTS` resolver fell through
   all branches and returned `{missing: [fid]}`. The chain_013 LLM agent
   was executing the multi-step manual recipe ("clickCoords → CDP keystrokes
   → wait listbox → click option"), got `cx,cy = undefined` from the empty
   resolver, and crashed trying to clickCoords nothing.

2. **reCAPTCHA v3 spam gate (pre-existing, NOT in scope):** Speak is in the
   strict-Ashby cluster (sitekey `6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y`).
   Without CapSolver, submit gets flagged regardless of form correctness.

## Code changes

### `projects/job-search/role-discovery/ashby_filler.py`
- **New:** `USE_LOCATION_TYPEAHEAD_SELF_CONTAINED = True` kill switch.
- **New:** `JS_FILL_ASHBY_LOCATION_TYPEAHEAD` — self-contained async JS that
  handles the whole typeahead in one `browser.act.evaluate` step:
  1. Fast path: setNative + look for `[role=option]` → pick best match.
  2. Per-char KeyboardEvent fallback (chain_026 async-typeahead recipe),
     polls up to 2500ms for options.
  3. Free-text + Tab/blur commit as last resort.
  - **ALWAYS** returns structured `{resolved: [...], unresolved: [...]}`.
  - **NEVER** throws (every step is try/catch wrapped → unresolved.push).
  - Hard bounded: ≤5s per field. No infinite waits.
- **New (live-fix):** Inline `resolve()` fallback — when fid contains "location"
  and standard id/name lookup fails, find `input[role="combobox"]` by
  placeholder/aria-label keyword match. **This was the actual crash fix** for
  Speak 1015.
- **Changed:** `emit_steps()` location-fields branch now emits ONE
  `browser.act.evaluate` step (with the self-contained helper) by default
  instead of the legacy two-step (`evaluate resolver` + virtual-tool
  `ashby.location_typeahead_fill`). Legacy path preserved behind the kill
  switch.

### `projects/job-search/role-discovery/test_ashby_filler_chain005.py`
- **Updated:** `test_location_emits_self_contained_typeahead_step` (was
  `test_location_emits_typeahead_fill_step`) — now asserts the self-contained
  evaluate step with `meta.self_contained_typeahead = True`.
- **Updated:** `test_location_typeahead_skipped_when_no_location_fields` —
  also asserts no self-contained step when no Location fields.
- **New class:** `TestChain028LocationGuard` with 7 cases:
  - `test_kill_switch_flag_exists_and_defaults_true`
  - `test_helper_js_has_setNative_and_keyboard_fallback`
  - `test_helper_js_handles_missing_input_gracefully`
  - `test_default_emit_uses_self_contained_evaluate`
  - `test_kill_switch_off_falls_back_to_legacy_two_step`
  - `test_required_flag_is_passed_into_helper_payload`
  - `test_speak_1015_real_spec_emits_self_contained_step` (regression)

## Test counts
- Before: 10/10 in `test_ashby_filler_chain005`
- After: **17/17** in `test_ashby_filler_chain005` (+7 new chain_028 cases)
- JS syntax validated via node: `JSON({resolved:[], unresolved:[]})` returned on empty input

## Live verification (Speak 1015)

| Step | Result |
|---|---|
| Navigate to /application | OK, form loaded |
| Fast-path text fields (name, email, phone, linkedin) | 4/4 filled, post_value matches |
| **chain_028 Location typeahead** | **resolved 1/1 via `per-char+pick` → "Kirkland, Washington, United States"** ✅ |
| Yes/No (button-style "Are you able to work from SF HQ 3 days/week") | Yes button shows `_active_` class ✅ |
| Resume upload (snapshot inputRef + browser.upload) | files.length=1 ✅ |
| Submit button | enabled, no validation errors |
| **Submit click** | **`[role=alert]`: "Your application submission was flagged as possible spam"** ❌ |

reCAPTCHA v3 spam-flag, as predicted for CapSolver-gated cluster.

## Speak 1015 outcome
**BLOCKED-SPAM-GATE** (joins ~85 CapSolver-gated cohort). No burn (strict
Ashby spam-gate kills cleanly per chain_013 lesson). Stamped tracker:
`status='blocked'`, `response_status='spam-gate'`, agent_notes appended.

## Files touched
- `projects/job-search/role-discovery/ashby_filler.py` (+chain_028 helper +
  emit_steps branch + resolver live-fix)
- `projects/job-search/role-discovery/test_ashby_filler_chain005.py` (+7 tests, 2 updated)
- `projects/job-search/applications/submitted/speak-59865014-2fe7-434e-b30f-72925f052991/STATUS.md` (BLOCKED-SPAM-GATE block)
- `projects/job-search/tracker.db` (status, response_status, agent_notes for role 1015)
- `projects/job-search/tracker.db.bak.20260528-speak1015-guard` (backup taken)
- `projects/job-search/role-discovery/output/inline-plan-speak-59865014-2fe7-434e-b30f-72925f052991.json` (regenerated by --dry-run with new step)
- `STATUS-speak1015.md` (this file)

## Blockers / honest follow-ups

1. **Speak 1015 needs CapSolver to actually submit.** Set
   `ENABLE_CAPSOLVER=1` + `CAPSOLVER_API_KEY=...` in `/home/azureuser/.openclaw/.env`
   and re-run; the plan already emits the `ashby.maybe_solve_recaptcha_v3`
   step with `driver_exec` wiring.
2. **Propagation win for cohort:** the chain_028 guard should auto-unblock
   any future Ashby tenant whose Location combobox has the same id-less DOM
   shape (likely most modern Ashby tenants). The 4 strict-cluster tenants
   from chain_013 (Bland/Exa/LlamaIndex/Tavily) were BLOCKED-SPAM-GATE not
   typeahead-crash, so this fix doesn't recover them — but it does future-
   proof any Ashby Location field across the next weekly crawl.
3. **The legacy `JS_RESOLVE_LOCATION_INPUTS` still exists** behind the
   kill switch. It is now dead code on the happy path but kept for
   rollback. Consider deletion in a future cleanup.
4. **`HANDOFF.md`'s "single Speak 1015 typeahead-crash" P0 line** can be
   removed — chain_028 resolved the typeahead crash class. Speak 1015 now
   correctly classifies as part of the 85-role CapSolver-gated bucket.
