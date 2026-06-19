#!/usr/bin/env python3
"""Unit tests for chain_005 P5: inline_submit.py URL-liveness HEAD probe.

Network-mocked. No browser, no tracker mutation.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inline_submit as isub  # noqa: E402


def _mk_head_resp(status):
    m = MagicMock()
    m.status_code = status
    return m


def _mk_get_resp(status, body=b""):
    m = MagicMock()
    m.status_code = status
    m.content = body
    raw = MagicMock()
    raw.read = MagicMock(return_value=body)
    m.raw = raw
    m.close = MagicMock(return_value=None)
    return m


class TestHeadProbeClassification(unittest.TestCase):
    def test_404_is_dead(self):
        with patch.object(isub.requests, "head", return_value=_mk_head_resp(404)):
            result = isub.probe_url_liveness("https://example.com/job/123")
        self.assertFalse(result["alive"])
        self.assertEqual(result["status"], 404)
        self.assertEqual(result["reason"], "http-404")

    def test_410_is_dead(self):
        with patch.object(isub.requests, "head", return_value=_mk_head_resp(410)):
            result = isub.probe_url_liveness("https://example.com/job/123")
        self.assertFalse(result["alive"])
        self.assertEqual(result["status"], 410)

    def test_999_linkedin_is_alive(self):
        """LinkedIn anti-bot returns 999 — must fall through, not be killed."""
        with patch.object(isub.requests, "head", return_value=_mk_head_resp(999)):
            result = isub.probe_url_liveness("https://www.linkedin.com/jobs/view/123")
        self.assertTrue(result["alive"])
        self.assertEqual(result["reason"], "linkedin-999")

    def test_200_plain_is_alive(self):
        with patch.object(isub.requests, "head", return_value=_mk_head_resp(200)), \
             patch.object(isub.requests, "get", return_value=_mk_get_resp(200, b"<html>job content</html>")):
            result = isub.probe_url_liveness("https://example.com/job/123")
        self.assertTrue(result["alive"])
        self.assertEqual(result["status"], 200)

    def test_200_with_soft_404_body_is_dead(self):
        body = b"<html><h1>Page Not Found</h1></html>"
        with patch.object(isub.requests, "head", return_value=_mk_head_resp(200)), \
             patch.object(isub.requests, "get", return_value=_mk_get_resp(200, body)):
            result = isub.probe_url_liveness("https://example.com/job/dead")
        self.assertFalse(result["alive"])
        self.assertEqual(result["reason"], "soft-404-body")
        self.assertEqual(result["body_marker"], "page not found")

    def test_200_with_position_closed_body_is_dead(self):
        body = b"<html>This position has been closed.</html>"
        with patch.object(isub.requests, "head", return_value=_mk_head_resp(200)), \
             patch.object(isub.requests, "get", return_value=_mk_get_resp(200, body)):
            result = isub.probe_url_liveness("https://example.com/job/x")
        self.assertFalse(result["alive"])
        self.assertEqual(result["body_marker"], "position has been closed")

    def test_network_error_is_treated_as_alive(self):
        """Prefer false-negative over killing a viable role on a flaky probe."""
        with patch.object(isub.requests, "head", side_effect=ConnectionError("dns")):
            result = isub.probe_url_liveness("https://example.com/job/x")
        self.assertTrue(result["alive"])
        self.assertIn("probe-error", result["reason"])

    def test_empty_url_is_skipped_alive(self):
        result = isub.probe_url_liveness("")
        self.assertTrue(result["alive"])
        self.assertEqual(result["reason"], "no-url-skip")


class TestHeadProbeIntegration(unittest.TestCase):
    """End-to-end: prep_role should short-circuit to CLOSED on a dead URL,
    without calling JD fetch / dryrun / bullet_rewriter."""

    def setUp(self):
        # Use a temp workdir so we don't pollute applications/submitted/.
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix="head-probe-test-")
        self.orig_submitted = isub.SUBMITTED_DIR
        isub.SUBMITTED_DIR = Path(self.tmpdir)

    def tearDown(self):
        isub.SUBMITTED_DIR = self.orig_submitted
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dead_url_short_circuits_before_jd_fetch(self):
        role = {
            "role_id": 0,  # 0 means slug-driven, no DB write
            "slug": "test-deadco-12345",
            "company": "DeadCo", "role": "PM",
            "url": "https://boards.greenhouse.io/deadco/jobs/12345",
            "ats": "greenhouse", "gh_org": "deadco", "gh_jid": "12345",
        }
        # Mock HEAD to return 404; assert fetch_jd is never called.
        with patch.object(isub.requests, "head", return_value=_mk_head_resp(404)), \
             patch.object(isub, "fetch_jd") as fake_fetch:
            res = isub.prep_role(role, dry_run=True)
        self.assertTrue(res["ok"])
        self.assertTrue(res.get("closed"))
        self.assertEqual(res["head_probe"]["status"], 404)
        fake_fetch.assert_not_called()
        # STATUS.md should record the closure
        status_p = Path(res["workdir"]) / "STATUS.md"
        self.assertTrue(status_p.exists())
        content = status_p.read_text()
        self.assertIn("CLOSED-URL-DEAD", content)
        self.assertIn("404", content)

    def test_skip_head_probe_flag_bypasses_check(self):
        role = {
            "role_id": 0, "slug": "test-skipprobe-99999",
            "company": "X", "role": "PM",
            "url": "https://boards.greenhouse.io/x/jobs/99999",
            "ats": "greenhouse", "gh_org": "x", "gh_jid": "99999",
        }
        # Even if HEAD would say 404, skip_head_probe=True should fall through
        # to the normal JD-fetch path (which we let raise to confirm).
        with patch.object(isub.requests, "head", return_value=_mk_head_resp(404)), \
             patch.object(isub, "fetch_jd", side_effect=RuntimeError("fetch-was-called")):
            res = isub.prep_role(role, dry_run=True, skip_head_probe=True)
        # prep_role should have proceeded to fetch (and aborted at jd-fetch)
        self.assertFalse(res["ok"])
        self.assertEqual(res["phase_failed"], "jd-fetch")
        self.assertIn("fetch-was-called", res.get("error", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
