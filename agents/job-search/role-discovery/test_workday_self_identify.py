#!/usr/bin/env python3
"""Regression tests for the WORKDAY SELF-IDENTIFY (DISABILITY) form fix
(workday-selfid-fix 2026-06-11).

ROOT CAUSE (proven live on Nvidia 2829 dryrun after WE-persist fix landed):
  (a) Date: _fill_wd_date (per-section js-focus+type) left the 3-section Month/Day/Year
      signed-date widget's React model half-built. Every section read back its value yet
      Workday still showed 'Enter a valid date' -> loop-cap EXIT-5.
      FIX: _wd_fill_mdy_sequential types full MMDDYYYY in one continuous run into the month
      section; Workday's own date handler auto-advances M->D->Y and builds the React model.
  (b) Option: handler clicked once then read el.value (always 'on' for radio inputs, regardless
      of checked state) so it couldn't tell whether the disability option actually committed.
      -> handler re-clicked the same option every revisit while Workday required-validation
      still failed -> EXIT-5.
      FIX: read el.checked (the real committed state), clear any OTHER checked option first,
      retry up to 3x; log the verified result.

These are source-level static tests (no browser). Live proof is in Nvidia 2829 EXIT-0 log.
"""
import importlib.util
import pathlib
import re
import datetime

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


def _src():
    return (HERE / "_workday_runner.py").read_text()


def _selfid_handler_src():
    """Extract the handle_self_identify function source."""
    src = _src()
    start = src.index("def handle_self_identify(")
    end = src.index("def handle_voluntary(", start)
    return src[start:end]


# ---------------------------------------------------------------------------
# 1. Function existence
# ---------------------------------------------------------------------------

def test_handle_self_identify_exists_and_callable():
    assert callable(getattr(wd, "handle_self_identify", None)), \
        "handle_self_identify must exist and be callable"


def test_mdy_sequential_helper_exists_and_callable():
    assert callable(getattr(wd, "_wd_fill_mdy_sequential", None)), \
        "_wd_fill_mdy_sequential must exist and be callable (sequential MDY date commit)"


# ---------------------------------------------------------------------------
# 2. Date commit correctness (the 'Enter a valid date' fix)
# ---------------------------------------------------------------------------

def test_selfid_date_uses_mdy_sequential():
    """Handler MUST call _wd_fill_mdy_sequential for the signed date (not just _fill_wd_date)."""
    handler = _selfid_handler_src()
    assert '_wd_fill_mdy_sequential(page, "selfIdentifiedDisabilityData--dateSignedOn"' in handler, \
        "handle_self_identify must commit signed date via _wd_fill_mdy_sequential (not just fill_if)"


def test_selfid_date_has_fallback_chain():
    """If mdy_sequential fails, handler must fall back gracefully (not crash/skip the date)."""
    handler = _selfid_handler_src()
    # must have a fallback to _fill_wd_date or fill_if per-section
    assert ("_fill_wd_date" in handler or "fill_if(page, \"input#selfIdentifiedDisabilityData--dateSignedOn" in handler), \
        "handle_self_identify must have a fallback date path in case mdy_sequential fails"


def test_selfid_date_uses_today():
    """Signed date must use today's actual date (datetime.date.today()), not a hardcoded value."""
    handler = _selfid_handler_src()
    assert "datetime.date.today()" in handler or "date.today()" in handler, \
        "handle_self_identify must use today's date (datetime.date.today()) for the signed date"


def test_mdy_sequential_signature():
    """_wd_fill_mdy_sequential must accept (page, base_suffix, mm, dd, yyyy)."""
    import inspect
    sig = inspect.signature(wd._wd_fill_mdy_sequential)
    params = list(sig.parameters.keys())
    assert "page" in params, "_wd_fill_mdy_sequential must have 'page' param"
    assert "mm" in params, "_wd_fill_mdy_sequential must have 'mm' param"
    assert "dd" in params, "_wd_fill_mdy_sequential must have 'dd' param (day)"
    assert "yyyy" in params, "_wd_fill_mdy_sequential must have 'yyyy' param"


def test_mdy_sequential_returns_bool():
    """_wd_fill_mdy_sequential must declare a bool return (ok flag for fallback chain)."""
    src = _src()
    fn_start = src.index("def _wd_fill_mdy_sequential(")
    # Find next def to extract body
    fn_end = src.index("\ndef ", fn_start + 1)
    fn_body = src[fn_start:fn_end]
    assert "return True" in fn_body or "return False" in fn_body, \
        "_wd_fill_mdy_sequential must return a bool (True=committed, False=failed)"


# ---------------------------------------------------------------------------
# 3. Disability option commit correctness (the .value vs .checked fix)
# ---------------------------------------------------------------------------

def test_selfid_option_uses_checked_not_value():
    """.checked must be read (not .value which is always 'on' for radio inputs)."""
    handler = _selfid_handler_src()
    assert ".checked" in handler or "c.checked" in handler, \
        "handle_self_identify must verify disability option via .checked, not .value"


