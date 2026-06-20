# Upload Regression Diagnostic — 2026-05-25

**Status:** Root cause identified. NOT a Chrome/binary regression. It is a
**caller-side arg-shape bug**: passing `selector=` to `browser.upload` falls into
the arm-only filechooser branch, which silently returns `ok:true` without actually
setting any files.

## TL;DR — One-line fix

Replace every `browser.upload selector="..."` call with `browser.upload element="..."`.

That's it. The string can be byte-identical (`#_systemfield_resume`, `#resume`,
`input#resume`, etc.) — only the **argument key** is wrong.

## Browser/binary state

| Item | Version | Last modified |
|---|---|---|
| `/usr/bin/google-chrome` (symlink) | 148.0.7778.178-1 | 2026-05-03 (symlink mtime) |
| `/opt/google/chrome/chrome` (real binary) | 148.0.7778.178 | 2026-05-18 23:12 UTC |
| Snapd chromium (unused) | 1:85.0.4183.83 | n/a |
| `apt history.log` chrome upgrade | 147 → 148.0.7778.167 | 2026-05-19 06:03 UTC |
| `apt history.log` chrome point upgrade | 148.0.7778.167 → 148.0.7778.178 | 2026-05-24 04:03 UTC |

Chrome did upgrade on **2026-05-24 04:03 UTC** — but yesterday's successful
submits (Harvey 03:53 UTC on 05-25, Snowflake 18:09 UTC on 05-25, Asana 17:14 UTC
on 05-25) were ALL on the same Chrome 148.0.7778.178. So the binary is innocent.
The Harvey STATUS.md from 2026-05-25 03:56 UTC explicitly documents the same
upload failure mode and the same workaround we re-confirmed today.

`browser action=doctor` returns all green (`enabled, profile, executable, CDP
HTTP, CDP websocket all pass`).

## Live re-pro on Bland AI 589 (Ashby) — same tenant family as OpenAI 801

Two file inputs on the form (one for resume, one anonymous). `browser.upload`
routing tested against the hidden `#_systemfield_resume` input:

| Incantation | Result | `_systemfield_resume.files.length` |
|---|---|---|
| `browser.upload selector="#_systemfield_resume" paths=[…]` | `ok:true` | **0** ← regression symptom |
| `browser.upload ref="e2" paths=[…]` (e2 = "Upload File" button from aria snapshot) | `ok:true` | **1** ✅ |
| `browser.upload element="#_systemfield_resume" paths=[…]` | `ok:true` | **1** ✅ |

## Live re-pro on Lyft 716 (Greenhouse embed)

Embed URL `https://job-boards.greenhouse.io/embed/job_app?for=lyft&token=8525086002`.
One `#resume` input (`visually-hidden`, type=file, display:block, 1×1 px).

| Incantation | Result | `#resume.files.length` |
|---|---|---|
| `browser.upload selector="#resume" paths=[…]` | `ok:true` | **0** ← regression symptom |
| `browser.upload selector="button.btn--pill:has-text('Attach')" paths=[…]` | `ok:true` | **0** (opens Filestack modal but no bytes) |
| `browser.upload element="input#resume" paths=[…]` | n/a — page reloaded between tests; was timing out on a stale tab | (would pass per Ashby parity; needs re-test in a clean run) |

The Greenhouse `#resume` only appears after some prior interaction (clicking
Apply on the wrapper site, or some lazy mount); a couple of test runs hit a
moment where it had been removed from the DOM. The arg-shape diagnosis still
holds — it is symmetric with the Ashby case.

## Root cause — OpenClaw routes-Cxt2X5Du.js upload handler

`/usr/lib/node_modules/openclaw/dist/routes-Cxt2X5Du.js` around line 405:

```js
if (inputRef || element) {
    if (ref) return jsonError(res, 400, "ref cannot be combined with inputRef/element");
    await pw.setInputFilesViaPlaywright({ cdpUrl, targetId, inputRef, element, paths });
} else {
    await pw.armFileUploadViaPlaywright({ cdpUrl, targetId, paths, timeoutMs });
    if (ref) await pw.clickViaPlaywright({ cdpUrl, targetId, ref });
}
res.json({ ok: true });
```

Branches:

1. `inputRef` OR `element` present → **direct `locator.setInputFiles(paths)`**.
   Bytes land on the input. Correct path for hidden file inputs.
2. `ref` only → arm a `waitForEvent("filechooser")` listener, then click the ref.
   Correct path for buttons that open a native file chooser (Ashby "Upload File").
