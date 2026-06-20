#!/usr/bin/env python3
"""Unit tests for linkedin_authed_resolver (offline; browser/network mocked)."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import linkedin_authed_resolver as ar  # noqa: E402
import linkedin_resolver_pipeline as lp  # noqa: E402


# ---------------------------------------------------------------------------
# Fake browser driver — records calls, returns scripted responses.
# ---------------------------------------------------------------------------

class FakeDriver(ar.BrowserDriver):
    def __init__(self,
                 open_result=None,
                 classify_result=None,
                 scrape_result=None,
                 company_url=None,
                 click_result=None,
                 list_tabs_before=None,
                 list_tabs_after=None,
                 fail_open=False):
        self.open_result = open_result or {"targetId": "T1", "tabId": "t1"}
        self.classify_result = classify_result
        self.scrape_result = scrape_result
        self.company_url = company_url
        self.click_result = click_result or {"clicked": True}
        self.list_tabs_before = list_tabs_before or [{"targetId": "T1"}]
        self.list_tabs_after = list_tabs_after or [{"targetId": "T1"}]
        self.fail_open = fail_open
        self.tabs_calls = 0
        self.closed: list[str] = []
        self.opened: list[tuple[str, str]] = []
        self.eval_calls: list[tuple[str, str]] = []

    def open_tab(self, url, label):
        self.opened.append((url, label))
        if self.fail_open:
            return ar.BrowserResult({"error": "fake-open-failed"})
        return ar.BrowserResult(self.open_result)

    def close_tab(self, target_id):
        self.closed.append(target_id)

    def list_tabs(self):
        self.tabs_calls += 1
        return self.list_tabs_before if self.tabs_calls == 1 else self.list_tabs_after

    def evaluate(self, target_id, fn):
        self.eval_calls.append((target_id, fn[:60]))
        if "classify" in fn or "easy" in fn.lower() and "sign-up-modal" in fn:
            # the classify JS
            return self.classify_result
        if "html.match" in fn or "rx" in fn and "greenhouse" in fn:
            return self.scrape_result
        if "topcard" in fn or "company/" in fn:
            return self.company_url
        if "apply.click" in fn:
            return self.click_result
        # default: classify-shaped fallback for tests that use the real JS
        # constant directly
        if fn.strip().startswith("()") and "easy" in fn.lower():
            return self.classify_result
        return None

    def snapshot_text(self, target_id, max_chars=4000):
        return ""

    def click_ref(self, target_id, ref):
        return True


# ---------------------------------------------------------------------------
# URL pattern tests
# ---------------------------------------------------------------------------

class TestUrlPatterns(unittest.TestCase):
    def test_is_linkedin_jd_url_positive(self):
        self.assertTrue(ar.is_linkedin_jd_url("https://www.linkedin.com/jobs/view/1234"))
        self.assertTrue(ar.is_linkedin_jd_url("https://linkedin.com/jobs/view/foo-bar-9999"))

    def test_is_linkedin_jd_url_negative(self):
        self.assertFalse(ar.is_linkedin_jd_url(""))
        self.assertFalse(ar.is_linkedin_jd_url("https://linkedin.com/feed"))
        self.assertFalse(ar.is_linkedin_jd_url("https://boards.greenhouse.io/plaid/jobs/123"))

    def test_looks_like_ats_url(self):
        self.assertTrue(ar.looks_like_ats_url("https://boards.greenhouse.io/plaid/jobs/1"))
        self.assertTrue(ar.looks_like_ats_url("https://jobs.ashbyhq.com/openai/abc"))
        self.assertTrue(ar.looks_like_ats_url("https://rivian.wd5.myworkdayjobs.com/x"))
        self.assertTrue(ar.looks_like_ats_url("https://jobs.lever.co/asana/123"))
        self.assertTrue(ar.looks_like_ats_url("https://careers.oraclecloud.com/sites/CX/foo"))
        self.assertFalse(ar.looks_like_ats_url("https://www.linkedin.com/jobs/view/1"))
        self.assertFalse(ar.looks_like_ats_url(""))

    def test_extract_ats_urls_from_dom_blob(self):
        blob = """
            random text https://boards.greenhouse.io/plaid/jobs/4567890 more
            text https://jobs.ashbyhq.com/openai/abc-def
            ignore https://linkedin.com/feed
            also https://example.com/careers
        """
        urls = ar.extract_ats_urls_from_dom_blob(blob)
        self.assertEqual(len(urls), 2)
        self.assertTrue(any("greenhouse" in u for u in urls))
        self.assertTrue(any("ashbyhq" in u for u in urls))

    def test_score_ats_urls_by_company_prefers_match(self):
        urls = [
            "https://boards.greenhouse.io/somethingelse/jobs/1",
            "https://boards.greenhouse.io/plaid/jobs/9999",
        ]
        picked = ar.score_ats_urls_by_company(urls, "Plaid")
        self.assertEqual(picked, "https://boards.greenhouse.io/plaid/jobs/9999")

    def test_score_ats_urls_no_company_match_falls_back(self):
        urls = ["https://boards.greenhouse.io/foo/jobs/1"]
        # No company match → still returns the only URL.
        self.assertEqual(ar.score_ats_urls_by_company(urls, "Bar"), urls[0])
        self.assertIsNone(ar.score_ats_urls_by_company([], "Plaid"))


# ---------------------------------------------------------------------------
# Tactic 1 — apply button classification
# ---------------------------------------------------------------------------

class TestTacticApplyButton(unittest.TestCase):
    def test_easy_apply_detected(self):
        d = FakeDriver(classify_result={"kind": "easy-apply", "sample_text": "Easy Apply", "sample_classes": ""})
        row = (1, "Plaid", "PM", "https://www.linkedin.com/jobs/view/1", 200000)
        url, kind, info = ar.tactic_apply_button(d, "T1", row)
        self.assertIsNone(url)
        self.assertEqual(kind, "easy-apply")

    def test_sign_up_wall_detected(self):
        d = FakeDriver(classify_result={"kind": "sign-up-wall", "sample_text": "Apply", "sample_classes": "sign-up-modal__outlet"})
        row = (1, "Rivian", "TPM", "https://www.linkedin.com/jobs/view/1", 200000)
        url, kind, info = ar.tactic_apply_button(d, "T1", row)
        self.assertIsNone(url)
        self.assertEqual(kind, "sign-up-wall")

    def test_apply_direct_href_resolved(self):
        d = FakeDriver(classify_result={
            "kind": "apply",
            "sample_text": "Apply on company website",
            "sample_classes": "",
            "href": "https://boards.greenhouse.io/plaid/jobs/9999",
        })
        row = (1, "Plaid", "PM", "https://www.linkedin.com/jobs/view/1", 200000)
        url, kind, info = ar.tactic_apply_button(d, "T1", row)
        self.assertEqual(url, "https://boards.greenhouse.io/plaid/jobs/9999")
        self.assertEqual(kind, "resolved")
        self.assertIn("apply-direct-href", info)


# ---------------------------------------------------------------------------
# Tactic 2 — DOM scrape
# ---------------------------------------------------------------------------

class TestTacticDomScrape(unittest.TestCase):
    def test_dom_scrape_finds_company_match(self):
        d = FakeDriver(scrape_result=[
            "https://boards.greenhouse.io/plaid/jobs/9999",
            "https://boards.greenhouse.io/somethingelse/jobs/1",
        ])
        row = (1, "Plaid", "PM", "https://www.linkedin.com/jobs/view/1", None)
        url, info = ar.tactic_dom_scrape(d, "T1", row)
        self.assertEqual(url, "https://boards.greenhouse.io/plaid/jobs/9999")

    def test_dom_scrape_empty(self):
        d = FakeDriver(scrape_result=[])
        row = (1, "Plaid", "PM", "https://www.linkedin.com/jobs/view/1", None)
        url, info = ar.tactic_dom_scrape(d, "T1", row)
        self.assertIsNone(url)
        self.assertEqual(info, "dom-no-ats")


# ---------------------------------------------------------------------------
# Tactic 3 — company careers
# ---------------------------------------------------------------------------

class TestTacticCompanyCareers(unittest.TestCase):
    def test_no_company_url(self):
        d = FakeDriver(company_url=None)
        row = (1, "Plaid", "PM", "https://www.linkedin.com/jobs/view/1", None)
        url, info = ar.tactic_company_careers(d, "T1", row)
        self.assertIsNone(url)
        self.assertEqual(info, "no-company-url")

    def test_company_url_that_is_ats(self):
        d = FakeDriver(company_url="https://boards.greenhouse.io/plaid")
        row = (1, "Plaid", "PM", "https://www.linkedin.com/jobs/view/1", None)
        url, info = ar.tactic_company_careers(d, "T1", row)
        self.assertEqual(url, "https://boards.greenhouse.io/plaid")


# ---------------------------------------------------------------------------
# resolve_one_row — orchestration
# ---------------------------------------------------------------------------

class TestResolveOneRow(unittest.TestCase):
    def test_invalid_linkedin_url_short_circuits(self):
        d = FakeDriver()
        row = (1, "Plaid", "PM", "https://greenhouse.io/plaid/jobs/1", None)
        r = ar.resolve_one_row(d, row, [], [])
        self.assertEqual(r["kind"], "error")
        self.assertIn("not-a-linkedin-jd-url", r["reasons"])
        # Did NOT try to open a tab.
        self.assertEqual(d.opened, [])

    def test_easy_apply_path(self):
        d = FakeDriver(classify_result={"kind": "easy-apply", "sample_text": "Easy Apply", "sample_classes": ""})
        row = (1, "Plaid", "PM", "https://www.linkedin.com/jobs/view/1", None)
        r = ar.resolve_one_row(d, row, [], [], per_row_seconds=30)
        self.assertEqual(r["kind"], "easy-apply")
        # Tab opened and closed cleanly
        self.assertEqual(d.opened[0][0], "https://www.linkedin.com/jobs/view/1")
        self.assertIn("T1", d.closed)

    def test_browser_open_fail_falls_through_to_anonymous(self):
        d = FakeDriver(fail_open=True)
        row = (1, "Plaid", "PM", "https://www.linkedin.com/jobs/view/1", None)
        # Patch lp.resolve_one so we don't actually fetch.
        with patch.object(lp, "resolve_one", return_value=("https://boards.greenhouse.io/plaid/jobs/5", "yaml(...)", ["yaml(...)"])):
            r = ar.resolve_one_row(d, row, [], [], per_row_seconds=30)
        self.assertEqual(r["kind"], "resolved")
        self.assertIn("anonymous-fallback", r["tactic"])
        self.assertIn("greenhouse", r["ats_url"])

    def test_full_unresolved_chain(self):
        """All 4 tactics fail → unresolved with reasons collected from each."""
        d = FakeDriver(
            classify_result={"kind": "sign-up-wall", "sample_text": "Apply", "sample_classes": "sign-up-modal__outlet"},
            scrape_result=[],
            company_url=None,
        )
        row = (1, "ObscureCo", "Senior Engineer",
               "https://www.linkedin.com/jobs/view/2222", None)
        with patch.object(lp, "resolve_one", return_value=(None, None, ["yaml-near-miss"])):
            r = ar.resolve_one_row(d, row, [], [], per_row_seconds=30)
        self.assertEqual(r["kind"], "unresolved")
        joined = " ".join(r["reasons"])
        self.assertIn("anonymous-sign-up-wall", joined)
        self.assertIn("dom-no-ats", joined)
        self.assertIn("no-company-url", joined)
        self.assertIn("yaml-near-miss", joined)


# ---------------------------------------------------------------------------
# DB write helpers
# ---------------------------------------------------------------------------

def _mk_db(tmpdir: Path) -> Path:
    db = tmpdir / "tracker.db"
    con = sqlite3.connect(db)
    con.execute("""
        CREATE TABLE roles (
            id INTEGER PRIMARY KEY,
            source_key TEXT, company TEXT, role TEXT, level TEXT,
            loc TEXT, exp_req TEXT, jd_url TEXT, app_url TEXT,
            status TEXT, flags TEXT, applied_by TEXT, applied_on TEXT,
            cyrus_notes TEXT, first_seen TEXT, last_seen TEXT,
            posted_on TEXT, est_tc INTEGER, agent_notes TEXT
        )
    """)
    con.executemany("""
        INSERT INTO roles (id, source_key, company, role, app_url, status,
                           applied_by, flags, est_tc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (1, "linkedin:5555", "Plaid", "Product Manager",
         "https://www.linkedin.com/jobs/view/5555", "", None, "", 200000),
        (2, "linkedin:6666", "OldCo", "PM",
         "https://www.linkedin.com/jobs/view/6666", "", None, "existing-flag", 150000),
        # already-processed (should be skipped by SELECT)
        (3, "linkedin:7777", "Stale", "PM",
         "https://www.linkedin.com/jobs/view/7777", "", None, "",
         100000),
    ])
    con.execute("UPDATE roles SET agent_notes='LINKEDIN-AUTHED 2026-05-26: UNRESOLVED | ...' WHERE id=3")
    con.commit()
    con.close()
    return db


