#!/usr/bin/env python3
"""Unit tests for linkedin_resolver_pipeline (offline / network-mocked)."""
import sys
import unittest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import linkedin_resolver_pipeline as lp  # noqa: E402


class FakeResp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


# Fixture HTML snippets (3 cases)
HTML_WITH_GREENHOUSE = """
<html><body>
<a class="apply-button" href="https://boards.greenhouse.io/plaid/jobs/4567890">
  Apply on company site
</a>
</body></html>
"""

HTML_AUTH_WALL = """
<html><body>
<div class="contextual-sign-in-modal">Sign in to view this job</div>
<button>Easy Apply</button>
</body></html>
"""

HTML_EASY_APPLY_ONLY = """
<html><body>
<button class="jobs-apply-button">Easy Apply</button>
<div class="description">Just a JD body, no off-site link.</div>
</body></html>
"""


class TestTactics(unittest.TestCase):
    def test_extract_ats_urls_greenhouse(self):
        urls = lp.extract_ats_urls_from_html(HTML_WITH_GREENHOUSE)
        self.assertEqual(len(urls), 1)
        self.assertIn("boards.greenhouse.io/plaid/jobs/4567890", urls[0])

    def test_extract_ats_urls_none_in_authwall(self):
        self.assertEqual(lp.extract_ats_urls_from_html(HTML_AUTH_WALL), [])

    def test_extract_ats_urls_none_in_easy_apply(self):
        self.assertEqual(lp.extract_ats_urls_from_html(HTML_EASY_APPLY_ONLY), [])

    def test_title_match_high_confidence(self):
        # Identical titles -> 1.0; substring match -> >=0.85
        self.assertEqual(lp.title_match("Product Manager", "Product Manager"), 1.0)
        self.assertGreaterEqual(
            lp.title_match("Product Manager", "Product Manager, Payments"), 0.7
        )

    def test_title_match_low(self):
        score = lp.title_match("Cloud Architect", "Frontend Engineer")
        self.assertLess(score, 0.5)

    def test_company_slug_candidates(self):
        cands = lp.company_slug_candidates("Plaid Inc.")
        self.assertIn("plaid", cands)

    def test_derive_source_key_greenhouse(self):
        sk = lp.derive_source_key("https://boards.greenhouse.io/plaid/jobs/4567890")
        self.assertEqual(sk, "greenhouse:plaid:4567890")

    def test_derive_source_key_ashby(self):
        sk = lp.derive_source_key("https://jobs.ashbyhq.com/snowflake/3f8a210b-9003-489a-91c8-e3f0abeee1fc")
        self.assertTrue(sk.startswith("ashby:snowflake:"))

    def test_derive_source_key_workday(self):
        sk = lp.derive_source_key(
            "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US-CA/Sales-Engineer_JR12345")
        self.assertTrue(sk.startswith("workday:nvidia:"))


