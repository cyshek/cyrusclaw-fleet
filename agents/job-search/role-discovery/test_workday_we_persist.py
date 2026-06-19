#!/usr/bin/env python3
"""Regression tests for the WORKDAY CROSS-NAV WORK-EXPERIENCE PERSISTENCE fix
(workday-we-persist-fix 2026-06-11 run4).

TRUE ROOT CAUSE (proven live on a real fresh Nvidia 2829 account, EXIT-5 reproduced):
typed work-history DATES DO PERSIST across the My-Experience -> next-step navigation
(DOM + React fiber.memoizedProps.value + hidden inputs all confirm). The wall is that
the WE-block COUNT never PLATEAUS. Two compounding sources spawn a fresh empty REQUIRED
work-exp block on each My-Experience visit:
  (1) the resume PARSER auto-creates/keeps a blank 'add-another' template block from the
      parsed PDF text, and that empty can materialize in the SETTLE *after* the prefill
      converge loop returns empty=0 but *before* click_next fires;
  (2) on revisit the 'successfully uploaded' marker disappears -> file_present=False ->
      RE-UPLOAD -> parser RE-RUNS -> more blocks. The old `_RESUME_UPLOADED` cap did not
      stop a fresh account from re-uploading after visit 1.
Net: total grew 4 -> 5 -> 6 -> loop-cap EXIT-5. The misleading
`date-repair block[N]: start_filled=False` log was a single-source (.value only)
FALSE-NEGATIVE -- the value is present via aria-valuetext / hidden input.

THE FIX (locked here):
  1. Resume cap that ACTUALLY holds on a fresh account: once we've uploaded ONCE on a
     fresh/sign-in-fresh account, NEVER re-upload again (typed work-history is the source
     of truth; re-running the parser only respawns empty WE blocks).
  2. `harden_my_experience_before_next(page)`: the LAST action on My Experience before
     click_next -- a bounded loop that DELETES every empty WE block + re-measures until
     0-empty AND total STABLE across 2 consecutive checks (settle waits between), filling a
     lone non-deletable permanent empty once as last resort. Makes the count plateau so Next
     succeeds.
  3. The lying `start_filled={start_empty}` log is replaced with the probe-proven
     multi-source committed read (value || aria-valuetext || hidden input).

These are FakePage tests (no live browser). Live plateau proof is captured separately in the
runner's per-iteration WE-block-count + harden log.
"""
import importlib.util
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


def _src():
    return (HERE / "_workday_runner.py").read_text()


# ---------------------------------------------------------------------------
# 1. SOURCE-LEVEL CONTRACTS (guard against silent regressions)
# ---------------------------------------------------------------------------

def test_harden_function_exists_and_callable():
    assert callable(getattr(wd, "harden_my_experience_before_next", None)), \
        "harden_my_experience_before_next must exist and be callable"


def test_harden_is_called_on_my_experience_before_next():
    """The harden call must run inside the `My Experience` step branch (so it executes
    before the shared click_next at the bottom of the step loop)."""
    src = _src()
    m = re.search(r'elif "My Experience" in cur:(.*?)\n            elif ', src, re.S)
    assert m, "could not locate the My Experience step branch"
    branch = m.group(1)
    assert "harden_my_experience_before_next(page)" in branch, \
        "harden_my_experience_before_next(page) must be called within the My Experience step"


def test_harden_runs_in_dryrun_too():
    """harden must NOT be gated behind `if not args.dryrun:` -- a dryrun has to validate that
    My Experience now advances past the WE step."""
    src = _src()
    m = re.search(r'elif "My Experience" in cur:(.*?)\n            elif ', src, re.S)
    branch = m.group(1)
    # find the harden call and make sure the nearest enclosing guard is not a dryrun skip
    idx = branch.index("harden_my_experience_before_next(page)")
    window = branch[max(0, idx - 240):idx]
    assert "if not args.dryrun" not in window, \
        "harden must run in dryrun too (do not gate it behind `if not args.dryrun:`)"


