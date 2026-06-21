"""Tests for SmartRecruiters, Workable, and BambooHR discovery adapters.

Uses unittest.mock to avoid real HTTP calls.
Run with: pytest test_new_ats_adapters.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


# ===========================================================================
# SmartRecruiters adapter tests
# ===========================================================================

class TestSmartRecruiters:
    """5 tests covering the SmartRecruiters discovery adapter."""

    def _make_posting(self, pid="743999000000001", title="Product Manager",
                      country="us", remote=False, city="San Francisco", region="CA",
                      released="2026-06-01") -> dict:
        return {
            "id": pid,
            "name": title,
            "location": {
                "city": city,
                "region": region,
                "country": country,
                "remote": remote,
                "hybrid": False,
            },
            "releasedDate": released,
            "experienceLevel": "Mid-Senior level",
            "typeOfEmployment": "Full-time",
        }

    @patch("adapters.smartrecruiters.http_get")
    def test_us_posting_included(self, mock_get):
        """US postings are returned."""
        from adapters.smartrecruiters import fetch

        posting = self._make_posting(country="us")
        mock_get.return_value = _mock_response(200, {
            "offset": 0, "limit": 100, "totalFound": 1,
            "content": [posting],
        })

        roles = fetch("Acme Corp", "AcmeCorp")
        assert len(roles) == 1
        assert roles[0].title == "Product Manager"
        assert roles[0].source == "smartrecruiters"

    @patch("adapters.smartrecruiters.http_get")
    def test_remote_posting_included(self, mock_get):
        """Remote postings (any country) are included."""
        from adapters.smartrecruiters import fetch

        posting = self._make_posting(country="gb", remote=True, title="TPM Remote")
        mock_get.return_value = _mock_response(200, {
            "offset": 0, "limit": 100, "totalFound": 1,
            "content": [posting],
        })

        roles = fetch("Acme Corp", "AcmeCorp")
        assert len(roles) == 1
        assert "Remote" in roles[0].location

    @patch("adapters.smartrecruiters.http_get")
    def test_non_us_non_remote_excluded(self, mock_get):
        """Non-US, non-remote postings are filtered out."""
        from adapters.smartrecruiters import fetch

        posting = self._make_posting(country="gb", remote=False, title="UK Engineer")
        mock_get.return_value = _mock_response(200, {
            "offset": 0, "limit": 100, "totalFound": 1,
            "content": [posting],
        })

        roles = fetch("Acme Corp", "AcmeCorp")
        assert len(roles) == 0

    @patch("adapters.smartrecruiters.http_get")
    def test_stable_url_built_from_id(self, mock_get):
        """URL is built from the stable posting ID, not the API ref."""
        from adapters.smartrecruiters import fetch

        posting = self._make_posting(pid="743999123456789", country="us")
        mock_get.return_value = _mock_response(200, {
            "offset": 0, "limit": 100, "totalFound": 1,
            "content": [posting],
        })

        roles = fetch("Acme Corp", "AcmeCorp")
        assert roles[0].url == "https://jobs.smartrecruiters.com/AcmeCorp/743999123456789"

    @patch("adapters.smartrecruiters.http_get")
    def test_http_error_returns_empty(self, mock_get):
        """Non-200 HTTP response returns empty list without raising."""
        from adapters.smartrecruiters import fetch

        mock_get.return_value = _mock_response(404, {})

        roles = fetch("Acme Corp", "AcmeCorp")
        assert roles == []

    @patch("adapters.smartrecruiters.http_get")
    def test_pagination_stops_at_total(self, mock_get):
        """Pagination stops when offset reaches totalFound."""
        from adapters.smartrecruiters import fetch

        posting = self._make_posting(country="us")
        # First page: 1 item, total=1 → should not request a second page
        mock_get.return_value = _mock_response(200, {
            "offset": 0, "limit": 100, "totalFound": 1,
            "content": [posting],
        })

        roles = fetch("Acme Corp", "AcmeCorp")
        assert len(roles) == 1
        mock_get.assert_called_once()

    @patch("adapters.smartrecruiters.http_get")
    def test_multiple_us_roles_returned(self, mock_get):
        """Multiple US roles all returned correctly."""
        from adapters.smartrecruiters import fetch

        postings = [
            self._make_posting(pid="1", title="PM", country="us"),
            self._make_posting(pid="2", title="TPM", country="us"),
            self._make_posting(pid="3", title="UK Dev", country="gb", remote=False),
        ]
        mock_get.return_value = _mock_response(200, {
            "offset": 0, "limit": 100, "totalFound": 3,
            "content": postings,
        })

        roles = fetch("Acme Corp", "AcmeCorp")
        assert len(roles) == 2
        titles = {r.title for r in roles}
        assert "PM" in titles and "TPM" in titles

    @patch("adapters.smartrecruiters.http_get")
    def test_network_exception_returns_empty(self, mock_get):
        """Network exception returns empty list without raising."""
        from adapters.smartrecruiters import fetch

        mock_get.side_effect = Exception("Connection timeout")

        roles = fetch("Acme Corp", "AcmeCorp")
        assert roles == []


# ===========================================================================
# Workable adapter tests
# ===========================================================================

class TestWorkable:
    """5 tests covering the Workable discovery adapter."""

    def _make_job(self, shortcode="A2DE40B6", title="Solutions Engineer",
                  country="United States", city="Austin", state="TX",
                  telecommuting=False, emp_type="full-time") -> dict:
        return {
            "title": title,
            "shortcode": shortcode,
            "code": "",
            "employment_type": emp_type,
            "telecommuting": telecommuting,
            "department": "Engineering",
            "url": f"https://apply.workable.com/acme/j/{shortcode}",
            "shortlink": f"https://apply.workable.com/j/{shortcode}",
            "application_url": f"https://apply.workable.com/j/{shortcode}/apply",
            "published_on": "2026-06-01",
            "created_at": "2026-05-15T10:00:00Z",
            "country": country,
            "city": city,
            "state": state,
            "education": "",
            "experience": "2+ years",
            "function": "Engineering",
            "industry": "Technology",
            "locations": [{"city": city, "region": state, "country": country}],
            "description": "<p>Role description</p>",
        }

    @patch("adapters.workable.http_get")
    def test_job_returned_for_us_company(self, mock_get):
        """Standard US job is returned."""
        from adapters.workable import fetch

        job = self._make_job()
        mock_get.return_value = _mock_response(200, {"name": "Acme", "jobs": [job]})

        roles = fetch("Acme", "acme")
        assert len(roles) == 1
        assert roles[0].title == "Solutions Engineer"
        assert roles[0].source == "workable"

    @patch("adapters.workable.http_get")
    def test_remote_job_location_label(self, mock_get):
        """Telecommuting=True produces a location string with '(Remote)'."""
        from adapters.workable import fetch

        job = self._make_job(telecommuting=True)
        mock_get.return_value = _mock_response(200, {"name": "Acme", "jobs": [job]})

        roles = fetch("Acme", "acme")
        assert len(roles) == 1
        assert "Remote" in roles[0].location

    @patch("adapters.workable.http_get")
    def test_apply_url_present(self, mock_get):
        """application_url is used as the role URL."""
        from adapters.workable import fetch

        job = self._make_job(shortcode="ZZ11AA22")
        mock_get.return_value = _mock_response(200, {"name": "Acme", "jobs": [job]})

        roles = fetch("Acme", "acme")
        assert "ZZ11AA22" in roles[0].url

    @patch("adapters.workable.http_get")
    def test_http_error_returns_empty(self, mock_get):
        """Non-200 HTTP returns empty list without raising."""
        from adapters.workable import fetch

        mock_get.return_value = _mock_response(404, {})
        roles = fetch("Acme", "acme")
        assert roles == []

    @patch("adapters.workable.http_get")
    def test_multiple_jobs_returned(self, mock_get):
        """Multiple jobs in response all appear in result."""
        from adapters.workable import fetch

        jobs = [
            self._make_job(shortcode="AA000001", title="PM"),
            self._make_job(shortcode="BB000002", title="TPM"),
            self._make_job(shortcode="CC000003", title="SE"),
        ]
        mock_get.return_value = _mock_response(200, {"name": "Acme", "jobs": jobs})

        roles = fetch("Acme", "acme")
        assert len(roles) == 3
        titles = {r.title for r in roles}
        assert titles == {"PM", "TPM", "SE"}

    @patch("adapters.workable.http_get")
    def test_empty_jobs_list_ok(self, mock_get):
        """Empty jobs array returns empty list without error."""
        from adapters.workable import fetch

        mock_get.return_value = _mock_response(200, {"name": "Acme", "jobs": []})
        roles = fetch("Acme", "acme")
        assert roles == []

    @patch("adapters.workable.http_get")
    def test_posted_on_date_preserved(self, mock_get):
        """published_on date is captured in posted_at."""
        from adapters.workable import fetch

        job = self._make_job()
        job["published_on"] = "2026-05-15"
        mock_get.return_value = _mock_response(200, {"name": "Acme", "jobs": [job]})

        roles = fetch("Acme", "acme")
        assert roles[0].posted_at == "2026-05-15"


# ===========================================================================
# BambooHR adapter tests
# ===========================================================================

class TestBambooHR:
    """5 tests covering the BambooHR discovery adapter."""

    def _make_job(self, jid="838", title="Solutions Architect",
                  ats_country="United States", ats_state="New York",
                  city="New York", state="New York",
                  is_remote=None, location_type="2",
                  emp_label="Full-Time", dept="Engineering") -> dict:
        return {
            "id": jid,
            "jobOpeningName": title,
            "departmentId": "100",
            "departmentLabel": dept,
            "employmentStatusLabel": emp_label,
            "location": {"city": city, "state": state},
            "atsLocation": {
                "country": ats_country,
                "state": ats_state,
                "province": None,
                "city": city,
            },
            "isRemote": is_remote,
            "locationType": location_type,
        }

    @patch("adapters.bamboohr.http_get")
    def test_us_job_included(self, mock_get):
        """US job (atsLocation.country=United States) is returned."""
        from adapters.bamboohr import fetch

        job = self._make_job()
        mock_get.return_value = _mock_response(200, {
            "meta": {"totalCount": 1},
            "result": [job],
        })

        roles = fetch("Uphold", "uphold")
        assert len(roles) == 1
        assert roles[0].title == "Solutions Architect"
        assert roles[0].source == "bamboohr"

    @patch("adapters.bamboohr.http_get")
    def test_remote_job_included(self, mock_get):
        """isRemote=True job is included regardless of country."""
        from adapters.bamboohr import fetch

        job = self._make_job(ats_country=None, ats_state=None, is_remote=True)
        mock_get.return_value = _mock_response(200, {
            "meta": {"totalCount": 1},
            "result": [job],
        })

        roles = fetch("Uphold", "uphold")
        assert len(roles) == 1
        assert "Remote" in roles[0].location

    @patch("adapters.bamboohr.http_get")
    def test_non_us_job_excluded(self, mock_get):
        """Non-US job with no remote flag is filtered out."""
        from adapters.bamboohr import fetch

        job = self._make_job(ats_country="United Kingdom", ats_state="Greater London",
                             city="London", state="Greater London")
        mock_get.return_value = _mock_response(200, {
            "meta": {"totalCount": 1},
            "result": [job],
        })

        roles = fetch("Clarity", "clarity")
        assert len(roles) == 0

    @patch("adapters.bamboohr.http_get")
    def test_apply_url_contains_slug_and_id(self, mock_get):
        """Apply URL is built as https://{slug}.bamboohr.com/careers/{id}."""
        from adapters.bamboohr import fetch

        job = self._make_job(jid="839")
        mock_get.return_value = _mock_response(200, {
            "meta": {"totalCount": 1},
            "result": [job],
        })

        roles = fetch("Uphold", "uphold")
        assert roles[0].url == "https://uphold.bamboohr.com/careers/839"

    @patch("adapters.bamboohr.http_get")
    def test_http_error_returns_empty(self, mock_get):
        """Non-200 HTTP returns empty list without raising."""
        from adapters.bamboohr import fetch

        mock_get.return_value = _mock_response(404, {})
        roles = fetch("Uphold", "uphold")
        assert roles == []

    @patch("adapters.bamboohr.http_get")
    def test_network_exception_returns_empty(self, mock_get):
        """Network exception returns empty list without raising."""
        from adapters.bamboohr import fetch

        mock_get.side_effect = Exception("Connection refused")
        roles = fetch("Uphold", "uphold")
        assert roles == []

    @patch("adapters.bamboohr.http_get")
    def test_part_time_job_excluded(self, mock_get):
        """Part-time jobs are filtered out."""
        from adapters.bamboohr import fetch

        job = self._make_job(emp_label="Part-Time")
        mock_get.return_value = _mock_response(200, {
            "meta": {"totalCount": 1},
            "result": [job],
        })

        roles = fetch("Uphold", "uphold")
        assert len(roles) == 0

    @patch("adapters.bamboohr.http_get")
    def test_multiple_us_jobs_returned(self, mock_get):
        """Multiple US jobs all returned."""
        from adapters.bamboohr import fetch

        jobs = [
            self._make_job(jid="100", title="PM"),
            self._make_job(jid="101", title="TPM"),
            self._make_job(jid="102", title="SE UK", ats_country="United Kingdom"),
        ]
        mock_get.return_value = _mock_response(200, {
            "meta": {"totalCount": 3},
            "result": jobs,
        })

        roles = fetch("Uphold", "uphold")
        assert len(roles) == 2
        titles = {r.title for r in roles}
        assert "PM" in titles and "TPM" in titles


