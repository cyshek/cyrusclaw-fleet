#!/usr/bin/env python3
"""Unit test for the chain_007 pickCombobox selector fix.

Chain_007 (2026-05-26): live Lyft 1343 verify showed pickCombobox
reported `picked: "March"` but the form's post-submit state still listed
"Start date month is required". Root cause: the JS used
`[role=option], [id^=react-select-]` and `find(startsWith)`. The FIRST
matching element was the LISTBOX container
(`react-select-start-date-month-0-listbox`, role=listbox), whose
textContent equals the filtered option text ("March"). Clicking the
listbox container is a no-op for react-select - form state never updates.

Fix: pickCombobox now prefers strict `[role=option]` matches; only falls
back to `[id^=react-select-][id*="-option-"]` if no role=option found.
LISTBOX containers, placeholders, and live-region spans are excluded.

This is a snapshot-style test against the JS string in greenhouse_filler.
We can't run the JS without a browser, but we can guarantee the fixed
shape of the selector is in place.
"""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Stub playwright so greenhouse_filler import succeeds
fake_pw = types.ModuleType("playwright")
fake_pw_sync = types.ModuleType("playwright.sync_api")
fake_pw_sync.sync_playwright = lambda *a, **k: None
class _PWT(Exception): ...
fake_pw_sync.TimeoutError = _PWT
sys.modules.setdefault("playwright", fake_pw)
sys.modules.setdefault("playwright.sync_api", fake_pw_sync)

import greenhouse_filler as gf  # noqa: E402


class ComboboxSelectorTests(unittest.TestCase):
    def setUp(self):
        self.js = gf.JS_FILL_WORK_EXPERIENCE_BLOCK

    def test_prefers_strict_role_option(self):
        """Primary query must be strict [role=option] without listbox-leak prefix."""
        self.assertIn("querySelectorAll('[role=option]')", self.js)

    def test_no_loose_id_prefix_in_primary_match(self):
        """The old `[role=option], [id^=react-select-]` selector must not appear
        as the primary querySelectorAll call. (Comment about the old pattern
        is allowed inside a `// chain_007` annotation block.)"""
        # Active call site for primary selector must not be the old broken one.
        self.assertNotIn("querySelectorAll('[role=option], [id^=react-select-]')", self.js)

    def test_fallback_scoped_to_option_elements(self):
        """Defensive fallback selector must include '-option-' substring guard
        so listbox/placeholder/live-region ids aren't matched."""
        self.assertIn('[id^=react-select-][id*="-option-"]', self.js)

    def test_documented_in_source(self):
        """Inline comment must call out the listbox-leak fix so the next
        person doesn't re-broaden the selector."""
        self.assertIn("LISTBOX", self.js)
        self.assertIn("listbox", self.js)

    def test_picks_first_match_via_startswith_then_includes(self):
        """Match strategy: startsWith first, then includes (unchanged from before)."""
        # Both helpers should still appear (preserved match logic).
        self.assertIn("startsWith(want)", self.js)
        self.assertIn("includes(want)", self.js)


if __name__ == "__main__":
    unittest.main()
