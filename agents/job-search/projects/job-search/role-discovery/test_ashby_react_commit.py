"""chain_p13 (2026-06-10, Curri 2557 / Knowtex 2593): React-fiber onChange commit.

Some Ashby controlled inputs (Full Name, free-text essay, Share-link, single-
selects) IGNORE the native value-setter + input/change path: React's internal
controlled state stays empty, so the GraphQL submit reads '' and banks "Missing
entry for required field" even though the DOM .value is correct AND _valueTracker
was reset. The fix adds a React-fiber onChange escape hatch inside the
_REASSERT_TEXT_JS forceSet path: locate the field's React props bag
(__reactProps$<hash>) on the element or a wrapping ancestor and invoke its
onChange handler directly with a synthetic event carrying the value, forcing
React to commit it into controlled/form state. Fully guarded so it is a pure
no-op for non-React inputs or inputs whose native path already worked.

This proves:
  1. The JS source still wires reactOnChangeCommit into forceSet (regression guard).
  2. Behaviorally (executed in node): when the native value-setter is ignored by a
     controlled component, the fiber onChange path STILL commits the value into
     React state -- exactly the Curri/Knowtex failure mode.
  3. reactOnChangeCommit is a no-op (returns false) when no React onChange exists,
     so it never corrupts plain/non-React inputs.
"""
import json
import pathlib
import shutil
import subprocess

_PI_REAL = json.loads((pathlib.Path(__file__).resolve().parents[1] / "personal-info.json").read_text())
_FULL_NAME = _PI_REAL["identity"]["first_name"] + " " + _PI_REAL["identity"]["last_name"]

import _ashby_runner

HERE = pathlib.Path(__file__).resolve().parent
NODE = shutil.which("node")


# ----------------------------------------------------------------------------
# 1. Source/regression guard: the fiber-onChange escape hatch is wired in.
# ----------------------------------------------------------------------------
def test_reassert_js_defines_react_onchange_commit():
    js = _ashby_runner._REASSERT_TEXT_JS
    assert "reactOnChangeCommit" in js, "fiber-onChange helper must exist"
    assert "__reactProps$" in js, "must read the React props bag"
    # forceSet must invoke it (so every reassert pass also commits via the fiber)
    assert "reactOnChangeCommit(e, useVal)" in js, "forceSet must call the fiber commit"
    # must be guarded (never-raises) and walk ancestors for the handler
    assert "onChange" in js and "onInput" in js
    assert "parentElement" in js, "must walk up to find a wrapping handler"


def test_forceset_calls_fiber_commit_after_native_setter():
    """The fiber commit must run AFTER the native value-setter (so the native
    path is still tried first) and BEFORE blur."""
    js = _ashby_runner._REASSERT_TEXT_JS
    i_native = js.index("ns.call(e, useVal)")
    i_fiber = js.index("reactOnChangeCommit(e, useVal)")
    i_blur = js.rindex("e.blur()")
    assert i_native < i_fiber < i_blur, "order must be native-setter -> fiber commit -> blur"


