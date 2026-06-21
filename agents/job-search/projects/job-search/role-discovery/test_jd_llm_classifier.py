#!/usr/bin/env python3
"""Tests for the simplified jd_llm_classifier (2026-05-29).

Covers the new pure-deterministic gate:
  1. Regex YOE extraction from JD body.
  2. Title-keyword fallback when JD has no YOE signal.
  3. is_people_manager / seniority signals are IGNORED by the gate (regression).
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import jd_llm_classifier as J  # noqa: E402


# ---------------------------------------------------------------------------
# YOE regex extraction
# ---------------------------------------------------------------------------

class TestYOEExtraction(unittest.TestCase):
    def test_simple_plus(self):
        self.assertEqual(
            J.extract_yoe_from_jd_text("We require 3+ years of relevant experience."),
            3,
        )

    def test_range_takes_upper(self):
        # Per existing convention (file comment): range returns upper bound.
        self.assertEqual(
            J.extract_yoe_from_jd_text("Looking for 5-7 years of professional experience."),
            7,
        )

    def test_range_with_to(self):
        self.assertEqual(
            J.extract_yoe_from_jd_text("Ideal candidate has 4 to 6 years experience."),
            6,
        )

    def test_no_yoe_just_experience_word(self):
        # "experience required" with no number -> None
        self.assertIsNone(
            J.extract_yoe_from_jd_text(
                "Strong experience required in distributed systems. Excellent communication."
            )
        )

    def test_no_yoe_empty(self):
        self.assertIsNone(J.extract_yoe_from_jd_text(""))
        self.assertIsNone(J.extract_yoe_from_jd_text(None))

    def test_max_across_mentions(self):
        # Multiple mentions: take the MAX (per existing convention)
        jd = ("3+ years of frontend experience. "
              "8 years of backend experience preferred.")
        self.assertEqual(J.extract_yoe_from_jd_text(jd), 8)

    def test_yrs_abbrev(self):
        self.assertEqual(
            J.extract_yoe_from_jd_text("Minimum 5 yrs experience in cloud."),
            5,
        )

    def test_at_least_pattern(self):
        self.assertEqual(
            J.extract_yoe_from_jd_text("Must have at least 6 years working with k8s."),
            6,
        )

    def test_junk_high_numbers_ignored(self):
        # 100 years of innovation isn't a YOE requirement
        self.assertIsNone(
            J.extract_yoe_from_jd_text("Our company has 100 years of heritage.")
        )

    def test_company_age_unfortunately_caught_but_under_25(self):
        # Known limitation: "5 years of history" matches. Acceptable trade-off
        # per Cyrus directive (simple regex; title fallback handles most cases).
        # This test pins current behavior so we know if it changes.
        self.assertEqual(
            J.extract_yoe_from_jd_text("Founded 5 years ago with deep experience in fintech."),
            5,
        )


# ---------------------------------------------------------------------------
# Title-keyword skip
# ---------------------------------------------------------------------------

class TestTitleSkip(unittest.TestCase):
    def test_senior_skips(self):
        self.assertEqual(J.extract_title_skip("Senior Product Manager"), "senior")

    def test_sr_dot_skips(self):
        self.assertEqual(J.extract_title_skip("Sr. Solutions Engineer"), "sr")

    def test_staff_skips(self):
        # Staff without target role = skip
        self.assertEqual(J.extract_title_skip("Staff Engineer"), "staff")

    def test_staff_tpm_keeps(self):
        # Staff + target role = KEEP (carve-out, 2026-06-20)
        self.assertIsNone(J.extract_title_skip("Staff TPM"))
        self.assertIsNone(J.extract_title_skip("Staff Technical Program Manager"))

    def test_principal_skips(self):
        self.assertEqual(J.extract_title_skip("Principal PM"), "principal")

    def test_director_skips(self):
        self.assertEqual(J.extract_title_skip("Director of Product"), "director")

    def test_head_of_skips(self):
        self.assertEqual(J.extract_title_skip("Head of Engineering"), "head of")

    def test_vp_skips(self):
        self.assertEqual(J.extract_title_skip("VP, Product"), "vp")

    def test_vice_president_skips(self):
        self.assertEqual(J.extract_title_skip("Vice President of Sales"), "vice president")

    def test_chief_skips(self):
        self.assertEqual(J.extract_title_skip("Chief of Staff"), "chief")

    def test_lead_skips(self):
        # Lead without target role = skip
        self.assertEqual(J.extract_title_skip("Lead Engineer"), "lead")

    def test_lead_tpm_keeps(self):
        # Lead + target role = KEEP (carve-out, 2026-06-20)
        self.assertIsNone(J.extract_title_skip("Lead TPM"))
        self.assertIsNone(J.extract_title_skip("Lead Product Manager"))
        self.assertIsNone(J.extract_title_skip("Lead Program Manager"))

    def test_program_manager_ii_keeps(self):
        # Cyrus's example: target-role + no senior keyword -> KEEP
        self.assertIsNone(J.extract_title_skip("Program Manager II"))

    def test_solutions_engineer_keeps(self):
        self.assertIsNone(J.extract_title_skip("Solutions Engineer"))

    def test_product_manager_keeps(self):
        self.assertIsNone(J.extract_title_skip("Product Manager, GTM"))

    def test_engineering_manager_skips_as_manager(self):
        # Soft 'manager' carve-out: NOT in target-role allowlist -> skip
        self.assertEqual(J.extract_title_skip("Engineering Manager"), "manager")


# ---------------------------------------------------------------------------
# decide_skip (the unified pure-function gate)
# ---------------------------------------------------------------------------

class TestDecideSkip(unittest.TestCase):
    def test_yoe_over_threshold_skips(self):
        flags, reasons, jd_yoe = J.decide_skip(
            "Product Manager",
            "Requires 6+ years of relevant experience.",
            "San Francisco, CA",
        )
        self.assertIn("yoe-threshold", flags)
        self.assertEqual(jd_yoe, 6)

    def test_yoe_under_threshold_keeps(self):
        flags, reasons, jd_yoe = J.decide_skip(
            "Product Manager",
            "Requires 2+ years of experience in fintech.",
            "San Francisco, CA",
        )
        self.assertNotIn("yoe-threshold", flags)
        self.assertEqual(jd_yoe, 2)

    def test_no_yoe_falls_back_to_title_senior(self):
        # Cyrus's exact spec: no YOE in JD -> title fallback
        flags, reasons, _ = J.decide_skip(
            "Senior PM",
            "We're looking for a great product person. Strong experience required.",
            "New York, NY",
        )
        self.assertIn("senior-title", flags)

    def test_no_yoe_no_senior_keyword_keeps(self):
        # Cyrus's exact spec: "Program Manager II" with no YOE -> KEEP
        flags, reasons, _ = J.decide_skip(
            "Program Manager II",
            "We're looking for a great product person. Strong communication required.",
            "Seattle, WA",
        )
        self.assertEqual(flags, [])

    def test_staff_title_with_no_yoe_skips(self):
        flags, _, _ = J.decide_skip(
            "Staff Engineer",
            "Help us build the future. Excellent communication required.",
            "Austin, TX",
        )
        self.assertIn("senior-title", flags)

    def test_yoe_in_jd_overrides_title_check(self):
        # If JD has YOE under threshold, we DO NOT fall back to title.
        # Senior in title but JD says 2 years -> KEEP.
        # (Cyrus's spec: title fallback only when JD has no YOE signal.)
        flags, _, jd_yoe = J.decide_skip(
            "Senior PM",
            "We require 2+ years of experience.",
            "San Francisco, CA",
        )
        self.assertEqual(jd_yoe, 2)
        self.assertNotIn("senior-title", flags)
        self.assertNotIn("yoe-threshold", flags)

    def test_threshold_boundary(self):
        # Threshold is >=6 (raised from 4 on 2026-06-20: keeps '3-5' and '5+' roles)
        self.assertEqual(J.YOE_THRESHOLD, 6)
        flags6, _, _ = J.decide_skip(
            "Product Manager",
            "Requires 6+ years of relevant experience.",
            "SF, CA",
        )
        self.assertIn("yoe-threshold", flags6)
        flags5, _, _ = J.decide_skip(
            "Product Manager",
            "Requires 5+ years of relevant experience.",
            "SF, CA",
        )
        self.assertNotIn("yoe-threshold", flags5)
        flags3, _, _ = J.decide_skip(
            "Product Manager",
            "Requires 3+ years of relevant experience.",
            "SF, CA",
        )
        self.assertNotIn("yoe-threshold", flags3)


# ---------------------------------------------------------------------------
# maybe_skip — regression: LLM signals must NOT influence the gate
# ---------------------------------------------------------------------------

class TestMaybeSkipIgnoresLLMSignals(unittest.TestCase):
    """The simplified classifier MUST NOT consult is_people_manager / seniority.

    Regression for the chain that built the lead/unclear backlog: rows where
    the LLM said is_people_manager=true but the title is benign and the JD
    has no YOE should now be KEPT.
    """

    def _row(self, **kw):
        defaults = dict(
            id=999, source_key="x", company="TestCo", role="Product Manager II",
            loc="San Francisco, CA", app_url="https://example.com",
            jd_url="https://example.com/jd", status="", flags="", applied_by=None,
        )
        defaults.update(kw)
        # Build a Row-like object that supports both index and key access.
        return _DictRow(defaults)

    def test_lying_llm_people_manager_does_not_skip(self):
        row = self._row()
        cls = {
            "yoe_required": None,
            "is_people_manager": True,   # LLM says yes
            "seniority": "manager",      # LLM says yes
            "fit_score": 0,
            "reason": "LLM hallucinated",
        }
        jd = "Great team. Excellent communication required."
        flip = J.maybe_skip(MagicMock(), row, cls, jd, dry_run=True)
        # No YOE in JD, title is benign, NO senior keywords -> KEEP
        self.assertIsNone(flip)

    def test_yoe_gate_fires_independently_of_cls(self):
        row = self._row(role="Product Manager")
        cls = {"yoe_required": None, "is_people_manager": False,
               "seniority": "ic", "fit_score": 100, "reason": ""}
        jd = "Requires 8+ years experience."
        flip = J.maybe_skip(MagicMock(), row, cls, jd, dry_run=True)
        self.assertIsNotNone(flip)
        self.assertIn("yoe-threshold", flip["new_flags"])

    def test_title_gate_fires_independently_of_cls(self):
        row = self._row(role="Senior Solutions Engineer")
        cls = None  # explicitly: cls is ignored
        jd = "Looking for talented engineers. Excellent communication required."
        flip = J.maybe_skip(MagicMock(), row, cls, jd, dry_run=True)
        self.assertIsNotNone(flip)
        self.assertIn("senior-title", flip["new_flags"])

    def test_applied_row_never_flips(self):
        row = self._row(applied_by="cyrus", role="Senior PM")
        flip = J.maybe_skip(MagicMock(), row, None, "", dry_run=True)
        self.assertIsNone(flip)

    def test_already_skipped_row_never_flips(self):
        row = self._row(status="skip", role="Senior PM")
        flip = J.maybe_skip(MagicMock(), row, None, "", dry_run=True)
        self.assertIsNone(flip)


class _DictRow:
    """Minimal sqlite3.Row stand-in supporting both ['key'] and .get()."""
    def __init__(self, d):
        self._d = d

    def __getitem__(self, k):
        if isinstance(k, int):
            return list(self._d.values())[k]
        return self._d[k]

    def keys(self):
        return self._d.keys()


class TestCompanyBlocklist(unittest.TestCase):
    """Company-level exclusions (Cyrus handles / excludes these himself).
    Google/Microsoft (2026-05-31) + Amazon/AWS (2026-05-31). Owned subsidiaries
    whose names don't contain a parent keyword stay in scope (safelist)."""

    def test_amazon_variants_blocked(self):
        for name in ["Amazon", "Amazon.com", "AWS", "Amazon Web Services (AWS)",
                     "Amazon Prime", "Amazon Web Services"]:
            self.assertIsNotNone(
                J.company_is_blocked(name),
                f"{name!r} should be company-blocked",
            )

    def test_amazon_subsidiaries_not_blocked(self):
        for name in ["Twitch", "Twitch Interactive", "Audible", "Zappos",
                     "Ring", "Whole Foods Market", "IMDb", "Goodreads",
                     "Annapurna Labs"]:
            self.assertIsNone(
                J.company_is_blocked(name),
                f"{name!r} (Amazon-owned, non-Amazon-named) should stay in scope",
            )

    def test_google_microsoft_blocklist_state(self):
        # Cyrus 2026-06-08: Google + Alphabet RE-ENABLED for discovery (BACKLOG
        # #1) -> NO LONGER company-blocked. Microsoft (and Amazon/AWS) stay
        # blocked. Subsidiary safelist still overrides for parent-prefixed names.
        for name in ["Google", "Alphabet"]:
            self.assertIsNone(
                J.company_is_blocked(name),
                f"{name!r} should be UN-blocked after 2026-06-08 re-enable",
            )
        for name in ["Microsoft", "Amazon", "AWS"]:
            self.assertIsNotNone(
                J.company_is_blocked(name),
                f"{name!r} should still be company-blocked",
            )
        # subsidiary safelist still overrides
        self.assertIsNone(J.company_is_blocked("Google DeepMind"))
        self.assertIsNone(J.company_is_blocked("Waymo"))

    def test_unrelated_company_not_blocked(self):
        for name in ["Stripe", "Cresta", "Jane Street", "Chime"]:
            self.assertIsNone(J.company_is_blocked(name))


