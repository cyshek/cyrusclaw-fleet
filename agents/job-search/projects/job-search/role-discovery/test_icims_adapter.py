"""Tests for adapters/icims.py."""
import os
import re
import time
import unittest
from unittest.mock import MagicMock, patch

from core import Role
from adapters.icims import (
    TITLE_KEEP_RE, API_PAGE_SIZE, fetch, _fetch_all_raw,
)


# ---------------------------------------------------------------------------
# Unit tests (mocked network)
# ---------------------------------------------------------------------------

def _make_job(req_id, title, country_code="US", applyable=True, internal=False,
              city="San Jose", state="California", apply_url=None,
              posted_date="2026-06-26T15:00:00+0000"):
    """Helper: build a minimal iCIMS job data dict."""
    if apply_url is None:
        apply_url = f"https://careers-test.icims.com/jobs/{req_id}/login"
    return {
        "req_id": req_id,
        "title": title,
        "country_code": country_code,
        "applyable": applyable,
        "internal": internal,
        "city": city,
        "state": state,
        "full_location": f"{city}, {state}",
        "apply_url": apply_url,
        "posted_date": posted_date,
        "description": "We are looking for a great candidate.",
        "employment_type": "Full-Time",
        "department": "Engineering",
    }


def _make_response(jobs, total_count=None):
    """Build a mock jibeapply API response."""
    total_count = total_count if total_count is not None else len(jobs)
    return {"totalCount": total_count, "jobs": [{"data": j} for j in jobs]}


class TestTitleFilter(unittest.TestCase):
    """TITLE_KEEP_RE should match target roles and reject non-targets."""

    KEEP = [
        "Product Manager",
        "Senior Product Manager",
        "Program Manager, Trust & Safety",
        "Technical Program Manager",
        "Sr. Technical Program Manager",
        "Solutions Engineer",
        "Solutions Architect",
        "Sales Engineer",
        "Customer Engineer",
        "Principal Solutions Architect",
        "TPM - Platform",
        "APM Intern",
    ]

    REJECT = [
        "Software Engineer",
        "Senior Software Engineer, Platform",
        "Data Scientist",
        "Director, People Operations",
        "Vice President of Engineering",
        "Marketing Coordinator",
        "UX Designer",
        "Sr. VLSI Physical Design Engineer",
    ]

    def test_keep(self):
        for title in self.KEEP:
            self.assertIsNotNone(TITLE_KEEP_RE.search(title), f"should KEEP: {title}")

    def test_reject(self):
        for title in self.REJECT:
            self.assertIsNone(TITLE_KEEP_RE.search(title), f"should REJECT: {title}")