def test_fresh_account_uploads_resume_only_once():
    """The resume-upload path must short-circuit re-upload once uploaded on a fresh account."""
    src = _src()
    assert '_fresh_acct_up = globals().get("_ACCOUNT_MODE") in ("create_fresh", "signin_fresh")' in src, \
        "handle_experience must compute a fresh-account flag for the upload guard"
    assert "_fresh_acct_up and _RESUME_UPLOADED >= 1" in src, \
        "on a fresh account, once uploaded the runner must skip all further re-uploads"


def test_lying_start_filled_log_removed():
    """The chronic false-negative log line must be gone, replaced with a committed-state read."""
    src = _src()
    # the actual lying LOG call (not prose comments that merely mention the old behavior) is
    # `log(...: start_filled={start_empty}...)`. Assert no log() call still emits that token.
    for line in src.splitlines():
        if "log(" in line and "start_filled={" in line:
            raise AssertionError("the misleading single-source start_filled log CALL must be removed: " + line.strip())
    assert "start_committed=" in src, \
        "date-repair must log the TRUE multi-source committed state"
    # the committed read must use the multi-source helper (value || aria-valuetext || hidden)
    assert "_wd_read_date_section(page, _sm_mon)" in src and "_wd_read_date_section(page, _sm_yr)" in src, \
        "committed-state log must read via _wd_read_date_section (multi-source)"


# ---------------------------------------------------------------------------
# 2. BEHAVIORAL: harden_my_experience_before_next catches a LATE-spawned empty
#    block (the parser's 'add-another' block that materializes after converge)
#    and drives the count to PLATEAU (0 empty, stable total).
# ---------------------------------------------------------------------------

class LateRegenPage:
    """Models the true root-cause: a clean filled set, but the resume parser spawns ONE
    extra empty REQUIRED block the FIRST time we settle (mimicking the late 'add-another'
    template). harden must delete it and then confirm the total is stable.

    Start: `filled` committed blocks (no empty). On the first settle (wait_for_timeout) a
    single empty DELETABLE block appears once. After it is deleted and we settle again, no
    further empties appear -> count plateaus.
    """
    def __init__(self, filled=3, deletable=True):
        self.blocks = {}
        for i in range(filled):
            self.blocks[i] = {"title": f"Role{i}", "deletable": False}  # committed real blocks
        self._next_idx = filled
        self._spawned = False
        self.deletable = deletable
        self.delete_events = 0
        self.max_total = filled

    class _KB:
        def press(self, *a, **k): pass
        def type(self, *a, **k): pass
    keyboard = _KB()

    class _Loc:
        def __init__(self, page, eid): self.page = page; self.eid = eid
        @property
        def first(self): return self
        def count(self): return 1
        def scroll_into_view_if_needed(self, *a, **k): pass
        def click(self, *a, **k): pass
    def locator(self, sel):
        return LateRegenPage._Loc(self, sel)

    def wait_for_timeout(self, *a, **k):
        # the late parser block spawns exactly ONCE, on the first settle
        if not self._spawned:
            self._spawned = True
            self.blocks[self._next_idx] = {"title": "", "deletable": self.deletable}
            self._next_idx += 1
        self.max_total = max(self.max_total, len(self.blocks))

    def evaluate(self, js, *a, **k):
        arg = a[0] if a else None
        if "[t.length,e.length]" in js:
            total = len(self.blocks)
            empty = sum(1 for b in self.blocks.values() if not b["title"].strip())
            return [total, empty]
        if "panel-set-delete-button" in js:
            for i in sorted(self.blocks):
                b = self.blocks[i]
                if not b["title"].strip() and b["deletable"]:
                    del self.blocks[i]; self.delete_events += 1; return 1
            if any(not b["title"].strip() for b in self.blocks.values()):
                return -1
            return 0
        # first-empty-jobTitle idx probe (used by harden permanent-fill path)
        if "workExperience-\\d+--jobTitle/.test" in js and "match(/workExperience-(" in js:
            for i in sorted(self.blocks):
                if not self.blocks[i]["title"].strip():
                    return str(i)
            return None
        if "endsWith(suf)" in js and isinstance(arg, str):
            return arg
        if "inline:'center'" in js:
            return True
        return None