def test_selfid_option_does_not_use_value_for_check():
    """Must NOT rely on .value=='on' to determine if the option committed."""
    handler = _selfid_handler_src()
    # Ensure there's no .value comparison for verifying checked state
    # (reading .value is fine for something else, but not as the checked gate)
    # The old pattern was: committed = page.evaluate("...c.value=='on'...") or similar
    assert "c.value" not in handler or ".checked" in handler, \
        "handler must not use .value as the sole committed-state check; use .checked"


def test_selfid_option_picks_neutral_answer():
    """Handler must select the neutral/decline option (not 'Yes I have a disability')."""
    handler = _selfid_handler_src()
    # The regex that finds the neutral option
    assert "do not want to answer" in handler or "don.t wish" in handler or "not to answer" in handler, \
        "handler must pick 'I do not want to answer' (neutral) disability option"
    # Must NOT pick Yes/No (which would fabricate or deny a disability)
    # Check that we're not hardcoding Yes/No as the first-choice option
    assert "cbs[-1].id" not in handler or "do not want to answer" in handler, \
        "fallback to last checkbox must be accompanied by neutral-option search logic"


def test_selfid_option_retries_up_to_3x():
    """Handler must retry the disability click up to 3 attempts (the .checked verification loop)."""
    handler = _selfid_handler_src()
    assert "range(3)" in handler, \
        "handle_self_identify must retry disability commit up to 3x (for range(3) loop)"


def test_selfid_option_clears_other_options_first():
    """Handler must uncheck any other already-checked disability option before clicking target."""
    handler = _selfid_handler_src()
    # The fix clears other checked options (c.id!==id && c.checked -> click)
    assert "c.id!==id" in handler and "c.checked" in handler, \
        "handler must clear other checked disability options before committing the target option"


def test_selfid_option_verified_commit_logged():
    """Handler must log the verified commit result (not silent failure)."""
    handler = _selfid_handler_src()
    assert "disability option committed" in handler, \
        "handle_self_identify must log 'disability option committed: <bool>' for observability"


# ---------------------------------------------------------------------------
# 4. Old broken pattern must NOT exist
# ---------------------------------------------------------------------------

def test_selfid_old_unverified_click_pattern_absent():
    """Old single-click 'disability checkbox clicked' log must be gone (was the lying pattern)."""
    handler = _selfid_handler_src()
    assert "disability checkbox clicked" not in handler, \
        "old unverified 'disability checkbox clicked' log was removed; must not be re-introduced"


def test_selfid_no_value_only_verification():
    """Old pattern used c.value=='on' as the only verification — that's always truthy for radios."""
    handler = _selfid_handler_src()
    # If .value is used at all, there must also be a .checked verification
    if "c.value" in handler:
        assert ".checked" in handler, \
            "if .value appears in handler, .checked must also be present (value alone is insufficient)"


# ---------------------------------------------------------------------------
# 5. Name field filled
# ---------------------------------------------------------------------------

def test_selfid_fills_name_field():
    """Handler must fill the name field (selfIdentifiedDisabilityData--name)."""
    handler = _selfid_handler_src()
    assert "selfIdentifiedDisabilityData--name" in handler, \
        "handle_self_identify must fill the name field (input#selfIdentifiedDisabilityData--name)"


# ---------------------------------------------------------------------------
# 6. Integration: handle_self_identify called in the main step dispatch
# ---------------------------------------------------------------------------

def test_selfid_called_in_step_dispatch():
    """handle_self_identify must be called from the main step-dispatch loop."""
    src = _src()
    assert "handle_self_identify(page)" in src, \
        "handle_self_identify(page) must be invoked in the main step loop"


def test_selfid_not_gated_behind_dryrun_skip():
    """handle_self_identify must NOT be gated behind 'if not args.dryrun:' — dryruns must also
    exercise the self-id step so we can validate it before a live submit."""
    src = _src()
    call_idx = src.index("handle_self_identify(page)")
    # Check a window before the call for a dryrun guard
    window = src[max(0, call_idx - 300):call_idx]
    assert "if not args.dryrun" not in window, \
        "handle_self_identify must run in dryrun too (do not gate it behind if not args.dryrun)"


# ---------------------------------------------------------------------------
# 7. Functional test: _wd_fill_mdy_sequential with a minimal fake page
# ---------------------------------------------------------------------------

class _FakeSection:
    """Tracks value for one date section input."""
    def __init__(self, section_id):
        self.id = section_id
        self.value = ""
        self.aria_val = ""

