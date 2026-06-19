#!/usr/bin/env python3
"""Tests for the Eightfold + gh_jid-wrapper JD fetchers (added 2026-06-08).

Covers the pure URL-parsing / token-derivation helpers and the network
fetchers (mocked) that unblock the previously-unclassifiable cohort:
  - Netflix Eightfold (explore.jobs.netflix.net/careers/job/<id>)
  - gh_jid wrappers on employer domains (Datadog/Okta/FanDuel/Dealpath/Credera)

These rows used to fall to fetch_jd_generic and return 0 chars ("JD body too
short"), so they could never be classified and were stuck in the open queue.
"""
import unittest
from unittest import mock

import jd_llm_classifier as J


class _FakeResp:
    def __init__(self, status=200, json_data=None, text=""):
        self.status_code = status
        self._json = json_data if json_data is not None else {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


# --------------------------------------------------------------------------
# gh_jid pure helpers
# --------------------------------------------------------------------------
class TestGhJidHelpers(unittest.TestCase):
    def test_parse_gh_jid(self):
        self.assertEqual(
            J._gh_jid_from_url("https://careers.datadoghq.com/detail/7982288/?gh_jid=7982288"),
            "7982288")
        self.assertEqual(
            J._gh_jid_from_url("https://www.harness.io/x?gh_jid=5088981007&gh_jid=5088981007"),
            "5088981007")

    def test_parse_gh_jid_none(self):
        self.assertIsNone(J._gh_jid_from_url("https://www.uber.com/careers/list/147863/"))
        self.assertIsNone(J._gh_jid_from_url(""))
        self.assertIsNone(J._gh_jid_from_url(None))

    def test_token_candidates_company_first(self):
        toks = J._gh_token_candidates("Datadog", "https://careers.datadoghq.com/x?gh_jid=1")
        # company-derived 'datadog' must be tried before the host label 'datadoghq'
        self.assertEqual(toks[0], "datadog")
        self.assertIn("datadoghq", toks)

    def test_token_candidates_compound_name(self):
        toks = J._gh_token_candidates("Gamma Reality Inc.", "https://x.com?gh_jid=1")
        self.assertIn("gammarealityinc", toks)
        self.assertIn("gammareality", toks)   # corp suffix stripped
        self.assertIn("gamma", toks)           # first word

    def test_token_candidates_dedup(self):
        toks = J._gh_token_candidates("Okta", "https://www.okta.com?gh_jid=1")
        self.assertEqual(len(toks), len(set(toks)))
        self.assertIn("okta", toks)


# --------------------------------------------------------------------------
# gh_jid fetcher (mocked network)
# --------------------------------------------------------------------------
class TestFetchGhJid(unittest.TestCase):
    def test_first_token_match_wins(self):
        url = "https://careers.datadoghq.com/detail/7982288/?gh_jid=7982288"
        payload = {"id": 7982288, "title": "Product Manager II",
                   "content": "<p>Do PM things.</p>"}
        with mock.patch.object(J, "_http_get",
                               return_value=_FakeResp(200, payload)) as g:
            out = J.fetch_jd_greenhouse_by_jid(url, "Datadog")
        self.assertIn("Product Manager II", out)
        self.assertIn("Do PM things.", out)
        # first candidate token = 'datadog'
        self.assertIn("/boards/datadog/jobs/7982288", g.call_args_list[0].args[0])

    def test_skips_404_token_then_matches(self):
        # Mirrors the real Datadog case: company token 'datadog' 404s on a board
        # that doesn't exist under that exact slug, then the distinct host label
        # 'datadoghq' resolves.
        url = "https://careers.datadoghq.com/x?gh_jid=9990"

        def fake_get(api, **kw):
            if "/boards/datadog/jobs/9990" in api:
                return _FakeResp(404, {"status": 404, "error": "not found"})
            return _FakeResp(200, {"id": 9990, "title": "PM", "content": "<p>hi</p>"})

        with mock.patch.object(J, "_http_get", side_effect=fake_get):
            out = J.fetch_jd_greenhouse_by_jid(url, "Datadog")
        self.assertIn("PM", out)

    def test_id_mismatch_rejected(self):
        url = "https://x.com/y?gh_jid=111"
        # token resolves but returns a DIFFERENT job id -> must not be accepted
        with mock.patch.object(J, "_http_get",
                               return_value=_FakeResp(200, {"id": 222, "title": "X",
                                                            "content": "<p>z</p>"})):
            with self.assertRaises(ValueError):
                J.fetch_jd_greenhouse_by_jid(url, "Xco")

    def test_no_gh_jid_raises(self):
        with self.assertRaises(ValueError):
            J.fetch_jd_greenhouse_by_jid("https://x.com/no-id", "Xco")

    def test_dispatch_routes_gh_jid_when_not_greenhouse_host(self):
        url = "https://www.fanduel.careers/open-positions?gh_jid=7954862"
        payload = {"id": 7954862, "title": "PM Poker", "content": "<p>cards</p>"}
        with mock.patch.object(J, "_http_get",
                               return_value=_FakeResp(200, payload)):
            ats, txt = J.detect_and_fetch(url, "FanDuel")
        self.assertEqual(ats, "greenhouse-jid")
        self.assertIn("PM Poker", txt)


# --------------------------------------------------------------------------
# Eightfold
# --------------------------------------------------------------------------
class TestEightfold(unittest.TestCase):
    def test_parse_url(self):
        self.assertEqual(
            J._parse_eightfold_url("https://explore.jobs.netflix.net/careers/job/790316232735"),
            ("netflix", "790316232735"))

    def test_parse_url_rejects_non_eightfold(self):
        self.assertIsNone(J._parse_eightfold_url("https://boards.greenhouse.io/foo/jobs/123"))
        self.assertIsNone(J._parse_eightfold_url("https://explore.jobs.netflix.net/careers/"))

    def test_fetch_builds_api_and_extracts_body(self):
        url = "https://explore.jobs.netflix.net/careers/job/790316232735"
        payload = {"name": "Product Manager, Plans Innovation",
                   "location": "Los Gatos,California,United States of America",
                   "job_description": "<p>Entertain the world.</p>"}
        with mock.patch.object(J, "_http_get",
                               return_value=_FakeResp(200, payload)) as g:
            out = J.fetch_jd_eightfold(url)
        api = g.call_args.args[0]
        self.assertIn("/api/apply/v2/jobs/790316232735", api)
        self.assertIn("domain=netflix.com", api)
        self.assertIn("Product Manager, Plans Innovation", out)
        self.assertIn("Entertain the world.", out)

    def test_fetch_falls_back_to_custom_jd(self):
        url = "https://explore.jobs.netflix.net/careers/job/790315472265"
        payload = {"name": "X", "custom_JD": "<p>custom body</p>"}  # no job_description
        with mock.patch.object(J, "_http_get",
                               return_value=_FakeResp(200, payload)):
            out = J.fetch_jd_eightfold(url)
        self.assertIn("custom body", out)

    def test_dispatch_routes_eightfold(self):
        url = "https://explore.jobs.netflix.net/careers/job/790316232735"
        payload = {"name": "TPM", "job_description": "<p>tpm work</p>"}
        with mock.patch.object(J, "_http_get",
                               return_value=_FakeResp(200, payload)):
            ats, txt = J.detect_and_fetch(url, "Netflix")
        self.assertEqual(ats, "eightfold")
        self.assertIn("tpm work", txt)


if __name__ == "__main__":
    unittest.main()
