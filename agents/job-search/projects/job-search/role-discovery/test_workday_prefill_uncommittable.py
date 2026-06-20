#!/usr/bin/env python3
"""Regression tests for the WORKDAY PROFILE-PREFILL-UNCOMMITTABLE fast-fail
(workday-prefill-uncommittable-fix 2026-06-05).

CONTEXT / WHY THIS EXISTS
-------------------------
The "54 -> 274 -> 437 explosion" originally chased as an empty-block-regen ENGINE bug was a
MISREAD (those were block-INDEX values of the single empty block regenerated per visit, not a
count explosion). Two subagents instrumented EXFO 2121 (exfo.wd10.myworkdayjobs.com,
Solutions-Engineer_R-100191) and proved:

  * The empty-block regen is ALREADY HANDLED by the prefill-guard convergence loop
    (workday-regen-fix 2026-06-05): the WE-block count converges (7->8->9) and empties->0.
  * The REAL wall is a DATA/profile-side bug: the tenant's saved candidate profile carries
    PROFILE-PREFILLED work-experience blocks (EXFO: ~5 Microsoft DUPES) whose REQUIRED
    start-date physically CANNOT be committed by our automation (read-only prefills). Workday
    sees them as incomplete -> keeps the form dirty -> regenerates an empty required block
    forever -> the My-Experience step spun to the GENERIC EXIT 5 loop-cap (~3 wasted visits).

THE FIX (locked here): after the prefill-guard date-repair pass, detect any PROFILE-PREFILLED
(jobTitle present, not currently-here) work-exp block whose required start-date MONTH is still
empty, set a module flag (`_WE_PREFILL_UNCOMMITTABLE`), and have the My-Experience step branch
fast-fail with a precise EXIT 9 + a clean 'workday-profile-prefill-uncommittable' bank reason
instead of grinding to EXIT 5. This is a profile-side blocker (Cyrus must dedupe his Workday
tenant profile work-history), NOT an engine bug -- so the row banks cleanly and is NOT
re-ground.

These are SOURCE-LEVEL CONTRACT tests (no live browser): they guard that the global, the
detection probe, the per-run reset, and the EXIT-9 banking all stay wired. They are the
companion to test_workday_regen_fix.py (which locks the converge loop those notes describe).
"""
import importlib.util
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

SRC = (HERE / "_workday_runner.py").read_text()


def _func_body(name):
    start = SRC.index(f"def {name}(")
    nxt = SRC.index("\ndef ", start + 1)
    return SRC[start:nxt]


# ---------------------------------------------------------------------------
# 1. The module-level flag exists and DEFAULTS to falsy (so a fresh import /
#    a clean row never spuriously banks).
# ---------------------------------------------------------------------------

def test_flag_exists_and_defaults_falsy():
    assert hasattr(wd, "_WE_PREFILL_UNCOMMITTABLE"), "_WE_PREFILL_UNCOMMITTABLE module flag must exist"
    assert not getattr(wd, "_WE_PREFILL_UNCOMMITTABLE"), "_WE_PREFILL_UNCOMMITTABLE must default to falsy (None)"


# ---------------------------------------------------------------------------
# 2. run() RESETS the flag at the top so it can NEVER leak across batch rows
#    (the same per-row hygiene as _MYINFO_COMMIT_FAIL / _RECOVER_TERMINAL).
# ---------------------------------------------------------------------------

def test_run_resets_flag_per_row():
    body = _func_body("run")
    assert "global _WE_PREFILL_UNCOMMITTABLE" in body, "run() must declare the flag global to reset it"
    # the reset assignment must appear in run() (per-run, before the step loop)
    assert re.search(r"_WE_PREFILL_UNCOMMITTABLE\s*=\s*None", body), "run() must reset the flag to None per row"


# ---------------------------------------------------------------------------
# 3. The DETECTION lives in populate_work_history (the prefill-guard), runs
#    AFTER the date-repair pass, only trips on FILLED (prefilled) blocks with an
#    empty required start MONTH, and EXCLUDES currently-work-here blocks (those
#    legitimately have no start... no -- they have no END; start is still
#    required, but the probe guards on the checkbox to avoid a false trip on the
#    end-date path). It must SET the module flag.
# ---------------------------------------------------------------------------