# ----------------------------------------------------------------------------
# 2. Behavioral proof (node): fiber onChange commits when native path is ignored.
# ----------------------------------------------------------------------------
def _extract_react_commit_fn(js: str) -> str:
    """Pull the reactOnChangeCommit arrow function body out of _REASSERT_TEXT_JS
    so it can be exercised standalone in node. We re-export it as a top-level
    function for the harness."""
    start = js.index("const reactOnChangeCommit = (el, val) => {")
    # find the matching closing "};" for this arrow function by brace counting
    body_start = js.index("{", start)
    depth = 0
    i = body_start
    while i < len(js):
        c = js[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    # include the trailing semicolon
    fn_src = js[start:i + 1]
    # rename the const to a hoisted function-style export for the harness
    return fn_src.replace("const reactOnChangeCommit = (el, val) =>",
                          "globalThis.reactOnChangeCommit = (el, val) =>")


def _run_node(harness_js: str) -> dict:
    fn_src = _extract_react_commit_fn(_ashby_runner._REASSERT_TEXT_JS)
    script = fn_src + "\n" + harness_js
    p = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, f"node failed: {p.stderr}\n{p.stdout}"
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_fiber_commit_lands_value_when_native_ignored():
    if not NODE:
        return  # node not available in this env; the source guards above still run
    # Simulate a React-controlled input where:
    #   - the native value setter is a no-op for "controlled state" (we keep a
    #     separate reactState that ONLY updates via the onChange handler), exactly
    #     like a controlled component that re-renders from props.
    #   - the props bag (__reactProps$abc) carries onChange that reads
    #     event.target.value and writes it into reactState.
    harness = r"""
    const reactState = { committed: null, calls: 0 };
    const el = {
      nodeType: 1,
      tagName: 'INPUT',
      type: 'text',
      value: '%FULL_NAME%',          // DOM value already correct (native path "worked")
      parentElement: null,
    };
    // attach a React props bag with onChange that drives controlled state
    el['__reactProps$x1y2z3'] = {
      onChange: (e) => { reactState.calls++; reactState.committed = e.target.value; },
    };
    Object.keys(el);  // ensure key enumeration works
    const fired = globalThis.reactOnChangeCommit(el, '%FULL_NAME%');
    console.log(JSON.stringify({ fired, committed: reactState.committed, calls: reactState.calls }));
    """.replace('%FULL_NAME%', _FULL_NAME)
    res = _run_node(harness)
    assert res["fired"] is True, "must fire the fiber onChange"
    assert res["committed"] == _FULL_NAME, "value must land in controlled React state"
    assert res["calls"] == 1


def test_fiber_commit_walks_ancestor_for_handler():
    if not NODE:
        return
    # onChange lives on a WRAPPING ancestor (some component libs bind there).
    harness = r"""
    const reactState = { committed: null };
    const parent = { nodeType: 1, tagName: 'DIV', parentElement: null };
    const el = { nodeType: 1, tagName: 'TEXTAREA', type: 'textarea', value: 'essay text', parentElement: parent };
    parent['__reactProps$wrap'] = { onChange: (e) => { reactState.committed = e.target.value; } };
    const fired = globalThis.reactOnChangeCommit(el, 'essay text');
    console.log(JSON.stringify({ fired, committed: reactState.committed }));
    """
    res = _run_node(harness)
    assert res["fired"] is True
    assert res["committed"] == "essay text"


def test_fiber_commit_noop_without_react_props():
    if not NODE:
        return
    # Plain input with NO React props bag -> reactOnChangeCommit returns false and
    # touches nothing (safe for non-React inputs / inputs whose native path worked).
    harness = r"""
    const el = { nodeType: 1, tagName: 'INPUT', type: 'text', value: 'x', parentElement: null };
    const fired = globalThis.reactOnChangeCommit(el, 'x');
    console.log(JSON.stringify({ fired }));
    """
    res = _run_node(harness)
    assert res["fired"] is False, "must be a no-op when no React onChange is wired"


def test_fiber_commit_never_throws_on_bad_handler():
    if not NODE:
        return
    # onChange that throws must be swallowed (best-effort, never-raises contract).
    harness = r"""
    const el = { nodeType: 1, tagName: 'INPUT', type: 'text', value: 'x', parentElement: null };
    el['__reactProps$boom'] = { onChange: () => { throw new Error('kaboom'); } };
    let threw = false;
    let fired = null;
    try { fired = globalThis.reactOnChangeCommit(el, 'x'); } catch (e) { threw = true; }
    console.log(JSON.stringify({ threw, fired }));
    """
    res = _run_node(harness)
    assert res["threw"] is False, "reactOnChangeCommit must never propagate handler errors"


# ----------------------------------------------------------------------------
# chain_p13: no-bounce final commit JS + verify-nonempty JS source guards.
# ----------------------------------------------------------------------------
def test_no_bounce_commit_js_defined_and_wired():
    js = _ashby_runner._FINAL_TEXT_COMMIT_NO_BOUNCE_JS
    assert "reactOnChangeCommit" in js, "no-bounce commit must also fire the fiber onChange"
    assert "__reactProps$" in js
    # must NOT bounce through '' before setting the real value (the empty-window
    # race the no-bounce commit exists to avoid): there is no `ns.call(e, '')`.
    assert "ns.call(el, '')" not in js and 'ns.call(el, "")' not in js, \
        "no-bounce commit must not clear-then-set (no empty bounce)"
    assert "ns.call(el, useVal)" in js, "must set the real value via native setter"


def test_verify_nonempty_js_defined():
    js = _ashby_runner._VERIFY_TEXT_NONEMPTY_JS
    assert "empty" in js
    # skips non-text controls so it never flags a radio/checkbox as 'empty text'.
    assert "radio" in js and "checkbox" in js


def test_no_bounce_commit_behavior_node():
    """Executed in node: the no-bounce JS sets a controlled input's value via the
    native setter AND fires the fiber onChange so React controlled state commits,
    in a single shot with no transient-empty write."""
    if not NODE:
        return
    js = _ashby_runner._FINAL_TEXT_COMMIT_NO_BOUNCE_JS
    # Build a DOM-ish harness with a controlled input + document.getElementById.
    harness = r"""
    global.window = global;
    function makeProto() {
      let _v = '';
      const proto = {};
      Object.defineProperty(proto, 'value', {
        get() { return this.__v || ''; },
        set(x) { this.__v = x; this.__nativeSets = (this.__nativeSets||0)+1; },
        configurable: true,
      });
      return proto;
    }
    global.HTMLInputElement = function(){}; global.HTMLInputElement.prototype = makeProto();
    global.HTMLTextAreaElement = function(){}; global.HTMLTextAreaElement.prototype = makeProto();
    const react = { committed: null };
    const el = Object.create(global.HTMLInputElement.prototype);
    el.nodeType = 1; el.tagName = 'INPUT'; el.type = 'text'; el.id = 'comp1';
    el.parentElement = null;
    el.dispatchEvent = function(){};
    el['__reactProps$z'] = { onChange: (e)=>{ react.committed = e.target.value; } };
    global.Event = function(t){ this.type = t; };
    global.document = { getElementById: (id)=> id==='comp1' ? el : null,
                        querySelector: ()=> null };
    const FN = REPLACE_FN;
    const out = FN({ fields: [{ fid: 'comp1', val: '$160-180K base' }] });
    console.log(JSON.stringify({ dom: el.value, react: react.committed,
                                 committed: out.committed.length }));
    """
    script = harness.replace("REPLACE_FN", js)
    p = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, f"node failed: {p.stderr}\n{p.stdout}"
    res = json.loads(p.stdout.strip().splitlines()[-1])
    assert res["dom"] == "$160-180K base", "native setter must land the DOM value"
    assert res["react"] == "$160-180K base", "fiber onChange must land controlled state"
    assert res["committed"] == 1


# ----------------------------------------------------------------------------
# chain_p13: generalized trusted-keystroke commit helper.
# ----------------------------------------------------------------------------
def test_trusted_commit_fields_defined_and_length_gated():
    fn = getattr(_ashby_runner, "_trusted_commit_fields", None)
    assert callable(fn), "_trusted_commit_fields must exist"
    # tel wrapper delegates to the general helper.
    assert callable(getattr(_ashby_runner, "_trusted_commit_tel_fields", None))


def test_trusted_commit_fields_skips_long_and_empty():
    """Pure-logic guard: the helper must skip empty values and values longer than
    max_len WITHOUT touching the page (so it never tries to keystroke a 4-para
    essay). We pass a sentinel page whose .locator would raise if called for a
    skipped field -- a skipped field must never reach .locator()."""
    calls = {"locator": 0}

    class _BoomLocator:
        def __getattr__(self, _):
            raise AssertionError("locator should not be used for skipped fields")

    class _Page:
        def locator(self, *_a, **_k):
            calls["locator"] += 1
            return _BoomLocator()

    # all fields are either empty or too long -> zero locator calls, empty result.
    tf = {"a": "", "b": None, "c": "x" * 500}
    done = _ashby_runner._trusted_commit_fields(_Page(), tf, max_len=160)
    assert done == []
    assert calls["locator"] == 0, "skipped fields must not hit the page at all"
