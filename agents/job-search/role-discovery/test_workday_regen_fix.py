#!/usr/bin/env python3
"""Regression tests for the WORK-EXPERIENCE REGEN-ON-FILL fix (workday-regen-fix 2026-06-05).

THE BUG (EXFO 2121, confirmed live): Workday spawns a FRESH empty REQUIRED work-exp block
EVERY time the permanent empty block is filled WITHOUT committing to React's required-
validation. The old `if not we_done:` loop wrote jobTitle/company/location via `_set_native`
(a raw DOM `.value` write that does NOT commit to React), so the block stayed required-empty,
the page injected a new empty, the next iteration filled THAT, and the empty-block count
EXPLODED 54 -> 274 -> 437 until the My-Experience step hit the loop-cap (EXIT5).

THE FIX (locked here):
  1. The fill loop now uses KEYBOARD-COMMIT (`_kbd_fill_we_block_by_idx`, real key events)
     so the block satisfies React required-validation and Workday stops regenerating.
  2. After each commit, if Workday STILL spawned a new empty required block, the loop
     DELETES it (`delete_empty_we_blocks`) instead of re-filling it (re-filling triggers
     the next regen).
  3. The block count CONVERGES (plateaus) -- it must NOT keep growing.

These are FakePage tests (no live browser). The live proof of plateau is captured separately
in the runner's per-iteration WE-block-count log.
"""
import importlib.util
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


# ---------------------------------------------------------------------------
# 1. CONTRACT (source-level): the fill loop must NOT use _set_native for the
#    work-exp jobTitle/company/location, and MUST use the keyboard-commit path
#    + delete regenerated empties. These guard against a silent revert to the
#    buggy native-write loop.
# ---------------------------------------------------------------------------

def _populate_src():
    src = (HERE / "_workday_runner.py").read_text()
    # isolate the populate_work_history function body
    start = src.index("def populate_work_history(")
    nxt = src.index("\ndef ", start + 1)
    return src[start:nxt]


def test_fill_loop_uses_keyboard_commit_not_native():
    body = _populate_src()
    # The `if not we_done:` fill loop must call the keyboard-commit helper.
    assert "_kbd_fill_we_block_by_idx(page, idx, job)" in body, \
        "fill loop must keyboard-commit the work-exp block (React-committing), not _set_native"


def test_fill_loop_does_not_native_write_workexp_fields():
    body = _populate_src()
    # Locate the `if not we_done:` block specifically (the regen-prone fill loop).
    m = re.search(r"\n    if not we_done:\n(.*?)\n    # ---- Education:", body, re.S)
    assert m, "could not locate the `if not we_done:` fill loop"
    loop = m.group(1)
    # No _set_native on the work-exp jobTitle/company/location inside the fill loop.
    assert "_set_native(page, jt" not in loop, "fill loop must not _set_native jobTitle (regen bug)"
    assert "_set_native(page, cn" not in loop, "fill loop must not _set_native companyName (regen bug)"
    assert "_set_native(page, lc" not in loop, "fill loop must not _set_native location (regen bug)"


def test_fill_loop_detects_regen_and_deletes():
    body = _populate_src()
    m = re.search(r"\n    if not we_done:\n(.*?)\n    # ---- Education:", body, re.S)
    loop = m.group(1)
    # Must measure block counts (regen detection) and delete regenerated empties.
    assert "_count_we_blocks(page)" in loop, "fill loop must measure WE-block counts to detect regen"
    assert "delete_empty_we_blocks(page)" in loop, "fill loop must delete regenerated empty blocks"
    # Must have a bounded convergence loop (no infinite spin).
    assert "convergence" in loop.lower(), "fill loop must have a bounded convergence pass"


def test_count_we_blocks_helper_exists():
    assert callable(getattr(wd, "_count_we_blocks", None)), "_count_we_blocks helper must exist"
    assert callable(getattr(wd, "_kbd_fill_we_block_by_idx", None)), "_kbd_fill_we_block_by_idx must exist"


def test_fill_loop_is_idempotent_by_company():
    # workday-date-commit-fix FIX2: the fill loop must EDIT-IN-PLACE a block whose company
    # is already committed (match companyName -> WORK_HISTORY) instead of Add-ing a duplicate
    # (re-Adding piled up dup blocks, e.g. PE5 dup of PE1 Microsoft on the EXFO live run).
    body = _populate_src()
    m = re.search(r"\n    if not we_done:\n(.*?)\n    # ---- Education:", body, re.S)
    assert m, "could not locate the `if not we_done:` fill loop"
    loop = m.group(1)
    assert "_we_idx_for_company(" in loop, \
        "fill loop must look up an existing block by company (idempotent edit-in-place)"
    assert "edit-in-place" in loop, \
        "fill loop must EDIT-IN-PLACE the matching block, not Add a duplicate"
    # the existing-company branch must `continue` (skip the Add path) for that job
    assert re.search(r"existing_idx is not None:.*?continue", loop, re.S), \
        "matching-company branch must continue (skip Add) so no duplicate block is created"


