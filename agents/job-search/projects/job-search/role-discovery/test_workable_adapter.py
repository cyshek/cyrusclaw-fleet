"""Unit tests for the Workable discovery adapter (offline, no live HTTP)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import workable  # noqa: E402


def test_location_uses_locations_array_and_remote_flag():
    j = {"telecommuting": True,
         "locations": [{"city": "Boston", "region": "Massachusetts", "country": "United States"}]}
    loc = workable._location(j)
    assert "Boston" in loc and "Massachusetts" in loc and "United States" in loc
    assert "Remote" in loc


def test_location_falls_back_to_flat_city_state():
    j = {"telecommuting": False, "city": "Orlando", "state": "Florida", "country": "United States"}
    loc = workable._location(j)
    assert loc == "Orlando, Florida, United States"
    assert "Remote" not in loc


def test_location_remote_only_when_no_city():
    assert workable._location({"telecommuting": True}) == "Remote"


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status
    def json(self):
        return self._p


def test_fetch_maps_application_url_and_source(monkeypatch):
    payload = {"name": "Acme", "jobs": [
        {"title": "Product Manager", "shortcode": "ABC123", "code": "42",
         "application_url": "https://apply.workable.com/j/ABC123/apply",
         "published_on": "2026-06-01", "telecommuting": True,
         "city": "Boston", "state": "Massachusetts", "country": "United States",
         "experience": "Mid-level", "function": "Product Management",
         "description": "We want 3 years of experience."},
    ]}
    monkeypatch.setattr(workable, "http_get", lambda *a, **k: _Resp(payload))
    roles = workable.fetch("Acme", "acme")
    assert len(roles) == 1
    r = roles[0]
    assert r.title == "Product Manager"
    assert r.url == "https://apply.workable.com/j/ABC123/apply"
    assert r.source == "workable"
    assert r.posted_at == "2026-06-01"
    assert r.raw["shortcode"] == "ABC123"


def test_fetch_raises_on_non_200(monkeypatch):
    monkeypatch.setattr(workable, "http_get", lambda *a, **k: _Resp({}, status=404))
    try:
        workable.fetch("Acme", "acme")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "404" in str(e)


def test_fetch_empty_jobs_returns_empty(monkeypatch):
    monkeypatch.setattr(workable, "http_get", lambda *a, **k: _Resp({"name": "X", "jobs": []}))
    assert workable.fetch("X", "x") == []
