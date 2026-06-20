#!/usr/bin/env python3
"""Regression tests for the gh_jid wrapper-host cohort gap.

Autonomous tick 2026-06-08. Bug: several companies publish Greenhouse-backed
postings on their OWN domain with a `?gh_jid=<id>` param (iframe-wrapper class),
but the host was missing from greenhouse_iframe.HOST_TO_GH_SLUG. Effect:
  - host_to_gh_slug(url) -> None
  - inline_submit.detect_ats(url) -> 'unknown'
  - inline_submit.resolve_role(...) raised "unsupported ATS URL"
  - the submit pipeline silently DROPPED the role despite it being submittable.

Concretely stranded: Dealpath 2454 (was blank, stale 'manual-apply' flag) and
Lob 2625 (block_reason=gh-embed-bounce-company-wrapper). Fix adds the verified
hosts (slugs confirmed live via boards-api id-match) so detect_ats classifies
them as 'greenhouse_iframe'.

Pure functions only; no Playwright / no network in the test.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "adapters"))

import greenhouse_iframe as G  # noqa: E402


class HostMapCohortTests(unittest.TestCase):
    # host -> (expected gh slug, a representative wrapper URL carrying gh_jid)
    CASES = {
        "dealpath.com": ("dealpath", "https://www.dealpath.com/job-post/?gh_jid=7947073"),
        "lob.com": ("lob", "https://www.lob.com/careers?gh_jid=4711111"),
        "careers.roblox.com": ("roblox", "https://careers.roblox.com/jobs/123?gh_jid=6000001"),
        "pubmatic.com": ("pubmatic", "https://pubmatic.com/careers/?gh_jid=7000002"),
        "videoamp.com": ("videoamp", "https://www.videoamp.com/careers/?gh_jid=5500003"),
    }

    def test_host_to_gh_slug_resolves_added_hosts(self):
        for host, (slug, url) in self.CASES.items():
            with self.subTest(host=host):
                self.assertEqual(G.host_to_gh_slug(url), slug)

    def test_www_prefix_normalized(self):
        # www. prefix must normalize to the bare host entry.
        self.assertEqual(
            G.host_to_gh_slug("https://www.dealpath.com/job-post/?gh_jid=7947073"),
            "dealpath",
        )

    def test_extract_gh_jid_still_works_on_wrapper(self):
        self.assertEqual(
            G.extract_gh_jid("https://www.dealpath.com/job-post/?gh_jid=7947073"),
            "7947073",
        )

    def test_unknown_host_still_returns_none(self):
        # Guard: an unrelated host with a gh_jid param must NOT be claimed by the
        # static map (it should fall through to the boards-api token resolver).
        self.assertIsNone(
            G.host_to_gh_slug("https://totally-unknown-vendor-xyz.example/?gh_jid=999")
        )


class DetectAtsCohortTests(unittest.TestCase):
    """detect_ats() must classify the newly-mapped hosts as greenhouse_iframe."""

    def setUp(self):
        # inline_submit imports adapters at module load; import lazily so a
        # failure here is a clear test error, not a collection error.
        import inline_submit  # noqa: E402
        self.I = inline_submit

    def test_dealpath_detected_as_iframe(self):
        self.assertEqual(
            self.I.detect_ats("https://www.dealpath.com/job-post/?gh_jid=7947073"),
            "greenhouse_iframe",
        )

    def test_lob_detected_as_iframe(self):
        self.assertEqual(
            self.I.detect_ats("https://www.lob.com/careers?gh_jid=4711111"),
            "greenhouse_iframe",
        )

    def test_native_greenhouse_unaffected(self):
        self.assertEqual(
            self.I.detect_ats("https://boards.greenhouse.io/acme/jobs/123"),
            "greenhouse",
        )


if __name__ == "__main__":
    unittest.main()
