"""Tests for the Google adapter's Min-quals YOE-floor parse (Cyrus 2026-06-08
re-enable, BACKLOG #1).

Covers the EXACT rule:
  - scope to 'Minimum qualifications' block ONLY (heading -> next section)
  - take the MAX '<N> years' in that block as the floor
  - IGNORE 'Preferred qualifications' entirely
  - no year in min block => unstated (keep)
And the downstream gate behaviour via core.is_qualifying_experience, plus the
exp_required string format core._EXP_NUM_RE parses, the title gate, and the
(best-effort, usually empty) posting-date scrape.

Fixtures use Google's REAL double-escaped HTML shape (\\u003c for '<') so the
decode path is exercised end-to-end.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "adapters"))

import google as G  # noqa: E402
from core import (  # noqa: E402
    exp_lower_bound,
    is_qualifying_experience,
    is_qualifying_title,
    is_us_location,
)


# --- Realistic fixtures (Google double-escaped server HTML) ----------------

def _gjd(min_quals_html: str, preferred_html: str = "", trailing: str = "About the job") -> str:
    """Build a Google-shaped JD page fragment with double-escaped HTML.

    `min_quals_html` / `preferred_html` are the inner <li> bodies (plain text
    lines joined). We wrap them in the same \\u003c-escaped markup Google emits.
    """
    def _ul(lines):
        items = "".join(f"\\u003cli\\u003e{ln}\\u003c/li\\u003e" for ln in lines)
        return f"\\u003cul\\u003e{items}\\u003c/ul\\u003e"

    parts = [
        "\\u003ch3\\u003eMinimum qualifications:\\u003c/h3\\u003e",
        _ul(min_quals_html if isinstance(min_quals_html, list) else [min_quals_html]),
    ]
    if preferred_html:
        parts.append("\\u003ch3\\u003ePreferred qualifications:\\u003c/h3\\u003e")
        parts.append(_ul(preferred_html if isinstance(preferred_html, list) else [preferred_html]))
    parts.append(f"\\u003ch3\\u003e{trailing}:\\u003c/h3\\u003e")
    return "<html><body>" + "".join(parts) + "</body></html>"


# (a) "8 years PM + 3 years technical" => floor 8 => DROP
FIX_A = _gjd(
    min_quals_html=[
        "Bachelor’s degree or equivalent practical experience.",
        "8 years of experience in product management.",
        "3 years of experience in a technical role.",
    ],
    preferred_html=["MBA or advanced degree."],
)

# (b) "2 years of experience" => floor 2 => KEEP
FIX_B = _gjd(
    min_quals_html=[
        "Bachelor’s degree or equivalent practical experience.",
        "2 years of experience in program management.",
    ],
    preferred_html=["1 year of experience with SQL."],
)

# (c) min "2 years" + Preferred "10 years" => Preferred IGNORED => floor 2 => KEEP
FIX_C = _gjd(
    min_quals_html=[
        "Bachelor’s degree or equivalent practical experience.",
        "2 years of experience in a customer-facing role.",
    ],
    preferred_html=[
        "10 years of experience in enterprise sales engineering.",
        "5 years of experience leading technical teams.",
    ],
)

# (d) no year in min block => unstated => KEEP
FIX_D = _gjd(
    min_quals_html=[
        "Bachelor’s degree or equivalent practical experience.",
        "Experience with cloud platforms and customer-facing technical work.",
    ],
    preferred_html=["7 years of experience in solutions architecture."],
)


# --- The 4 mandatory YOE-parse cases ---------------------------------------

def test_a_max_year_in_min_block_floor8_drops():
    floor = G.parse_min_quals_floor(FIX_A)
    assert floor == 8, f"expected MAX(8,3)=8, got {floor}"
    exp = G._exp_required_from_floor(floor)
    assert exp == "exp:8+yrs"
    assert exp_lower_bound(exp) == 8
    assert is_qualifying_experience(exp) is False  # 8 >= 4 -> DROP


def test_b_single_2yr_floor2_keeps():
    floor = G.parse_min_quals_floor(FIX_B)
    assert floor == 2, f"expected 2, got {floor}"
    exp = G._exp_required_from_floor(floor)
    assert exp == "exp:2+yrs"
    assert exp_lower_bound(exp) == 2
    assert is_qualifying_experience(exp) is True  # 2 <= 3 -> KEEP


def test_c_preferred_10yr_ignored_floor2_keeps():
    floor = G.parse_min_quals_floor(FIX_C)
    assert floor == 2, f"Preferred 10yr must be ignored; expected 2, got {floor}"
    exp = G._exp_required_from_floor(floor)
    assert exp == "exp:2+yrs"
    assert is_qualifying_experience(exp) is True  # KEEP


def test_d_no_year_in_min_block_unstated_keeps():
    floor = G.parse_min_quals_floor(FIX_D)
    assert floor is None, f"expected None (unstated), got {floor}"
    exp = G._exp_required_from_floor(floor)
    assert exp == "exp:unstated"
    assert exp_lower_bound(exp) is None
    assert is_qualifying_experience(exp) is True  # unstated -> KEEP


# --- Supporting parse-robustness checks ------------------------------------

def test_min_quals_block_extraction_stops_at_preferred():
    text = G._decode_google_html(FIX_C)
    block = G.extract_min_quals_block(text)
    assert "customer-facing" in block
    assert "enterprise sales engineering" not in block, "block leaked into Preferred"
    assert "10 years" not in block


def test_plus_years_and_yrs_variants_parse():
    fx = _gjd(min_quals_html=["5+ years of experience.", "3 yrs of leadership."])
    assert G.parse_min_quals_floor(fx) == 5


def test_missing_min_quals_heading_returns_none():
    fx = "<html><body>\\u003ch3\\u003eAbout the job:\\u003c/h3\\u003e some text 6 years</body></html>"
    assert G.parse_min_quals_floor(fx) is None


def test_job_not_found_via_detail_returns_unstated(monkeypatch):
    class _R:
        status_code = 200
        text = "Job not found."

    monkeypatch.setattr(G, "http_get", lambda *a, **k: _R())
    floor, posted = G._fetch_detail("123")
    assert floor is None and posted == ""


# --- Posting-date scrape (best-effort; usually empty for Google) ------------

def test_scrape_posted_date_empty_when_no_label():
    # Google JD pages carry no labelled date -> "".
    assert G.scrape_posted_date(FIX_A) == ""


def test_scrape_posted_date_jsonld_when_present():
    html = '<script type="application/ld+json">{"datePosted":"2026-05-30","title":"PM"}</script>'
    assert G.scrape_posted_date(html) == "2026-05-30"


def test_scrape_posted_date_label_when_present():
    html = "<html><body>Posted on 2026-06-01 in Mountain View</body></html>"
    assert G.scrape_posted_date(html) == "2026-06-01"


# --- Title-gate integration (confirm senior/group/etc drop) ----------------

def test_title_gate_drops_senior_group_director():
    assert is_qualifying_title("Group Product Manager, Search") is False
    assert is_qualifying_title("Senior Product Manager") is False
    assert is_qualifying_title("Director, ML Platform") is False
    # Level-3+/III+ suffix drops; levels I/II are KEPT (existing doctrine: 1,2,I,II allowed).
    assert is_qualifying_title("Customer Engineer III, Platform, Google Cloud") is False
    assert is_qualifying_title("Solutions Architect IV, Google Cloud") is False
    # Keeps: vanilla qualifying titles incl. level I/II
    assert is_qualifying_title("Product Manager") is True
    assert is_qualifying_title("Product Manager I, Ads") is True
    assert is_qualifying_title("Customer Engineer II, Platform, Google Cloud") is True  # II = mid, kept
    assert is_qualifying_title("Customer Engineer, Platform, Google Cloud") is True


def test_us_location_gate_google_strings():
    assert is_us_location("Mountain View, CA, USA") is True
    assert is_us_location("Bengaluru, India") is False
    assert is_us_location("Mountain View, CA, USA; Bengaluru, India") is True  # one US slot


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