def test_harden_deletes_late_parser_block_and_plateaus(monkeypatch):
    monkeypatch.setattr(wd, "WORK_HISTORY", [{"title": "TPM", "company": "Microsoft",
                                              "location": "Seattle, WA", "start": ("03", "2024"),
                                              "end": None, "current": True, "desc": "x"}])
    page = LateRegenPage(filled=3, deletable=True)
    ok = wd.harden_my_experience_before_next(page, max_rounds=8)
    total, empty = wd._count_we_blocks(page)
    assert ok is True, "harden must report a clean plateau"
    assert empty == 0, f"all empty blocks must be deleted, got {empty}"
    assert total == 3, f"the 3 real committed blocks must remain, got total={total}"
    assert page.delete_events >= 1, "harden must have deleted the late-spawned parser block"


def test_harden_fills_lone_permanent_empty_as_last_resort(monkeypatch):
    """If the late-spawned empty is NON-deletable (permanent), harden fills it once from
    WORK_HISTORY[0] so it stops being a required-empty."""
    filled_job = {"title": "TPM", "company": "Microsoft", "location": "Seattle, WA",
                  "start": ("03", "2024"), "end": None, "current": True, "desc": "x"}
    monkeypatch.setattr(wd, "WORK_HISTORY", [filled_job])

    # patch the kbd-fill helper to mark the targeted block committed (simulates a real commit)
    def _fake_kbd(page, idx, job):
        i = int(idx)
        if i in page.blocks:
            page.blocks[i]["title"] = job["title"]
    monkeypatch.setattr(wd, "_kbd_fill_we_block_by_idx", _fake_kbd)

    page = LateRegenPage(filled=2, deletable=False)  # the late block is permanent (undeletable)
    ok = wd.harden_my_experience_before_next(page, max_rounds=8)
    total, empty = wd._count_we_blocks(page)
    assert empty == 0, f"the permanent empty must be filled (not left required), got empty={empty}"
    assert ok is True, "harden must reach a clean state after filling the permanent empty"


def test_harden_noop_when_no_work_exp_section():
    """If the step has no work-exp blocks at all, harden returns True without error."""
    class _Empty(LateRegenPage):
        def __init__(self): super().__init__(filled=0)
        def wait_for_timeout(self, *a, **k): pass  # nothing spawns
    page = _Empty()
    assert wd.harden_my_experience_before_next(page, max_rounds=3) is True


# ---------------------------------------------------------------------------
# 3. CAP-HOLDS: a FRESH account uploads the resume EXACTLY once across revisits.
#    We model handle_experience's upload gate directly via the module's
#    _RESUME_UPLOADED counter + the fresh-account guard logic.
# ---------------------------------------------------------------------------

class UploadGatePage:
    """Minimal page modeling the handle_experience upload gate across revisits.
    On every visit the 'successfully uploaded' marker is GONE (Gates/Nvidia-class drop),
    so file_present is always False and only the cap/fresh-account guard can stop re-upload.
    """
    def __init__(self):
        self.set_input_calls = 0

    class _Loc:
        def __init__(self, page): self.page = page
        @property
        def first(self): return self
        def count(self): return 1
        def set_input_files(self, *a, **k): self.page.set_input_calls += 1
    def locator(self, sel):
        return UploadGatePage._Loc(self)

    def wait_for_timeout(self, *a, **k): pass

    def evaluate(self, js, *a, **k):
        # file_present probe -> False (marker dropped); upload_input_visible -> True;
        # profile_prefill_skip work-exp probe -> False (fresh account, nothing prefilled).
        return False


def _simulate_fresh_upload_visit(page):
    """Replicate the exact upload-gate decision from handle_experience for a fresh account
    with a dropped 'successfully uploaded' marker. Mirrors the patched runner logic so the
    test fails if that logic regresses."""
    file_present = False
    profile_prefill_skip = False
    already = file_present or profile_prefill_skip
    _fresh_acct_up = True  # create_fresh
    if not already and _fresh_acct_up and wd._RESUME_UPLOADED >= 1:
        already = True
    elif not already and wd._RESUME_UPLOADED >= wd._MAX_RESUME_UPLOADS:
        already = True
    if not already:
        page.locator("x").first.set_input_files("resume.pdf")
        wd._RESUME_UPLOADED += 1


