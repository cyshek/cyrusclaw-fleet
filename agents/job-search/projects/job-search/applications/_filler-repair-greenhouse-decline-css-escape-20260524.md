# Greenhouse-filler react-select CSS selector escape — candidate patch

**Date:** 2026-05-24 17:08 UTC
**Origin:** BACKLOG.md P0 follow-up #5 (Lyft retest exposed `JS_DECLINE_DEMOGRAPHICS` SyntaxError when question id contained `[]`)
**Scope:** purely defensive parsing; no behavior change for ids without special chars

## The bug

Four JS blobs inside `greenhouse_filler.py` (lines 213, 419, 519, 839 on the original) build a CSS attribute selector via template literal:

```js
const opts = [...document.querySelectorAll(`[id^=react-select-${id}-option]`)];
```

When `id` is a react-select v5 input id like `question_36310349002[]` (Lyft), the resulting selector string

```
[id^=react-select-question_36310349002[]-option]
```

is **not** a valid CSS selector — the unescaped `[` `]` mid-token break the attribute lexer. `document.querySelectorAll` throws `SyntaxError: '...' is not a valid selector`, and `JS_DECLINE_DEMOGRAPHICS` silently misses every demographic field on that form. (The iframe runner catches the exception and logs `JS_DECLINE_DEMOGRAPHICS err (continuing): …`, so the failure is non-fatal but every demographic decline is lost.)

Secondary issue: even the non-bracket case relies on an unquoted attribute value selector, which is technically only legal when the value matches the CSS `<ident>` production. Quoting the value is safer and also free.

## The fix

Replace each of the four occurrences with:

```js
const escId = (window.CSS && CSS.escape) ? CSS.escape(id) : id.replace(/([\[\]\.\:\(\)\#])/g, '\\$1');
const opts = [...document.querySelectorAll(`[id^="react-select-${escId}-option"]`)];
```

- `CSS.escape()` is the standard primitive for this (Chromium/Firefox/Safari all support it; Playwright runs Chromium where it's always available).
- The regex fallback handles bracket/dot/colon/paren/hash for the highly unlikely case `CSS.escape` is missing.
- The selector value is now quoted so the escape sequence parses correctly.

The same idiom is already used elsewhere in the file (line 670, `JS_TICK_GDPR_CONSENT`), so this isn't introducing a new dependency.

## Files

- `_repair/greenhouse_filler.py.candidate` — proposed replacement (diff: 4 occurrences patched; no other changes)
- `_repair/_selector_regression.js` — jsdom regression test

## Verification

1. **Python AST parse:** `ast.parse()` passes.
2. **JS template parse:** all 18 `JS_*` blobs in the candidate file pass `node --check` when wrapped as `(blob)`. (Same as the original — confirms the embedded JS didn't get malformed by the Python string-replace.)
3. **DOM regression (jsdom):**
   - Buggy selector with Lyft-style id throws `SyntaxError` ✓
   - Fixed selector with Lyft-style id matches the seeded `<div id="react-select-question_36310349002[]-option-0">` element exactly once ✓
   - Test driver: `_repair/_selector_regression.js` (requires `npm install jsdom` once; reproduce with `cd /tmp && npm i --no-save jsdom && node /path/to/_selector_regression.js`).

Output of the smoke run:
```
{
  "buggyThrew": true,
  "fixedHits": 1,
  "buggySel": "[id^=react-select-question_36310349002[]-option]",
  "fixedSel": "[id^=\"react-select-question_36310349002\\[\\]-option\"]"
}
REGRESSION TEST PASS
```

## Recommend-merge

Yes, low-risk. The change is mechanical (4 spots), backwards-compatible (CSS.escape on a non-special id is a no-op), and unblocks Lyft + any other react-select v5 tenant that gives questions array-suffix ids.

### Promotion command (manual, for the operator)
```
cp projects/job-search/role-discovery/_repair/greenhouse_filler.py.candidate \
   projects/job-search/role-discovery/greenhouse_filler.py
```

Then re-run the iframe runner against a Lyft packet to confirm the demographic-decline pass now finds and decides options instead of erroring out.

## Follow-ups (not blocking)

- Search for other selectors in the file that interpolate `${id}` unquoted (lines 571/628 use quoted `name^="..."` with the `[]` already stripped from the stem — safe).
- Consider exposing a small JS helper `escAttrId(id)` to remove the inline ternary duplication. Not done here to keep the patch surgical.
