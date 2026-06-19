"""Unit tests for staffing_blocklist.is_staffing_firm.

Run from role-discovery/ as:
    .venv/bin/python -m unittest test_staffing_blocklist
or directly:
    .venv/bin/python test_staffing_blocklist.py

Covers:
- True-positive blocklist hits (case-insensitive, with/without Inc/LLC suffix)
- True-positive keyword pattern hits (staffing/recruiters/IT services)
- True-negative legit product companies that contain ambiguous tokens
- Allowlist escape hatch (AWS shouldn't trip on `aston`-like substring fuzz)
- Edge cases: empty, None-ish, whitespace, punctuation
- No regressions on the 65+ explicit entries (smoke check via len())

Codified 2026-05-24 by burndown subagent — staffing_blocklist.py shipped
2026-05-23 with zero tests; the 28-row retro pass that ran against tracker.db
counts as integration evidence but doesn't lock down the API contract for
future regressions.
"""
from __future__ import annotations

import unittest

from staffing_blocklist import (
    is_staffing_firm,
    filter_companies,
    EXPLICIT_BLOCKLIST,
    KEYWORD_PATTERNS,
    ALLOWLIST,
    _normalize,
)


class NormalizeTests(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(_normalize("Aquent"), "aquent")

    def test_strips_punctuation(self):
        self.assertEqual(_normalize("Aquent, LLC."), "aquent llc")

    def test_collapses_whitespace(self):
        self.assertEqual(_normalize("  Aquent   LLC  "), "aquent llc")

    def test_empty_and_none(self):
        self.assertEqual(_normalize(""), "")
        self.assertEqual(_normalize(None), "")


class ExplicitBlocklistHits(unittest.TestCase):
    # Names that should match an entry in EXPLICIT_BLOCKLIST.
    POSITIVES = [
        "Aquent",
        "Aquent LLC",
        "Aquent, Inc.",
        "Aston Carter",
        "Actalent",
        "Robert Half",
        "Robert Half International",
        "Kforce",
        "TekSystems",
        "Tek Systems",
        "Insight Global",
        "Beacon Hill Staffing Group",  # also hits keyword
        "CyberCoders",
        "Jobot",
        "Brooksource",
        "BayOne Solutions",
    ]

    def test_all_known_firms_match(self):
        for name in self.POSITIVES:
            with self.subTest(name=name):
                self.assertTrue(
                    is_staffing_firm(name),
                    f"Expected {name!r} to be classified as staffing firm",
                )


class KeywordPatternHits(unittest.TestCase):
    # Names that should match via KEYWORD_PATTERNS even if not in explicit list.
    POSITIVES = [
        "Acme Staffing Solutions",
        "FooBar Recruiters",
        "Big Talent Solutions",
        "Apex Executive Search",
        "Generic IT Services Inc",
        "XYZ Infotech",
        "Tier One Software Services",
        "Best Search Group",
        "Pyramid Consulting Group",
        "Acme Talent Acquisition Partners",
    ]

    def test_all_keyword_hits_match(self):
        for name in self.POSITIVES:
            with self.subTest(name=name):
                self.assertTrue(
                    is_staffing_firm(name),
                    f"Expected {name!r} to match a keyword pattern",
                )

    def test_pluralised_headhunters(self):
        """Plural 'Headhunters' is caught by the extended `headhunt(?:er|ing|ers)` regex.

        Promoted to live 2026-05-24 from `_repair/staffing_blocklist.py.candidate`.
        """
        self.assertTrue(is_staffing_firm("Atlas Headhunters"))


class TrueNegatives(unittest.TestCase):
    # Real product/SaaS companies that should NOT be classified as staffing.
    NEGATIVES = [
        "Anthropic",
        "Stripe",
        "Databricks",
        "Datadog",
        "Pinterest",
        "Fivetran",
        "Vercel",
        "Apple",
        "Google",
        "Meta",
        "OpenAI",
        "Snowflake",
        "MongoDB",
        "Atlassian",
        "Workday",   # tricky: contains common ATS name but is itself a product co
        "Salesforce",
        "GitHub",
        "Lyft",
        "SpaceX",
        "Talent.com",  # has "talent" but no qualifying space pattern
        "ServiceNow",  # contains "service" but no "services" keyword
        "Search Engine Land",  # Has "search" but not "search group/partners"
    ]

    def test_known_product_companies_pass(self):
        for name in self.NEGATIVES:
            with self.subTest(name=name):
                self.assertFalse(
                    is_staffing_firm(name),
                    f"FALSE POSITIVE: {name!r} should NOT be a staffing firm",
                )


class AllowlistEscape(unittest.TestCase):
    def test_aws_in_allowlist(self):
        # AWS sits in the allowlist; even if some collision were to trip the
        # blocklist, allowlist short-circuits.
        self.assertFalse(is_staffing_firm("AWS"))
        self.assertFalse(is_staffing_firm("Amazon Web Services"))


class EdgeCases(unittest.TestCase):
    def test_empty_string_is_false(self):
        self.assertFalse(is_staffing_firm(""))

    def test_none_is_false(self):
        self.assertFalse(is_staffing_firm(None))  # type: ignore[arg-type]

    def test_whitespace_only_is_false(self):
        self.assertFalse(is_staffing_firm("   "))

    def test_case_insensitive_match(self):
        self.assertTrue(is_staffing_firm("AQUENT"))
        self.assertTrue(is_staffing_firm("aquent"))
        self.assertTrue(is_staffing_firm("AqUeNt"))

    def test_punctuation_does_not_break_match(self):
        self.assertTrue(is_staffing_firm("Aquent, LLC."))
        self.assertTrue(is_staffing_firm("Robert Half®"))


class FilterCompaniesAPI(unittest.TestCase):
    def test_partitions_correctly(self):
        kept, dropped = filter_companies(["Anthropic", "Aquent", "Stripe", "TekSystems"])
        self.assertEqual(sorted(kept), ["Anthropic", "Stripe"])
        self.assertEqual(sorted(dropped), ["Aquent", "TekSystems"])

    def test_empty_input(self):
        kept, dropped = filter_companies([])
        self.assertEqual(kept, [])
        self.assertEqual(dropped, [])


class RegistryShape(unittest.TestCase):
    """Sanity check the curated lists haven't been silently emptied."""

    def test_blocklist_size(self):
        # 2026-05-24: 65+ explicit entries per TOOLS/MEMORY notes.
        self.assertGreaterEqual(
            len(EXPLICIT_BLOCKLIST), 30,
            f"EXPLICIT_BLOCKLIST shrunk to {len(EXPLICIT_BLOCKLIST)} entries — "
            "did someone empty it out?",
        )

    def test_keyword_patterns_size(self):
        self.assertGreaterEqual(
            len(KEYWORD_PATTERNS), 10,
            f"KEYWORD_PATTERNS shrunk to {len(KEYWORD_PATTERNS)} patterns",
        )

    def test_allowlist_present(self):
        self.assertGreater(len(ALLOWLIST), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