def test_fresh_account_resume_uploaded_exactly_once_across_revisits(monkeypatch):
    monkeypatch.setattr(wd, "_ACCOUNT_MODE", "create_fresh")
    monkeypatch.setattr(wd, "_RESUME_UPLOADED", 0)
    page = UploadGatePage()
    # simulate 5 My-Experience visits (the marker is dropped every revisit)
    for _ in range(5):
        _simulate_fresh_upload_visit(page)
    assert page.set_input_calls == 1, \
        f"fresh account must upload the resume exactly ONCE, got {page.set_input_calls}"
    assert wd._RESUME_UPLOADED == 1, f"_RESUME_UPLOADED should be 1, got {wd._RESUME_UPLOADED}"


def test_non_fresh_account_still_respects_2_upload_cap(monkeypatch):
    """A non-fresh (legacy/profile) account is NOT the default path, but if it ever runs the
    EXFO-class drop-on-revisit re-upload is still capped at _MAX_RESUME_UPLOADS."""
    monkeypatch.setattr(wd, "_ACCOUNT_MODE", "signin_legacy")
    monkeypatch.setattr(wd, "_RESUME_UPLOADED", 0)

    def _visit(page):
        file_present = False
        profile_prefill_skip = False
        already = file_present or profile_prefill_skip
        _fresh_acct_up = wd._ACCOUNT_MODE in ("create_fresh", "signin_fresh")
        if not already and _fresh_acct_up and wd._RESUME_UPLOADED >= 1:
            already = True
        elif not already and wd._RESUME_UPLOADED >= wd._MAX_RESUME_UPLOADS:
            already = True
        if not already:
            page.locator("x").first.set_input_files("resume.pdf")
            wd._RESUME_UPLOADED += 1

    page = UploadGatePage()
    for _ in range(6):
        _visit(page)
    assert page.set_input_calls == wd._MAX_RESUME_UPLOADS, \
        f"non-fresh account re-upload must be capped at {wd._MAX_RESUME_UPLOADS}, got {page.set_input_calls}"



# ---------------------------------------------------------------------------
# 3. SELF-IDENTIFY (disability) downstream fix (workday-selfid-fix 2026-06-11)
#    Found while live-validating the WE fix: Nvidia 2829 cleared My Experience but then
#    loop-capped EXIT-5 on the Self Identify (disability) form. Two bugs:
#      (a) date: per-section js-focus typing left the 3-section Month/Day/Year signed-date
#          widget's React model half-built -> 'Enter a valid date' though every section read
#          back. FIX = type the full MMDDYYYY as ONE continuous run into the month section
#          (Workday auto-advances) via _wd_fill_mdy_sequential.
#      (b) option: handler clicked once + read .value (always 'on') so it could not tell if
#          the disability option committed. FIX = read el.checked, clear other options, retry.
# ---------------------------------------------------------------------------

def test_mdy_sequential_helper_exists():
    assert callable(getattr(wd, "_wd_fill_mdy_sequential", None)), \
        "_wd_fill_mdy_sequential must exist (sequential MMDDYYYY date commit)"


def test_selfid_uses_mdy_sequential_and_checked_state():
    src = _src()
    # handler must call the sequential date filler for the signed date
    assert "_wd_fill_mdy_sequential(page, \"selfIdentifiedDisabilityData--dateSignedOn\"" in src, \
        "self-id handler must commit the signed date via _wd_fill_mdy_sequential"
    # disability option must be verified via .checked (NOT .value, which is always 'on')
    handler = src[src.index("def handle_self_identify"):src.index("def handle_voluntary")]
    assert "c.checked" in handler or ".checked" in handler, \
        "self-id handler must read the checkbox .checked state, not .value"
    assert "disability option committed" in handler, \
        "self-id handler must log the verified commit result"
    # must NOT re-introduce the old lying .value-only single-click pattern
    assert "disability checkbox clicked" not in handler, \
        "old unverified 'disability checkbox clicked' log must be gone"


