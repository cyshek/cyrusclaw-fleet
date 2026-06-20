# OPTION-A-DESIGN.md — React-onChange poke for GH iframe resume

**Date:** 2026-05-26 PDT (chain_010 sidecar)
**Author:** chain_010
**Builds on:** chain_009 ESCALATE.md Option A

## Goal
Populate React's internal `application.resume` state so the client-side validator
stops short-circuiting submit on Lyft 1343 / 716 / Hume 1379.

## Design

After our S3 upload + `JS_INSTALL_RESUME_INJECT` (chain_009 path) succeeds,
inject + run a NEW JS payload `JS_REACT_RESUME_TRIGGER` that:

1. Queries `document.querySelector('#resume')` (file input).
   - Fallback selector: `input[type=file][name*=resume i], input[type=file]`.
2. Constructs a **page-realm** `File` from the same base64 the runner already
   passed in (avoids cross-realm `instanceof File` mismatch).
3. Wraps it in `DataTransfer`.
4. Uses the React-native value setter:
   ```js
   const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'files');
   desc.set.call(input, dt.files);
   ```
5. Dispatches a real bubbling `change` event:
   ```js
   input.dispatchEvent(new Event('change', { bubbles: true }));
   ```
6. Returns observability fields:
   - `triggered: true` if all steps ran
   - `input_selector` used
   - `files_after`: input.files.length
   - `change_dispatched: true`

After dispatch, the runner waits up to ~6s polling for evidence that React's
own upload ran:
- Look for a filename chip in the DOM, OR
- Look for `input[type=file]#resume` being detached and replaced by a
  "filename + Remove" widget (React's progress chip pattern).

We do NOT inspect React fiber directly — too fragile across bundle revs.

## Integration point

`greenhouse_iframe_runner.py` after the existing `gh_s3_upload` block (which
plants the inject payload). Only runs when all are true:
- `USE_REACT_RESUME_TRIGGER` (new flag, default True)
- `USE_GH_S3_UPLOADER` was True and `inject` succeeded
- `resume_path` exists

## Why this is safe

- Acceptance of double upload per ESCALATE.md (React may re-upload via its own
  uploader after onChange → +2s acceptable).
- If `change` event blows away our DataTransfer-bound file (replaced by React's
  own upload), submit STILL succeeds: React state is populated with its own
  uploader's URL.
- If React's uploader fails (e.g. CORS difference), our fetch+XHR patch from
  chain_009 STILL mutates the JSON body with our presigned URL on submit. So
  we have two independent paths to a valid submit body.
- Kill-switch flag → easy rollback if regression observed elsewhere.

## Fallback strategy

If Option A fails after 2 live runs on Lyft 1343, write `ESCALATE-optB.md`
covering Option B (fiber walk) + Option C (direct submitPath POST).

## Tests

`test_react_resume_trigger.py` (NEW):
- Assert `JS_REACT_RESUME_TRIGGER` is well-formed JS.
- Assert it references `Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'files').set`.
- Assert it dispatches `new Event('change', { bubbles: true })`.
- Assert it accepts a `b64` arg (page-realm File construction).
- Assert `USE_REACT_RESUME_TRIGGER` controls whether the runner emits the call
  (regex check on runner source).
