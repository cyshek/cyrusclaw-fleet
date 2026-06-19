"""Unit tests for adapters.rippling and jd_llm_classifier.fetch_jd_rippling.

Uses a captured Hammerspace listing & JD page fixture so no network is
required for the test suite.
"""
from __future__ import annotations

import json
import textwrap
from unittest.mock import patch

import pytest

from adapters import rippling as rip_adapter
from core import is_us_location, is_qualifying_title


# Minimal __NEXT_DATA__ fixtures — same schema as live Hammerspace.

LISTING_HTML = '''
<html><body><script id="__NEXT_DATA__" type="application/json">''' + json.dumps({
    "props": {"pageProps": {"dehydratedState": {"queries": [
        {"queryKey": ["board", "hammerspace", "job-posts", False, {}],
         "state": {"data": {"items": [
             {"id": "uuid-fde-1", "name": " Forward Deployed Engineer",
              "url": "https://ats.rippling.com/hammerspace/jobs/uuid-fde-1",
              "department": {"name": "Customer Success"},
              "locations": [{"name": "Remote (TX, US)", "country": "United States",
                             "countryCode": "US", "state": "TX", "city": None,
                             "workplaceType": "REMOTE"}]},
             {"id": "uuid-fde-uk", "name": "Forward Deployed Engineer - UK",
              "url": "https://ats.rippling.com/hammerspace/jobs/uuid-fde-uk",
              "department": {"name": "Customer Success"},
              "locations": [{"name": "Remote (United Kingdom)", "country": "United Kingdom",
                             "countryCode": "GB", "state": None, "city": None,
                             "workplaceType": "REMOTE"}]},
             {"id": "uuid-sales-ny", "name": "Regional Sales Director - New York",
              "url": "https://ats.rippling.com/hammerspace/jobs/uuid-sales-ny",
              "department": {"name": "Sales"},
              "locations": [{"name": "New York", "country": "United States",
                             "countryCode": "US", "state": "NY", "city": "",
                             "workplaceType": "REMOTE"}]},
         ]}}},
        {"queryKey": ["board", "hammerspace", "locations"],
         "state": {"data": {"items": []}}},
        {"queryKey": ["board", "hammerspace", "departments"],
         "state": {"data": {"items": []}}},
    ]}}}
}) + '''</script></body></html>'''

JD_HTML = '''
<html><body><script id="__NEXT_DATA__" type="application/json">''' + json.dumps({
    "props": {"pageProps": {"apiData": {
        "jobPost": {
            "uuid": "uuid-fde-1",
            "name": " Forward Deployed Engineer",
            "description": {
                "company": "<p>Hammerspace builds storage</p>",
                "role": "<p>About the role: 3 years of experience required.</p>",
                "responsibilities": "<ul><li>Embed with customer</li></ul>",
                "requirements": "<p>BS in CS, 3+ years experience</p>",
                "benefits": "<p>Full remote, great benefits</p>",
            },
        }}}}
}) + '''</script></body></html>'''


class FakeResp:
    def __init__(self, text, status=200):
        self.status_code = status
        self.text = text


def test_extract_next_data_ok():
    data = rip_adapter._extract_next_data(LISTING_HTML)
    assert "props" in data


def test_extract_next_data_missing():
    with pytest.raises(RuntimeError, match="no __NEXT_DATA__"):
        rip_adapter._extract_next_data("<html>no script</html>")


def test_fetch_listing_picks_job_posts_query():
    with patch.object(rip_adapter, "http_get", return_value=FakeResp(LISTING_HTML)):
        items = rip_adapter._fetch_listing("hammerspace")
    assert len(items) == 3
    assert items[0]["id"] == "uuid-fde-1"


def test_fetch_listing_http_error():
    with patch.object(rip_adapter, "http_get", return_value=FakeResp("nope", status=500)):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            rip_adapter._fetch_listing("hammerspace")


def test_format_location_us_remote():
    item = {"locations": [{"name": "Remote (TX, US)", "country": "United States",
                           "state": "TX", "city": None, "workplaceType": "REMOTE"}]}
    loc = rip_adapter._format_location(item)
    # Must include US so is_us_location() classifies correctly
    assert "United States" in loc or "US" in loc.upper()
    assert is_us_location(loc), loc


def test_format_location_uk_remote_is_not_us():
    item = {"locations": [{"name": "Remote (United Kingdom)", "country": "United Kingdom",
                           "state": None, "city": None, "workplaceType": "REMOTE"}]}
    loc = rip_adapter._format_location(item)
    assert not is_us_location(loc), loc


def test_format_location_multi():
    item = {"locations": [
        {"country": "United States", "state": "CA", "city": "SF", "workplaceType": "ONSITE"},
        {"country": "United States", "state": "NY", "city": "NYC", "workplaceType": "ONSITE"},
    ]}
    loc = rip_adapter._format_location(item)
    assert "SF" in loc and "NYC" in loc
    assert "|" in loc  # separator


def test_fetch_listing_to_roles_us_qualifying():
    """End-to-end discovery: parse listing, build Role objects, filter US+qualifying."""
    with patch.object(rip_adapter, "http_get", return_value=FakeResp(LISTING_HTML)):
        roles = rip_adapter.fetch("Hammerspace", "hammerspace")
    assert len(roles) == 3
    fde_roles = [r for r in roles if is_qualifying_title(r.title)]
    # 2 FDE roles (US + UK); both have qualifying title; only US is_us_location
    assert len(fde_roles) == 2
    us_fde = [r for r in fde_roles if is_us_location(r.location)]
    assert len(us_fde) == 1
    assert us_fde[0].raw["id"] == "uuid-fde-1"
    assert us_fde[0].source == "rippling"
    assert us_fde[0].raw["slug"] == "hammerspace"
    assert us_fde[0].url.endswith("uuid-fde-1")


def test_fetch_jd_text():
    with patch.object(rip_adapter, "http_get", return_value=FakeResp(JD_HTML)):
        title, body = rip_adapter._fetch_jd_text("hammerspace", "uuid-fde-1")
    assert title == "Forward Deployed Engineer"
    assert "Hammerspace builds storage" in body
    assert "About the role" in body
    assert "BS in CS" in body
    assert "Full remote" in body
    assert "<p>" not in body  # HTML stripped


def test_fetch_jd_text_404_returns_empty():
    with patch.object(rip_adapter, "http_get", return_value=FakeResp("not found", status=404)):
        title, body = rip_adapter._fetch_jd_text("hammerspace", "missing")
    assert title == "" and body == ""


def test_fetch_with_jd_pulls_yoe():
    """When fetch_jd=True, exp_required is parsed from JD body."""
    # First call: listing. Subsequent: JD pages.
    responses = [FakeResp(LISTING_HTML)] + [FakeResp(JD_HTML)] * 3
    with patch.object(rip_adapter, "http_get", side_effect=responses):
        roles = rip_adapter.fetch("Hammerspace", "hammerspace", fetch_jd=True)
    assert all(r.exp_required.startswith("exp:3") for r in roles)


# --- jd_llm_classifier integration -----------------------------------------

def test_classifier_routes_rippling():
    from jd_llm_classifier import detect_and_fetch, fetch_jd_rippling
    with patch("adapters.rippling.http_get", return_value=FakeResp(JD_HTML)):
        ats, txt = detect_and_fetch(
            "https://ats.rippling.com/hammerspace/jobs/uuid-fde-1"
        )
    assert ats == "rippling"
    assert "Forward Deployed Engineer" in txt
    assert "Hammerspace" in txt