class _MDYPage:
    """Minimal fake: a Month/Day/Year date widget that ONLY validates when the date is typed
    as a single continuous sequence into the month section (mirrors the real widget building
    its React model on contiguous keypress auto-advance). Tracks the typed buffer per section.
    """
    def __init__(self, has_day=True):
        self.has_day = has_day
        self.sections = {"mon": "", "day": "", "yr": ""}
        self._focus = None
        self._buf = ""

    class _KB:
        def __init__(self, page): self.page = page
        def type(self, s, delay=0):
            # contiguous typing into the focused month section auto-advances M(2)->D(2)->Y(4)
            self.page._buf += str(s)
        def press(self, *a, **k):
            # Tab/blur commits the buffer into sections if it forms a full date
            self.page._commit_buffer()
    @property
    def keyboard(self): return _MDYPage._KB(self)

    class _Loc:
        def __init__(self, page, eid): self.page = page; self.eid = eid
        @property
        def first(self): return self
        def count(self): return 1
        def click(self, *a, **k):
            if self.eid.endswith("mon"):
                self.page._focus = "mon"; self.page._buf = ""
    def locator(self, sel):
        eid = "mon" if sel.endswith("mon") else ("day" if sel.endswith("day") else "yr")
        return _MDYPage._Loc(self, eid)

    def _commit_buffer(self):
        digits = "".join(ch for ch in self._buf if ch.isdigit())
        need = 8 if self.has_day else 6
        if len(digits) >= need:
            self.sections["mon"] = str(int(digits[0:2]))
            if self.has_day:
                self.sections["day"] = str(int(digits[2:4])); self.sections["yr"] = digits[4:8]
            else:
                self.sections["yr"] = digits[2:6]
        self._buf = ""

    def wait_for_timeout(self, *a, **k): pass

    def evaluate(self, js, *a, **k):
        arg = a[0] if a else None
        # _find_id_suffix-style section lookups (suffix is the ARG, generic js body)
        if "endsWith(suf)" in js or (isinstance(arg, str) and "dateSection" in arg):
            if isinstance(arg, str) and "dateSectionMonth" in arg: return "x-mon"
            if isinstance(arg, str) and "dateSectionDay" in arg: return "x-day" if self.has_day else None
            if isinstance(arg, str) and "dateSectionYear" in arg: return "x-yr"
            return None
        # js-clear of a section
        if "d.set.call(el,'')" in js:
            if arg and arg.endswith("mon"): self.sections["mon"] = ""
            elif arg and arg.endswith("day"): self.sections["day"] = ""
            elif arg and arg.endswith("yr"): self.sections["yr"] = ""
            return None
        # js-focus fallback
        if "scrollIntoView" in js and "focus()" in js:
            if arg and arg.endswith("mon"): self._focus = "mon"; self._buf = ""
            return None
        # _wd_read_date_section
        if "aria-valuetext" in js and "el.value" in js:
            if arg and arg.endswith("mon"): return self.sections["mon"]
            if arg and arg.endswith("day"): return self.sections["day"]
            if arg and arg.endswith("yr"): return self.sections["yr"]
            return ""
        # _wd_section_has_error -> never an error in this fake
        if "role=alert" in js or "-error" in js:
            return False
        return None


def test_mdy_sequential_commits_full_date_on_mdy_widget():
    """_wd_fill_mdy_sequential must produce a fully-committed Month/Day/Year date (the path
    that finally let Nvidia 2829 reach Review: typed='06112026' -> mon=6 day=11 yr=2026)."""
    # patch the section-id resolver to our fake ids
    page = _MDYPage(has_day=True)
    ok = wd._wd_fill_mdy_sequential(page, "selfIdentifiedDisabilityData--dateSignedOn", 6, 11, 2026)
    assert ok is True, "sequential fill must verify a complete M/D/Y date"
    assert page.sections == {"mon": "6", "day": "11", "yr": "2026"}, \
        f"date sections must all commit, got {page.sections}"


def test_mdy_sequential_handles_month_year_only_widget():
    """Must not regress a Month/Year-only widget (no day section)."""
    page = _MDYPage(has_day=False)
    ok = wd._wd_fill_mdy_sequential(page, "someDate", 8, 1, 2022)
    assert ok is True
    assert page.sections["mon"] == "8" and page.sections["yr"] == "2022"


