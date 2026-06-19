#!/usr/bin/env python3
"""Tests for the WORK-EXPERIENCE RUNAWAY fix (workday-workexp-fix 2026-06-02).

The EXFO/RBI/NVIDIA-class bug: on profile-prefill tenants, each freshly-Added work-exp
block renders BELOW the fold; Playwright Locator.click aborts 'Element is outside of the
viewport', leaving the block required-empty -> 'Next' bounces forever, AND each iteration
spawns a NEW permanent escalating-index block (50->278->670->927).

These pin the fix contract with FakePage stubs (no live browser):
  1. _scroll_into_view_js is CALLED before every work-exp field/date interaction.
  2. delete_empty_we_blocks DELETES deletable empty blocks (runaway stop).
  3. delete_empty_we_blocks LEAVES permanent (non-deletable) empty blocks for kbd-fill.
"""
import importlib.util, pathlib

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


class FakeKeyboard:
    def type(self, *a, **k): pass
    def press(self, *a, **k): pass


class ScrollSpyPage:
    """Records every JS scrollIntoView call (via evaluate) and keyboard.type calls so we
    can assert the date widget is scrolled into view (JS-focus) and committed via REAL
    page.keyboard.type per-section (workday-date-commit-fix 2026-06-09)."""
    def __init__(self):
        self.scroll_calls = []   # ids scrolled into view (JS-focus or _scroll_into_view_js)
        self.events = []         # ordered ('scroll'|'type'|'click', payload)
        self.keyboard = self._KB(self)

    class _KB:
        def __init__(self, page): self.page = page
        def type(self, text, *a, **k):
            self.page.events.append(("type", text))
        def press(self, *a, **k): pass

    def evaluate(self, js, *a, **k):
        arg = a[0] if a else None
        # _scroll_into_view_js: js contains scrollIntoView({block:'center',inline:'center'})
        if "inline:'center'" in js and isinstance(arg, str):
            self.scroll_calls.append(arg)
            self.events.append(("scroll", arg))
            return True
        # _wd_kbd_type_section JS-focus: scrollIntoView({block:'center'}); el.focus()
        if "scrollIntoView({block:'center'})" in js and ".focus()" in js and isinstance(arg, str):
            self.scroll_calls.append(arg)
            self.events.append(("scroll", arg))
            return None
        # _find_id_suffix: return the suffix as a usable id
        if "endsWith(suf)" in js:
            return arg  # echo suffix as the id
        # generic value probes / read-back -> empty string (date never sticks in this mock)
        return ""

    def wait_for_timeout(self, *a, **k): pass

    def locator(self, sel):
        page = self
        eid = sel.lstrip("#")
        class L:
            @property
            def first(self):
                return self
            def scroll_into_view_if_needed(self, *a, **k):
                # Simulate Playwright's actionability scroll TIMING OUT on below-fold blocks
                raise Exception("Timeout exceeded; element is outside of the viewport")
            def click(self, *a, **k):
                page.events.append(("click", eid))
        return L()


class DeleteSimPage:
    """Simulates a draft with a mix of deletable + permanent empty work-exp blocks.
    Each delete_empty_we_blocks JS call removes ONE deletable empty block (returns 1),
    returns -1 when only a permanent empty remains, 0 when none empty."""
    def __init__(self, deletable_empties, permanent_empties):
        self.deletable = deletable_empties
        self.permanent = permanent_empties
        self.keyboard = FakeKeyboard()

    def evaluate(self, js, *a, **k):
        if "panel-set-delete-button" in js:  # the delete-one-block JS
            if self.deletable > 0:
                self.deletable -= 1
                return 1
            if self.permanent > 0:
                return -1
            return 0
        return None

    def wait_for_timeout(self, *a, **k): pass


# ---- _scroll_into_view_js ----

def test_scroll_into_view_js_called_and_returns_true():
    page = ScrollSpyPage()
    assert wd._scroll_into_view_js(page, "workExperience-50--jobTitle") is True
    assert page.scroll_calls == ["workExperience-50--jobTitle"]

def test_scroll_into_view_js_noop_on_empty_id():
    page = ScrollSpyPage()
    assert wd._scroll_into_view_js(page, None) is False
    assert page.scroll_calls == []


# ---- _fill_wd_date scrolls each date section into view via JS-focus (the viewport fix) ----

def test_fill_wd_date_scrolls_before_click():
    # workday-date-commit-fix 2026-06-09: the date widget is now committed via REAL
    # page.keyboard.type per-section, with a JS-focus (scrollIntoView+focus) first -- so
    # the below-fold block is always brought into view WITHOUT a Playwright .click that
    # could time out. Assert a scroll happened (JS-focus) AND real keyboard typing fired.
    page = ScrollSpyPage()
    # _find_id_suffix echoes the suffix back as id, so month/year ids resolve.
    wd._fill_wd_date(page, "workExperience-927--startDate", "03", "2024")
    assert any(e[0] == "scroll" for e in page.events), "no JS scrollIntoView/JS-focus before date fill"
    assert any(e[0] == "type" for e in page.events), "date must be typed via real page.keyboard.type"
    first_scroll = next(i for i, e in enumerate(page.events) if e[0] == "scroll")
    first_type = next(i for i, e in enumerate(page.events) if e[0] == "type")
    assert first_scroll < first_type, "section must be scrolled/focused before typing"


def test_fill_wd_date_returns_false_when_value_does_not_stick():
    # workday-date-commit-fix 2026-06-09 CORE CONTRACT: the old code returned True without
    # reading the value back -> false-positive start_filled=True even though the YEAR never
    # committed -> Workday regenerated empty blocks -> EXIT 5. The fix READS BACK each
    # section and returns False when month/year don't verify. This mock's read-back always
    # returns '' (value never sticks), so _fill_wd_date MUST return False (after a retry).
    page = ScrollSpyPage()
    result = wd._fill_wd_date(page, "workExperience-5--startDate", "08", "2022")
    assert result is False, "must NOT report success when the date read-back is empty"
    # and it must have RETRIED (typed the year more than once across the two attempts)
    year_types = [e for e in page.events if e[0] == "type" and e[1] == "2022"]
    assert len(year_types) >= 2, "must retry the per-section type at least once before giving up"


# ---- delete_empty_we_blocks ----

def test_delete_removes_all_deletable_empties():
    page = DeleteSimPage(deletable_empties=4, permanent_empties=0)
    n = wd.delete_empty_we_blocks(page)
    assert n == 4
    assert page.deletable == 0

def test_delete_stops_at_permanent_block_for_kbd_fallback():
    # 2 deletable then a permanent empty remains -> delete the 2, LEAVE the permanent.
    page = DeleteSimPage(deletable_empties=2, permanent_empties=1)
    n = wd.delete_empty_we_blocks(page)
    assert n == 2, "should delete only the 2 deletable, leave permanent for kbd-fill"
    assert page.permanent == 1

def test_delete_noop_when_no_empties():
    page = DeleteSimPage(deletable_empties=0, permanent_empties=0)
    assert wd.delete_empty_we_blocks(page) == 0

def test_delete_loop_cap_does_not_spin_forever():
    # huge deletable count but max_iter caps the work (loop-cap safety).
    page = DeleteSimPage(deletable_empties=10_000, permanent_empties=0)
    n = wd.delete_empty_we_blocks(page, max_iter=5)
    assert n == 5, "max_iter must cap the delete loop"


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
            except Exception as e:
                fails += 1; print("ERROR", name, repr(e))
    sys.exit(1 if fails else 0)