3. `selector` only (no `inputRef`, no `element`, no `ref`) → **falls into the
   else branch**, arms the filechooser listener, and since there is no `ref` to
   click, nothing ever fires the chooser. The listener times out silently.
   Handler still `res.json({ ok: true })`. **Files never set. No error surfaced.**

`selector` IS NOT a recognized parameter for the upload action in any branch —
it just gets ignored. The arm-only `armFileUploadViaPlaywright` returns
immediately because it just registers the listener; it doesn't await the chooser
event before responding.

This is also why yesterday's working Harvey submit used `ref=e2` (button, branch
2) and yesterday's working Asana/Snowflake submits used Python
`frame.set_input_files()` directly in `greenhouse_iframe_runner.py` — they
bypassed the OpenClaw `browser.upload` route entirely.

## Recommended fixes

### 1. `ashby_filler.js` / Ashby submit plan emitter

Anywhere the plan currently emits:

```jsonc
{ "tool": "browser.upload", "args": { "selector": "#_systemfield_resume", "paths": [...] } }
```

change to one of (in priority order):

```jsonc
// Preferred: aria-snapshot the "Upload File" button container and use ref.
// Matches what Harvey 671 used; works on every Ashby tenant.
{ "tool": "browser.upload", "args": { "ref": "<e# of Upload File button>", "paths": [...] } }
```

or, simpler and equivalent for the actual byte transfer:

```jsonc
// Alternative: use `element` (CSS selector via Playwright .locator()).
// Same end result on the hidden input. No snapshot step required.
{ "tool": "browser.upload", "args": { "element": "#_systemfield_resume", "paths": [...] } }
```

Both verified live on Bland AI today.

### 2. Greenhouse iframe runner / Greenhouse filler

`greenhouse_iframe_runner.py` already uses Playwright's
`frame.query_selector_all('input#resume')[0].set_input_files(resume_path)` —
that path is fine and was not the regression. If anything reverted to using
`browser.upload selector="#resume"` from the dryrun-generated plan, swap to
`element="input#resume"` (or, ideally, keep the Playwright direct path which
runs inside the iframe context without needing a `targetId` round-trip).

### 3. Defensive harness — verify after upload, retry once

Both Ashby and Greenhouse should always evaluate
`document.querySelector(<input>).files.length` after the upload step and treat
`length === 0` as a hard failure, not trust `ok:true`. The pipeline already does
this for Greenhouse (`JS_VERIFY_RESUME_ATTACHED`) — extend the same gate to
Ashby and have it auto-retry once with the `element=` form.

### 4. Optional upstream patch to OpenClaw

The cleanest fix would be for OpenClaw's upload handler to either:

- treat `body.selector` as an alias of `body.element`, OR
- return `501` / `400` when `selector` is the only arg (instead of silently
  arming a chooser that will never fire).

Worth surfacing to `main` / OpenClaw repo maintainers, but the workspace-side
fix (use `element=`) is sufficient to unblock submits today.

## Files to touch

- `projects/job-search/role-discovery/ashby_filler.js` (and any caller emitting
  `selector=` in a `browser.upload` step).
- Inspect `role-discovery/greenhouse_filler.py` lines 1191–1212 — the
  `JS_VERIFY_RESUME_ATTACHED` retry block currently re-emits
  `browser.upload selector="#resume"`. That retry would have silently failed too.
  Swap the retry to `element="input#resume"`.
- `role-discovery/inline_submit.py` if it constructs plans inline anywhere.

## What was NOT broken

- Chrome 148 itself. Harvey/Snowflake/Asana all submitted clean on the same
  binary 14+ hours after the chrome upgrade.
- OpenClaw browser tool's `setInputFiles` Playwright path. It works fine when
  invoked via `element=` or `inputRef=`.
- `greenhouse_iframe_runner.py`'s direct Playwright `set_input_files()` path.
- Tracker / dryrun / classifier pipelines.

## Repro one-liner for future verification

```bash
# From the workspace, in an isolated session:
# 1. browser navigate to https://jobs.ashbyhq.com/bland/804fbd27-027e-4de5-8a6f-77241a65e599/application
# 2. browser upload selector="#_systemfield_resume" paths=["/tmp/openclaw/uploads/Cyrus_Shekari_Resume.pdf"]
# 3. browser evaluate () => document.querySelector('#_systemfield_resume').files.length
#    → 0 (REGRESSION SYMPTOM)
# 4. browser upload element="#_systemfield_resume" paths=["/tmp/openclaw/uploads/Cyrus_Shekari_Resume.pdf"]
# 5. re-evaluate
#    → 1 (FIXED)
```
