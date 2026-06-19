#!/usr/bin/env python3
"""FIX 2 regression: _fill_wd_date is READBACK-GATED -- it returns True ONLY when the
month (and year, and day if present) actually COMMIT (read back correct) AND no
required/invalid error remains; it returns False on an empty/red field.

WHY THIS EXISTS (workday-date-commit-fix 2026-06-09, EXFO 2121)
--------------------------------------------------------------
The old _fill_wd_date typed digits via synthetic KeyboardEvent dispatch which committed
the MONTH but SILENTLY FAILED to commit the YEAR, AND returned True WITHOUT reading the
value back -> false-positive start_filled=True on an EMPTY/red date field. Because the
date never validated, Workday regenerated a fresh empty required work-experience block on
every My-Experience revisit -> blocks accumulated -> loop-cap EXIT 5. This locks the
read-back gate: a date that does NOT commit must return False so the caller never logs a
false start_filled=True.

These are LOGIC-LEVEL tests: a tiny in-memory FakePage models the Workday date-section
DOM (separate Month/Year spinbutton sub-inputs) and routes the helper JS by stable source
markers. No live browser is used. Two scenarios are exercised end-to-end through the real
_fill_wd_date control flow:
  * COMMIT-OK  : keyboard.type lands in the focused section -> readback matches -> True
  * COMMIT-FAIL: keyboard.type is dropped (section stays empty) + a required error is
                 present -> readback empty -> False (the exact false-positive we killed)
"""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

SRC = (HERE / "_workday_runner.py").read_text()


# ---------------------------------------------------------------------------
# In-memory DOM model of a Workday Month/Year date widget + a FakePage that
# routes the helper JS by stable source markers (no real browser).
# ---------------------------------------------------------------------------
class _Section:
    def __init__(self, sec_id):
        self.id = sec_id
        self.value = ""          # committed digits (what readback returns)
        self.error = False       # required/invalid error showing on this section


class _FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def type(self, digits, delay=0):
        """Type into whichever section is currently focused -- but ONLY if that section is
        in the 'commits' set (commit-ok scenario). In the commit-fail scenario the section
        is NOT in `commits`, so the typed digits are dropped (value stays empty), mirroring
        Workday's spinbutton silently rejecting the synthetic input."""
        sec = self.page._focused
        if sec is None:
            return
        if sec.id in self.page._commits:
            sec.value = str(digits)
            sec.error = False  # a real commit clears the required error
        # else: dropped -> value stays "" -> stays errored (commit-fail)

    def press(self, _key):
        return None


class _FakePage:
    def __init__(self, sections, commits, suffix_present):
        # sections: dict[id -> _Section]; commits: set of ids that accept keyboard input;
        # suffix_present: set of base-suffixes that _find_id_suffix should resolve.
        self._sections = sections
        self._commits = set(commits)
        self._suffix_present = set(suffix_present)
        self._focused = None
        self.keyboard = _FakeKeyboard(self)

    def wait_for_timeout(self, _ms):
        return None

    def evaluate(self, js, arg=None):
        # --- _find_id_suffix: "endsWith(suf)" -> resolve a section id by suffix ---
        if "endsWith(suf)" in js:
            suf = arg
            for sid in self._sections:
                if sid.endswith(suf) and suf in self._suffix_present:
                    return sid
            return None
        # --- _wd_read_date_section: contains 'aria-valuetext' -> committed value ---
        if "aria-valuetext" in js:
            sec = self._sections.get(arg)
            return sec.value if sec else ""
        # --- _wd_section_has_error: 'formField-(start|end)Date' + error scan -> bool ---
        if "formField-(start|end)Date" in js:
            sec = self._sections.get(arg)
            return bool(sec.error) if sec else False
        # --- _wd_kbd_type_section js-clear: contains "d.set.call(el,'')" -> blank value ---
        if "d.set.call(el,''" in js:
            sec = self._sections.get(arg)
            if sec and sec.id not in self._commits:
                # clearing a non-committing section leaves it empty (and still errored)
                sec.value = ""
            elif sec:
                sec.value = ""
            return None
        # --- _wd_kbd_type_section js-focus: contains 'scrollIntoView' + 'focus' -> set focus ---
        if "scrollIntoView" in js and "focus()" in js:
            self._focused = self._sections.get(arg)
            return None
        # --- calendar fallback dateIcon open: return a non-'clicked' so fallback no-ops ---
        if "dateIcon" in js:
            return "no-icon"
        return None


