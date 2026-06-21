"""Tests for adapters/himalayas.py — all offline (no network).

Covers:
  - Full-time filter (exclude intern/contractor/part-time)
  - US/Worldwide location filter
  - Pagination logic (mock totalCount=25, two pages)
  - source_key format via tracker_merger
  - Role field mapping (company, title, location, url, posted_at, source)
  - Empty response handling

Run: cd projects/job-search/role-discovery && .venv/bin/python -m pytest test_himalayas_adapter.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import date

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from adapters.himalayas import (
    fetch,
    _is_us_accessible,
    _is_full_time,
    _parse_pub_date,
)
import tracker_merger


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_job(**kwargs):
    """Build a minimal valid job dict (Full Time, US-accessible, sensible defaults)."""
    defaults = {
        "title": "Product Manager",
        "companyName": "Acme Corp",
        "employmentType": "Full Time",
        "locationRestrictions": [],
        "applicationLink": "https://himalayas.app/companies/acme/jobs/pm",
        "guid": "https://himalayas.app/companies/acme/jobs/pm",
        "pubDate": 1750000000,
        "description": "<p>3+ years of experience required.</p>",
        "categories": ["Product-Management"],
    }
    defaults.update(kwargs)
    return defaults


def _mock_response(jobs, total_count=None):
    """Build a mock requests.Response for a single API page."""
    if total_count is None:
        total_count = len(jobs)
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"totalCount": total_count, "jobs": jobs}
    return r


# ── unit tests: filters ────────────────────────────────────────────────────────

class TestIsUsAccessible:
    def test_empty_restrictions_is_worldwide(self):
        assert _is_us_accessible([]) is True

    def test_none_restrictions_is_worldwide(self):
        assert _is_us_accessible(None) is True

    def test_united_states_accepted(self):
        assert _is_us_accessible(["United States"]) is True

    def test_worldwide_accepted(self):
        assert _is_us_accessible(["Worldwide"]) is True

    def test_mixed_with_us_accepted(self):
        assert _is_us_accessible(["Canada", "United States", "Germany"]) is True

    def test_non_us_only_rejected(self):
        assert _is_us_accessible(["Germany", "United Kingdom"]) is False

    def test_canada_only_rejected(self):
        assert _is_us_accessible(["Canada"]) is False


class TestIsFullTime:
    def test_full_time_accepted(self):
        assert _is_full_time("Full Time") is True

    def test_full_time_hyphen(self):
        assert _is_full_time("Full-Time") is True

    def test_intern_rejected(self):
        assert _is_full_time("Intern") is False

    def test_part_time_rejected(self):
        assert _is_full_time("Part Time") is False

    def test_contractor_rejected(self):
        assert _is_full_time("Contractor") is False

    def test_none_passes_through(self):
        # Unknown type should not filter
        assert _is_full_time(None) is True

    def test_empty_passes_through(self):
        assert _is_full_time("") is True


class TestParsePubDate:
    def test_unix_timestamp(self):
        # 1750000000 → 2025-06-15
        result = _parse_pub_date(1750000000)
        assert len(result) == 10
        assert result.startswith("202")

    def test_string_date_truncated(self):
        assert _parse_pub_date("2025-06-20T12:00:00Z") == "2025-06-20"

    def test_none_returns_empty(self):
        assert _parse_pub_date(None) == ""

    def test_zero_returns_empty_or_epoch(self):
        # 0 is a valid but ancient timestamp; just ensure no crash
        result = _parse_pub_date(0)
        assert isinstance(result, str)


# ── integration tests: fetch() with mocked HTTP ────────────────────────────────

class TestFetchFiltering:
    def test_full_time_filter_excludes_intern(self):
        """Intern roles should be excluded by the full-time filter."""
        jobs = [
            _make_job(title="PM Intern", employmentType="Intern",
                      applicationLink="https://himalayas.app/companies/acme/jobs/pm-intern",
                      guid="https://himalayas.app/companies/acme/jobs/pm-intern"),
            _make_job(title="Product Manager", employmentType="Full Time"),
        ]
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response(jobs)
            roles = fetch("Himalayas (PM)", "product manager")

        assert len(roles) == 1
        assert roles[0].title == "Product Manager"

    def test_full_time_filter_excludes_contractor(self):
        """Contractor roles should be excluded."""
        jobs = [
            _make_job(title="PM Contractor", employmentType="Contractor",
                      applicationLink="https://himalayas.app/companies/acme/jobs/pm-c",
                      guid="https://himalayas.app/companies/acme/jobs/pm-c"),
        ]
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response(jobs)
            roles = fetch("Himalayas (PM)", "product manager")

        assert len(roles) == 0

    def test_location_filter_excludes_non_us(self):
        """Roles restricted to non-US locations should be excluded."""
        jobs = [
            _make_job(
                title="Product Manager",
                locationRestrictions=["Germany", "United Kingdom"],
                applicationLink="https://himalayas.app/companies/acme/jobs/pm-eu",
                guid="https://himalayas.app/companies/acme/jobs/pm-eu",
            ),
        ]
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response(jobs)
            roles = fetch("Himalayas (PM)", "product manager")

        assert len(roles) == 0

    def test_location_filter_keeps_worldwide(self):
        """Worldwide roles should be included."""
        jobs = [
            _make_job(locationRestrictions=["Worldwide"]),
        ]
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response(jobs)
            roles = fetch("Himalayas (PM)", "product manager")

        assert len(roles) == 1

    def test_location_filter_keeps_empty_restriction(self):
        """Empty locationRestrictions = no restriction = worldwide = keep."""
        jobs = [_make_job(locationRestrictions=[])]
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response(jobs)
            roles = fetch("Himalayas (PM)", "product manager")

        assert len(roles) == 1


class TestFetchPagination:
    def test_pagination_fetches_all_pages(self):
        """With totalCount=25 and page_size=20, should make 2 HTTP calls."""
        page1_jobs = [_make_job(
            title=f"PM {i}",
            applicationLink=f"https://himalayas.app/companies/co/jobs/pm-{i}",
            guid=f"https://himalayas.app/companies/co/jobs/pm-{i}",
        ) for i in range(20)]

        page2_jobs = [_make_job(
            title=f"PM {i+20}",
            applicationLink=f"https://himalayas.app/companies/co/jobs/pm-{i+20}",
            guid=f"https://himalayas.app/companies/co/jobs/pm-{i+20}",
        ) for i in range(5)]

        def side_effect(url, params=None):
            offset = (params or {}).get("offset", 0)
            if offset == 0:
                return _mock_response(page1_jobs, total_count=25)
            else:
                return _mock_response(page2_jobs, total_count=25)

        with patch("adapters.himalayas.http_get", side_effect=side_effect) as mock_get:
            with patch("adapters.himalayas.time.sleep"):  # don't actually sleep
                roles = fetch("Himalayas (PM)", "product manager")

        assert mock_get.call_count == 2
        assert len(roles) == 25

    def test_pagination_stops_on_empty_page(self):
        """Should stop pagination if an empty jobs list is returned before totalCount."""
        page1_jobs = [_make_job(
            applicationLink=f"https://himalayas.app/companies/co/jobs/pm-{i}",
            guid=f"https://himalayas.app/companies/co/jobs/pm-{i}",
        ) for i in range(20)]

        def side_effect(url, params=None):
            offset = (params or {}).get("offset", 0)
            if offset == 0:
                return _mock_response(page1_jobs, total_count=100)
            else:
                return _mock_response([], total_count=100)  # API returns empty early

        with patch("adapters.himalayas.http_get", side_effect=side_effect):
            with patch("adapters.himalayas.time.sleep"):
                roles = fetch("Himalayas (PM)", "product manager")

        assert len(roles) == 20


class TestFetchRoleMapping:
    def test_role_fields_mapped_correctly(self):
        """Verify all Role fields are populated correctly from job dict."""
        job = _make_job(
            title="Technical Program Manager",
            companyName="Stripe Inc",
            employmentType="Full Time",
            locationRestrictions=["United States"],
            applicationLink="https://himalayas.app/companies/stripe/jobs/tpm",
            guid="https://himalayas.app/companies/stripe/jobs/tpm",
            pubDate=1750000000,
            description="<p>Requires 3+ years of TPM experience.</p>",
            categories=["Technical-Program-Management"],
        )
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response([job])
            roles = fetch("Himalayas (TPM)", "technical program manager")

        assert len(roles) == 1
        r = roles[0]
        assert r.title == "Technical Program Manager"
        assert r.company == "Stripe Inc"
        assert r.location == "United States"
        assert r.url == "https://himalayas.app/companies/stripe/jobs/tpm"
        assert r.source == "himalayas"
        assert r.posted_at != ""  # non-empty date
        assert r.raw["guid"] == "https://himalayas.app/companies/stripe/jobs/tpm"
        assert "Technical-Program-Management" in r.raw["categories"]

    def test_location_empty_restriction_shows_remote(self):
        """Empty locationRestrictions should produce 'Remote' in role.location."""
        job = _make_job(locationRestrictions=[])
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response([job])
            roles = fetch("Himalayas (PM)", "product manager")

        assert roles[0].location == "Remote"

    def test_location_multiple_countries_joined(self):
        """Multiple locationRestrictions joined with ', '."""
        job = _make_job(locationRestrictions=["United States", "Canada"])
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response([job])
            roles = fetch("Himalayas (PM)", "product manager")

        assert roles[0].location == "United States, Canada"

    def test_company_fallback_to_arg(self):
        """If companyName missing, fall back to company arg."""
        job = _make_job(companyName=None)
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response([job])
            roles = fetch("Himalayas (PM)", "product manager")

        assert roles[0].company == "Himalayas (PM)"


class TestFetchEmptyResponse:
    def test_empty_jobs_list(self):
        """Empty jobs list returns empty roles."""
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response([], total_count=0)
            roles = fetch("Himalayas (PM)", "product manager")

        assert roles == []

    def test_http_error_raises_runtime_error(self):
        """Non-200 HTTP status raises RuntimeError."""
        r = MagicMock()
        r.status_code = 429
        with patch("adapters.himalayas.http_get", return_value=r):
            with pytest.raises(RuntimeError, match="himalayas.*429"):
                fetch("Himalayas (PM)", "product manager")


# ── source_key tests via tracker_merger ────────────────────────────────────────

class TestSourceKey:
    def test_source_key_format(self):
        """source_key must start with 'himalayas:' prefix."""
        job = _make_job(
            applicationLink="https://himalayas.app/companies/acme/jobs/product-manager",
            guid="https://himalayas.app/companies/acme/jobs/product-manager",
        )
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response([job])
            roles = fetch("Himalayas (PM)", "product manager")

        assert len(roles) == 1
        row = tracker_merger.role_to_db_row(roles[0].to_dict())
        assert row["source_key"].startswith("himalayas:"), row["source_key"]

    def test_source_key_is_stable(self):
        """Same input always produces same source_key (idempotent)."""
        job = _make_job(
            applicationLink="https://himalayas.app/companies/acme/jobs/tpm",
            guid="https://himalayas.app/companies/acme/jobs/tpm",
        )
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response([job])
            roles = fetch("Himalayas (PM)", "product manager")

        r = roles[0]
        row1 = tracker_merger.role_to_db_row(r.to_dict())
        row2 = tracker_merger.role_to_db_row(r.to_dict())
        assert row1["source_key"] == row2["source_key"]

    def test_source_key_unique_per_role(self):
        """Different URLs produce different source_keys."""
        jobs = [
            _make_job(
                title="PM",
                applicationLink="https://himalayas.app/companies/acme/jobs/pm",
                guid="https://himalayas.app/companies/acme/jobs/pm",
            ),
            _make_job(
                title="TPM",
                applicationLink="https://himalayas.app/companies/acme/jobs/tpm",
                guid="https://himalayas.app/companies/acme/jobs/tpm",
            ),
        ]
        with patch("adapters.himalayas.http_get") as mock_get:
            mock_get.return_value = _mock_response(jobs)
            roles = fetch("Himalayas (PM)", "product manager")

        keys = [tracker_merger.role_to_db_row(r.to_dict())["source_key"] for r in roles]
        assert len(set(keys)) == len(keys), "source_keys must be unique"
