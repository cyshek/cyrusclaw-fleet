#!/usr/bin/env python3
"""Regression test: detect_and_fetch must route stripe.com/jobs/... to GH API.

Background: 2026-05-24 6 Stripe submits slipped past the YOE classifier
because detect_and_fetch had no stripe.com branch. This test pins the new
branch in place.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import jd_llm_classifier as jdc  # noqa: E402


STRIPE_GH_API_RESPONSE = {
    "id": 7901987,
    "title": "Solutions Architect",
    "content": "<p>We're looking for a <b>Solutions Architect</b> with 4+ years of experience.</p>",
}


def _mock_resp(json_payload=None, status=200, text=""):
    r = MagicMock()
    r.status_code = status
    r.raise_for_status = MagicMock()
    if json_payload is not None:
        r.json = MagicMock(return_value=json_payload)
    r.text = text or ""
    return r


class TestStripeRouting(unittest.TestCase):
    def test_stripe_jobs_listing_url_routes_to_stripe(self):
        url = "https://stripe.com/jobs/listing/solutions-architect/7901987"
        called = {}

        def fake_get(api_url, headers=None):
            called["url"] = api_url
            return _mock_resp(json_payload=STRIPE_GH_API_RESPONSE)

        with patch.object(jdc, "_http_get", side_effect=fake_get):
            ats, jd = jdc.detect_and_fetch(url)
        self.assertEqual(ats, "stripe")
        self.assertIn("Solutions Architect", jd)
        self.assertEqual(
            called["url"],
            "https://boards-api.greenhouse.io/v1/boards/stripe/jobs/7901987",
        )

    def test_stripe_jobs_listing_apply_url(self):
        url = "https://stripe.com/jobs/listing/solutions-architect/7901987/apply"
        called = {}

        def fake_get(api_url, headers=None):
            called["url"] = api_url
            return _mock_resp(json_payload=STRIPE_GH_API_RESPONSE)

        with patch.object(jdc, "_http_get", side_effect=fake_get):
            ats, jd = jdc.detect_and_fetch(url)
        self.assertEqual(ats, "stripe")
        self.assertIn(
            "boards-api.greenhouse.io/v1/boards/stripe/jobs/7901987",
            called["url"],
        )

    def test_stripe_search_gh_jid_url(self):
        url = "https://stripe.com/jobs/search?gh_jid=7901987"
        called = {}

        def fake_get(api_url, headers=None):
            called["url"] = api_url
            return _mock_resp(json_payload=STRIPE_GH_API_RESPONSE)

        with patch.object(jdc, "_http_get", side_effect=fake_get):
            ats, jd = jdc.detect_and_fetch(url)
        self.assertEqual(ats, "stripe")
        self.assertIn("7901987", called["url"])

    def test_stripe_unparseable_url_raises(self):
        url = "https://stripe.com/jobs/"
        with self.assertRaises(ValueError):
            jdc.fetch_jd_stripe(url)

    def test_non_stripe_url_still_falls_through(self):
        """Sanity: a non-stripe URL should NOT hit the stripe branch."""
        url = "https://boards.greenhouse.io/plaid/jobs/4567890"
        # Mock generic fetcher to detect mis-routing
        with patch.object(jdc, "fetch_jd_greenhouse",
                          return_value="# Plaid PM\n\nA Plaid posting."):
            ats, jd = jdc.detect_and_fetch(url)
        self.assertEqual(ats, "greenhouse")

    def test_stripe_jd_contains_extracted_text(self):
        """Full end-to-end (mocked): JD body text is extracted from GH content HTML."""
        url = "https://stripe.com/jobs/listing/solutions-architect/7901987"
        with patch.object(jdc, "_http_get",
                          side_effect=lambda u, headers=None: _mock_resp(json_payload=STRIPE_GH_API_RESPONSE)):
            ats, jd = jdc.detect_and_fetch(url)
        self.assertIn("4+ years", jd)


if __name__ == "__main__":
    unittest.main()