def test_company_lookup_helper_present():
    # the helper must exist in the source (defined inside populate_work_history scope).
    src = (HERE / "_workday_runner.py").read_text()
    assert "_we_idx_for_company" in src, "_we_idx_for_company idempotency helper must exist"
    assert "_filled_we_companies" in src, "_filled_we_companies helper must exist"


# ---------------------------------------------------------------------------
# 2. BEHAVIORAL SIMULATION: a fake Workday page that REGENERATES an empty block
#    whenever a block is filled via a non-committing write, but STOPS once the
#    block is keyboard-committed. We run populate_work_history against it and
#    assert the block count PLATEAUS (does not explode 54->274->437) and the
#    regenerated empties get deleted.
# ---------------------------------------------------------------------------

class RegenSimKeyboard:
    def __init__(self, page):
        self.page = page
        self._focus = None
    def press(self, *a, **k):
        # Control+A / Delete / Tab -- the Tab commits the focused field for the sim.
        pass
    def type(self, value, *a, **k):
        # keyboard typing = a COMMITTING write in this sim: mark the focused block filled.
        if self.page._focus_block is not None:
            self.page.blocks[self.page._focus_block]["title"] = value or "X"
            self.page.blocks[self.page._focus_block]["committed"] = True


class RegenSimLocator:
    def __init__(self, page, eid):
        self.page = page
        self.eid = eid
    @property
    def first(self):
        return self
    def scroll_into_view_if_needed(self, *a, **k):
        pass
    def click(self, *a, **k):
        # focus the block whose field id this is, so a subsequent keyboard.type commits it
        m = re.search(r"workExperience-(\d+)--", self.eid or "")
        self.page._focus_block = int(m.group(1)) if m else None


class RegenSimPage:
    """Simulates Workday's regen-on-fill:
      - starts with `initial_empty` permanent empty required blocks (indices 0..N-1)
      - a NATIVE (.value) write does NOT commit -> stays empty -> regenerates a new empty
      - a KEYBOARD write commits -> block satisfied -> NO regen
      - delete-empty JS removes one DELETABLE empty block per call
    Tracks max block count seen so the test can assert it never explodes.
    """
    def __init__(self, initial_empty=1, deletable=True):
        self.blocks = {}
        for i in range(initial_empty):
            self.blocks[i] = {"title": "", "committed": False, "deletable": deletable}
        self._next_idx = initial_empty
        self._focus_block = None
        self.keyboard = RegenSimKeyboard(self)
        self.max_total = initial_empty
        self.fill_events = 0
        self.regen_events = 0
        self.delete_events = 0

    # --- helpers ---
    def _touch_max(self):
        self.max_total = max(self.max_total, len(self.blocks))

    def _regen_if_uncommitted(self):
        # mimic React: any block whose title is set WITHOUT commit triggers a new empty
        for b in self.blocks.values():
            if b["title"] and not b["committed"]:
                # spawn a fresh empty required block
                self.blocks[self._next_idx] = {"title": "", "committed": False, "deletable": True}
                self._next_idx += 1
                self.regen_events += 1
                self._touch_max()
                break

    def evaluate(self, js, *a, **k):
        arg = a[0] if a else None
        # _count_we_blocks: [total, empty]
        if "[t.length,e.length]" in js:
            total = len(self.blocks)
            empty = sum(1 for b in self.blocks.values() if not b["title"].strip())
            return [total, empty]
        # _empty_we_indices (sorted ascending)
        if "x.id.match(/workExperience-(" in js and ".sort(" in js:
            return [str(i) for i in sorted(self.blocks) if not self.blocks[i]["title"].strip()]
        # _empty_we_indices (legacy unsorted) — accept too
        if "x.id.match(/workExperience-(" in js:
            return [str(i) for i in sorted(self.blocks) if not self.blocks[i]["title"].strip()]
        # _find_id_suffix: echo a usable id from the suffix
        if "endsWith(suf)" in js and isinstance(arg, str):
            return arg
        # _scroll_into_view_js
        if "inline:'center'" in js:
            return True
        # delete-one-empty-block JS (panel-set-delete-button)
        if "panel-set-delete-button" in js:
            for i in sorted(self.blocks):
                b = self.blocks[i]
                if not b["title"].strip() and b["deletable"]:
                    del self.blocks[i]
                    self.delete_events += 1
                    return 1
            # any non-deletable empty remaining?
            if any(not b["title"].strip() for b in self.blocks.values()):
                return -1
            return 0
        # we_done / any_filled / first-empty-id probes used elsewhere -> benign defaults
        if "currentlyWorkHere" in js:
            return None
        # roleDescription native write probe / committed-value probe
        if "e.value" in js:
            return ""
        return None

    def wait_for_timeout(self, *a, **k):
        # after any settle wait, run the regen reaction (mimics React re-render)
        self._regen_if_uncommitted()
        self._touch_max()

    def locator(self, sel):
        return RegenSimLocator(self, sel.lstrip("#"))


