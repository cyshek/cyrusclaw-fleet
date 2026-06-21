"""Tests for adapters/remoteok.py.

Mocks HTTP responses so no network calls are made.
Run: cd role-discovery && python3 -m pytest tests/test_remoteok_adapter.py -v
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

HERE = Path(__file__).parent.parent
sys.path.insert(0, str(HERE))
from adapters.remoteok import fetch

# ── Sample payload helpers ────────────────────────────────────────────────────

LEGAL_NOTICE = {
    "legal": "RemoteOK® is a registered trademark.",
    "disclaimer": "Use the API for reasonable purposes only.",
}


def _make_job(
    id="1133001",
    position="Product Manager",
    company="AcmeCo",
    url="https://remoteOK.com/remote-jobs/remote-product-manager-acmeco-1133001",
    apply_url="https://remoteOK.com/remote-jobs/remote-product-manager-acmeco-1133001",
    tags=["product manager", "remote"],
    location="Remote",
    description="<p>We need 5+ years of PM experience.</p>",
    date="2026-06-15T10:00:00",
    epoch=1750000000,
) -> dict:
    return dict(
        id=id,
        position=position,
        company=company,
        url=url,
        apply_url=apply_url,
        tags=tags,
        location=location,
        description=description,
        date=date,
        epoch=epoch,
    )


def _make_response(jobs: list, include_legal: bool = True) -> MagicMock:
    """Build a mock HTTP response. RemoteOK always prepends the legal notice dict."""
    data = ([LEGAL_NOTICE] if include_legal else []) + jobs
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = data
    return mock


# ── Unit tests ────────────────────────────────────────────────────────────────

class TestFetch:
    def test_basic_fetch_returns_roles(self):
        """fetch() skips legal notice and returns Role objects."""
        jobs = [_make_job(id="100001", position="Product Manager")]
        with patch("adapters.remoteok.http_get", return_value=_make_response(jobs)):
            roles = fetch("RemoteOK (PM)", "product-manager")
        assert len(roles) == 1
        assert roles[0].title == "Product Manager"
        assert roles[0].company == "AcmeCo"
        assert roles[0].source == "remoteok"

    def test_legal_notice_skipped(self):
        """The legal notice dict (no 'id' field) is always skipped."""
        with patch("adapters.remoteok.http_get", return_value=_make_response([])):
            roles = fetch("RemoteOK (PM)", "product-manager")
        assert len(roles) == 0

    def test_no_legal_notice_still_works(self):
        """If the API response has no legal notice prepended, still works."""
        jobs = [_make_job(id="200001", position="TPM")]
        with patch("adapters.remoteok.http_get", return_value=_make_response(jobs, include_legal=False)):
            roles = fetch("RemoteOK (TPM)", "technical-program-manager")
        assert len(roles) == 1
        assert roles[0].title == "TPM"

    def test_url_uses_apply_url(self):
        """apply_url is preferred over url for the Role.url field."""
        jobs = [_make_job(
            id="300001",
            apply_url="https://company.com/apply/job/300001",
            url="https://remoteOK.com/...-300001",
        )]
        with patch("adapters.remoteok.http_get", return_value=_make_response(jobs)):
            roles = fetch("RemoteOK (PM)", "product-manager")
        assert roles[0].url == "https://company.com/apply/job/300001"

    def test_fallback_url_when_no_apply_url(self):
        """Falls back to url when apply_url is absent."""
        job = _make_job(id="400001")
        del job["apply_url"]
        with patch("adapters.remoteok.http_get", return_value=_make_response([job])):
            roles = fetch("RemoteOK (PM)", "product-manager")
        assert "remoteOK.com" in roles[0].url

    def test_posted_at_from_date_field(self):
        """date field is truncated to YYYY-MM-DD."""
        jobs = [_make_job(id="500001", date="2026-06-15T10:30:00Z")]
        with patch("adapters.remoteok.http_get", return_value=_make_response(jobs)):
            roles = fetch("RemoteOK (PM)", "product-manager")
        assert roles[0].posted_at == "2026-06-15"

    def test_posted_at_from_epoch_fallback(self):
        """epoch is used when date field is absent."""
        job = _make_job(id="600001", epoch=1750060800)  # 2025-06-16
        job["date"] = ""
        with patch("adapters.remoteok.http_get", return_value=_make_response([job])):
            roles = fetch("RemoteOK (PM)", "product-manager")
        # Just check it's a valid date string, not empty
        assert len(roles[0].posted_at) == 10

    def test_exp_required_parsed(self):
        """parse_experience is called from description."""
        jobs = [_make_job(id="700001", description="<p>Requires 5+ years of PM experience.</p>")]
        with patch("adapters.remoteok.http_get", return_value=_make_response(jobs)):
            roles = fetch("RemoteOK (PM)", "product-manager")
        assert "5" in roles[0].exp_required

    def test_http_error_raises(self):
        """Non-200 response raises RuntimeError."""
        mock = MagicMock()
        mock.status_code = 429
        with patch("adapters.remoteok.http_get", return_value=mock):
            with pytest.raises(RuntimeError, match="remoteok"):
                fetch("RemoteOK (PM)", "product-manager")

    def test_unexpected_response_type_raises(self):
        """Non-list response raises RuntimeError."""
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"error": "bad"}
        with patch("adapters.remoteok.http_get", return_value=mock):
            with pytest.raises(RuntimeError, match="unexpected response type"):
                fetch("RemoteOK (PM)", "product-manager")

    def test_multiple_jobs(self):
        """Multiple jobs all returned."""
        jobs = [
            _make_job(id="800001", position="Product Manager"),
            _make_job(id="800002", position="Senior PM"),
            _make_job(id="800003", position="TPM"),
        ]
        with patch("adapters.remoteok.http_get", return_value=_make_response(jobs)):
            roles = fetch("RemoteOK (PM)", "product-manager")
        assert len(roles) == 3

    def test_location_defaults_to_remote(self):
        """Missing or empty location defaults to 'Remote'."""
        job = _make_job(id="900001")
        job["location"] = ""
        with patch("adapters.remoteok.http_get", return_value=_make_response([job])):
            roles = fetch("RemoteOK (PM)", "product-manager")
        assert roles[0].location == "Remote"
