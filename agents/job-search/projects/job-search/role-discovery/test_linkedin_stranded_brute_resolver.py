#!/usr/bin/env python3
"""Tests for linkedin_stranded_brute_resolver.py — pure-HTTP, mocked.

Covers:
  - normalize_title (seniority + abbreviations strip)
  - fuzzy_ratio (positive + negative)
  - title_substring_match, location_overlap
  - is_linkedin_url defensive guard
  - best_match conservative gates (no false RESOLVED)
  - derive_source_key for each ATS shape
  - per-ATS fetch_*_jobs query shapes (mocked requests)
  - Dry-run-no-mutation integration test on tmp DB
  - Apply-mutates-DB integration test (with mocked HTTP)
  - Non-LinkedIn URL guard skips
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import linkedin_stranded_brute_resolver as brute  # noqa: E402


class NormalizationTests(unittest.TestCase):
    def test_strips_seniority(self):
        self.assertNotIn("senior", brute.normalize_title("Senior Product Manager"))
        self.assertNotIn("staff", brute.normalize_title("Staff Software Engineer"))
        self.assertNotIn("principal", brute.normalize_title("Principal Engineer"))

    def test_expands_abbreviations(self):
        self.assertIn("product manager", brute.normalize_title("PM, Growth"))
        self.assertIn("technical program manager", brute.normalize_title("TPM"))
        self.assertIn("solutions engineer", brute.normalize_title("SE, Enterprise"))

    def test_punctuation_collapsed(self):
        self.assertEqual(
            brute.normalize_title("Product  Manager, AI/ML"),
            brute.normalize_title("Product Manager AI ML"),
        )


class FuzzyMatchTests(unittest.TestCase):
    def test_identical_titles(self):
        self.assertGreaterEqual(
            brute.fuzzy_ratio("Product Manager", "Product Manager"), 0.95,
        )

    def test_seniority_variant_high_score(self):
        # "Senior PM" should match "Product Manager" after normalization
        score = brute.fuzzy_ratio("Senior PM, Growth", "Product Manager, Growth")
        self.assertGreaterEqual(score, 0.8)

    def test_distinct_titles_low_score(self):
        score = brute.fuzzy_ratio("Sales Engineer", "Backend Engineer")
        self.assertLess(score, 0.75)

    def test_substring_helper(self):
        self.assertTrue(brute.title_substring_match(
            "Solutions Engineer", "Solutions Engineer, NAM",
        ))
        self.assertFalse(brute.title_substring_match(
            "Sales Engineer", "Forward Deployed Engineer",
        ))


class LocationOverlapTests(unittest.TestCase):
    def test_city_in_both(self):
        self.assertTrue(brute.location_overlap("Seattle, WA", "Seattle, Washington"))

    def test_no_overlap(self):
        self.assertFalse(brute.location_overlap("Boston, MA", "Tokyo, Japan"))

    def test_united_states_alone_does_not_match(self):
        # "United States" token-only should NOT trigger a match
        self.assertFalse(brute.location_overlap("United States", "United States"))

    def test_empty_strings(self):
        self.assertFalse(brute.location_overlap("", "Seattle"))
        self.assertFalse(brute.location_overlap("Seattle", ""))


class LinkedInGuardTests(unittest.TestCase):
    def test_recognizes_linkedin(self):
        self.assertTrue(brute.is_linkedin_url("https://www.linkedin.com/jobs/view/123"))
        self.assertTrue(brute.is_linkedin_url("https://LinkedIn.com/x"))

    def test_rejects_non_linkedin(self):
        self.assertFalse(brute.is_linkedin_url("https://boards.greenhouse.io/x/jobs/1"))
        self.assertFalse(brute.is_linkedin_url(""))
        self.assertFalse(brute.is_linkedin_url(None))


class BestMatchTests(unittest.TestCase):
    def test_positive_with_loc_overlap(self):
        jobs = [{"title": "Product Manager, Growth", "location": "Seattle, WA", "url": "X", "id": 1}]
        best, score, reason = brute.best_match("Product Manager, Growth", "Seattle, WA", jobs)
        self.assertIsNotNone(best)
        self.assertGreaterEqual(score, 0.75)

    def test_positive_with_title_substring(self):
        jobs = [{"title": "Solutions Engineer, NAM", "location": "London, UK", "url": "X", "id": 1}]
        best, _, _ = brute.best_match("Solutions Engineer", "New York, NY", jobs)
        self.assertIsNotNone(best)

    def test_high_fuzzy_no_loc_no_sub_rejects(self):
        # title close enough by fuzzy but no loc overlap AND no substring → reject
        jobs = [{"title": "Product Manager", "location": "Tokyo", "url": "X", "id": 1}]
        best, score, _ = brute.best_match("Project Manager", "Boston, MA", jobs)
        # Should not resolve (no loc, fuzzy may be high but neither guard satisfied)
        # depending on exact ratio — either way, we accept either outcome but reason is meaningful
        if best is not None:
            # If matched, MUST be because of substring guard
            self.assertTrue(
                brute.title_substring_match("Project Manager", best["title"])
            )

    def test_completely_different_titles_no_match(self):
        jobs = [{"title": "Mechanical Engineer", "location": "Boston", "url": "X", "id": 1}]
        best, _, _ = brute.best_match("Marketing Director", "Boston", jobs)
        self.assertIsNone(best)

    def test_empty_jobs(self):
        best, score, reason = brute.best_match("anything", "anywhere", [])
        self.assertIsNone(best)
        self.assertEqual(reason, "no-jobs")


class BroadenedMatcherTests(unittest.TestCase):
    """The 2026-06-11 safe-broadening: ACCEPT legit title variants (seniority,
    abbreviation, reordering, region/team suffix) while still REJECTING true
    collisions (different role sharing only generic words, or a wrong-company
    board). Each ACCEPT must resolve; each REJECT must return None."""

    # ---- helpers ----
    @staticmethod
    def _match(target, board_title, board_loc="Remote", target_loc="Remote"):
        jobs = [{"title": board_title, "location": board_loc, "url": "X", "id": 1}]
        return brute.best_match(target, target_loc, jobs)

    # ---- collision-guard unit ----
    def test_collision_guard_distinctive_shared(self):
        self.assertTrue(brute.collision_guard_ok(
            "Product Manager, Crypto", "Senior Product Manager, Crypto Wallet"))

    def test_collision_guard_generic_only_blocks(self):
        # 'Sales Engineer' vs 'Sales Manager' share only generic tokens AND
        # neither is a substring of the other -> must block.
        self.assertFalse(brute.collision_guard_ok("Sales Engineer", "Sales Manager"))

    def test_collision_guard_fully_generic_suffix_ok(self):
        # fully-generic target, board adds a region suffix -> structural match OK
        self.assertTrue(brute.collision_guard_ok(
            "Solutions Engineer", "Solutions Engineer, NAM"))

    def test_collision_guard_distinctive_target_not_shared_blocks(self):
        # target has a distinctive token the board lacks -> block
        self.assertFalse(brute.collision_guard_ok(
            "Product Manager, Payments", "Product Manager"))

    # ---- ACCEPT: legit variants resolve ----
    def test_accept_seniority_variant(self):
        best, _, _ = self._match("Sr. Solutions Engineer, Networking",
                                 "Senior Solutions Engineer - Networking")
        self.assertIsNotNone(best)

    def test_accept_abbreviation_variant(self):
        best, _, _ = self._match("TPM, Data Platform",
                                 "Technical Program Manager, Data Platform")
        self.assertIsNotNone(best)

    def test_accept_reordered_tokens(self):
        # sequence-fuzzy under-scores reordering; the token-overlap tier catches it
        best, _, reason = self._match("Solutions Engineer, Cloud Platform",
                                      "Cloud Platform Solutions Engineer")
        self.assertIsNotNone(best, reason)

    def test_accept_region_suffix_generic(self):
        best, _, _ = self._match("Sales Engineer", "Sales Engineer (West Region)")
        self.assertIsNotNone(best)

    # ---- REJECT: true collisions stay unmatched ----
    def test_reject_sales_engineer_vs_sales_manager(self):
        best, _, _ = self._match("Sales Engineer", "Sales Manager")
        self.assertIsNone(best)

    def test_reject_generic_pm_onto_specialized_pm(self):
        # bare 'Product Manager' should NOT grab a different specialized PM
        # when the board only has the specialized one (distinctive token unshared)
        best, _, _ = self._match("Product Manager, Crypto", "Product Manager, Ads")
        self.assertIsNone(best)

    def test_reject_wrong_company_board_collision(self):
        # Epic SYSTEMS 'Technical Solutions Engineer' must NOT map to Epic GAMES
        # 'Solutions Architect (Animation)' -- different role, no shared
        # distinctive token ('animation' vs 'technical').
        jobs = [
            {"title": "Solutions Architect (Animation)", "location": "Cary, NC", "url": "X", "id": 1},
            {"title": "Senior AI Engineer", "location": "Cary, NC", "url": "Y", "id": 2},
        ]
        best, _, _ = brute.best_match("Technical Solutions Engineer", "Verona, WI", jobs)
        self.assertIsNone(best)

    def test_reject_different_discipline_same_seniority(self):
        best, _, _ = self._match("Senior Backend Engineer", "Senior Frontend Engineer")
        self.assertIsNone(best)


class SourceKeyTests(unittest.TestCase):
    def test_greenhouse(self):
        sk = brute.derive_source_key("https://boards.greenhouse.io/anthropic/jobs/12345")
        self.assertEqual(sk, "greenhouse:anthropic:12345")

    def test_ashby(self):
        sk = brute.derive_source_key("https://jobs.ashbyhq.com/openai/abc-123-def")
        self.assertEqual(sk, "ashby:openai:abc-123-def")

    def test_lever(self):
        sk = brute.derive_source_key("https://jobs.lever.co/spotify/abcd1234-5678-90ef")
        self.assertEqual(sk, "lever:spotify:abcd1234-5678-90ef")

    def test_workday(self):
        sk = brute.derive_source_key(
            "https://tesla.wd5.myworkdayjobs.com/Tesla/job/Palo-Alto/Eng_PM/req-123"
        )
        self.assertTrue(sk.startswith("workday:tesla:"))


# ---------------------------------------------------------------------------
# Mocked HTTP per-ATS query shape tests
# ---------------------------------------------------------------------------

def _mock_response(status: int, payload):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    return m


class GreenhouseFetchTests(unittest.TestCase):
    def test_parses_greenhouse_response(self):
        payload = {
            "jobs": [
                {"title": "PM, X", "absolute_url": "https://...gh.../1",
                 "location": {"name": "SF"}, "id": 1},
                {"title": "PM, Y", "absolute_url": "https://...gh.../2",
                 "location": {"name": "NY"}, "id": 2},
            ]
        }
        with patch.object(brute.requests, "get", return_value=_mock_response(200, payload)):
            jobs, err = brute.fetch_greenhouse_jobs("anthropic")
        self.assertIsNone(err)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["title"], "PM, X")
        self.assertEqual(jobs[0]["location"], "SF")

    def test_404_returns_error(self):
        with patch.object(brute.requests, "get", return_value=_mock_response(404, {})):
            jobs, err = brute.fetch_greenhouse_jobs("bogus")
        self.assertEqual(err, "http-404")
        self.assertEqual(jobs, [])


class AshbyFetchTests(unittest.TestCase):
    def test_parses_ashby_response(self):
        payload = {"jobs": [{"title": "PM", "jobUrl": "https://...ashby...", "id": "abc", "location": {"name": "SF"}}]}
        with patch.object(brute.requests, "get", return_value=_mock_response(200, payload)):
            jobs, err = brute.fetch_ashby_jobs("openai")
        self.assertIsNone(err)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["location"], "SF")


class LeverFetchTests(unittest.TestCase):
    def test_parses_lever_response(self):
        payload = [{"text": "PM", "hostedUrl": "https://lever.co/x", "id": "1",
                    "categories": {"location": "SF"}}]
        with patch.object(brute.requests, "get", return_value=_mock_response(200, payload)):
            jobs, err = brute.fetch_lever_jobs("netflix")
        self.assertIsNone(err)
        self.assertEqual(jobs[0]["title"], "PM")


class WorkdayFetchTests(unittest.TestCase):
    def test_paginates_workday(self):
        page1 = {"jobPostings": [
            {"title": "PM 1", "externalPath": "/job/x/1", "locationsText": "SF"},
            {"title": "PM 2", "externalPath": "/job/x/2", "locationsText": "NY"},
        ], "total": 2}
        with patch.object(brute.requests, "post", return_value=_mock_response(200, page1)):
            jobs, err = brute.fetch_workday_jobs(
                "tesla.wd5.myworkdayjobs.com", "tesla", "Tesla", search_text="",
            )
        self.assertIsNone(err)
        self.assertEqual(len(jobs), 2)
        self.assertTrue(jobs[0]["url"].endswith("/job/x/1"))


# ---------------------------------------------------------------------------
# Integration tests on tmp DB
# ---------------------------------------------------------------------------

class TmpDBHelper:
    @staticmethod
    def make_tracker(tmpdir: Path) -> Path:
        db = tmpdir / "tracker.db"
        con = sqlite3.connect(str(db))
        con.executescript("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                source_key TEXT,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                level TEXT, loc TEXT, exp_req TEXT, jd_url TEXT,
                app_url TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                flags TEXT, applied_by TEXT, applied_on TEXT,
                cyrus_notes TEXT, first_seen TEXT, last_seen TEXT,
                posted_on TEXT, last_response_at TEXT, response_status TEXT,
                last_email_subject TEXT, last_email_from TEXT,
                prep_status TEXT, prep_path TEXT, est_tc INTEGER,
                agent_notes TEXT DEFAULT '',
                llm_classified_at TEXT, llm_yoe_required INTEGER,
                llm_is_people_manager INTEGER, llm_seniority TEXT,
                llm_fit_score INTEGER, llm_reason TEXT
            );
        """)
        con.executemany(
            "INSERT INTO roles (id, source_key, company, role, loc, app_url, status, agent_notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                # Row 1: LinkedIn-stranded, ashby company "openai", title fuzzy-matches
                (1, "linkedin:1", "OpenAI", "Product Manager, ChatGPT", "San Francisco, CA",
                 "https://www.linkedin.com/jobs/view/1", "", ""),
                # Row 2: LinkedIn-stranded, unknown ATS
                (2, "linkedin:2", "RandomBogusCo", "Forward Deployed Engineer", "SF",
                 "https://www.linkedin.com/jobs/view/2", "", ""),
                # Row 3: already brute-resolved (TERMINAL marker) → must be skipped
                (3, "linkedin:3", "OpenAI", "PM", "SF",
                 "https://www.linkedin.com/jobs/view/3", "",
                 "LINKEDIN-BRUTE-DONE 2026-05-27: resolved via ashby"),
                # Row 4: non-LinkedIn url (idempotency belt-and-suspenders, won't be selected by SQL anyway)
                # Row 5: applied_by set → must not be selected
                (5, "linkedin:5", "OpenAI", "PM", "SF",
                 "https://www.linkedin.com/jobs/view/5", "queued", ""),
            ],
        )
        # Mark row 5 as applied_by
        con.execute("UPDATE roles SET applied_by='someone' WHERE id=5")
        con.commit()
        con.close()
        return db

    @staticmethod
    def make_map(tmpdir: Path) -> Path:
        mp = tmpdir / "_map.json"
        mp.write_text(json.dumps({
            "mapping": {
                "OpenAI": {"company": "OpenAI", "ats": "ashby", "slug": "openai"},
                "RandomBogusCo": {"company": "RandomBogusCo", "ats": "UNKNOWN",
                                  "reason": "no-public-board-hit"},
            }
        }))
        return mp