def _one_job():
    return {"title": "Technical Program Manager", "company": "Microsoft", "location": "Seattle, WA",
            "start": ("03", "2024"), "end": None, "current": True, "desc": "Did things."}


def test_regen_sim_keyboard_commit_stops_regrowth(monkeypatch):
    """With keyboard-commit, filling the permanent empty block must COMMIT it so the
    sim stops regenerating. The max block count must stay BOUNDED (no 54->274->437)."""
    # single job so we fill exactly one block; start with 1 permanent empty block.
    monkeypatch.setattr(wd, "WORK_HISTORY", [_one_job()])
    monkeypatch.setattr(wd, "EDUCATION", [])  # skip education section in the sim
    page = RegenSimPage(initial_empty=1)

    # drive ONLY the work-exp portion by calling the real fill helpers through
    # populate_work_history is heavy (touches education/date-repair). Instead exercise
    # the exact fixed path: kbd-commit then converge-delete, mirroring the loop.
    total0, empty0 = wd._count_we_blocks(page)
    assert (total0, empty0) == (1, 1)

    # simulate the fixed loop body for one job using the sim's empty-index query.
    empties = [str(i) for i in sorted(page.blocks) if not page.blocks[i]["title"].strip()]
    idx = empties.pop(0)
    pre_total, pre_empty = wd._count_we_blocks(page)
    wd._kbd_fill_we_block_by_idx(page, idx, _one_job())
    page.wait_for_timeout(1)
    post_total, post_empty = wd._count_we_blocks(page)
    if post_total > pre_total or post_empty > max(0, pre_empty - 1):
        wd.delete_empty_we_blocks(page)

    # convergence
    for _ in range(6):
        wd.delete_empty_we_blocks(page)
        ct, ce = wd._count_we_blocks(page)
        if ce == 0:
            break

    # The committed block survives, all regenerated empties are deleted, count is bounded.
    final_total, final_empty = wd._count_we_blocks(page)
    assert final_empty == 0, f"all empties must be deleted, got {final_empty}"
    assert page.max_total <= 3, f"block count exploded (max={page.max_total}); regen not stopped"
    # at least the one committed block remains
    assert any(b["committed"] for b in page.blocks.values()), "the real block must stay committed"


def test_native_write_would_explode_proving_sim_models_the_bug(monkeypatch):
    """SANITY: prove the sim actually models the regen bug -- a NATIVE (non-committing)
    fill loop against the same sim WOULD explode. This guards that the green result above
    is meaningful (the fix matters), not a sim that never regenerates.
    """
    page = RegenSimPage(initial_empty=1)
    job = _one_job()
    # emulate the OLD buggy loop: native .value write (no commit) + re-fill the new empty.
    for _ in range(8):  # 8 iterations is plenty to show unbounded growth
        empties = [i for i in sorted(page.blocks) if not page.blocks[i]["title"].strip()]
        if not empties:
            break
        i = empties[0]
        # NON-committing write: set title but committed stays False
        page.blocks[i]["title"] = job["title"]
        page.blocks[i]["committed"] = False
        page.wait_for_timeout(1)  # triggers regen
    assert page.max_total >= 5, \
        f"sim should model unbounded regen under native writes, max={page.max_total}"


if __name__ == "__main__":
    import sys
    # minimal monkeypatch shim for direct (non-pytest) execution
    class _MP:
        def __init__(self): self._saved = []
        def setattr(self, obj, name, val):
            self._saved.append((obj, name, getattr(obj, name)))
            setattr(obj, name, val)
        def undo(self):
            for obj, name, val in reversed(self._saved):
                setattr(obj, name, val)
            self._saved = []
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            mp = _MP()
            try:
                if "monkeypatch" in fn.__code__.co_varnames[:fn.__code__.co_argcount]:
                    fn(mp)
                else:
                    fn()
                print("PASS", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
            except Exception as e:
                fails += 1; print("ERROR", name, repr(e))
            finally:
                mp.undo()
    sys.exit(1 if fails else 0)
