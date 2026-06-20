"""Unit tests for greenhouse_csp_blocklist.yaml + inline_submit short-circuit.

Three cases:
  1. Slug in blocklist  -> prep_role short-circuits, writes
     PREP-READY-MANUAL-CSP-CAPTCHA, sets tracker.prep_status='manual_ready'.
  2. Slug NOT in blocklist (e.g. 'airtable') -> short-circuit does NOT fire
     (we verify by checking that load_gh_csp_blocklist does not contain it).
  3. Slug derivable from app_url -> parse_gh_url + detect_ats yield the same
     slug we store in the blocklist YAML.

Tests are self-contained: they import inline_submit and operate against a
tempfile sqlite DB so the real tracker.db is never touched.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inline_submit  # type: ignore  # noqa: E402


class TestGreenhouseCspBlocklist(unittest.TestCase):
    def setUp(self):
        self.blocklist = inline_submit.load_gh_csp_blocklist()
        # tempfile sqlite db with the minimal roles columns we touch
        fd, self.db_path = tempfile.mkstemp(prefix="tracker-test-", suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE roles (id INTEGER PRIMARY KEY, company TEXT, role TEXT, "
            "app_url TEXT, prep_status TEXT, prep_path TEXT, agent_notes TEXT, "
            "applied_by TEXT, applied_on TEXT, status TEXT)"
        )
        conn.execute(
            "INSERT INTO roles (id, company, role, app_url, agent_notes) VALUES "
            "(9001, 'Similarweb', 'PM', "
            "'https://job-boards.greenhouse.io/similarweb/jobs/7743380', "
            "'pre-existing-note')"
        )
        conn.commit()
        conn.close()
        # Point inline_submit at our tempfile DB
        self._orig_db = inline_submit.DB_PATH
        inline_submit.DB_PATH = Path(self.db_path)
        # Sandbox the SUBMITTED_DIR so we don't dirty the real one
        self._orig_submitted = inline_submit.SUBMITTED_DIR
        self._tmp_submitted = Path(tempfile.mkdtemp(prefix="submitted-test-"))
        inline_submit.SUBMITTED_DIR = self._tmp_submitted

    def tearDown(self):
        inline_submit.DB_PATH = self._orig_db
        inline_submit.SUBMITTED_DIR = self._orig_submitted
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
        import shutil
        shutil.rmtree(self._tmp_submitted, ignore_errors=True)

    # ---- Case 1: slug in blocklist short-circuits prep ---------------------
    def test_slug_in_blocklist_short_circuits(self):
        self.assertIn("similarweb", self.blocklist,
                      "similarweb must be in greenhouse_csp_blocklist.yaml")
        role = {
            "role_id": 9001,
            "company": "Similarweb",
            "role": "PM",
            "loc": "Remote",
            "url": "https://job-boards.greenhouse.io/similarweb/jobs/7743380",
            "ats": "greenhouse",
            "gh_org": "similarweb",
            "gh_jid": "7743380",
            "slug": "similarweb-7743380",
            "flags": "",
        }
        res = inline_submit.prep_role(role, dry_run=False)
        self.assertTrue(res["ok"])
        self.assertTrue(res.get("csp_blocklist_skip"))
        status_md = (Path(res["workdir"]) / "STATUS.md").read_text()
        self.assertIn("PREP-READY-MANUAL-CSP-CAPTCHA", status_md)
        # Tracker mutation
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT prep_status, prep_path, agent_notes FROM roles WHERE id=9001"
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "manual_ready")
        self.assertEqual(row[1], str(Path(res["workdir"])))
        self.assertIn("CSP-CAPTCHA-BLOCK-BLOCKLIST", row[2])
        self.assertIn("pre-existing-note", row[2])  # preserved

    # ---- Case 2: slug NOT in blocklist -------------------------------------
    def test_slug_not_in_blocklist(self):
        self.assertNotIn("airtable", self.blocklist)
        self.assertNotIn("discord", self.blocklist)
        self.assertNotIn("anthropic", self.blocklist)

    # ---- Case 3: slug derivable from app_url -------------------------------
    def test_slug_derivable_from_app_url(self):
        cases = {
            "https://job-boards.greenhouse.io/similarweb/jobs/7743380": "similarweb",
            "https://job-boards.greenhouse.io/hackerrank/jobs/7482134": "hackerrank",
            "https://job-boards.greenhouse.io/ascend21/jobs/5215133008": "ascend21",
        }
        for url, expected_slug in cases.items():
            parsed = inline_submit.parse_gh_url(url)
            self.assertIsNotNone(parsed, f"failed to parse {url}")
            self.assertEqual(parsed[0], expected_slug)
            self.assertEqual(inline_submit.detect_ats(url), "greenhouse")
            self.assertIn(expected_slug, self.blocklist,
                          f"{expected_slug} (derived from {url}) must be in blocklist")


if __name__ == "__main__":
    unittest.main()