def _commit_ok_page():
    sm = _Section("wx-0--startDate-dateSectionMonth-input")
    sy = _Section("wx-0--startDate-dateSectionYear-input")
    sm.error = True
    sy.error = True  # start errored/required (empty)
    sections = {sm.id: sm, sy.id: sy}
    suffixes = {"wx-0--startDate-dateSectionMonth-input",
                "wx-0--startDate-dateSectionYear-input"}
    # both month + year sections accept keyboard input -> commit succeeds
    return _FakePage(sections, commits={sm.id, sy.id}, suffix_present=suffixes)


def _commit_fail_page():
    sm = _Section("wx-0--startDate-dateSectionMonth-input")
    sy = _Section("wx-0--startDate-dateSectionYear-input")
    sm.error = True
    sy.error = True
    sections = {sm.id: sm, sy.id: sy}
    suffixes = {"wx-0--startDate-dateSectionMonth-input",
                "wx-0--startDate-dateSectionYear-input"}
    # MONTH commits but YEAR does NOT (the exact old bug) -> overall must be False
    return _FakePage(sections, commits={sm.id}, suffix_present=suffixes)


# ===========================================================================
# 1. READBACK GATE -- True only on a real commit.
# ===========================================================================
def test_date_commit_ok_returns_true():
    page = _commit_ok_page()
    ok = wd._fill_wd_date(page, "wx-0--startDate", 8, 2022)
    assert ok is True, "a date that fully commits (month+year readback OK, no error) must return True"
    # and the sections actually hold the committed values
    assert page._sections["wx-0--startDate-dateSectionMonth-input"].value == "8"
    assert page._sections["wx-0--startDate-dateSectionYear-input"].value == "2022"


def test_date_commit_fail_returns_false_not_false_positive():
    """The killer case: YEAR never commits (stays empty + errored). Old code returned True
    (false positive start_filled=True). The gated version MUST return False."""
    page = _commit_fail_page()
    ok = wd._fill_wd_date(page, "wx-0--startDate", 8, 2022)
    assert ok is False, "a date whose YEAR never commits (empty/red) must return False (no false positive)"
    # year stayed empty -> proves the gate read it back rather than trusting the type call
    assert page._sections["wx-0--startDate-dateSectionYear-input"].value == ""


def test_date_missing_widget_returns_false():
    """No month/year section resolvable -> nothing to fill -> False (caller must not treat a
    missing date widget as filled)."""
    page = _FakePage({}, commits=set(), suffix_present=set())
    assert wd._fill_wd_date(page, "wx-0--startDate", 8, 2022) is False


# ===========================================================================
# 2. SOURCE CONTRACT -- the gate + readback wiring stays in place.
# ===========================================================================
def _func_body(name):
    start = SRC.index(f"def {name}(")
    nxt = SRC.index("\ndef ", start + 1)
    return SRC[start:nxt]


def test_fill_wd_date_is_readback_gated_in_source():
    body = _func_body("_fill_wd_date")
    # reads each section back for the verdict
    assert "_wd_read_date_section" in body, "_fill_wd_date must read the section value back"
    # the verdict combines month+year (+day) read-back AND no error
    assert "yr_ok" in body and "mon_ok" in body, "verdict must gate on month + year read-back"
    assert "not err" in body, "verdict must require the required/invalid error to be gone"
    # NEVER returns True on an empty/red field (explicit fail-closed return False path)
    assert "returning False" in body or "return False" in body, (
        "must have a fail-closed return False path")


def test_caller_logs_date_commit_verdict():
    """The WE-block fill path must capture _fill_wd_date's verdict and log when a date did
    NOT commit (visibility for the EXIT-5 regen root), not silently assume start_filled."""
    body = _func_body("_kbd_fill_we_block_by_idx")
    assert "_sd_ok = _fill_wd_date" in body, "start-date fill must capture the readback verdict"
    assert "did NOT commit" in body, "a failed date commit must be logged (read-back failed)"
