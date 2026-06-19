"""Tests for the Rippling dispatch wiring in inline_submit.py.

These cover the cheap, pure-Python pieces: URL detection, URL parsing, and
the inline_submit --ats CLI choice. The full prep pipeline
(prep_role_rippling) requires DB + network and is exercised end-to-end by
the rippling-adapter chain smoke test (applications/_rippling-smoke-2026-05-30.json).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import inline_submit as ins  # noqa: E402


# ---------------------------------------------------------------------------
# detect_ats
# ---------------------------------------------------------------------------

def test_detect_ats_rippling_canonical():
    url = "https://ats.rippling.com/hammerspace/jobs/2c09a9fe-fedd-472a-9198-f2f6001934bc"
    assert ins.detect_ats(url) == "rippling"


def test_detect_ats_rippling_short_id():
    # Some Rippling boards (esp. older or non-UUID jids) use shorter ids.
    # The regex requires >= 6 chars; verify a plausible shape resolves.
    url = "https://ats.rippling.com/exampletenant/jobs/abc1234"
    assert ins.detect_ats(url) == "rippling"


def test_detect_ats_rippling_trailing_path_ignored():
    url = "https://ats.rippling.com/hammerspace/jobs/2c09a9fe-fedd-472a-9198-f2f6001934bc/apply?utm_source=test"
    assert ins.detect_ats(url) == "rippling"


def test_detect_ats_non_rippling_unchanged():
    # Don't regress on the other ATSes after wiring.
    assert ins.detect_ats("https://job-boards.greenhouse.io/acme/jobs/12345") == "greenhouse"
    assert ins.detect_ats(
        "https://jobs.ashbyhq.com/cursor/abc12345-1234-1234-1234-abcdef012345"
    ) == "ashby"
    assert ins.detect_ats("https://jobs.lever.co/acme/abcdef12-3456-7890-abcd-ef1234567890") == "lever"
    assert ins.detect_ats("https://example.com/about") == "unknown"


def test_detect_ats_rippling_root_not_a_match():
    # /jobs index page (no UUID) is the board listing, not a single job.
    assert ins.detect_ats("https://ats.rippling.com/hammerspace/jobs") != "rippling"


# ---------------------------------------------------------------------------
# parse_rippling_url
# ---------------------------------------------------------------------------

def test_parse_rippling_url_basic():
    url = "https://ats.rippling.com/hammerspace/jobs/2c09a9fe-fedd-472a-9198-f2f6001934bc"
    out = ins.parse_rippling_url(url)
    assert out == ("hammerspace", "2c09a9fe-fedd-472a-9198-f2f6001934bc")


def test_parse_rippling_url_with_query():
    url = "https://ats.rippling.com/example-co/jobs/abc1234?utm_source=x"
    out = ins.parse_rippling_url(url)
    assert out == ("example-co", "abc1234")


def test_parse_rippling_url_none_for_garbage():
    assert ins.parse_rippling_url("") is None
    assert ins.parse_rippling_url("https://example.com") is None
    assert ins.parse_rippling_url("https://ats.rippling.com/x/jobs/") is None  # no jid
    # Too-short jid (< 6 chars).
    assert ins.parse_rippling_url("https://ats.rippling.com/x/jobs/abc") is None


# ---------------------------------------------------------------------------
# write_jd_files_rippling (pure file write — no network).
# ---------------------------------------------------------------------------

def test_write_jd_files_rippling_basic(tmp_path):
    role = {
        "role_id": 999,
        "company": "Hammerspace",
        "role": "FDE",
        "loc": "Remote (US)",
        "exp_req": 3,
        "url": "https://ats.rippling.com/hammerspace/jobs/2c09a9fe-fedd-472a-9198-f2f6001934bc",
        "ats": "rippling",
        "rp_slug": "hammerspace",
        "rp_jid": "2c09a9fe-fedd-472a-9198-f2f6001934bc",
        "flags": "",
    }
    apply_url = ins.write_jd_files_rippling(tmp_path, role, "Forward-Deployed Engineer", "JD body. " * 50)
    assert apply_url.endswith("/jobs/2c09a9fe-fedd-472a-9198-f2f6001934bc")
    jd = (tmp_path / "JD.md").read_text()
    assert "Forward-Deployed Engineer" in jd
    assert "Hammerspace" in jd
    assert "hammerspace" in jd  # board slug printed
    import json
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["ats"] == "rippling"
    assert meta["rp_slug"] == "hammerspace"
    assert meta["rp_jid"] == "2c09a9fe-fedd-472a-9198-f2f6001934bc"
    assert meta["gh_org"] == "rippling-hammerspace"
    assert meta["gh_jid"] == "2c09a9fe"
    assert meta["apply_url"].startswith("https://ats.rippling.com/")


def test_write_jd_files_rippling_falls_back_to_role_title(tmp_path):
    role = {
        "role_id": 1,
        "company": "Hammerspace",
        "role": "FDE",
        "loc": None,
        "exp_req": None,
        "url": "https://ats.rippling.com/hammerspace/jobs/abc1234",
        "ats": "rippling",
        "rp_slug": "hammerspace",
        "rp_jid": "abc1234",
        "flags": "",
    }
    ins.write_jd_files_rippling(tmp_path, role, "", "body")
    jd = (tmp_path / "JD.md").read_text()
    # Empty title falls back to role.role.
    assert "FDE" in jd
