#!/usr/bin/env python3
"""Regression test: 'immigration case' sponsorship phrasing must resolve.

Autonomous tick 2026-06-08. Dealpath 2454 stranded because its Greenhouse
sponsorship question used wording that slipped through every LABEL_RULES needle:

  "Will you now, or in the future require Dealpath to commence ('sponsor') an
   immigration case in order to employ you (for example, H-1B or other
   employment-based immigration case)?"

Misses because:
  - uses the VERB 'sponsor' (in quotes), not the noun 'sponsorship'
  - "now, or in the future require" (comma after 'now') != the existing
    "now or in the future require" needle

Fix adds ("immigration case", "needs_sponsorship"). This test pins that the
phrase resolves to needs_sponsorship AND that the fix does not steal benign
work-authorization labels.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import greenhouse_dryrun as D  # noqa: E402

DEALPATH_LABEL = (
    "Will you now, or in the future require Dealpath to commence "
    "(\u201csponsor\u201d) an immigration case in order to employ you "
    "(for example, H-1B or other employment-based immigration case)?"
)


class ImmigrationCaseSponsorshipTests(unittest.TestCase):
    def test_dealpath_label_resolves_to_sponsorship(self):
        self.assertEqual(D.find_resolver(DEALPATH_LABEL), "needs_sponsorship")

    def test_generic_immigration_case_phrase(self):
        self.assertEqual(
            D.find_resolver("Will you require us to file an immigration case for you?"),
            "needs_sponsorship",
        )

    def test_does_not_steal_plain_work_authorization(self):
        # The fix must not affect a pure work-auth question (answered Yes).
        self.assertEqual(
            D.find_resolver("Are you legally authorized to work in the United States?"),
            "work_authorized",
        )

    def test_existing_sponsorship_noun_still_resolves(self):
        self.assertEqual(
            D.find_resolver("Do you now or will you in the future require visa sponsorship?"),
            "needs_sponsorship",
        )

    def test_immigration_support_still_resolves(self):
        self.assertEqual(
            D.find_resolver("Do you require immigration support?"),
            "needs_sponsorship",
        )


if __name__ == "__main__":
    unittest.main()
