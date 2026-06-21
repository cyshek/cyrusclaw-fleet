"""Tests for adapters/remotive.py.

Mocks HTTP responses so no network calls are made.
Run: cd role-discovery && python3 -m pytest tests/test_remotive_adapter.py -v
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

HERE = Path(__file__).parent.parent
sys.path.insert(0, str(HERE))
from adapters.remotive import fetch, _is_us_accessible

# ── Sample payload helpers ────────────────────────────────────────────────────

def _make_job(
    id=1001,
    title="Product Manager",
    company_name="Acme Corp",
    url="https://remotive.com/remote-jobs/product/product-manager-1001",
    candidate_required_location="USA",
    job_type="full_time",
    tags=["product", "remote"],
    description="<p>We need 3+ years of experience in product management.</p>",
    publication_date="2026-06-15T10:00:00",
) -> dict:
    return dict(
        id=id,
        title=title,
        company_name=company_name,
        url=url,
        candidate_required_location=candidate_required_location,
        job_type=job_type,
        tags=tags,
        description=description,
        publication_date=publication_date,
    )


def _make_response(jobs: list) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"jobs": jobs}
    return mock


# ── Unit tests ────────────────────────────────────────────────────────────────

class TestIsUsAccessible:
    def test_usa_exact(self):
        assert _is_us_accessible("USA") is True

    def test_worldwide(self):
        assert _is_us_accessible("Worldwide") is True

    def test_americas(self):
        assert _is_us_accessible("Americas, Europe") is True

    def test_north_america(self):
        assert _is_us_accessible("North America") is True

    def test_us_standalone(self):
        assert _is_us_accessible("US") is True

    def test_germany_excluded(self):
        assert _is_us_accessible("Germany") is False

    def test_brazil_excluded(self):
        assert _is_us_accessible("Brazil") is False

    def test_empty_is_ok(self):
        # empty location = unspecified = worldwide
        assert _is_us_accessible("") is True

    def test_australia_not_matched_as_us(self):
        # "AUSTRALIA" should NOT match "US" via \bUS\b
        assert _is_us_accessible("Australia") is False

    def test_russia_not_matched(self):
        assert _is_us_accessible("Russia") is False


class TestFetch:
    def test_basic_fetch_returns_roles(self):
        """fetch() returns a list of Role objects for US-eligible jobs."""
        jobs = [_make_job(id=100, title="Product Manager", candidate_required_location="USA")]
        with patch("adapters.remotive.http_get", return_value=_make_response(jobs)):
            roles = fetch("Remotive (product)", "product")
        assert len(roles) == 1
        assert roles[0].title == "Product Manager"
        assert roles[0].company == "Acme Corp"
        assert roles[0].source == "remotive"

    def test_non_us_location_filtered_out(self):
        """Jobs with non-US location are excluded."""
        jobs = [
            _make_job(id=200, candidate_required_location="Germany"),
            _make_job(id=201, candidate_required_location="Brazil"),
        ]
        with patch("adapters.remotive.http_get", return_value=_make_response(jobs)):
            roles = fetch("Remotive (product)", "product")
        assert len(roles) == 0

    def test_worldwide_location_included(self):
        """Worldwide jobs are included."""
        jobs = [_make_job(id=300, candidate_required_location="Worldwide")]
        with patch("adapters.remotive.http_get", return_value=_make_response(jobs)):
            roles = fetch("Remotive (product)", "product")
        assert len(roles) == 1

    def test_url_preserved(self):
        """URL from job listing is stored on the Role."""
        jobs = [_make_job(id=400, url="https://remotive.com/remote-jobs/product/pm-400")]
        with patch("adapters.remotive.http_get", return_value=_make_response(jobs)):
            roles = fetch("Remotive (product)", "product")
        assert roles[0].url == "https://remotive.com/remote-jobs/product/pm-400"

    def test_posted_at_truncated_to_date(self):
        """publication_date is truncated to YYYY-MM-DD."""
        jobs = [_make_job(id=500, publication_date="2026-06-15T10:30:00Z")]
        with patch("adapters.remotive.http_get", return_value=_make_response(jobs)):
            roles = fetch("Remotive (product)", "product")
        assert roles[0].posted_at == "2026-06-15"

    def test_exp_required_parsed(self):
        """parse_experience is called; 3+ years description → exp:3+yrs."""
        jobs = [_make_job(id=600, description="<p>Requires 3+ years of PM experience.</p>")]
        with patch("adapters.remotive.http_get", return_value=_make_response(jobs)):
            roles = fetch("Remotive (product)", "product")
        assert "3" in roles[0].exp_required

    def test_http_error_raises(self):
        """Non-200 response raises RuntimeError."""
        mock = MagicMock()
        mock.status_code = 503
        with patch("adapters.remotive.http_get", return_value=mock):
            with pytest.raises(RuntimeError, match="remotive"):
                fetch("Remotive (product)", "product")

    def test_empty_jobs_list(self):
        """Empty jobs list returns empty list."""
        with patch("adapters.remotive.http_get", return_value=_make_response([])):
            roles = fetch("Remotive (product)", "product")
        assert roles == []

    def test_company_name_from_job(self):
        """company field uses company_name from the job, not the adapter name."""
        jobs = [_make_job(id=700, company_name="TechStartup Inc.")]
        with patch("adapters.remotive.http_get", return_value=_make_response(jobs)):
            roles = fetch("Remotive (product)", "product")
        assert roles[0].company == "TechStartup Inc."

    def test_mixed_locations_filtered_correctly(self):
        """Mixed US/non-US batch correctly keeps only US-accessible."""
        jobs = [
            _make_job(id=800, candidate_required_location="USA"),
            _make_job(id=801, candidate_required_location="France"),
            _make_job(id=802, candidate_required_location="Worldwide"),
            _make_job(id=803, candidate_required_location="Japan"),
            _make_job(id=804, candidate_required_location="Americas"),
        ]
        with patch("adapters.remotive.http_get", return_value=_make_response(jobs)):
            roles = fetch("Remotive (product)", "product")
        assert len(roles) == 3  # 800, 802, 804
