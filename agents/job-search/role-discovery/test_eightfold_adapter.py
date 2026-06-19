"""Tests for the reusable Eightfold PCSX jobs adapter (adapters/eightfold.py).

NO NETWORK: the Eightfold v2 jobs API is mocked by monkeypatching
core.http_get (which adapters.eightfold imports). Sample JSON below is a
trimmed capture from the live Netflix tenant (explore.jobs.netflix.net,
2026-06-08) so field shapes are real.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import core
import adapters.eightfold as ef


# --- Captured (trimmed) Eightfold position records -------------------------
# Real field shapes from explore.jobs.netflix.net/api/apply/v2/jobs.
_POS = [
    {
        "id": 790314756260,
        "name": "Group Product Manager, Payments Product Journey",
        "posting_name": "Group Product Manager, Payments Product Journey",
        "location": "Los Gatos,California,United States of America",
        "locations": [
            "Los Gatos,California,United States of America",
            "Los Angeles,California,United States of America",
        ],
        "department": "Product Management",
        "t_update": 1773100800,
        "t_create": 1773100800,
        "ats_job_id": "JR39395",
        "display_job_id": "JR39395",
        "canonicalPositionUrl": "https://explore.jobs.netflix.net/careers/job/790314756260",
        "work_location_option": "onsite",
    },
    {
        "id": 790316232735,
        "name": "Product Manager, Plans Innovation",
        "posting_name": "Product Manager, Plans Innovation",
        "location": "Los Gatos,California,United States of America",
        "locations": ["Los Gatos,California,United States of America"],
        "department": "Product Management",
        "t_update": 1780531200,
        "t_create": 1780531200,
        "ats_job_id": "JR41029",
        "display_job_id": "JR41029",
        "canonicalPositionUrl": "https://explore.jobs.netflix.net/careers/job/790316232735",
        "work_location_option": "onsite",
    },
    {
        "id": 790315245289,
        "name": "Support Solutions Engineer (L5), Graph Search",
        "location": "USA - Remote",
        "locations": ["USA - Remote"],
        "department": "Engineering",
        "t_update": 1779000000,
        "ats_job_id": "JR40555",
        "display_job_id": "JR40555",
        # No canonicalPositionUrl -> exercise the id fallback URL.
    },
    {
        # A non-US role that the US gate (run.py) must drop. Adapter still maps it.
        "id": 790399999999,
        "name": "Product Manager, Localization",
        "location": "Amsterdam,Netherlands",
        "locations": ["Amsterdam,Netherlands"],
        "department": "Product Management",
        "t_update": 1779500000,
        "ats_job_id": "JR40999",
        "display_job_id": "JR40999",
        "canonicalPositionUrl": "https://explore.jobs.netflix.net/careers/job/790399999999",
    },
]


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def _make_paginated_http_get(positions, count, page_size=10):
    """Return an http_get stand-in that paginates `positions` like Eightfold.

    Honors start/num params; returns `count` in every payload; returns an
    EMPTY positions list once start >= len(positions) (Eightfold actually
    repeats the trailing page, which the adapter's new_this_page==0 guard
    also handles, but empty is the simplest faithful stop signal).
    """
    calls = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=30):
        calls["n"] += 1
        start = int((params or {}).get("start", 0))
        page = positions[start:start + page_size]
        return _FakeResp({"positions": page, "count": count})

    return fake_get, calls


def test_pagination_walks_all_pages(monkeypatch):
    """Adapter must page through start=0,10,20... until a page is empty."""
    # 23 synthetic positions across 3 pages.
    many = []
    for i in range(23):
        many.append({
            "id": 1000 + i,
            "name": f"Product Manager {i}",
            "location": "Seattle,Washington,United States of America",
            "locations": ["Seattle,Washington,United States of America"],
            "ats_job_id": f"JR{i}",
            "display_job_id": f"JR{i}",
            "t_update": 1779000000,
            "canonicalPositionUrl": f"https://h/careers/job/{1000+i}",
        })
    fake_get, calls = _make_paginated_http_get(many, count=23)
    monkeypatch.setattr(ef, "http_get", fake_get)
    # Single search term so we can reason about page count deterministically.
    monkeypatch.setattr(ef, "SEARCH_TERMS", ["product manager"])

    roles = ef.fetch("Netflix", domain="netflix.com", host="explore.jobs.netflix.net")
    # All 23 unique positions returned (deduped by id).
    assert len(roles) == 23, f"expected 23 roles, got {len(roles)}"
    # start=0,10,20 yield data; start=30 is empty -> 4 fetches.
    assert calls["n"] == 4, f"expected 4 page fetches, got {calls['n']}"


def test_role_mapping_fields(monkeypatch):
    fake_get, _ = _make_paginated_http_get(_POS, count=len(_POS))
    monkeypatch.setattr(ef, "http_get", fake_get)
    monkeypatch.setattr(ef, "SEARCH_TERMS", ["product manager"])

    roles = ef.fetch("Netflix", domain="netflix.com", host="explore.jobs.netflix.net")
    by_title = {r.title: r for r in roles}

    gpm = by_title["Group Product Manager, Payments Product Journey"]
    assert gpm.company == "Netflix"
    assert gpm.source == "eightfold"
    assert gpm.exp_required == "exp:unstated"
    assert gpm.url == "https://explore.jobs.netflix.net/careers/job/790314756260"
    # multi-location joined + comma-normalized + "; " separated
    assert "Los Gatos, California, United States of America" in gpm.location
    assert "Los Angeles, California, United States of America" in gpm.location
    assert "; " in gpm.location
    # posted_at derived from t_update (UTC date)
    assert gpm.posted_at == "2026-03-10", gpm.posted_at
    assert gpm.raw["display_job_id"] == "JR39395"
    assert gpm.raw["eightfold_host"] == "explore.jobs.netflix.net"


def test_url_id_fallback_when_no_canonical(monkeypatch):
    fake_get, _ = _make_paginated_http_get(_POS, count=len(_POS))
    monkeypatch.setattr(ef, "http_get", fake_get)
    monkeypatch.setattr(ef, "SEARCH_TERMS", ["product manager"])
    roles = ef.fetch("Netflix", domain="netflix.com", host="explore.jobs.netflix.net")
    sse = next(r for r in roles if r.title.startswith("Support Solutions Engineer"))
    # No canonicalPositionUrl in fixture -> built from host + id.
    assert sse.url == "https://explore.jobs.netflix.net/careers/job/790315245289"


def test_us_and_nonus_locations_pass_through(monkeypatch):
    """Adapter maps BOTH US and non-US roles; gating is run.py's job.

    But we assert the mapped location strings are exactly what core.is_us_location
    needs to make the right call downstream.
    """
    fake_get, _ = _make_paginated_http_get(_POS, count=len(_POS))
    monkeypatch.setattr(ef, "http_get", fake_get)
    monkeypatch.setattr(ef, "SEARCH_TERMS", ["product manager"])
    roles = ef.fetch("Netflix", domain="netflix.com", host="explore.jobs.netflix.net")

    us = next(r for r in roles if r.title == "Product Manager, Plans Innovation")
    assert core.is_us_location(us.location) is True

    remote_us = next(r for r in roles if r.title.startswith("Support Solutions Engineer"))
    # "USA - Remote" is normalized to "United States - Remote" so the gate passes.
    assert remote_us.location == "United States - Remote"
    assert core.is_us_location(remote_us.location) is True

    nonus = next(r for r in roles if r.title == "Product Manager, Localization")
    assert core.is_us_location(nonus.location) is False


def test_empty_positions_resilience(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=30):
        return _FakeResp({"positions": [], "count": 0})
    monkeypatch.setattr(ef, "http_get", fake_get)
    monkeypatch.setattr(ef, "SEARCH_TERMS", ["product manager"])
    roles = ef.fetch("Netflix", domain="netflix.com", host="explore.jobs.netflix.net")
    assert roles == []


def test_http_error_does_not_crash_other_terms(monkeypatch):
    """A non-200 on one term must be swallowed; other terms still produce rows."""
    def fake_get(url, headers=None, params=None, timeout=30):
        term = (params or {}).get("query", "")
        if term == "product manager":
            return _FakeResp({}, status=500)  # this term errors out
        start = int((params or {}).get("start", 0))
        if start > 0:
            return _FakeResp({"positions": [], "count": 1})
        return _FakeResp({
            "count": 1,
            "positions": [{
                "id": 555,
                "name": "Solutions Engineer, Partner",
                "location": "Austin,Texas,United States of America",
                "locations": ["Austin,Texas,United States of America"],
                "ats_job_id": "JR555",
                "display_job_id": "JR555",
                "t_update": 1779000000,
                "canonicalPositionUrl": "https://h/careers/job/555",
            }],
        })
    monkeypatch.setattr(ef, "http_get", fake_get)
    monkeypatch.setattr(ef, "SEARCH_TERMS", ["product manager", "solutions engineer"])
    roles = ef.fetch("Netflix", domain="netflix.com", host="explore.jobs.netflix.net")
    titles = [r.title for r in roles]
    assert "Solutions Engineer, Partner" in titles
    assert len(roles) == 1


def test_requires_host(monkeypatch):
    def fake_get(*a, **k):
        raise AssertionError("should not fetch without a host")
    monkeypatch.setattr(ef, "http_get", fake_get)
    try:
        ef.fetch("SomeCo")  # no host, no slug
        assert False, "expected RuntimeError for missing host"
    except RuntimeError as e:
        assert "host" in str(e).lower()


def test_slug_backstop_domain_host(monkeypatch):
    """slug='domain|host' should populate domain+host when opts omit them."""
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=30):
        captured["url"] = url
        captured["domain"] = (params or {}).get("domain")
        return _FakeResp({"positions": [], "count": 0})

    monkeypatch.setattr(ef, "http_get", fake_get)
    monkeypatch.setattr(ef, "SEARCH_TERMS", ["product manager"])
    ef.fetch("Netflix", slug="netflix.com|explore.jobs.netflix.net")
    assert captured["url"] == "https://explore.jobs.netflix.net/api/apply/v2/jobs"
    assert captured["domain"] == "netflix.com"


def test_usa_remote_normalized_for_gate(monkeypatch):
    """Eightfold 'USA - Remote' must normalize so core.is_us_location passes.

    Regression guard: core's US markers don't match a bare leading 'USA'
    (they want ' usa' / '(usa)'), so Netflix-style 'USA - Remote' roles would
    be silently dropped by the run.py US gate without this adapter-side fix.
    """
    pos = [{
        "id": 42,
        "name": "Solutions Engineer, Remote",
        "location": "USA - Remote",
        "locations": ["USA - Remote"],
        "ats_job_id": "JR42",
        "display_job_id": "JR42",
        "t_update": 1779000000,
        "canonicalPositionUrl": "https://h/careers/job/42",
    }]
    fake_get, _ = _make_paginated_http_get(pos, count=1)
    monkeypatch.setattr(ef, "http_get", fake_get)
    monkeypatch.setattr(ef, "SEARCH_TERMS", ["solutions engineer"])
    roles = ef.fetch("Netflix", domain="netflix.com", host="explore.jobs.netflix.net")
    assert len(roles) == 1
    assert roles[0].location == "United States - Remote"
    assert core.is_us_location(roles[0].location) is True


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
