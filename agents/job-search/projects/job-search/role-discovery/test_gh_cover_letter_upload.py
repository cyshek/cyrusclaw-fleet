#!/usr/bin/env python3
"""Tests for the Greenhouse cover-letter-FILE upload path in _gh_submit.py.

Covers detect_cover_letter_input() and upload_cover_letter() WITHOUT a live
browser or LLM: a tiny FakePage stubs page.evaluate / page.query_selector so we
exercise the detect/skip/generate/upload branching logic deterministically.

Added 2026-06-02 (gh-coverletter): Forbes 1399 hard-blocked because a REQUIRED
Cover Letter was a FILE input (#cover_letter) with no text alternative and the
runner had no generate+upload path. This locks in the new helper's contract.

Run: python -m pytest role-discovery/test_gh_cover_letter_upload.py -q
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _gh_submit as gh  # noqa: E402


class FakePage:
    """Records page.evaluate calls and returns scripted results in order."""

    def __init__(self, evaluate_returns, query_selector_obj=None):
        self._returns = list(evaluate_returns)
        self._qs = query_selector_obj
        self.evaluate_calls = []
        self.query_selector_calls = []

    def evaluate(self, fn, *args):
        self.evaluate_calls.append((fn, args))
        if self._returns:
            return self._returns.pop(0)
        return None

    def query_selector(self, sel):
        self.query_selector_calls.append(sel)
        return self._qs


class FakeInput:
    def __init__(self):
        self.files = []

    def set_input_files(self, path, timeout=None):
        self.files.append(path)


# --------------------------------------------------------------------------- #
# detect_cover_letter_input
# --------------------------------------------------------------------------- #
def test_detect_returns_none_when_absent():
    page = FakePage([{"found": False}])
    assert gh.detect_cover_letter_input(page) is None


def test_detect_returns_info_when_present():
    page = FakePage([
        {"found": True, "selector": "#cover_letter", "id": "cover_letter",
         "name": "cover_letter", "already": False},
    ])
    det = gh.detect_cover_letter_input(page)
    assert det and det["selector"] == "#cover_letter"
    assert det["already"] is False


def test_detect_flags_already_committed():
    page = FakePage([
        {"found": True, "selector": None, "committedChip": True, "already": True},
    ])
    det = gh.detect_cover_letter_input(page)
    assert det and det["already"] is True


# --------------------------------------------------------------------------- #
# upload_cover_letter
# --------------------------------------------------------------------------- #
def test_upload_skips_when_no_cover_field():
    page = FakePage([{"found": False}])
    res = gh.upload_cover_letter(page, {"slug": "x"}, company="Acme", role="PM")
    assert res == {"present": False}


def test_upload_idempotent_when_already_uploaded():
    page = FakePage([
        {"found": True, "selector": "#cover_letter", "already": True},
    ])
    res = gh.upload_cover_letter(page, {"slug": "x"}, company="Acme", role="PM")
    assert res["present"] is True
    assert res["already_uploaded"] is True


def test_upload_generates_and_sets_files(monkeypatch, tmp_path):
    # detect -> present, not uploaded
    # then: files-check evaluate -> {files:1}, committed evaluate -> True
    page = FakePage(
        evaluate_returns=[
            {"found": True, "selector": "#cover_letter", "already": False},
            {"files": 1},   # files-in-input check
            True,           # filename committed in body
        ],
        query_selector_obj=FakeInput(),
    )

    fake_pdf = tmp_path / "cover.pdf"
    fake_pdf.write_bytes(b"%PDF-1.6 fake")

    import cover_letter_pdf as clp

    def fake_generate(**kwargs):
        assert kwargs["company"] == "Forbes"
        assert kwargs["role"] == "Product Manager"
        return {"pdf": str(fake_pdf), "docx": str(fake_pdf), "chars": 1500}

    monkeypatch.setattr(clp, "generate", fake_generate)

    res = gh.upload_cover_letter(
        page, {"slug": "forbes-x"}, company="Forbes", role="Product Manager")
    assert res["present"] is True
    assert res["uploaded"] is True
    assert res["filename_committed"] is True
    # the generated pdf was set_input_files'd onto the hidden input
    assert page._qs.files == [str(fake_pdf)]


def test_upload_reports_generate_failure(monkeypatch):
    page = FakePage([
        {"found": True, "selector": "#cover_letter", "already": False},
    ])
    import cover_letter_pdf as clp

    def boom(**kwargs):
        raise RuntimeError("model down")

    monkeypatch.setattr(clp, "generate", boom)
    res = gh.upload_cover_letter(page, {"slug": "x"}, company="Acme", role="PM")
    assert res["present"] is True
    assert "generate-failed" in res["err"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
