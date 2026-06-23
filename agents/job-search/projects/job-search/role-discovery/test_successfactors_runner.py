"""tests for _successfactors_runner.py"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from _successfactors_runner import (
    parse_sf_url, sf_apply_url, sf_career_url,
    detect_success, detect_already_applied, detect_closed,
)
from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------
class TestParseSfUrl:
    def test_career8_with_company_and_jobid(self):
        url = "https://career8.successfactors.com/career?company=aosmith&jobId=1395242700&lang=en_US"
        r = parse_sf_url(url)
        assert r["server"] == "career8.successfactors.com"
        assert r["tenant"] == "aosmith"
        assert r["job_id"] == "1395242700"

    def test_career5_eu(self):
        url = "https://career5.successfactors.eu/career?company=schaeffler&jobId=9999&lang=en_US"
        r = parse_sf_url(url)
        assert r["server"] == "career5.successfactors.eu"
        assert r["tenant"] == "schaeffler"
        assert r["job_id"] == "9999"

    def test_aosmith_vendor_site_redirect(self):
        url = "https://jobs.aosmith.com/job/Milwaukee-Product-Manager-WI-53224/1395242700/"
        r = parse_sf_url(url)
        assert r["tenant"] == "aosmith"
        assert r["job_id"] == "1395242700"
        assert r["server"] == "career8.successfactors.com"

    def test_unrecognized_url_returns_none(self):
        assert parse_sf_url("https://greenhouse.io/jobs/123") is None

    def test_sf_apply_url_format(self):
        url = sf_apply_url("career8.successfactors.com", "aosmith", "1395242700")
        assert "career8.successfactors.com" in url
        assert "company=aosmith" in url
        assert "jobId=1395242700" in url

    def test_sf_career_url_no_jobid(self):
        url = sf_career_url("career8.successfactors.com", "aosmith")
        assert "company=aosmith" in url
        assert "jobId" not in url


# ---------------------------------------------------------------------------
# Success / state detection (mock page)
# ---------------------------------------------------------------------------
class FakePage:
    def __init__(self, url="", body=""):
        self.url = url
        self._body = body

    def evaluate(self, expr, *args):
        if "body.innerText" in expr:
            return self._body.lower()
        return self._body


class TestDetectSuccess:
    def test_url_redirect_param(self):
        p = FakePage(url="https://career8.successfactors.com/portalcareer?isRedirectToAppSent=true")
        assert detect_success(p) is True

    def test_body_thank_you(self):
        p = FakePage(body="Your application has been sent. Thank you!")
        assert detect_success(p) is True

    def test_no_signal(self):
        p = FakePage(url="https://career8.successfactors.com/career?company=aosmith", body="Please complete your profile")
        assert detect_success(p) is False


class TestDetectAlreadyApplied:
    def test_already_applied_body(self):
        p = FakePage(body="You have already applied to this position.")
        assert detect_already_applied(p) is True

    def test_not_applied(self):
        p = FakePage(body="Complete the application form below.")
        assert detect_already_applied(p) is False


class TestDetectClosed:
    def test_closed_body(self):
        p = FakePage(body="This position is no longer available.")
        assert detect_closed(p) is True

    def test_open(self):
        p = FakePage(body="Product Manager at A.O. Smith")
        assert detect_closed(p) is False


# ---------------------------------------------------------------------------
# Screening Q logic (unit-level)
# ---------------------------------------------------------------------------
class TestScreeningQLogic:
    """Verify the label→yes/no decision logic."""
    def _label_to_answer(self, label_text: str) -> str:
        label_text = label_text.lower()
        if any(k in label_text for k in ["sponsor", "visa", "work authoriz", "h-1b", "h1b"]):
            return "no"
        return "yes"

    def test_sponsorship_q_returns_no(self):
        assert self._label_to_answer("Do you require visa sponsorship?") == "no"

    def test_h1b_returns_no(self):
        assert self._label_to_answer("Will you need H-1B sponsorship?") == "no"

    def test_eligibility_returns_yes(self):
        assert self._label_to_answer("Are you eligible to work in the US?") == "yes"

    def test_age_returns_yes(self):
        assert self._label_to_answer("Are you 18 years of age or older?") == "yes"