class TestDryRunDoesNotMutate(unittest.TestCase):
    def test_dry_run_default_no_writes(self):
        with tempfile.TemporaryDirectory() as td:
            db = _mk_db(Path(td))
            # Driver returns a resolvable apply-direct-href on every call.
            def factory(_profile):
                return FakeDriver(classify_result={
                    "kind": "apply",
                    "sample_text": "Apply",
                    "sample_classes": "",
                    "href": "https://boards.greenhouse.io/plaid/jobs/1",
                })
            rc = ar.main(["--db", str(db), "--quiet"], driver_factory=factory)
            self.assertEqual(rc, 0)
            con = sqlite3.connect(db)
            rows = con.execute("SELECT id, app_url, agent_notes FROM roles ORDER BY id").fetchall()
            con.close()
            # id=1 and id=2 untouched
            self.assertEqual(rows[0][1], "https://www.linkedin.com/jobs/view/5555")
            self.assertIsNone(rows[0][2])
            self.assertEqual(rows[1][1], "https://www.linkedin.com/jobs/view/6666")
            self.assertIsNone(rows[1][2])

    def test_already_processed_filtered_out(self):
        """SELECT must exclude rows whose agent_notes already mention LINKEDIN-AUTHED."""
        with tempfile.TemporaryDirectory() as td:
            db = _mk_db(Path(td))
            con = sqlite3.connect(db)
            targets = ar.fetch_targets(con, 0)
            con.close()
            ids = [r[0] for r in targets]
            self.assertIn(1, ids)
            self.assertIn(2, ids)
            self.assertNotIn(3, ids)

    def test_apply_writes_and_makes_backup(self):
        with tempfile.TemporaryDirectory() as td:
            db = _mk_db(Path(td))
            def factory(_profile):
                return FakeDriver(classify_result={
                    "kind": "apply",
                    "sample_text": "Apply on company website",
                    "sample_classes": "",
                    "href": "https://boards.greenhouse.io/plaid/jobs/9999",
                })
            rc = ar.main(["--db", str(db), "--apply", "--limit", "1", "--quiet"],
                         driver_factory=factory)
            self.assertEqual(rc, 0)
            # Backup file exists
            baks = list(Path(td).glob("tracker.db.bak.*-linkedin-authed-resolver"))
            self.assertEqual(len(baks), 1)
            # Row 1 (highest TC) was resolved
            con = sqlite3.connect(db)
            row = con.execute("SELECT app_url, source_key, agent_notes FROM roles WHERE id=1").fetchone()
            con.close()
            self.assertEqual(row[0], "https://boards.greenhouse.io/plaid/jobs/9999")
            self.assertTrue(row[1].startswith("greenhouse:plaid:"))
            self.assertIn("LINKEDIN-AUTHED", row[2])
            self.assertIn("resolved", row[2])

    def test_apply_easy_apply_appends_manual_apply_flag(self):
        with tempfile.TemporaryDirectory() as td:
            db = _mk_db(Path(td))
            def factory(_profile):
                return FakeDriver(classify_result={
                    "kind": "easy-apply", "sample_text": "Easy Apply",
                    "sample_classes": "",
                })
            rc = ar.main(["--db", str(db), "--apply", "--role-id", "2", "--quiet"],
                         driver_factory=factory)
            self.assertEqual(rc, 0)
            con = sqlite3.connect(db)
            row = con.execute("SELECT flags, agent_notes FROM roles WHERE id=2").fetchone()
            con.close()
            self.assertIn("manual-apply", row[0])
            self.assertIn("existing-flag", row[0])  # didn't drop prior flags
            self.assertIn("EASY-APPLY-ONLY", row[1])

    def test_apply_unresolved_writes_diagnostic_note(self):
        with tempfile.TemporaryDirectory() as td:
            db = _mk_db(Path(td))
            def factory(_profile):
                return FakeDriver(
                    classify_result={"kind": "sign-up-wall",
                                     "sample_text": "Apply",
                                     "sample_classes": "sign-up-modal__outlet"},
                    scrape_result=[],
                    company_url=None,
                )
            # Stub anon ladder so it also fails
            with patch.object(lp, "resolve_one", return_value=(None, None, ["yaml-empty", "linkedin-no-ats", "careers-tried"])):
                rc = ar.main(["--db", str(db), "--apply", "--role-id", "1", "--quiet"],
                             driver_factory=factory)
            self.assertEqual(rc, 0)
            con = sqlite3.connect(db)
            row = con.execute("SELECT app_url, agent_notes FROM roles WHERE id=1").fetchone()
            con.close()
            # app_url unchanged on unresolved
            self.assertEqual(row[0], "https://www.linkedin.com/jobs/view/5555")
            self.assertIn("LINKEDIN-AUTHED", row[1])
            self.assertIn("UNRESOLVED", row[1])
            self.assertIn("apply-button", row[1])  # tactics_tried list