class TestResolveOneNetworkMocked(unittest.TestCase):
    """Three LinkedIn URL fixtures: resolvable, auth-walled, easy-apply-only."""

    def setUp(self):
        # Empty yaml + roles index so we exercise tactics 2 + 4
        self.yaml_cos: list[dict] = []
        self.roles_idx: list[dict] = []

    def test_resolvable_via_linkedin_fetch(self):
        """Tactic 2 fires when LinkedIn HTML embeds an ATS off-site URL."""
        def fake_get(url, timeout=15):
            if "linkedin.com" in url:
                return FakeResp(200, HTML_WITH_GREENHOUSE)
            return FakeResp(404, "")
        with patch.object(lp, "http_get", side_effect=fake_get):
            url, info, reasons = lp.resolve_one(
                "Plaid", "Product Manager",
                "https://www.linkedin.com/jobs/view/1111",
                self.yaml_cos, self.roles_idx,
            )
        self.assertIsNotNone(url)
        self.assertIn("greenhouse.io", url)
        self.assertIn("linkedin-jd", info)

    def test_authwall_unresolvable(self):
        """LinkedIn returns auth-wall HTML, careers probe also fails."""
        def fake_get(url, timeout=15):
            if "linkedin.com" in url:
                return FakeResp(200, HTML_AUTH_WALL)
            # All careers probes 404
            return FakeResp(404, "")
        with patch.object(lp, "http_get", side_effect=fake_get):
            url, info, reasons = lp.resolve_one(
                "ObscureCo", "Senior Engineer",
                "https://www.linkedin.com/jobs/view/2222",
                self.yaml_cos, self.roles_idx,
            )
        self.assertIsNone(url)
        # Should have reasons logged from each tactic that ran
        joined = " ".join(reasons)
        self.assertIn("linkedin-no-ats", joined)

    def test_easy_apply_only_unresolvable(self):
        """LinkedIn HTML has Easy Apply only, no off-site URL anywhere."""
        def fake_get(url, timeout=15):
            if "linkedin.com" in url:
                return FakeResp(200, HTML_EASY_APPLY_ONLY)
            return FakeResp(404, "")
        with patch.object(lp, "http_get", side_effect=fake_get):
            url, info, reasons = lp.resolve_one(
                "NoCareersCo", "PM",
                "https://www.linkedin.com/jobs/view/3333",
                self.yaml_cos, self.roles_idx,
            )
        self.assertIsNone(url)

    def test_yaml_match_short_circuits(self):
        """Tactic 1 fires when companies.yaml + crawl-output has a match."""
        yaml_cos = [{"name": "Plaid", "adapter": "greenhouse", "slug": "plaid"}]
        roles_idx = [{
            "company": "Plaid",
            "title": "Product Manager",
            "url": "https://boards.greenhouse.io/plaid/jobs/9999",
        }]
        # No HTTP call should be needed; mock to fail if invoked
        with patch.object(lp, "http_get", side_effect=AssertionError("should not call HTTP")):
            url, info, _ = lp.resolve_one(
                "Plaid", "Product Manager",
                "https://www.linkedin.com/jobs/view/4444",
                yaml_cos, roles_idx,
            )
        self.assertEqual(url, "https://boards.greenhouse.io/plaid/jobs/9999")
        self.assertIn("yaml", info)


class TestDryRunDoesNotMutate(unittest.TestCase):
    def test_dry_run_default(self):
        """Default (no --apply) must not write to DB."""
        # Create a temp tracker.db with a single LinkedIn row
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "tracker.db"
            con = sqlite3.connect(db_path)
            con.execute("""
                CREATE TABLE roles (
                    id INTEGER PRIMARY KEY,
                    source_key TEXT, company TEXT, role TEXT,
                    app_url TEXT, status TEXT, applied_by TEXT,
                    agent_notes TEXT
                )
            """)
            con.execute("""INSERT INTO roles
                (id, source_key, company, role, app_url, status, applied_by, agent_notes)
                VALUES (1, 'linkedin:5555', 'Plaid', 'Product Manager',
                        'https://www.linkedin.com/jobs/view/5555', '', NULL, NULL)""")
            con.commit()
            con.close()

            # Mock so tactic-2 would succeed if we were applying
            with patch.object(lp, "http_get",
                              side_effect=lambda u, timeout=15: FakeResp(200, HTML_WITH_GREENHOUSE)):
                rc = lp.main(["--db", str(db_path), "--quiet"])
            self.assertEqual(rc, 0)

            # Verify DB unchanged
            con = sqlite3.connect(db_path)
            row = con.execute("SELECT app_url, source_key, agent_notes FROM roles WHERE id=1").fetchone()
            con.close()
            self.assertEqual(row[0], "https://www.linkedin.com/jobs/view/5555")
            self.assertEqual(row[1], "linkedin:5555")
            self.assertIsNone(row[2])


if __name__ == "__main__":
    unittest.main()
