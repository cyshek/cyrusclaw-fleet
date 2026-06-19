"""education_answers.py — single source of truth for academic-field form answers.

Imported by `greenhouse_filler.py` / `greenhouse_dryrun.py`, `ashby_filler.py`,
and `workday_playwright.py` so all three ATSes use identical answers when an
application form has academic fields (School, Degree, Major, Minor, GPA,
SAT, ACT, GRE).

Source of truth: MEMORY.md "Education / academic-field answers" section
(2026-05-29) + `projects/job-search/resume/Cyrus_Shekari_Resume.txt`.

Cyrus's secondary school (HS) info is intentionally absent — if a form
HARD-requires HS, the calling driver MUST flag BLOCKED-HS-INFO-NEEDED
(don't fabricate).

Created 2026-05-30 by `fix_gh_academic_fields` subagent (chain
`gh-academic-fields-2026-05-30`).
"""
from __future__ import annotations

import re
from typing import Iterable

# ---------------------------------------------------------------------------
# Canonical answers (MEMORY.md ground truth)
# ---------------------------------------------------------------------------

EDUCATION_ANSWERS: dict[str, object] = {
    # Plain values
    "school": "University of Houston",
    "school_city": "Houston",
    "school_state": "TX",
    # Degree shape varies per ATS: long-form ("Bachelor of Computer Science",
    # printed on resume), generic dropdown-friendly ("Bachelor's degree"),
    # or Workday-style ("Bachelors"). Helpers below pick the closest from a
    # given option list.
    "degree_canonical": "Bachelor of Computer Science",
    "degree_generic": "Bachelor's degree",
    "degree_workday": "Bachelors",
    "major": "Computer Science",
    "minor": "Mathematics",
    "gpa": "3.8",
    "gpa_scale": "4.0",
    "graduation_year": "2024",
    "start_year": "2021",
    "end_year": "2024",
    "start_month": "August",
    "end_month": "December",
    # Currently-enrolled? No, graduated Dec 2024.
    "currently_enrolled": False,
    "did_graduate": True,
    # Test scores: SAT taken, ACT/GRE not taken.
    # 2026-05-29 MEMORY.md: SAT 1580/1600 on current (post-2016) 1600 scale,
    # Math 800 + Reading/Writing 780. ACT and GRE: not taken.
    "sat_total": 1580,
    "sat_scale": 1600,
    "sat_math": 800,
    "sat_reading_writing": 780,
    "act_total": None,        # not taken
    "act_scale": 36,
    "gre_total": None,        # not taken
    "gre_scale": 340,
    # High school: NOT in resume. If a form hard-requires HS, flag for Cyrus.
    "high_school": None,
}

# Phrases dropdowns/buttons use to mean "I never took this test".
NOT_TAKEN_LABEL_PATTERNS: tuple[str, ...] = (
    "did not take", "do not recall", "not applicable", "n/a", "none of the",
    "i did not", "haven't taken", "have not taken", "not taken",
    "other/not applicable", "prefer not", "do not wish",
)


def _norm(s: object) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _options_text(options: Iterable[object]) -> list[tuple[object, str]]:
    """Return [(original_option, normalized_label), ...] for any option shape.

    Accepts either raw strings or dicts shaped like Greenhouse's
    `{"label": "...", "value": ...}`.
    """
    out: list[tuple[object, str]] = []
    for opt in options or []:
        if isinstance(opt, dict):
            lbl = opt.get("label") or opt.get("name") or ""
        else:
            lbl = opt
        out.append((opt, _norm(lbl)))
    return out


def _find_not_taken(options: Iterable[object]) -> object | None:
    """Return the first option that means 'did not take', else None."""
    pairs = _options_text(options)
    for opt, lbl in pairs:
        for needle in NOT_TAKEN_LABEL_PATTERNS:
            if needle in lbl:
                return opt
    return None


