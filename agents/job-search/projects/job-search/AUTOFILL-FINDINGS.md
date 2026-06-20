# AUTOFILL-FINDINGS.md — Greenhouse react-select + Filestack autofill

**Date:** 2026-05-08
**Test page:** https://job-boards.greenhouse.io/anthropic/jobs/4985877008
**Outcome:** ALL FIELDS WORK. Recipe below is reproducible. Driver lives at
`projects/job-search/role-discovery/greenhouse_filler.py`.

---

## TL;DR — the recipe

For a modern Greenhouse "job-boards" application form (the React app, not
legacy `/embed/job_app`), every field type can be auto-populated from a
headless Chromium without a real user clicking anything:

| Field type           | What works                                                                                   |
|----------------------|----------------------------------------------------------------------------------------------|
| `<input type=text>`  | Native `value` setter via `Object.getOwnPropertyDescriptor` + `input` event                  |
| `<textarea>`         | Same as above                                                                                |
| react-select dropdown| `mousedown` + `mouseup` + `click` on `.select__control`, then same on `[id$=-option-N]` div  |
| Resume / file upload | Click visible "Attach" button, **then** call browser tool `upload` against `#resume`         |

The bug that ate Wednesday was that *every reasonable-looking shortcut fails
silently*:

- `act:fill` with `fields[]` → no-op on React-controlled inputs
- `el.value = 'Cyrus'` → React overwrites it on next render
- `act:type` into `select__input` → focuses but never commits a selection
- Clicking the `aria-label="Toggle flyout"` chevron button → does NOT open the menu
- Synthetic `keydown('Enter')` on the open menu → React ignores
- `inputRef`-based upload from a snapshot ref → tab crashes mid-call

---

## Workarounds tried (in order)

### (a) Toggle flyout button + click rendered option ⭐ **WINNER (modified)**
Original idea: click the `<button aria-label="Toggle flyout">`. **Did not
work** — the chevron button is visual only; react-select's handlers are on
the parent `.select__control` div, not the button. Modified to dispatch
`mousedown` on the control div itself: **works perfectly.** All 6 required
dropdowns flip to the correct value on first try.

```js
const ctrl = inp.closest('.select__control');
const r = ctrl.getBoundingClientRect();
['mousedown','mouseup','click'].forEach(t =>
  ctrl.dispatchEvent(new MouseEvent(t, {
    bubbles: true, cancelable: true, view: window, button: 0,
    clientX: r.left + 5, clientY: r.top + 5,
  })));
// wait ~300ms, then locate target:
const target = document.getElementById(`react-select-${id}-option-N`);
// dispatch the same three events on the target div
```

Why mousedown matters: react-select v5's onMouseDown is what opens the menu.
A plain `click()` doesn't fire mousedown, so the menu never appears.

### (b) Synthetic keyboard events on `select__input` — failed
Tried `keydown` / `keypress` for "Y" / "Enter" with `bubbles: true`. The
input gets focus and the value briefly appears as a search-highlight, but
react-select never picks it up because the menu was never opened by a
mousedown. Confirmed earlier in `MEMORY.md` "Open blockers".

### (c) Hidden native `<select>` — does not exist
Greenhouse renders react-select with NO underlying `<select>`. The only
DOM input for each combobox is the `<input class="select__input">`, which
is a search field, not a selectable element. Playwright `selectOption`
has nothing to target.

### (d) File upload — needs the visible button click first
The `<input type=file id=resume>` IS in the DOM from page load (it's
`visually-hidden`, not lazy). But calling the browser tool's `upload`
action directly against `#resume` after page load only sometimes worked.
The reliable recipe:

1. JS-click the visible `<button>Attach</button>` next to the input.
   This wakes up Filestack's adapter that listens for the file change.
2. Immediately call `browser action="upload" selector="#resume" paths=[…]`.
3. After upload, the input is removed from the DOM and replaced with a
   filename label. Verify by searching `document.body.textContent` for the
   filename.

Files must live under `/tmp/openclaw/uploads/` (browser tool sandbox).

---

## Browser tool quirks discovered

- **`act:fill` with `fields[]` is a no-op on React-controlled inputs.** Use
  `act` with `kind:"evaluate"` and the native value-setter trick.
- **The `targetId` in `act` responses sometimes lies.** The `targetId` echoed
  in the result can be a *different* tab than the one the action ran on,
  especially when multiple greenhouse.io pages are open and Chrome's
  session restore reopens old tabs. Always pass the raw target id (the
  long hex from `tabs`), and double-check with `location.href` inside JS.
- **Chrome session restore fights you.** Every browser restart re-opens the
  last greenhouse application page even after we close it. Close orphan
  greenhouse tabs at the start of each driver run.
- **`screenshot` requires the `sharp` npm package** which is not installed.
  Use `pdf` for visual capture, or just JS-evaluate `document.body.textContent`
  for verification.
- **Avoid the `iti-0__search-input`** for the country/phone iti widget — let
  the native iti library handle it via the `phone` field; the dropdown is
  not exposed via a stable id.

---

## Generic Greenhouse autofill loop

```python
# Pseudocode — see greenhouse_filler.py for the real implementation
1. open(label, url)
2. evaluate JS_OPEN_APPLY            # click the visible "Apply" button
3. sleep 600ms
4. evaluate JS_FILL_TEXT_FIELDS      # all input/textarea
5. evaluate JS_PICK_DROPDOWNS        # all react-select required questions
6. evaluate JS_CLICK_ATTACH          # wakes Filestack
7. browser.upload selector="#resume" paths=[resume]
8. evaluate JS_VERIFY                # read back state
9. STOP — Cyrus clicks Submit himself
```

The Python driver `greenhouse_filler.py` reads any
`applications/dryrun/{org}-{job_id}.json` and emits this step list.

## Future Greenhouse forms that will probably "just work"

Any company on `job-boards.greenhouse.io` whose form follows the same
React class names (`select__control`, `select__option`, `select__single-value`,
`input.input__single-line`, `#resume`). That covers the vast majority of
greenhouse-hosted boards as of 2026-05-08, including Anthropic, Apollo.io,
and most Series-B-and-up startups.

Forms on `boards.greenhouse.io` (legacy, no React) need a different driver
— they use plain `<select>` and standard `<input type=file>` and don't
need any of these hacks.

## Things still TODO

- The `country` dropdown is also react-select but uses a typeahead with a
  large option list. The current driver doesn't fill it because the dryrun
  spec doesn't ask for it on the Anthropic form. If a future form requires
  it, extend `JS_PICK_DROPDOWNS` to handle option matching by partial-text
  search (it likely won't have a hardcoded option index).
- Demographic dropdowns (`gender`, `race`, `hispanic_ethnicity`,
  `veteran_status`, `disability_status`) — the driver currently leaves
  them at the default. Anthropic happens to default to "Decline To Self
  Identify" for two of them automatically. Other companies may not.
  Add an explicit decline-pass when a form's `declined_demo` list is
  non-empty AND the value isn't already set.
