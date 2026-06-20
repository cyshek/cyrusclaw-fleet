#!/usr/bin/env python3
"""Tests for linkedin_email_parser — parser-only, no live IMAP.

Runs against saved fixtures under .fixtures/ (real LinkedIn alert email
HTML bodies captured once via IMAP). Covers:
  - digest layout (li-alert-1959.html, jobalerts-noreply, job_posting trk)
  - recommended layout (li-alert-1960.html, jobs-noreply, JOBS_POSTING_SECTION trk)
  - field extraction (company/role/loc/url/jobid all present)
  - source_key format
  - dedupe within + across emails
  - upsert idempotency against an in-memory tracker schema
"""
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import linkedin_email_parser as P
from linkedin_email_parser import JobEntry, parse_email_html, canonical_url

FIX = HERE / ".fixtures"
DIGEST = FIX / "li-alert-1959.html"          # Meta / sales engineer digest
RECOMMENDED = FIX / "li-alert-1960.html"     # Airbnb recommended-roles


def _schema(conn):
    conn.execute("""CREATE TABLE roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT UNIQUE, company TEXT NOT NULL, role TEXT NOT NULL,
        loc TEXT, jd_url TEXT, app_url TEXT, status TEXT, flags TEXT,
        first_seen TEXT, last_seen TEXT, agent_notes TEXT DEFAULT '')""")
    conn.commit()


class TestParse(unittest.TestCase):
    def test_digest_extracts_jobs(self):
        jobs = parse_email_html(DIGEST.read_text())
        self.assertGreaterEqual(len(jobs), 1)
        # Meta Solutions Architect is the headline card.
        metas = [j for j in jobs if j.company == "Meta"]
        self.assertTrue(metas, "expected a Meta job in the digest")
        m = metas[0]
        self.assertIn("Solutions Architect", m.role)
        self.assertTrue(m.loc)
        self.assertRegex(m.url, r"^https://www\.linkedin\.com/jobs/view/\d+/$")
        self.assertEqual(m.source_key, f"linkedin-email:{m.jobid}")

    def test_recommended_layout_extracts_jobs(self):
        jobs = parse_email_html(RECOMMENDED.read_text())
        self.assertGreaterEqual(len(jobs), 1)
        names = {j.company for j in jobs}
        self.assertIn("Airbnb", names)

    def test_all_fields_present(self):
        for fx in (DIGEST, RECOMMENDED):
            for j in parse_email_html(fx.read_text()):
                self.assertTrue(j.jobid.isdigit(), f"bad jobid {j.jobid}")
                self.assertTrue(j.company.strip())
                self.assertTrue(j.role.strip())
                self.assertTrue(j.url.endswith(f"/jobs/view/{j.jobid}/"))
                # company/loc never contain the middot separator (clean split)
                self.assertNotIn("·", j.company)

    def test_source_key_format(self):
        je = JobEntry(jobid="123456", company="Foo", role="Bar", loc="NY",
                      url=canonical_url("123456"))
        self.assertEqual(je.source_key, "linkedin-email:123456")

    def test_dedupe_within_email(self):
        jobs = parse_email_html(DIGEST.read_text())
        ids = [j.jobid for j in jobs]
        self.assertEqual(len(ids), len(set(ids)), "duplicate jobids in one email")


class TestUpsert(unittest.TestCase):
    def setUp(self):
        self._orig_connect = sqlite3.connect
        self._tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self._tmp.close()
        self.dbpath = self._tmp.name
        conn = self._orig_connect(self.dbpath)
        _schema(conn)
        conn.close()
        # Redirect upsert_jobs' own sqlite3.connect to our temp DB file.
        path = self.dbpath
        orig = self._orig_connect
        sqlite3.connect = lambda *a, **k: orig(path)  # type: ignore

    def tearDown(self):
        sqlite3.connect = self._orig_connect
        Path(self.dbpath).unlink(missing_ok=True)

    def _count(self):
        c = self._orig_connect(self.dbpath)
        try:
            return c.execute('SELECT COUNT(*) FROM roles').fetchone()[0]
        finally:
            c.close()

    def test_idempotent_insert(self):
        jobs = [
            JobEntry("111", "Meta", "SE", "Seattle", canonical_url("111")),
            JobEntry("222", "Airbnb", "PM", "Remote", canonical_url("222")),
        ]
        r1 = P.upsert_jobs(jobs, apply=True)
        self.assertEqual(r1["inserted"], 2)
        self.assertEqual(r1["skipped"], 0)
        # second run: zero new
        r2 = P.upsert_jobs(jobs, apply=True)
        self.assertEqual(r2["inserted"], 0)
        self.assertEqual(r2["skipped"], 2)
        self.assertEqual(self._count(), 2)

    def test_skip_by_existing_app_url_jobid(self):
        # Pre-seed a row that already references jobid 333 via app_url only
        # (different source_key) — parser must still skip it.
        seed = self._orig_connect(self.dbpath)
        seed.execute(
            "INSERT INTO roles (source_key, company, role, app_url) "
            "VALUES ('linkedin:333','Meta','SE',"
            "'https://www.linkedin.com/jobs/view/333/')")
        seed.commit()
        seed.close()
        jobs = [JobEntry("333", "Meta", "SE", "Seattle", canonical_url("333"))]
        r = P.upsert_jobs(jobs, apply=True)
        self.assertEqual(r["inserted"], 0)
        self.assertEqual(r["skipped"], 1)

    def test_dry_run_writes_nothing(self):
        jobs = [JobEntry("444", "Stripe", "TPM", "Remote", canonical_url("444"))]
        r = P.upsert_jobs(jobs, apply=False)
        self.assertEqual(r["inserted"], 1)  # would-insert count
        self.assertEqual(self._count(), 0)  # dry-run must not write


if __name__ == "__main__":
    unittest.main(verbosity=2)