def _score_match(score: int | None, scale: int, options: Iterable[object]) -> object | None:
    """For SAT/ACT/GRE dropdowns shaped like `'1580 out of 1600'`, find the
    option matching `score`. Falls back to 'did not take' if score is None or
    no numeric match.

    The matcher is intentionally generous about formatting:
    - "1580 out of 1600", "1580/1600", "1580", "SAT 1580", "1580 - 1600" all
      score-match.
    - For ACT (whole-integer scale 36) a bare "<n>" with no scale matches.
    """
    if score is None:
        return _find_not_taken(options)
    pairs = _options_text(options)
    s = str(int(score))
    # Exact match for "<score> out of <scale>" / "<score>/<scale>".
    exact = f"{score} out of {scale}".lower()
    slash = f"{score}/{scale}".lower()
    for opt, lbl in pairs:
        if lbl == exact or lbl == slash or lbl == s:
            return opt
    # Substring match: "<score>" anywhere as a token boundary.
    rx = re.compile(rf"(?<!\d){score}(?!\d)")
    for opt, lbl in pairs:
        if rx.search(lbl):
            return opt
    # No numeric match — fall back to "did not take" to avoid blocking submit.
    return _find_not_taken(options)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def match_sat_option(options: Iterable[object]) -> object | None:
    """Pick the dropdown option for Cyrus's SAT (1580/1600), else not-taken."""
    return _score_match(EDUCATION_ANSWERS["sat_total"], EDUCATION_ANSWERS["sat_scale"], options)


def match_act_option(options: Iterable[object]) -> object | None:
    """Pick the dropdown option for ACT — Cyrus didn't take it."""
    return _score_match(EDUCATION_ANSWERS["act_total"], EDUCATION_ANSWERS["act_scale"], options)


def match_gre_option(options: Iterable[object]) -> object | None:
    """Pick the dropdown option for GRE — Cyrus didn't take it."""
    return _score_match(EDUCATION_ANSWERS["gre_total"], EDUCATION_ANSWERS["gre_scale"], options)


def match_gpa_option(options: Iterable[object], gpa: str | None = None) -> object | None:
    """Pick a GPA dropdown option (e.g. '3.8 out of 4.0') for a numeric GPA."""
    g = gpa or EDUCATION_ANSWERS["gpa"]
    if g is None:
        return _find_not_taken(options)
    pairs = _options_text(options)
    needle = str(g).strip().lower()
    # Exact "3.8 out of 4.0" / "3.8/4.0" / "3.8".
    for opt, lbl in pairs:
        if lbl == needle or lbl.startswith(needle + " ") or lbl.startswith(needle + "/"):
            return opt
    # Substring (e.g. "GPA 3.8").
    rx = re.compile(rf"(?<!\d){re.escape(needle)}(?!\d)")
    for opt, lbl in pairs:
        if rx.search(lbl):
            return opt
    return None


def pick_degree_for_options(options: Iterable[object]) -> object | None:
    """Pick the best 'degree' dropdown option for a bachelor's holder.

    Tries (in order): exact 'bachelor of computer science' match, then
    'bachelor of science', then any option containing 'bachelor'.
    """
    pairs = _options_text(options)
    if not pairs:
        return None
    candidates = [
        "bachelor of computer science",
        "bachelor of science",
        "bachelor's degree",
        "bachelors degree",
        "bachelor's",
        "bachelors",
    ]
    for needle in candidates:
        for opt, lbl in pairs:
            if lbl == needle:
                return opt
    # Anything containing "bachelor".
    for opt, lbl in pairs:
        if "bachelor" in lbl:
            return opt
    return None


def is_high_school_required(label: str) -> bool:
    """True if a field label is asking specifically about HIGH SCHOOL.

    Used by drivers so they can write `BLOCKED-HS-INFO-NEEDED` instead of
    fabricating a HS name.
    """
    if not label:
        return False
    l = label.lower()
    if "high school" in l or "secondary school" in l or "secondary education" in l:
        return True
    return False
