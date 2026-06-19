#!/usr/bin/env python3
"""Tests for the ACK-WIDGET resolver (workday-ack-widget 2026-06-10 GEICO 2358).

The blocker: a REQUIRED acknowledgement field (text "read and acknowledge", qid
abbe100a87fcd9ee2deb000a) renders as a widget that is NOT an <input type=checkbox>, so
handle_ack_checkboxes() finds no box to tick -> the required field never satisfies ->
'Next' bounces -> EXIT-5 loop-cap.

handle_ack_widget() is the generic (role/data-automation-id-based, NOT qid-hardcoded)
resolver. It satisfies three non-checkbox ack widget classes:
  (a) ARIA checkbox  [role=checkbox][aria-checked=false]   -> toggle
  (b) radio group    [role=radio]  (none selected)         -> pick affirmative/ack option
  (c) single-option listbox button[aria-haspopup=listbox]  -> open, pick affirmative option

These pin the contract with FakePage stubs (no live browser):
  1. handle_ack_widget is wired into handle_questions (called after handle_ack_checkboxes).
  2. When the page reports an unsatisfied ARIA-checkbox/radio ack widget, the resolver
     processes it (does not raise, logs the action).
  3. When an ack-class listbox is present, the resolver OPENS it and clicks an
     affirmative option ("I have read and acknowledge"-class).
  4. When NOTHING is acted on but an ack field still looks present, the diagnostic
     dump fires (so an unknown widget class is captured, not silently looped).
  5. Idempotent: an already-satisfied page yields no actions and no diag.
"""
import importlib.util, pathlib, inspect

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


class FakeKeyboard:
    def __init__(self): self.presses = []
    def type(self, *a, **k): pass
    def press(self, key, *a, **k): self.presses.append(key)


class FakeOption:
    def __init__(self, text, clicks):
        self._text = text
        self._clicks = clicks
    def text_content(self): return self._text
    def click(self, *a, **k): self._clicks.append(self._text)


class FakeLocator:
    """Stands in for page.locator(sel).first / .all(). Click is recorded."""
    def __init__(self, page, sel):
        self.page = page
        self.sel = sel
    @property
    def first(self): return self
    def click(self, *a, **k): self.page.locator_clicks.append(self.sel)
    def all(self): return []


class AckPage:
    """Drives handle_ack_widget through its evaluate() decision points.

    `aria_results` -> what pass 1+2 (the ARIA checkbox/radio JS) returns.
    `listbox_ids`  -> what pass 3 reports as ack-class listbox button ids.
    `option_texts` -> options rendered when a listbox is opened (for pass 3 click).
    `still_present`-> what pass 4 (residual ack text probe) returns.
    """
    def __init__(self, aria_results=None, listbox_ids=None, option_texts=None, still_present=False):
        self.aria_results = aria_results or []
        self.listbox_ids = listbox_ids or []
        self.option_texts = option_texts or []
        self.still_present = still_present
        self.keyboard = FakeKeyboard()
        self.evaluate_calls = []
        self.locator_clicks = []
        self.option_clicks = []
        self.diag_dumped = False

    def evaluate(self, js, *a, **k):
        self.evaluate_calls.append(js)
        # Pass 1+2: ARIA checkbox / radio group. JS builds results[] and references role=checkbox.
        if "role=checkbox" in js and "role=radio" in js and "results" in js:
            return list(self.aria_results)
        # Pass 3: ack-class listbox enumeration (aria-haspopup=listbox).
        if "aria-haspopup=listbox" in js and "select one" in js:
            return list(self.listbox_ids)
        # Pass 4: residual ack-text presence probe.
        if "label,span,div,p,legend" in js:
            return self.still_present
        # _dump_ack_diag: full-DOM diagnostic dump.
        if "seen=new Set()" in js or "interactive" in js:
            self.diag_dumped = True
            return []
        return None

    def locator(self, sel):
        # the listbox open uses page.locator(sel).first.click(); options come from
        # page.locator("[role=option]").all()
        if sel == "[role=option]":
            opts = [FakeOption(t, self.option_clicks) for t in self.option_texts]
            class _OptLoc:
                def __init__(self, o): self._o = o
                def all(self): return self._o
            return _OptLoc(opts)
        return FakeLocator(self, sel)

    def wait_for_timeout(self, *a, **k): pass


def test_handle_ack_widget_wired_into_questions():
    """handle_questions must call handle_ack_widget (after handle_ack_checkboxes)."""
    src = inspect.getsource(wd.handle_questions)
    assert "handle_ack_widget(page)" in src, "handle_ack_widget not wired into handle_questions"
    assert "handle_ack_checkboxes(page)" in src
    # ordering: ack_widget called after ack_checkboxes
    assert src.index("handle_ack_checkboxes(page)") < src.index("handle_ack_widget(page)")


def test_handle_ack_widget_aria_checkbox_acted_no_diag():
    """An ARIA-checkbox ack widget reported satisfied -> processed, no diag dump."""
    page = AckPage(aria_results=[{"kind": "aria-checkbox", "text": "read and acknowledge", "ok": True}],
                   still_present=True)
    wd.handle_ack_widget(page)
    # acted with ok=True -> diagnostic must NOT fire
    assert page.diag_dumped is False


def test_handle_ack_widget_radio_group_acted():
    """An ARIA radio ack group reported satisfied -> processed, no diag dump."""
    page = AckPage(aria_results=[{"kind": "aria-radio", "text": "I have read and acknowledge", "ok": True}],
                   still_present=True)
    wd.handle_ack_widget(page)
    assert page.diag_dumped is False


def test_handle_ack_widget_listbox_picks_affirmative_option():
    """An ack-class single-option listbox -> opened and an affirmative option clicked."""
    page = AckPage(aria_results=[],
                   listbox_ids=["primaryQuestionnaire--abbe100a87fcd9ee2deb000a"],
                   option_texts=["Select One", "I have read and acknowledge"],
                   still_present=False)
    wd.handle_ack_widget(page)
    # the listbox button was opened (locator click) and the affirmative option clicked
    assert any("abbe100a87fcd9ee2deb000a" in s for s in page.locator_clicks), \
        f"listbox button not opened: {page.locator_clicks}"
    assert "I have read and acknowledge" in page.option_clicks, \
        f"affirmative option not clicked: {page.option_clicks}"


def test_handle_ack_widget_unknown_widget_dumps_diag():
    """Nothing acted but an ack field still present -> diagnostic dump fires (no silent loop)."""
    page = AckPage(aria_results=[], listbox_ids=[], still_present=True)
    wd.handle_ack_widget(page)
    assert page.diag_dumped is True, "expected ack-widget diagnostic dump for unknown widget"


def test_handle_ack_widget_idempotent_when_nothing_present():
    """No ack widgets and none residual -> no actions, no diag."""
    page = AckPage(aria_results=[], listbox_ids=[], still_present=False)
    wd.handle_ack_widget(page)
    assert page.diag_dumped is False
    assert page.option_clicks == []


def test_handle_ack_widget_is_generic_not_qid_hardcoded():
    """The resolver must be role/data-automation-id-based, not hardcoded to the GEICO qid.
    (The qid may appear in the docstring as provenance, but never in executable logic.)"""
    src = inspect.getsource(wd.handle_ack_widget)
    # strip the docstring, then assert the qid is absent from executable code
    body = src.split('"""', 2)[-1] if src.count('"""') >= 2 else src
    assert "abbe100a87fcd9ee2deb000a" not in body, "ack-widget resolver must NOT hardcode the GEICO qid in logic"
    assert "role=checkbox" in src and "role=radio" in src and "aria-haspopup=listbox" in src
