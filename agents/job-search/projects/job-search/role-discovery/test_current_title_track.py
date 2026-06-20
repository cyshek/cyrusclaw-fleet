#!/usr/bin/env python3
"""Regression: form 'current title' answer must TRACK-MATCH the role applied to
(Cyrus 2026-06-02), mirroring the resume headline fix (coerce_title_track). A PM role
must not claim 'Technical Program Manager'; a non-PM-family role (SE/FDE) keeps the
static profile title (no PM inflation).

Run: role-discovery/.venv/bin/python -m pytest role-discovery/test_current_title_track.py -q
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from tailor_resume import resolve_headline_title, detect_family  # noqa: E402


def _current_title_for(target_title: str, static="Technical Program Manager"):
    """Replicate the injection logic used in greenhouse_dryrun/ashby_dryrun build_dryrun."""
    if not target_title:
        return static
    m = resolve_headline_title(target_title, detect_family(target_title))
    return m if m else static


def test_pm_role_does_not_claim_tpm():
    # the Chime case that Cyrus flagged
    assert _current_title_for("Product Manager, Data Platform") == "Product Manager"


def test_senior_pm_resolves_to_product_manager():
    assert _current_title_for("Senior Product Manager") == "Product Manager"


def test_program_manager_role():
    assert _current_title_for("Program Manager II") == "Program Manager"


def test_tpm_role_keeps_tpm():
    assert _current_title_for("Technical Program Manager") == "Technical Program Manager"


def test_tpm_product_variant():
    assert _current_title_for("Technical Product Manager") == "Technical Product Manager"


def test_non_pm_family_keeps_static_no_inflation():
    # SE/FDE: resolver returns None -> we keep the static profile title, never claim PM
    assert _current_title_for("Solutions Engineer") == "Technical Program Manager"
    assert _current_title_for("Forward Deployed Engineer") == "Technical Program Manager"


def test_empty_title_keeps_static():
    assert _current_title_for("") == "Technical Program Manager"


def test_greenhouse_dryrun_imports_and_wires():
    # the injection code path must be present in both ATS dryrun modules
    gh = (HERE / "greenhouse_dryrun.py").read_text()
    ab = (HERE / "ashby_dryrun.py").read_text()
    for src in (gh, ab):
        assert "resolve_headline_title" in src
        assert 'es["current_title"] = _matched' in src


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
