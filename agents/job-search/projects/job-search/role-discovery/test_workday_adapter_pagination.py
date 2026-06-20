"""Pagination regression tests for the Workday discovery adapter
(adapters/workday.py). Offline — mocks http_post_json, no live HTTP.

Bug fixed 2026-06-08: some Workday tenants (Salesforce wd12) report the real
`total` ONLY on the first page (offset=0) and return total=0 on every page
after. The old loop read `total` fresh each page, so on page 2
`offset(40) >= total(0)` tripped and pagination stopped at 40 jobs/term —
Salesforce was capped to ~1 kept role despite a 376-job board. The fix locks
the total from the first non-trivial page and continues until a short/empty
page (or the locked total) is reached.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import workday as wd  # noqa: E402


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def _make_sf_quirk_poster(total_jobs, page_size=20, total_only_first_page=True):
    """Return an http_post_json stand-in that paginates `total_jobs` jobs.

    Mimics the Salesforce quirk: `total` is the real count on offset=0 and
    0 on every subsequent page (when total_only_first_page=True).
    """
    def fake_post(url, body, headers=None, timeout=30):
        offset = int(body.get("offset", 0))
        n = max(0, min(page_size, total_jobs - offset))
        jobs = [
            {"title": f"Product Manager {offset + i}",
             "locationsText": "California - San Francisco",
             "externalPath": f"/job/JR{offset + i}",
             "postedOn": "Posted Today"}
            for i in range(n)
        ]
        if total_only_first_page:
            total = total_jobs if offset == 0 else 0
        else:
            total = total_jobs
        return _Resp({"jobPostings": jobs, "total": total})

    return fake_post


def test_pagination_survives_total_zero_after_first_page(monkeypatch):
    """The SF quirk must NOT cap the crawl at 40; it should fetch all 376."""
    monkeypatch.setattr(wd, "http_post_json",
                        _make_sf_quirk_poster(376, total_only_first_page=True))
    jobs = wd._fetch_one("h", "salesforce", "External_Career_Site",
                         "product manager", page_size=20)
    assert len(jobs) == 376, f"expected 376 jobs, got {len(jobs)} (capped early?)"


def test_pagination_well_behaved_total(monkeypatch):
    """When total is reported correctly on every page, still fetch all."""
    monkeypatch.setattr(wd, "http_post_json",
                        _make_sf_quirk_poster(95, total_only_first_page=False))
    jobs = wd._fetch_one("h", "t", "s", "program manager", page_size=20)
    assert len(jobs) == 95


def test_pagination_stops_on_short_page(monkeypatch):
    """A short final page (< page_size) terminates the loop cleanly."""
    # 50 jobs / 20 page_size -> pages of 20,20,10 (short -> stop).
    calls = {"n": 0}

    def fake_post(url, body, headers=None, timeout=30):
        calls["n"] += 1
        offset = int(body.get("offset", 0))
        n = max(0, min(20, 50 - offset))
        jobs = [{"title": f"PM {offset+i}", "externalPath": f"/j/{offset+i}",
                 "locationsText": "TX", "postedOn": ""} for i in range(n)]
        # total=0 always -> exercises the short-page stop, not the total stop.
        return _Resp({"jobPostings": jobs, "total": 0})

    monkeypatch.setattr(wd, "http_post_json", fake_post)
    jobs = wd._fetch_one("h", "t", "s", "x", page_size=20)
    assert len(jobs) == 50
    # 3 fetches: 20, 20, 10(short->stop). No infinite loop.
    assert calls["n"] == 3, f"expected 3 page fetches, got {calls['n']}"


def test_pagination_empty_board(monkeypatch):
    def fake_post(url, body, headers=None, timeout=30):
        return _Resp({"jobPostings": [], "total": 0})
    monkeypatch.setattr(wd, "http_post_json", fake_post)
    assert wd._fetch_one("h", "t", "s", "x") == []


def test_fetch_dedupes_across_terms_and_maps_role(monkeypatch):
    """End-to-end fetch(): dedup by externalPath, map Role fields."""
    def fake_post(url, body, headers=None, timeout=30):
        offset = int(body.get("offset", 0))
        # Each term returns the SAME single job at offset 0 -> dedup to 1 role.
        if offset == 0:
            return _Resp({"jobPostings": [{
                "title": "Solutions Engineer",
                "locationsText": "California - San Francisco",
                "externalPath": "/job/JR-SHARED",
                "postedOn": "2026-06-01",
            }], "total": 1})
        return _Resp({"jobPostings": [], "total": 0})

    monkeypatch.setattr(wd, "http_post_json", fake_post)
    roles = wd.fetch("Salesforce", "", host="h", tenant="salesforce",
                     site="External_Career_Site")
    assert len(roles) == 1
    r = roles[0]
    assert r.company == "Salesforce"
    assert r.title == "Solutions Engineer"
    assert r.source == "workday"
    assert r.url == "https://h/External_Career_Site/job/JR-SHARED"
    assert r.raw["externalPath"] == "/job/JR-SHARED"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