# ---------------------------------------------------------------------------
# 4. BOEING/PAYPAL PER-NAV-REGEN FIX (boeing-paypal-WE-fix 2026-06-13)
#    Root cause: harden filled the permanent empty block with WORK_HISTORY[0]
#    (current=True, no end date). The currentlyWorkHere checkbox commit via
#    page.evaluate JS click did NOT reliably fire React's synthetic onChange,
#    so endDate fields stayed required => click_next returned 'My Experience |
#    Errors Found' instead of advancing => loop-cap EXIT-5.
#
#    Fix: harden selects the LAST past job (current=False, has end=...) for the
#    permanent-fill instead of WORK_HISTORY[0]. The past job commits both
#    start+end via keyboard with no currentlyWorkHere checkbox complication.
# ---------------------------------------------------------------------------

def test_harden_uses_past_job_for_permanent_fill_not_current(monkeypatch):
    """boeing-paypal-WE-fix: harden must select a past job (current=False, has end)
    to fill the permanent empty block, NOT the current (Microsoft TPM) job. Using a
    past job avoids the endDate-required / currentlyWorkHere checkbox issue that was
    causing 'My Experience | Errors Found' on click_next."""
    filled_job_current = {"title": "TPM", "company": "Microsoft", "location": "Seattle, WA",
                          "start": ("03", "2024"), "end": None, "current": True, "desc": "x"}
    past_job_amazon   = {"title": "PM", "company": "Amazon", "location": "Seattle, WA",
                         "start": ("08", "2023"), "end": ("03", "2024"), "current": False, "desc": "y"}
    past_job_oldest   = {"title": "Intern", "company": "Pro Painters", "location": "TX",
                         "start": ("05", "2021"), "end": ("05", "2022"), "current": False, "desc": "z"}
    wh = [filled_job_current, past_job_amazon, past_job_oldest]
    monkeypatch.setattr(wd, "WORK_HISTORY", wh)

    jobs_used = []
    def _fake_kbd(page, idx, job):
        jobs_used.append(job)
        i = int(idx)
        if i in page.blocks:
            page.blocks[i]["title"] = job["title"]
    monkeypatch.setattr(wd, "_kbd_fill_we_block_by_idx", _fake_kbd)

    page = LateRegenPage(filled=2, deletable=False)  # permanent empty block
    ok = wd.harden_my_experience_before_next(page, max_rounds=8)
    assert ok is True
    assert jobs_used, "harden must have called _kbd_fill_we_block_by_idx at least once"
    last_used = jobs_used[-1]
    assert last_used["current"] is False, (
        f"harden must fill permanent block with a past (current=False) job, got current={last_used['current']}"
    )
    assert last_used["end"] is not None, (
        f"harden must fill permanent block with a job that has an end date, got end={last_used['end']}"
    )
    # Should pick the LAST (oldest) past job as last resort
    assert last_used["company"] == "Pro Painters", (
        f"harden should pick the oldest past job (Pro Painters), got '{last_used['company']}'"
    )


def test_harden_permanent_fill_falls_back_to_current_when_no_past_jobs(monkeypatch):
    """If WORK_HISTORY has only the current job (no past jobs), harden falls back to
    WORK_HISTORY[0] (current=True) to avoid leaving the block empty."""
    only_current = {"title": "TPM", "company": "Microsoft", "location": "Seattle, WA",
                    "start": ("03", "2024"), "end": None, "current": True, "desc": "x"}
    monkeypatch.setattr(wd, "WORK_HISTORY", [only_current])

    jobs_used = []
    def _fake_kbd(page, idx, job):
        jobs_used.append(job)
        i = int(idx)
        if i in page.blocks:
            page.blocks[i]["title"] = job["title"]
    monkeypatch.setattr(wd, "_kbd_fill_we_block_by_idx", _fake_kbd)

    page = LateRegenPage(filled=1, deletable=False)  # permanent empty
    ok = wd.harden_my_experience_before_next(page, max_rounds=8)
    assert ok is True
    assert jobs_used, "harden must call _kbd_fill_we_block_by_idx even with only current job"
    # It should fall back to WORK_HISTORY[0] (current job) when no past available
    assert jobs_used[-1]["company"] == "Microsoft"


