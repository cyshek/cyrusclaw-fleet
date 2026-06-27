"""Pinning tests for the 2-parent (cross-parent combo) prompt support added to
`_build_llm_prompt` on 2026-06-26.

The change is PURELY ADDITIVE: a new optional `second_parent` kwarg. These tests
lock two invariants:

  1. BACKWARD-COMPAT: calling `_build_llm_prompt(seed, directive, name)` with NO
     `second_parent` must produce output byte-identical to the pre-change
     behavior (so the protected-md5 enforcement path is semantically unchanged).
     We pin the exact MD5 captured from the pre-change implementation.

  2. SECOND-PARENT INJECTION: when `second_parent="rsi_oversold_spy"` is passed,
     the prompt MUST contain a clearly-labeled second-parent reference block that
     includes that parent's actual strategy.py source (so cross-parent combos see
     real code, not just a prose description), WITHOUT clobbering the primary
     seed parent's block.
"""
from __future__ import annotations

import hashlib

from runner.strategy_gen import _build_llm_prompt

# Golden MD5 of the pre-change default output for this exact call. Captured
# 2026-06-26 BEFORE adding the second_parent kwarg. If this changes, the
# backward-compat invariant is broken (existing single-parent mutation prompts
# would silently shift).
_GOLDEN_DEFAULT_MD5 = "c122c51be2662bbecf477a71eaa0b3ce"
_GOLDEN_DEFAULT_LEN = 13376


def test_default_call_is_byte_identical_to_pre_change():
    """No second_parent -> output unchanged vs pre-change implementation."""
    out = _build_llm_prompt("breakout_xlk", "TEST DIRECTIVE XYZ", "cand_test_123")
    assert len(out) == _GOLDEN_DEFAULT_LEN, (
        f"length drift: got {len(out)}, expected {_GOLDEN_DEFAULT_LEN}"
    )
    assert hashlib.md5(out.encode()).hexdigest() == _GOLDEN_DEFAULT_MD5, (
        "default _build_llm_prompt output changed — backward-compat broken"
    )


def test_default_call_has_no_second_parent_section():
    out = _build_llm_prompt("breakout_xlk", "TEST DIRECTIVE XYZ", "cand_test_123")
    assert "SECOND PARENT" not in out
    # The second parent's name should not leak into a single-parent prompt.
    assert "rsi_oversold_spy" not in out


def test_second_parent_injects_its_code():
    """Passing second_parent injects a labeled block with that parent's source."""
    out = _build_llm_prompt(
        "breakout_xlk",
        "Combine the breakout entry with the second parent's RSI mean-reversion.",
        "cand_combo_123",
        second_parent="rsi_oversold_spy",
    )
    # Labeled section present.
    assert "SECOND PARENT" in out
    # The second parent's module name is referenced.
    assert "rsi_oversold_spy" in out
    # The second parent's ACTUAL code is injected — `decide` def plus an
    # RSI-specific token that appears in that strategy's source.
    assert "def decide(" in out
    assert "rsi" in out.lower()


def test_second_parent_preserves_primary_seed_block():
    """The primary seed parent block must still be present + come first."""
    out = _build_llm_prompt(
        "breakout_xlk",
        "Combine with second parent.",
        "cand_combo_456",
        second_parent="rsi_oversold_spy",
    )
    # Primary seed parent still named in its own block.
    assert "`breakout_xlk`" in out
    # Primary parent block header appears BEFORE the second-parent header.
    idx_primary = out.find("Parent strategy")
    idx_second = out.find("SECOND PARENT")
    assert idx_primary != -1 and idx_second != -1
    assert idx_primary < idx_second, "primary parent block must precede second parent"


def test_second_parent_none_explicit_equals_default():
    """Explicit second_parent=None behaves exactly like omitting it."""
    a = _build_llm_prompt("breakout_xlk", "D", "n")
    b = _build_llm_prompt("breakout_xlk", "D", "n", second_parent=None)
    assert a == b


def test_unknown_second_parent_degrades_gracefully():
    """A nonexistent second parent must not raise; it degrades to a note."""
    out = _build_llm_prompt(
        "breakout_xlk",
        "Combine with second parent.",
        "cand_combo_789",
        second_parent="does_not_exist_zzz",
    )
    # Still labeled, but flags the missing source rather than crashing.
    assert "SECOND PARENT" in out
    assert "does_not_exist_zzz" in out