class TestFetchMocked(unittest.TestCase):
    """fetch() with mocked http_get — validates filtering and Role mapping."""

    def _mock_response(self, data: dict):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = data
        return m

    def test_role_mapping(self):
        """fetch() maps iCIMS job data to Role objects correctly."""
        pm_job = _make_job(1001, "Product Manager", city="Austin", state="Texas",
                           apply_url="https://careers-test.icims.com/jobs/1001/login")
        response = _make_response([pm_job], total_count=1)
        with patch("adapters.icims.http_get", return_value=self._mock_response(response)):
            roles = fetch("TestCo", "test", icims_client_code="test")
        self.assertEqual(len(roles), 1)
        r = roles[0]
        self.assertEqual(r.title, "Product Manager")
        self.assertEqual(r.company, "TestCo")
        self.assertEqual(r.url, "https://careers-test.icims.com/jobs/1001/login")
        self.assertEqual(r.source, "icims")
        self.assertEqual(r.location, "Austin, Texas")
        self.assertEqual(r.posted_at, "2026-06-26")
        self.assertEqual(r.raw["req_id"], "1001")
        self.assertEqual(r.raw["client_code"], "test")

    def test_us_filter(self):
        """Non-US roles should be excluded."""
        jobs = [
            _make_job(101, "Product Manager", country_code="US"),
            _make_job(102, "Product Manager", country_code="CA"),
            _make_job(103, "Product Manager", country_code="GB"),
        ]
        response = _make_response(jobs, total_count=3)
        with patch("adapters.icims.http_get", return_value=self._mock_response(response)):
            roles = fetch("TestCo", "test", icims_client_code="test")
        self.assertEqual(len(roles), 1)  # only US
        self.assertEqual(roles[0].raw["req_id"], "101")

    def test_internal_filter(self):
        """Internal=True roles should be excluded."""
        jobs = [
            _make_job(201, "Product Manager", internal=False),
            _make_job(202, "Product Manager", internal=True),
        ]
        response = _make_response(jobs, total_count=2)
        with patch("adapters.icims.http_get", return_value=self._mock_response(response)):
            roles = fetch("TestCo", "test", icims_client_code="test")
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0].raw["req_id"], "201")

    def test_not_applyable_filter(self):
        """applyable=False roles should be excluded."""
        jobs = [
            _make_job(301, "Product Manager", applyable=True),
            _make_job(302, "Product Manager", applyable=False),
        ]
        response = _make_response(jobs, total_count=2)
        with patch("adapters.icims.http_get", return_value=self._mock_response(response)):
            roles = fetch("TestCo", "test", icims_client_code="test")
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0].raw["req_id"], "301")

    def test_title_filter(self):
        """Only target-role titles should pass."""
        jobs = [
            _make_job(401, "Senior Product Manager"),
            _make_job(402, "Software Engineer"),
            _make_job(403, "Solutions Architect"),
            _make_job(404, "Data Scientist"),
        ]
        response = _make_response(jobs, total_count=4)
        with patch("adapters.icims.http_get", return_value=self._mock_response(response)):
            roles = fetch("TestCo", "test", icims_client_code="test")
        titles = [r.title for r in roles]
        self.assertIn("Senior Product Manager", titles)
        self.assertIn("Solutions Architect", titles)
        self.assertNotIn("Software Engineer", titles)
        self.assertNotIn("Data Scientist", titles)

    def test_dedup(self):
        """Duplicate req_ids should produce only one Role."""
        jobs = [
            _make_job(501, "Product Manager"),
            _make_job(501, "Product Manager"),  # duplicate
        ]
        response = _make_response(jobs, total_count=2)
        with patch("adapters.icims.http_get", return_value=self._mock_response(response)):
            roles = fetch("TestCo", "test", icims_client_code="test")
        self.assertEqual(len(roles), 1)

    def test_location_dedup(self):
        """Duplicate semicolon-separated locations should be deduplicated."""
        job = _make_job(601, "Program Manager")
        # Simulate multi-location duplication from API
        job["full_location"] = "New York, New York; Atlanta, Georgia; New York, New York; Atlanta, Georgia"
        response = _make_response([job], total_count=1)
        with patch("adapters.icims.http_get", return_value=self._mock_response(response)):
            roles = fetch("TestCo", "test", icims_client_code="test")
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0].location, "New York, New York; Atlanta, Georgia")

    def test_missing_client_code_raises(self):
        """Missing icims_client_code should raise ValueError."""
        with self.assertRaises(ValueError):
            fetch("TestCo", "")


