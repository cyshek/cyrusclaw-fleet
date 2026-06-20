"""Tests for the LinkedIn offsite-ATS extractor (no live calls — fixtures only)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import linkedin_ats_resolver_v2 as v2

FIX = HERE / "test_fixtures"


def test_extract_offsite_from_ats_html():
    html = (FIX / "li_guest_with_ats.html").read_text()
    res = v2.extract_offsite_ats_from_li_html(html)
    assert res is not None, "should extract an ATS link"
    kind, url = res
    assert kind in ("greenhouse", "ashby")
    assert "linkedin.com" not in url
    assert url.startswith("https://")


def test_signwall_returns_none():
    # the realistic anonymous LinkedIn response: only a cold-join/signup decoy
    html = (FIX / "li_guest_signwall.html").read_text()
    res = v2.extract_offsite_ats_from_li_html(html)
    assert res is None, "sign-in-wall HTML must NOT yield a (decoy) linkedin.com URL"


def test_empty_html_returns_none():
    assert v2.extract_offsite_ats_from_li_html("") is None
    assert v2.extract_offsite_ats_from_li_html(None) is None


def test_decoy_linkedin_link_filtered():
    html = '<a href="https://www.linkedin.com/signup/cold-join?trk=public_jobs_apply-link-offsite">x</a>'
    assert v2.extract_offsite_ats_from_li_html(html) is None


def test_greenhouse_preferred_when_present():
    html = '<a href="https://boards.greenhouse.io/foo/jobs/9">a</a>'
    kind, url = v2.extract_offsite_ats_from_li_html(html)
    assert kind == "greenhouse"
    assert "greenhouse.io/foo/jobs/9" in url


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