# ---------------------------------------------------------------------------
# Selection ordering (highest TC first)
# ---------------------------------------------------------------------------

class TestSelectionOrdering(unittest.TestCase):
    def test_sorts_by_est_tc_desc_then_id_asc(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "tracker.db"
            con = sqlite3.connect(db)
            con.execute("""
                CREATE TABLE roles (
                    id INTEGER PRIMARY KEY, source_key TEXT, company TEXT,
                    role TEXT, app_url TEXT, status TEXT, applied_by TEXT,
                    flags TEXT, agent_notes TEXT, est_tc INTEGER
                )
            """)
            con.executemany("""
                INSERT INTO roles (id, source_key, company, role, app_url, status, applied_by, flags, agent_notes, est_tc)
                VALUES (?, 'linkedin:x', ?, 'PM', ?, '', NULL, '', NULL, ?)
            """, [
                (10, "Low",  "https://www.linkedin.com/jobs/view/10", 100000),
                (20, "High", "https://www.linkedin.com/jobs/view/20", 300000),
                (30, "Null", "https://www.linkedin.com/jobs/view/30", None),
                (40, "Mid",  "https://www.linkedin.com/jobs/view/40", 200000),
            ])
            con.commit()
            rows = ar.fetch_targets(con, 0)
            con.close()
            ids = [r[0] for r in rows]
            # High TC first, then mid, then low, then NULL.
            self.assertEqual(ids, [20, 40, 10, 30])


# ---------------------------------------------------------------------------
# Bug 2 regression: anonymous-fallback returning a LinkedIn URL must NOT
# be stamped as resolved. Defensive `is_linkedin_host` guard.
# ---------------------------------------------------------------------------

class IsLinkedInHostTests(unittest.TestCase):
    def test_linkedin_view_url(self):
        self.assertTrue(ar.is_linkedin_host("https://www.linkedin.com/jobs/view/4407094249"))

    def test_subdomain_linkedin(self):
        self.assertTrue(ar.is_linkedin_host("https://careers.linkedin.com/jobs/123"))

    def test_greenhouse_url(self):
        self.assertFalse(ar.is_linkedin_host("https://boards.greenhouse.io/rivian/jobs/1"))

    def test_empty(self):
        self.assertFalse(ar.is_linkedin_host(""))
        self.assertFalse(ar.is_linkedin_host(None))  # type: ignore[arg-type]

    def test_linkedinish_substring_in_path_only(self):
        # Path contains "linkedin.com" but host is greenhouse — must NOT trigger.
        self.assertFalse(ar.is_linkedin_host("https://boards.greenhouse.io/rivian/jobs/1?ref=linkedin.com"))


class FalseResolveStillLinkedInTests(unittest.TestCase):
    """Bug 2 regression: when tactic 4 (lp.resolve_one) returns a LinkedIn
    URL (because the crawler's roles.json stored a LinkedIn discovery URL
    as canonical), the resolver must NOT stamp the row resolved — it must
    treat that as UNRESOLVED with reason `false-resolve-still-linkedin`."""

    def _row(self):
        return (829, "Rivian", "Technical Program Manager",
                "https://www.linkedin.com/jobs/view/4407094249", 264200)

    def test_t4_returns_linkedin_url_is_rejected(self):
        driver = FakeDriver(fail_open=True)  # force fallback only
        bad_url = "https://www.linkedin.com/jobs/view/4407094249"
        with patch.object(ar, "tactic_anonymous_fallback",
                          return_value=(bad_url, "yaml(workday) score=1.00", ["yaml(workday) score=1.00"])):
            r = ar.resolve_one_row(driver, self._row(), [], [])
        self.assertEqual(r["kind"], "unresolved")
        self.assertIsNone(r["ats_url"])
        self.assertIn("false-resolve-still-linkedin", r["reasons"])

    def test_t4_returns_real_ats_url_is_accepted(self):
        driver = FakeDriver(fail_open=True)
        good_url = "https://rivian.wd5.myworkdayjobs.com/Rivian/job/123"
        with patch.object(ar, "tactic_anonymous_fallback",
                          return_value=(good_url, "yaml(workday) score=1.00", ["yaml(workday) score=1.00"])):
            r = ar.resolve_one_row(driver, self._row(), [], [])
        self.assertEqual(r["kind"], "resolved")
        self.assertEqual(r["ats_url"], good_url)

    def test_t1_apply_direct_href_is_linkedin_rejected(self):
        # If tactic_apply_button somehow returns a LinkedIn URL (e.g. the
        # popup-capture path captured a linkedin auth-wall redirect), the
        # resolver wrapper must reject it. We patch the tactic directly so
        # the test is robust to internal-predicate changes.
        bad_url = "https://www.linkedin.com/jobs/view/12345"
        good_fallback = "https://boards.greenhouse.io/rivian/jobs/9"
        driver = FakeDriver(open_result={"targetId": "T1"})
        with patch.object(ar, "tactic_apply_button",
                          return_value=(bad_url, "resolved", "apply-click-new-tab")), \
             patch.object(ar, "tactic_dom_scrape", return_value=(None, "dom-no-ats")), \
             patch.object(ar, "tactic_company_careers", return_value=(None, "no-company-url")), \
             patch.object(ar, "tactic_anonymous_fallback",
                          return_value=(good_fallback, "yaml(greenhouse) score=0.95", ["yaml"])):
            r = ar.resolve_one_row(driver, self._row(), [], [])
        # T1 should be rejected, then T4 picks up the good URL.
        self.assertEqual(r["kind"], "resolved")
        self.assertEqual(r["ats_url"], good_fallback)
        self.assertTrue(any("t1-rejected-still-linkedin" in x for x in r["reasons"]),
                        f"reasons={r['reasons']}")

    def test_unresolved_when_all_tactics_yield_linkedin_or_nothing(self):
        driver = FakeDriver(
            open_result={"targetId": "T1"},
            classify_result={"kind": "none"},
            scrape_result=[],
            company_url=None,
        )
        bad_url = "https://www.linkedin.com/jobs/view/4407094249"
        with patch.object(ar, "tactic_anonymous_fallback",
                          return_value=(bad_url, "yaml(workday) score=1.00", ["yaml(workday)"])):
            r = ar.resolve_one_row(driver, self._row(), [], [])
        self.assertEqual(r["kind"], "unresolved")
        self.assertIsNone(r["ats_url"])
        self.assertIn("false-resolve-still-linkedin", r["reasons"])


if __name__ == "__main__":
    unittest.main()
