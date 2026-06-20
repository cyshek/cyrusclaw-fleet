"""Regression: a Yes/No 'commuting distance to ... New York City / relocating
at your own expense' question must route to answer_yes, NOT the generic
('city','city') address resolver (which previously stole it via the 'city'
substring in 'New York City' and filled the home city 'Kirkland').

Shipped 2026-06-10 (Swayable 2623). Cyrus: US onsite/relocation is NEVER a
knockout -> answer Yes.
"""
import greenhouse_dryrun as gd


def _first_match(label):
    lab = label.lower()
    for needle, key in gd.LABEL_RULES:
        if needle in lab:
            return needle, key
    return None, None


def test_swayable_commute_question_routes_to_answer_yes():
    label = ("Are you currently located within commuting distance to San Francisco "
             "or New York City OR comfortable relocating to one of these areas at "
             "your own expense?")
    needle, key = _first_match(label)
    assert key == "answer_yes", f"got {needle!r}->{key!r}"


def test_plain_city_field_still_routes_to_city():
    # a genuine 'City' address field must STILL use the city resolver
    needle, key = _first_match("City")
    assert key == "city"


def test_current_city_field_still_city():
    needle, key = _first_match("Current City")
    assert key == "city"


def test_commuting_distance_generic_yes():
    needle, key = _first_match("Are you within commuting distance of our Austin office?")
    assert key == "answer_yes"