class TestPaginationMocked(unittest.TestCase):
    """Pagination logic with totalCount > one page."""

    def _make_page(self, req_id_start, count, total_count):
        jobs = [_make_job(req_id_start + i, "Product Manager") for i in range(count)]
        return {"totalCount": total_count, "jobs": [{"data": j} for j in jobs]}

    def test_pagination_stops_at_total_count(self):
        """Fetcher should stop when fetched >= totalCount."""
        # 25 total roles = 3 pages (10 + 10 + 5)
        page1 = self._make_page(1000, 10, 25)
        page2 = self._make_page(1010, 10, 25)
        page3 = self._make_page(1020, 5, 25)
        responses = [page1, page2, page3]
        call_count = [0]

        def mock_get(url, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = responses[min(idx, len(responses) - 1)]
            return m

        with patch("adapters.icims.http_get", side_effect=mock_get):
            with patch("time.sleep"):  # skip rate limit
                raw = _fetch_all_raw("test")
        self.assertEqual(len(raw), 25)
        self.assertEqual(call_count[0], 3)  # exactly 3 pages

    def test_pagination_stops_on_empty_page(self):
        """Fetcher should stop on empty jobs array even if totalCount > 0."""
        page1 = self._make_page(2000, 10, 100)
        page2 = {"totalCount": 100, "jobs": []}  # empty page
        responses = [page1, page2]
        call_count = [0]

        def mock_get(url, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = responses[min(idx, len(responses) - 1)]
            return m

        with patch("adapters.icims.http_get", side_effect=mock_get):
            with patch("time.sleep"):
                raw = _fetch_all_raw("test")
        self.assertEqual(len(raw), 10)  # only page 1
        self.assertEqual(call_count[0], 2)

    def test_http_error_raises(self):
        """Non-200 response should raise RuntimeError."""
        m = MagicMock()
        m.status_code = 503
        m.json.return_value = {}
        with patch("adapters.icims.http_get", return_value=m):
            with self.assertRaises(RuntimeError):
                _fetch_all_raw("test")


# ---------------------------------------------------------------------------
# Live integration test (hits real AMD API)
# ---------------------------------------------------------------------------

SKIP_LIVE = os.environ.get("SKIP_LIVE", "").lower() in ("1", "true", "yes")


@unittest.skipIf(SKIP_LIVE, "SKIP_LIVE=1 set")
class TestLiveAMD(unittest.TestCase):
    """Live smoke test against AMD jibeapply endpoint.

    AMD has 1100+ total roles but the title filter leaves only those matching
    PM/SE/SA/TPM patterns. We spot-check that we get at least a handful.
    Full pagination is skipped to keep CI fast (just verify first page cycles).
    """

    @classmethod
    def setUpClass(cls):
        """Fetch AMD roles once for all live tests."""
        from core import http_get
        # Quick connectivity check
        try:
            r = http_get("https://amd.jibeapply.com/api/jobs",
                         params={"keyword":"","pagesize":10,"page":1,
                                 "internal":"false","activelanguagetag":"en-us"},
                         timeout=10)
            if r.status_code != 200:
                raise unittest.SkipTest("AMD API not reachable")
            cls.total_count = r.json().get("totalCount", 0)
        except Exception as e:
            raise unittest.SkipTest(f"AMD API not reachable: {e}")

    def test_amd_total_count_nonzero(self):
        """AMD should expose > 100 total roles."""
        self.assertGreater(self.total_count, 100,
                           f"Expected >100 total roles, got {self.total_count}")

    def test_amd_single_page_fetch(self):
        """Fetching a single page should return exactly 10 raw jobs."""
        from core import http_get
        r = http_get("https://amd.jibeapply.com/api/jobs",
                     params={"keyword":"","pagesize":10,"page":1,
                             "internal":"false","activelanguagetag":"en-us"},
                     timeout=10)
        self.assertEqual(r.status_code, 200)
        jobs = r.json().get("jobs", [])
        self.assertEqual(len(jobs), API_PAGE_SIZE,
                         f"Expected {API_PAGE_SIZE} jobs/page, got {len(jobs)}")

    def test_amd_job_fields_present(self):
        """Raw AMD job dicts should have required fields."""
        from core import http_get
        r = http_get("https://amd.jibeapply.com/api/jobs",
                     params={"keyword":"","pagesize":10,"page":1,
                             "internal":"false","activelanguagetag":"en-us"},
                     timeout=10).json()
        j0 = r["jobs"][0]["data"]
        for field in ("req_id", "title", "country_code", "applyable", "apply_url"):
            self.assertIn(field, j0, f"Missing field: {field}")


@unittest.skipIf(SKIP_LIVE, "SKIP_LIVE=1 set")
class TestLiveSiriusXM(unittest.TestCase):
    """Live smoke test against SiriusXM (75 roles — fast to fetch)."""

    @classmethod
    def setUpClass(cls):
        from core import http_get
        try:
            r = http_get("https://siriusxmradio.jibeapply.com/api/jobs",
                         params={"keyword":"","pagesize":10,"page":1,
                                 "internal":"false","activelanguagetag":"en-us"},
                         timeout=10)
            if r.status_code != 200:
                raise unittest.SkipTest("SiriusXM API not reachable")
        except Exception as e:
            raise unittest.SkipTest(f"SiriusXM API not reachable: {e}")

    def test_sirius_fetch_returns_roles(self):
        """fetch() should return at least 1 TPM/PM role for SiriusXM."""
        roles = fetch("SiriusXM", "siriusxmradio", icims_client_code="siriusxmradio")
        self.assertGreater(len(roles), 0,
                           "Expected at least 1 target role from SiriusXM")
        for r in roles:
            self.assertEqual(r.source, "icims")
            self.assertTrue(r.url.startswith("https://"),
                            f"URL malformed: {r.url}")
            self.assertIn("/login", r.url,
                            f"Expected /login in URL: {r.url}")
            self.assertEqual(r.company, "SiriusXM")
            self.assertRegex(r.posted_at, r"^\d{4}-\d{2}-\d{2}$|^$",
                             f"posted_at not ISO: {r.posted_at}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