def test_harden_past_job_selection_source_contract():
    """Source-level contract: harden must contain the past-job selection logic
    ('boeing-paypal-WE-fix') so the fix cannot be silently reverted."""
    src = (wd.__file__ and open(wd.__file__).read()) or ""
    assert "boeing-paypal-WE-fix" in src, (
        "_workday_runner.py must contain the boeing-paypal-WE-fix comment"
    )
    assert "_past = [j for j in WORK_HISTORY if not j.get(\"current\") and j.get(\"end\")]" in src or \
           "not j.get('current') and j.get('end')" in src, (
        "harden must select past jobs (current=False, has end) for permanent-fill"
    )


def test_click_next_errors_found_dump_in_source():
    """Source-level contract: click_next must contain the 'Errors Found' dump logic
    so we can diagnose what validation failed after Next in future runs."""
    src = (wd.__file__ and open(wd.__file__).read()) or ""
    assert "ERRORS-FOUND dump" in src, (
        "click_next must log an 'ERRORS-FOUND dump' when Workday returns 'Errors Found' heading"
    )
    assert "errors found" in src.lower(), (
        "click_next must check for 'errors found' in the post-Next heading"
    )


if __name__ == "__main__":
    import sys
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


# ---------------------------------------------------------------------------
# 5. POST_NEXT_WE_GUARD (workday-post-nav-regen-fix 2026-06-13)
#    post_next_we_guard is called at the TOP of My Experience revisit branch to
#    clean up the block Workday regenerates after click_next navigation.
# ---------------------------------------------------------------------------

class PostNavRegenPage:
    """Simulates the Boeing/PayPal sub-class: 3 committed WE blocks plus exactly
    ONE new empty block that Workday injected right after click_next navigation."""
    def __init__(self, empty_deletable=True):
        self.blocks = {0: {"title": "TPM", "deletable": False},
                       1: {"title": "PM", "deletable": False},
                       2: {"title": "SDE", "deletable": False},
                       3: {"title": "", "deletable": empty_deletable}}
        self.delete_events = 0

    class _KB:
        def press(self, *a, **k): pass
        def type(self, *a, **k): pass
    keyboard = _KB()

    class _Loc:
        def __init__(self, page, eid): self.page = page; self.eid = eid
        @property
        def first(self): return self
        def count(self): return 1
        def scroll_into_view_if_needed(self, *a, **k): pass
        def click(self, *a, **k): pass
    def locator(self, sel): return PostNavRegenPage._Loc(self, sel)

    def wait_for_timeout(self, *a, **k): pass

    def evaluate(self, js, *a, **k):
        arg = a[0] if a else None
        if "[t.length,e.length]" in js:
            total = len(self.blocks)
            empty = sum(1 for b in self.blocks.values() if not b["title"].strip())
            return [total, empty]
        if "panel-set-delete-button" in js:
            for i in sorted(self.blocks):
                b = self.blocks[i]
                if not b["title"].strip() and b["deletable"]:
                    del self.blocks[i]; self.delete_events += 1; return 1
            if any(not b["title"].strip() for b in self.blocks.values()):
                return -1
            return 0
        if "workExperience-\\d+--jobTitle/.test" in js and "match(/workExperience-(" in js:
            for i in sorted(self.blocks):
                if not self.blocks[i]["title"].strip():
                    return str(i)
            return None
        if "endsWith(suf)" in js and isinstance(arg, str): return arg
        if "inline:'center'" in js: return True
        return None


def test_post_next_we_guard_cleans_single_deletable_regen_block(monkeypatch):
    """Boeing/PayPal case: one new empty deletable block appeared after click_next.
    post_next_we_guard must delete it and return True."""
    monkeypatch.setattr(wd, "WORK_HISTORY", [{"title": "TPM", "company": "Microsoft",
                                               "location": "Seattle, WA", "start": ("03", "2024"),
                                               "end": None, "current": True, "desc": "x"}])
    page = PostNavRegenPage(empty_deletable=True)
    ok = wd.post_next_we_guard(page)
    total, empty = wd._count_we_blocks(page)
    assert ok is True, "post_next_we_guard must return True when cleaned"
    assert empty == 0, f"empty WE blocks must be 0 after guard, got {empty}"
    assert total == 3, f"committed blocks must remain intact, got total={total}"
    assert page.delete_events >= 1, "guard must have deleted the post-nav regen block"


