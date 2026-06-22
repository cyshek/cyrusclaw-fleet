#!/usr/bin/env python3
"""Tests for cover_letter_pdf.py — pure-function coverage (no LLM/soffice calls).
Run: python -m pytest role-discovery/test_cover_letter_pdf.py -q
"""
import sys
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_PI_REAL = json.loads((HERE.parent / "personal-info.json").read_text())
_FULL_NAME = _PI_REAL["identity"]["first_name"] + " " + _PI_REAL["identity"]["last_name"]

import cover_letter_pdf as clp  # noqa: E402


def test_sanitize_strips_salutation_and_signoff():
    raw = ("Dear Forbes Hiring Team,\n"
           "I am excited about this role.\n\n"
           "My experience fits well.\n\n"
           f"Sincerely,\n{_FULL_NAME}")
    out = clp.sanitize_body(raw)
    assert "Dear Forbes" not in out
    assert "Sincerely" not in out
    assert "excited about this role" in out


def test_sanitize_enforces_max_chars():
    big = ("para one. " * 400) + "\n\n" + ("para two. " * 400)
    out = clp.sanitize_body(big)
    assert len(out) <= clp.MAX_BODY_CHARS


def test_validate_flags_ai_leak():
    body = "I built systems. As an AI language model, I can help. " * 5
    errs = clp.validate(body)
    assert any("AI-disclosure" in e for e in errs)


def test_validate_flags_placeholder_bracket():
    body = "I am thrilled to apply to [Company] for the role. " * 6
    errs = clp.validate(body)
    assert any("placeholder" in e for e in errs)


def test_validate_flags_too_short():
    assert any("short" in e for e in clp.validate("tiny"))


def test_validate_passes_clean_body():
    body = ("I am a Technical Program Manager at Microsoft with a track record "
            "of shipping platform features that move real metrics. "
            "I would bring that same operating rigor to this team. "
            "My background in computer science and data structures maps "
            "directly to the technical depth this role requires.")
    assert clp.validate(body) == []


def test_build_prompt_contains_truthfulness_rules():
    p = clp.build_prompt("Forbes", "Product Manager", "JD text", "RESUME text",
                         {"identity": {"full_name": _FULL_NAME}})
    assert "truthful" in p.lower()
    assert "Forbes" in p
    assert "Product Manager" in p
    assert "never mention ai" in p.lower()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