def test_detection_in_prefill_guard():
    body = _func_body("populate_work_history")
    assert "global _WE_PREFILL_UNCOMMITTABLE" in body, "populate_work_history must declare the flag global to set it"
    # probes the required start-date MONTH input for prefilled blocks
    assert "startDate-dateSectionMonth-input" in body, "detection must probe the required start-date month input"
    # only considers blocks that already have a jobTitle (i.e. PROFILE-PREFILLED), not empties
    assert "jobTitle" in body and "currentlyWorkHere" in body, (
        "detection must scope to prefilled jobTitle blocks and exclude currently-work-here"
    )
    # actually assigns the flag when uncommittable blocks are found
    assert re.search(r"_WE_PREFILL_UNCOMMITTABLE\s*=\s*\(?f?\"", body) or "_WE_PREFILL_UNCOMMITTABLE = (" in body, (
        "detection must SET _WE_PREFILL_UNCOMMITTABLE when uncommittable prefilled blocks are found"
    )


def test_detection_runs_after_date_repair():
    """The detector must come AFTER the guard date-repair (so a block we COULD repair is not
    falsely flagged). Enforce ordering by source position within populate_work_history."""
    body = _func_body("populate_work_history")
    repair_pos = body.find("date-repair (guard)")
    detect_pos = body.find("_WE_PREFILL_UNCOMMITTABLE =")
    assert repair_pos != -1, "expected the guard date-repair log marker"
    assert detect_pos != -1, "expected the uncommittable detection assignment"
    assert detect_pos > repair_pos, "uncommittable detection must run AFTER the date-repair pass"


# ---------------------------------------------------------------------------
# 4. The My-Experience step branch in run() FAST-FAILS with EXIT 9 when the flag
#    is set -- and does so BEFORE the generic loop-cap can fire. Mirrors the
#    existing _MYINFO_COMMIT_FAIL -> EXIT 8 pattern.
# ---------------------------------------------------------------------------

def test_step_loop_fast_fails_exit9():
    body = _func_body("run")
    # the check reads the flag and returns 9
    assert 'globals().get("_WE_PREFILL_UNCOMMITTABLE")' in body, (
        "My-Experience branch must read the flag via globals().get"
    )
    # find the guard block and assert it returns 9 with a precise bank reason
    idx = body.find('globals().get("_WE_PREFILL_UNCOMMITTABLE")')
    window = body[idx: idx + 400]
    assert "return 9" in window, "the uncommittable fast-fail must return EXIT 9"
    assert "workday-profile-prefill-uncommittable" in window, (
        "the fast-fail must log the 'workday-profile-prefill-uncommittable' bank reason"
    )


def test_fast_fail_is_before_generic_loopcap_in_my_experience():
    """Within the My-Experience branch, the EXIT-9 fast-fail must be evaluated as part of that
    branch (right after handle_experience), so it pre-empts the >revisit-cap EXIT 5. We assert
    the fast-fail sits AFTER the handle_experience() call and the EXIT-9 return is in the same
    branch."""
    body = _func_body("run")
    he = body.find("handle_experience(page, args.resume)")
    ff = body.find('globals().get("_WE_PREFILL_UNCOMMITTABLE")')
    assert he != -1 and ff != -1, "expected handle_experience call + fast-fail check in run()"
    assert ff > he, "fast-fail must be checked AFTER handle_experience populates/detects"
    # and it must be reasonably close (same branch), not paragraphs away in another step
    assert ff - he < 1500, "fast-fail check should be in the My-Experience branch right after handle_experience"


# ---------------------------------------------------------------------------
# 5. EXIT-9 must be a DISTINCT code (not colliding with existing semantic exits
#    2/3/4/5/6/7/8). Guards against a future edit reusing 9 for something else.
# ---------------------------------------------------------------------------

def test_exit9_is_distinct_and_only_for_uncommittable():
    body = _func_body("run")
    # every literal `return 9` in run() must be the uncommittable fast-fail
    for m in re.finditer(r"return 9\b", body):
        ctx = body[max(0, m.start() - 500): m.start()]
        assert "_WE_PREFILL_UNCOMMITTABLE" in ctx or "workday-profile-prefill-uncommittable" in ctx, (
            "every `return 9` in run() must be the profile-prefill-uncommittable fast-fail"
        )


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