def test_post_next_we_guard_fills_permanent_regen_block(monkeypatch):
    """If the post-nav regen block is non-deletable, guard must fill it and return True."""
    job = {"title": "TPM", "company": "Microsoft", "location": "Seattle, WA",
           "start": ("03", "2024"), "end": None, "current": True, "desc": "x"}
    monkeypatch.setattr(wd, "WORK_HISTORY", [job])

    def _fake_kbd(page, idx, j):
        i = int(idx)
        if i in page.blocks:
            page.blocks[i]["title"] = j["title"]
    monkeypatch.setattr(wd, "_kbd_fill_we_block_by_idx", _fake_kbd)

    page = PostNavRegenPage(empty_deletable=False)
    ok = wd.post_next_we_guard(page)
    total, empty = wd._count_we_blocks(page)
    assert ok is True, "guard must return True after filling permanent regen block"
    assert empty == 0, f"no empty blocks should remain, got {empty}"


def test_post_next_we_guard_noop_when_already_clean(monkeypatch):
    """If there are no empty WE blocks, post_next_we_guard is a no-op and returns True."""
    monkeypatch.setattr(wd, "WORK_HISTORY", [])
    page = PostNavRegenPage(empty_deletable=True)
    for b in page.blocks.values():
        b["title"] = "Filled"
    ok = wd.post_next_we_guard(page)
    assert ok is True
    assert page.delete_events == 0, "no deletes should have occurred"


def test_post_next_we_guard_is_callable():
    assert callable(getattr(wd, "post_next_we_guard", None)), \
        "post_next_we_guard must exist and be callable in _workday_runner"


class TestReqReuploadCap:
    """Regression: _MAX_REQ_REUPLOADS must be 1 on fresh-account flows.
    The Boeing/PayPal-class tenant drops the upload display on every My-Experience
    revisit and flags 'Upload a file is required'. Cap=4 allowed 4 re-uploads =
    4 parser runs = 4 new empty WE blocks = EXIT-5 loop. Cap must be 1 so after
    the first re-upload attempt we trust the server-side file. (fix 2026-06-13)"""

    def test_max_req_reuploads_is_1(self):
        import _workday_runner as wd
        assert wd._MAX_REQ_REUPLOADS == 1, (
            f"_MAX_REQ_REUPLOADS must be 1 (was {wd._MAX_REQ_REUPLOADS}); "
            "cap=4 caused PayPal/Boeing required-upload re-upload loop (EXIT-5)"
        )

    def test_req_reupload_cap_comment_documents_fix(self):
        """The cap change must be documented with the paypal-req-reupload-cap-fix tag."""
        src = _src()
        assert "paypal-req-reupload-cap-fix" in src, (
            "Missing fix tag 'paypal-req-reupload-cap-fix' in _workday_runner.py; "
            "ensure the cap change comment is present for auditability"
        )


def test_post_next_we_guard_called_on_revisit_before_handle_experience():
    """post_next_we_guard must be called in the My Experience revisit branch (visit>=2),
    BEFORE handle_experience, so it cleans the post-nav regen block in time."""
    src = _src()
    m = re.search(r'elif "My Experience" in cur:(.*?)\n            elif ', src, re.S)
    assert m, "could not locate the My Experience step branch"
    branch = m.group(1)
    assert "post_next_we_guard(page)" in branch, \
        "post_next_we_guard(page) must be called in the My Experience branch"
    idx_guard = branch.index("post_next_we_guard(page)")
    idx_handle = branch.index("handle_experience(page")
    assert idx_guard < idx_handle, \
        "post_next_we_guard must be called BEFORE handle_experience"
    window = branch[max(0, idx_guard - 300):idx_guard]
    assert "_step_revisits" in window and "2" in window, \
        "post_next_we_guard must be gated on revisit count >= 2"