if __name__ == "__main__":
    unittest.main()


def test_fde_unblocked_2026_06_20():
    """Cyrus 2026-06-20 full-unblock: FDE + all SWE discipline blocks removed.
    FDE, Software Engineer, full-stack, backend, ML engineer, etc. all KEEP now."""
    import jd_llm_classifier as c
    # FDE titles now KEEP (not skipped)
    assert c.extract_title_skip("Forward Deployed Engineer") is None
    assert c.extract_title_skip("FDE, Applied AI") is None
    assert c.extract_title_skip("Forward Deployed Engineer, Solutions Engineer") is None
    # SWE disciplines now KEEP
    assert c.extract_title_skip("Software Engineer, Backend") is None
    assert c.extract_title_skip("ML Engineer") is None
    assert c.extract_title_skip("Full Stack Engineer") is None
    assert c.extract_title_skip("Data Engineer") is None
    assert c.extract_title_skip("Infrastructure Engineer") is None
    # Target roles still KEEP (unchanged)
    assert c.extract_title_skip("Solutions Engineer") is None
    assert c.extract_title_skip("Customer Solutions Engineer (Full Stack)") is None


def test_fde_unblocked_survives_yoe_check():
    """FDE with sub-threshold YOE should now be KEEP (no fde-block flag)."""
    import jd_llm_classifier as c
    flags, reasons, yoe = c.decide_skip(
        "Forward Deployed Engineer", "We are looking for 3 years of experience.",
        None, company="Addepar")
    assert "fde-block" not in flags, f"FDE still blocked unexpectedly: {flags}"
    # SWE with low YOE also KEEP
    flags2, _, _ = c.decide_skip(
        "Software Engineer, Backend", "2 years experience preferred.", None,
        company="X")
    assert "fde-block" not in flags2