class DryRunNoMutationTest(unittest.TestCase):
    def test_dry_run_does_not_mutate_db(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            db = TmpDBHelper.make_tracker(tdp)
            mp = TmpDBHelper.make_map(tdp)
            # Mock Ashby fetch to return a fuzzy-matchable job
            jobs_payload = {"jobs": [
                {"title": "Product Manager, ChatGPT Apps",
                 "jobUrl": "https://jobs.ashbyhq.com/openai/abcdef-12345",
                 "id": "abcdef-12345",
                 "location": {"name": "San Francisco, California"}},
            ]}
            with patch.object(brute.requests, "get",
                              return_value=_mock_response(200, jobs_payload)):
                rc = brute.main(["--db", str(db), "--map", str(mp), "--quiet"])
            self.assertEqual(rc, 0)
            # DB unchanged for row 1
            con = sqlite3.connect(str(db))
            url, notes = con.execute(
                "SELECT app_url, agent_notes FROM roles WHERE id=1"
            ).fetchone()
            con.close()
            self.assertIn("linkedin.com", url)
            self.assertEqual(notes, "")  # untouched


class ApplyMutatesTest(unittest.TestCase):
    def test_apply_writes_resolved_and_no_ats_notes(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            db = TmpDBHelper.make_tracker(tdp)
            mp = TmpDBHelper.make_map(tdp)
            jobs_payload = {"jobs": [
                {"title": "Product Manager, ChatGPT Apps",
                 "jobUrl": "https://jobs.ashbyhq.com/openai/abcdef-12345",
                 "id": "abcdef-12345",
                 "location": {"name": "San Francisco, California"}},
            ]}
            with patch.object(brute.requests, "get",
                              return_value=_mock_response(200, jobs_payload)):
                rc = brute.main(["--db", str(db), "--map", str(mp), "--apply", "--quiet"])
            self.assertEqual(rc, 0)
            con = sqlite3.connect(str(db))
            row1 = con.execute(
                "SELECT app_url, source_key, agent_notes FROM roles WHERE id=1"
            ).fetchone()
            row2 = con.execute(
                "SELECT app_url, agent_notes FROM roles WHERE id=2"
            ).fetchone()
            row3 = con.execute("SELECT agent_notes FROM roles WHERE id=3").fetchone()
            row5 = con.execute("SELECT agent_notes FROM roles WHERE id=5").fetchone()
            con.close()
            # Row 1: resolved
            self.assertIn("ashbyhq.com", row1[0])
            self.assertTrue(row1[1].startswith("ashby:openai:"))
            self.assertIn("LINKEDIN-BRUTE", row1[2])
            self.assertIn("resolved", row1[2])
            # Row 2: NO-ATS notes written, url unchanged
            self.assertIn("linkedin.com", row2[0])
            self.assertIn("NO-ATS", row2[1])
            # Row 3: untouched (already TERMINALLY brute-resolved, -DONE marker)
            self.assertEqual(row3[0], "LINKEDIN-BRUTE-DONE 2026-05-27: resolved via ashby")
            # Row 5: untouched (applied_by set, excluded by SELECT)
            self.assertEqual(row5[0], "")


class BackupTest(unittest.TestCase):
    def test_apply_creates_backup(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            db = TmpDBHelper.make_tracker(tdp)
            mp = TmpDBHelper.make_map(tdp)
            with patch.object(brute.requests, "get",
                              return_value=_mock_response(200, {"jobs": []})):
                rc = brute.main(["--db", str(db), "--map", str(mp), "--apply", "--quiet"])
            self.assertEqual(rc, 0)
            baks = list(tdp.glob("tracker.db.bak.*-linkedin-brute-resolver"))
            self.assertEqual(len(baks), 1)


class StatusSelectionTest(unittest.TestCase):
    """manual-apply / queued LinkedIn rows must be selected (offsite resolution
    should run against them); applied_by rows must still be excluded."""

    def _make_db(self, tmpdir: Path) -> Path:
        db = tmpdir / "tracker.db"
        con = sqlite3.connect(str(db))
        con.executescript("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY, source_key TEXT,
                company TEXT NOT NULL, role TEXT NOT NULL,
                loc TEXT, app_url TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                applied_by TEXT, agent_notes TEXT DEFAULT ''
            );
        """)
        con.executemany(
            "INSERT INTO roles (id, company, role, loc, app_url, status, applied_by, agent_notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (10, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/10", "manual-apply", None, ""),
                (11, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/11", "queued", None, ""),
                (12, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/12", "blocked", None, ""),
                (13, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/13", "", None, ""),
                # excluded: applied_by set
                (14, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/14", "manual-apply", "someone", ""),
                # INCLUDED (re-attemptable): a NON-terminal LINKEDIN-BRUTE note
                # (prior NO-ATS/UNRESOLVED/ERRORED) must be retried, e.g. after
                # the map is refreshed (idempotency fix 2026-06-11).
                (15, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/15", "manual-apply", None, "LINKEDIN-BRUTE 2026-01-01: NO-ATS | reason=no-public-board-hit"),
                # excluded: closed status (not resolvable)
                (16, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/16", "closed", None, ""),
                # excluded: skip status
                (17, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/17", "skip", None, ""),
                # excluded: non-linkedin url
                (18, "Acme", "PM", "SF", "https://jobs.ashbyhq.com/acme/x", "manual-apply", None, ""),
                # excluded: TERMINALLY resolved (-DONE marker) must NOT be retried
                (19, "Acme", "PM", "SF", "https://www.linkedin.com/jobs/view/19", "manual-apply", None, "LINKEDIN-BRUTE-DONE 2026-01-01: resolved via ashby(acme)"),
            ],
        )
        con.commit()
        con.close()
        return db

    def test_manual_apply_and_queued_selected_guards_hold(self):
        with tempfile.TemporaryDirectory() as td:
            db = self._make_db(Path(td))
            con = sqlite3.connect(str(db))
            ids = {r[0] for r in brute.fetch_targets(con, None, None)}
            con.close()
            # included: 10-13 (open/queued/blocked/'') + 15 (non-terminal
            # brute note = re-attemptable). Excluded: 14 applied_by, 16 closed,
            # 17 skip, 18 non-linkedin, 19 terminal -DONE marker.
            self.assertEqual(ids, {10, 11, 12, 13, 15},
                             "manual-apply/queued/blocked/'' linkedin rows + non-terminal "
                             "brute-noted rows must be selected; applied_by/closed/skip/"
                             "non-linkedin/terminal-DONE excluded. got=%r" % ids)


if __name__ == "__main__":
    unittest.main()