# ===========================================================================
# tracker_merger source_key generation tests
# ===========================================================================

class TestTrackerMergerSourceKeys:
    """Verify tracker_merger.role_to_db_row generates correct source_keys
    for each new adapter."""

    def _row(self, source: str, url: str, company="Acme", title="PM") -> dict:
        return {"source": source, "url": url, "company": company,
                "title": title, "location": "US", "exp_required": "exp:unstated",
                "posted_at": ""}

    def test_smartrecruiters_source_key(self):
        from tracker_merger import role_to_db_row
        row = role_to_db_row(self._row(
            "smartrecruiters",
            "https://jobs.smartrecruiters.com/Workato/743999962266534"
        ))
        assert row["source_key"] == "smartrecruiters:743999962266534"

    def test_smartrecruiters_source_key_with_title_slug(self):
        from tracker_merger import role_to_db_row
        row = role_to_db_row(self._row(
            "smartrecruiters",
            "https://jobs.smartrecruiters.com/Workato/743999962266534-principal-architect"
        ))
        assert row["source_key"] == "smartrecruiters:743999962266534"

    def test_workable_source_key(self):
        from tracker_merger import role_to_db_row
        row = role_to_db_row(self._row(
            "workable",
            "https://apply.workable.com/j/A2DE40B6D5/apply"
        ))
        assert row["source_key"] == "workable:A2DE40B6D5"

    def test_workable_source_key_company_path(self):
        from tracker_merger import role_to_db_row
        row = role_to_db_row(self._row(
            "workable",
            "https://apply.workable.com/unusual-machines/j/F1FDA75040/apply"
        ))
        assert row["source_key"] == "workable:F1FDA75040"

    def test_bamboohr_source_key(self):
        from tracker_merger import role_to_db_row
        row = role_to_db_row(self._row(
            "bamboohr",
            "https://uphold.bamboohr.com/careers/839"
        ))
        assert row["source_key"] == "bamboohr:uphold:839"

    def test_bamboohr_source_key_different_slug(self):
        from tracker_merger import role_to_db_row
        row = role_to_db_row(self._row(
            "bamboohr",
            "https://wistia.bamboohr.com/careers/1234"
        ))
        assert row["source_key"] == "bamboohr:wistia:1234"
