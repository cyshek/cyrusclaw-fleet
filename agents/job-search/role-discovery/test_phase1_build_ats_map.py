#!/usr/bin/env python3
"""Tests for _phase1_build_ats_map.py — the stage-3a2 company->ATS map builder.

Guards the 2026-06-11 fixes:
  - company-selection SQL must include the SAME statuses the brute resolver
    targets (incl. 'manual-apply'/'queued'), else stranded companies never get
    mapped (the original NO-ATS-for-everything bug).
  - companies.yaml matching must be NORMALIZED (case/punct/suffix-insensitive),
    so 'Docusign'->'DocuSign', 'Gamma Reality Inc.'->'Gamma' resolve from yaml
    without a live HTTP probe.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _phase1_build_ats_map as p1  # noqa: E402


class StatusCoverageTests(unittest.TestCase):
    def test_resolvable_statuses_match_brute_resolver(self):
        import linkedin_stranded_brute_resolver as brute
        # The map builder MUST cover every status the resolver will look up.
        self.assertEqual(set(p1.RESOLVABLE_STATUSES),
                         set(brute.RESOLVABLE_STATUSES))
        self.assertIn("manual-apply", p1.RESOLVABLE_STATUSES)
        self.assertIn("queued", p1.RESOLVABLE_STATUSES)


class CompanySelectionTests(unittest.TestCase):
    """The builder's main() SELECT must pick up manual-apply/queued LinkedIn
    rows, not just status in ('','blocked')."""

    def _make_db(self, tmpdir: Path) -> Path:
        db = tmpdir / "tracker.db"
        con = sqlite3.connect(str(db))
        con.executescript(
            """
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY, company TEXT, role TEXT,
                app_url TEXT, status TEXT, applied_by TEXT
            );
            """
        )
        con.executemany(
            "INSERT INTO roles (id, company, role, app_url, status, applied_by) "
            "VALUES (?,?,?,?,?,?)",
            [
                (1, "AlphaCo", "PM", "https://www.linkedin.com/jobs/view/1", "manual-apply", None),
                (2, "BetaCo", "PM", "https://www.linkedin.com/jobs/view/2", "queued", None),
                (3, "GammaCo", "PM", "https://www.linkedin.com/jobs/view/3", "blocked", None),
                (4, "DeltaCo", "PM", "https://www.linkedin.com/jobs/view/4", "", None),
                # excluded: applied_by set
                (5, "EpsCo", "PM", "https://www.linkedin.com/jobs/view/5", "manual-apply", "x"),
                # excluded: non-linkedin
                (6, "ZetaCo", "PM", "https://jobs.ashbyhq.com/zeta/x", "manual-apply", None),
                # excluded: closed
                (7, "EtaCo", "PM", "https://www.linkedin.com/jobs/view/7", "closed", None),
            ],
        )
        con.commit()
        con.close()
        return db

    def test_select_covers_manual_apply_and_queued(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            db = self._make_db(tdp)
            out = tdp / "_map.json"
            # Point the module's paths at the tmp fixtures; stub probing + yaml.
            with patch.object(p1, "DB", db), \
                 patch.object(p1, "OUT", out), \
                 patch.object(p1, "COMPANIES_YAML", HERE / "companies.yaml"), \
                 patch.object(p1, "probe_one_company",
                              lambda name: {"company": name, "ats": "UNKNOWN",
                                            "reason": "stubbed"}):
                rc = p1.main()
            self.assertEqual(rc, 0)
            import json
            mapping = json.loads(out.read_text())["mapping"]
            got = set(mapping.keys())
            self.assertEqual(got, {"AlphaCo", "BetaCo", "GammaCo", "DeltaCo"},
                             "manual-apply/queued/blocked/'' linkedin rows must be "
                             "selected; applied_by/non-linkedin/closed excluded. got=%r" % got)


class NormalizedYamlMatchTests(unittest.TestCase):
    """A stranded company whose name differs from companies.yaml only by
    case/punctuation/suffix must still hit the yaml entry (no HTTP probe)."""

    def _make_db(self, tmpdir: Path, company: str) -> Path:
        db = tmpdir / "tracker.db"
        con = sqlite3.connect(str(db))
        con.executescript(
            "CREATE TABLE roles (id INTEGER PRIMARY KEY, company TEXT, role TEXT, "
            "app_url TEXT, status TEXT, applied_by TEXT);"
        )
        con.execute(
            "INSERT INTO roles (id, company, role, app_url, status, applied_by) "
            "VALUES (1, ?, 'PM', 'https://www.linkedin.com/jobs/view/1', 'manual-apply', NULL)",
            (company,),
        )
        con.commit()
        con.close()
        return db

    def test_case_punct_variant_hits_yaml(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            yml = tdp / "companies.yaml"
            yml.write_text(
                "companies:\n"
                "  - name: DocuSign\n"
                "    adapter: smartrecruiters\n"
                "    slug: docusign\n"
            )
            db = self._make_db(tdp, "Docusign")  # lower-case 's'
            out = tdp / "_map.json"

            def _boom(name):
                raise AssertionError(
                    "probe_one_company called for %r -> normalized yaml match "
                    "should have handled it without a probe" % name)

            with patch.object(p1, "DB", db), \
                 patch.object(p1, "OUT", out), \
                 patch.object(p1, "COMPANIES_YAML", yml), \
                 patch.object(p1, "probe_one_company", _boom):
                rc = p1.main()
            self.assertEqual(rc, 0)
            import json
            entry = json.loads(out.read_text())["mapping"]["Docusign"]
            self.assertEqual(entry["ats"], "smartrecruiters")
            self.assertEqual(entry["slug"], "docusign")
            self.assertEqual(entry["source"], "yaml")


if __name__ == "__main__":
    unittest.main()
