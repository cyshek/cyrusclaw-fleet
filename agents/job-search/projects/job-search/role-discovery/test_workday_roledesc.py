#!/usr/bin/env python3
"""Regression test for the Workday roleDescription fix (EXFO 2121 churn-loop).
Pure-logic coverage of _wd_sanitize_desc + presence/wiring of the sweep.
Run: role-discovery/.venv/bin/python -m pytest role-discovery/test_workday_roledesc.py -q
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# import without executing run(): the module only does light top-level work.
import _workday_runner as wd  # noqa: E402


def test_sanitize_strips_workday_illegal_chars():
    raw = 'Scaled <Azure> [recovery] "platform" {system} back\\slash'
    out = wd._wd_sanitize_desc(raw)
    for bad in '<>[]"{}\\':
        assert bad not in out
    assert "Scaled Azure recovery platform system backslash" in out


def test_sanitize_handles_none_and_empty():
    assert wd._wd_sanitize_desc(None) == ""
    assert wd._wd_sanitize_desc("") == ""
    assert wd._wd_sanitize_desc("   ") == ""


def test_work_history_entries_all_have_desc():
    # the sweep relies on every WORK_HISTORY job carrying a non-empty desc
    assert wd.WORK_HISTORY
    for j in wd.WORK_HISTORY:
        assert j.get("desc"), f"missing desc: {j.get('company')}"
        # sanitized desc must remain non-trivial
        assert len(wd._wd_sanitize_desc(j["desc"])) > 20


def test_sweep_is_called_at_end_of_populate():
    src = (HERE / "_workday_runner.py").read_text()
    # the sweep call must appear inside populate_work_history, before handle_experience
    pop = src.index("def populate_work_history")
    he = src.index("def handle_experience")
    assert "_sweep_role_descriptions(page)" in src[pop:he], "sweep not called in populate_work_history"


def test_sweep_helper_defined():
    assert hasattr(wd, "_sweep_role_descriptions")
    assert hasattr(wd, "_wd_sanitize_desc")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