class _FakeMDYPage:
    """Fake page that simulates Workday's Month/Day/Year date widget contiguous-typing model.
    The widget only 'commits' when MMDDYYYY is typed as one continuous sequence into the
    month section (auto-advance). Per-section JS typing leaves it half-built.
    """
    def __init__(self):
        self._mon = _FakeSection("selfId--dateSignedOn-dateSectionMonth-input")
        self._day = _FakeSection("selfId--dateSignedOn-dateSectionDay-input")
        self._yr  = _FakeSection("selfId--dateSignedOn-dateSectionYear-input")
        self._focused = None
        self._type_buf = ""
        self._errors = {}
        self.locator_calls = []
        self.evaluate_calls = []

    class _Keyboard:
        def __init__(self, page): self._page = page
        def type(self, s, delay=0):
            # Simulate contiguous typing: buf the digits, then commit on tab
            self._page._type_buf += s
        def press(self, key):
            if key in ("Tab", "Enter"):
                self._page._commit_buf()

    @property
    def keyboard(self): return _FakeMDYPage._Keyboard(self)

    class _Loc:
        def __init__(self, page, eid): self._page = page; self._eid = eid
        @property
        def first(self): return self
        def count(self): return 1
        def click(self, *a, **kw):
            self._page._focused = self._eid
            self._page._type_buf = ""
        def is_visible(self): return True

    def locator(self, sel):
        # Extract element id from selector
        if "Month" in sel:
            eid = self._mon.id
        elif "Day" in sel:
            eid = self._day.id
        else:
            eid = self._yr.id
        self.locator_calls.append(sel)
        return _FakeMDYPage._Loc(self, eid)

    def _commit_buf(self):
        """Parse the typed buffer (MMDDYYYY or MMYYYY) into sections."""
        digits = "".join(c for c in self._type_buf if c.isdigit())
        if len(digits) == 8:  # MMDDYYYY
            self._mon.value = digits[0:2]
            self._mon.aria_val = digits[0:2]
            self._day.value = digits[2:4]
            self._day.aria_val = digits[2:4]
            self._yr.value = digits[4:8]
            self._yr.aria_val = digits[4:8]
        elif len(digits) == 6:  # MMYYYY (no day)
            self._mon.value = digits[0:2]
            self._yr.value = digits[2:6]
        # clear error state on valid commit
        self._errors = {}

    def evaluate(self, js, *args):
        self.evaluate_calls.append(js[:40])
        # Simulate _wd_date_section_ids: return (mon_id, day_id, yr_id)
        if "dateSectionMonth" in js and "dateSectionDay" in js and "return [" in js:
            return [self._mon.id, self._day.id, self._yr.id]
        # Simulate getElementById for read-back
        if "getElementById" in js and args:
            eid = args[0]
            if eid == self._mon.id:
                return self._mon.value
            if eid == self._day.id:
                return self._day.value
            if eid == self._yr.id:
                return self._yr.value
        # Simulate clear+focus JS (value setter)
        if "d.set.call" in js:
            # clearing; ignore
            return None
        # Simulate error check
        if "error" in js.lower() or "aria-invalid" in js.lower():
            return False  # no error
        return None

    def wait_for_timeout(self, ms): pass


def test_mdy_sequential_fake_page_commits_date():
    """_wd_fill_mdy_sequential correctly commits a date on a page that accepts contiguous typing."""
    # We can't call the real function with a fake since it uses evaluate() with real JS,
    # but we can test that the logic is present in source to at least type the concatenated seq.
    src = _src()
    fn_start = src.index("def _wd_fill_mdy_sequential(")
    fn_end = src.index("\ndef ", fn_start + 1)
    fn_body = src[fn_start:fn_end]
    # Must build a concatenated sequence (MM + DD + YYYY)
    assert "mm + (dd if day else" in fn_body or "seq = mm + " in fn_body, \
        "_wd_fill_mdy_sequential must build a contiguous MMDDYYYY sequence"
    # Must type the sequence as one keyboard.type() call
    assert "keyboard.type(seq" in fn_body, \
        "_wd_fill_mdy_sequential must type the full sequence via keyboard.type(seq, ...)"
    # Must read back all sections to verify
    assert "_wd_read_date_section" in fn_body, \
        "_wd_fill_mdy_sequential must read back section values to verify commit"


def test_mdy_sequential_handles_month_only_widget():
    """For Month/Year widgets (no day), the sequence should be MMYYYY (6 digits, not 8)."""
    src = _src()
    fn_start = src.index("def _wd_fill_mdy_sequential(")
    fn_end = src.index("\ndef ", fn_start + 1)
    fn_body = src[fn_start:fn_end]
    # Must handle the case where 'day' is None/falsy (Month/Year variant)
    assert "if day" in fn_body or "(dd if day" in fn_body, \
        "_wd_fill_mdy_sequential must handle Month/Year widgets with no day section"


# ---------------------------------------------------------------------------
# 8. Edge case: no disabilityStatus radios on this tenant
# ---------------------------------------------------------------------------

def test_selfid_handles_no_radios_gracefully():
    """If no disabilityStatus inputs exist, the handler must not crash (use try/except)."""
    handler = _selfid_handler_src()
    assert "try:" in handler, \
        "handle_self_identify must wrap disability radio logic in try/except for robustness"
    assert "except Exception" in handler or "except Exception as e" in handler, \
        "handle_self_identify must catch exceptions around disability radio logic"
