#!/usr/bin/env python3
"""Tests for debug_shots.prune_step_shots_on_success.
Run: role-discovery/.venv/bin/python -m pytest role-discovery/test_debug_shots.py -q
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from debug_shots import prune_step_shots_on_success  # noqa: E402


def _touch(d, name):
    p = d / name
    p.write_bytes(b"\x89PNG\r\n")  # tiny fake png
    return p


def test_success_prunes_steps_keeps_confirmation(tmp_path):
    _touch(tmp_path, "exfo-step-0.png")
    _touch(tmp_path, "exfo-step-1.png")
    conf = _touch(tmp_path, "exfo-05-confirmation.png")
    deleted, kept = prune_step_shots_on_success(str(tmp_path), "exfo", 0, success_codes=(0,))
    assert deleted == 2
    assert kept == 1
    assert conf.exists()              # evidence preserved
    assert not (tmp_path / "exfo-step-0.png").exists()


def test_failure_keeps_everything(tmp_path):
    _touch(tmp_path, "exfo-step-0.png")
    _touch(tmp_path, "exfo-step-1.png")
    _touch(tmp_path, "exfo-05-confirmation.png")
    deleted, kept = prune_step_shots_on_success(str(tmp_path), "exfo", 2, success_codes=(0,))
    assert deleted == 0               # nothing deleted on failure
    assert len(list(tmp_path.glob("*.png"))) == 3


def test_already_applied_code_7_prunes(tmp_path):
    _touch(tmp_path, "nvidia-step-0.png")
    _touch(tmp_path, "nvidia-step-1.png")
    deleted, kept = prune_step_shots_on_success(str(tmp_path), "nvidia", 7, success_codes=(0, 7))
    assert deleted == 2


def test_proof_and_submit_substrings_preserved(tmp_path):
    _touch(tmp_path, "t-step-0.png")
    _touch(tmp_path, "t-proof-archive.png")
    _touch(tmp_path, "t-filled-form-presubmit.png")  # contains 'submit'
    deleted, kept = prune_step_shots_on_success(str(tmp_path), "t", 0, success_codes=(0,))
    assert deleted == 1               # only the step shot
    assert kept == 2
    assert (tmp_path / "t-proof-archive.png").exists()
    assert (tmp_path / "t-filled-form-presubmit.png").exists()


def test_explicit_patterns_and_scoped_dir(tmp_path):
    # Tesla-style: per-row dir, names 00-../05-confirmation, no tenant prefix
    _touch(tmp_path, "00-landing.png")
    _touch(tmp_path, "01-form.png")
    _touch(tmp_path, "05-confirmation.png")
    deleted, kept = prune_step_shots_on_success(str(tmp_path), None, 0, success_codes=(0,))
    assert deleted == 2               # 00,01 gone
    assert (tmp_path / "05-confirmation.png").exists()


def test_missing_dir_is_safe(tmp_path):
    deleted, kept = prune_step_shots_on_success(str(tmp_path / "nope"), "x", 0)
    assert (deleted, kept) == (0, 0)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
