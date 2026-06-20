"""LABEL_RULES grind-gap additions (2026-06-08, Rogo/grind batch).

Fills four resolver gaps that previously fell through to `unresolved` and banked
the field `uncertain`:
  1. "willing to travel up to 20%" / "willing to travel" -> affirmative
     (willing_to_travel resolver, now Yes/No-option-aware).
  2. CJIS clearance affirmation-of-understanding + "contingent upon maintaining"
     -> answer_yes (benign affirmation, NOT a claim of holding a clearance).
  3. "from where do you intend to work" -> city_state (home location text).
  4. "Agree"-only affirmation class (option literally "Agree", no "Yes") -> Agree.
Plus a regression that plain "Yes" still wins for answer_yes.
"""
import greenhouse_dryrun as g

# Minimal personal stub mirroring the real personal-info.json shape used by the
# resolvers exercised here.
P = {
    "address": {"city": "Kirkland", "state": "WA"},
    "preferences": {"willing_to_travel_pct": "25"},
    "work_authorization": {"status": "us_citizen"},
}


def test_willing_to_travel_pct_label_resolves_affirmatively():
    # "Are you willing to travel up to 20%?" -> willing_to_travel resolver.
    assert g.find_resolver("Are you willing to travel up to 20%?") == "willing_to_travel"
    assert g.find_resolver("Are you willing to travel?") == "willing_to_travel"
    # On a Yes/No select the resolver must pick 'Yes' (NOT emit "25%" text that
    # matches no option and banks the field empty).
    f = {"values": [{"label": "Yes", "value": "1"}, {"label": "No", "value": "0"}]}
    st, val, _ = g.r_willing_to_travel(P, f)
    assert st == "ok" and val == "Yes"
    # Free-text (no options) still returns the truthful pct string.
    st2, val2, _ = g.r_willing_to_travel(P, {})
    assert st2 == "ok" and val2 == "25%"


def test_cjis_clearance_affirmation_resolves_yes():
    # "contingent upon maintaining a valid CJIS clearance ... do you understand?"
    assert g.find_resolver(
        "This offer is contingent upon maintaining a valid CJIS clearance. Do you understand?"
    ) == "answer_yes"
    assert g.find_resolver(
        "I affirm my understanding of the CJIS clearance requirement"
    ) == "answer_yes"
    # MUST NOT be stolen by the generic clearance/security-clearance rules.
    assert g.find_resolver("Do you maintain a valid CJIS clearance?") == "answer_yes"


def test_from_where_do_you_intend_to_work_resolves_to_city_state():
    assert g.find_resolver("From where do you intend to work?") == "city_state"
    assert g.find_resolver("Where do you intend to work?") == "city_state"
    # And the resolver yields the home city+state text.
    st, val, _ = g.r_city_state(P, {})
    assert st == "ok" and val == "Kirkland, WA"


def test_agree_only_affirmation_picks_agree():
    # Affirmation select whose only positive option is the literal "Agree"
    # (no "Yes"/"I agree"/"I acknowledge"). answer_yes must pick "Agree".
    f = {"values": [{"label": "Agree", "value": "1"}, {"label": "Disagree", "value": "2"}]}
    st, val, _ = g.r_answer_yes(P, f)
    assert st == "ok" and val == "Agree"


def test_answer_yes_plain_yes_still_wins_regression():
    # Regression: a normal Yes/No select must still resolve to 'Yes', and the
    # I-agree / I-acknowledge / sole-option affirmative paths must be unaffected.
    f_yes = {"values": [{"label": "Yes", "value": "1"}, {"label": "No", "value": "2"}]}
    assert g.r_answer_yes(P, f_yes)[1] == "Yes"
    f_iagree = {"values": [{"label": "I agree", "value": "1"}, {"label": "No", "value": "2"}]}
    assert g.r_answer_yes(P, f_iagree)[1] == "I agree"
    f_sole = {"values": [{"label": "I acknowledge and accept", "value": "1"}]}
    assert g.r_answer_yes(P, f_sole)[1] == "I acknowledge and accept"


def test_new_rules_do_not_collide_with_export_or_extreme_hours():
    # ITAR/export inverted-polarity must still route to itar_us_person_ack, NOT
    # to the new answer_yes CJIS rule.
    assert g.find_resolver(
        "Does the deemed export rule affect your employment?"
    ) == "itar_us_person_ack"
    # Extreme-hours 996 still auto-answers via the find_resolver chokepoint.
    assert g.find_resolver("Are you willing to work 996?") == "answer_yes"


# --- bare / home single-line address fields (Zuora 2755, 2026-06-08) ----------
# 'Home Address' previously returned None from find_resolver -> no plan emitted
# -> the row banked blocked 'prep-blocker: Home address field no LABEL_RULES
# match'. A bare single-line address box wants the full one-line mailing address.
_ADDR_P = {
    "address": {
        "street": "123 Example St",
        "city": "Kirkland",
        "state": "WA",
        "zip": "98034",
        "country": "United States",
    }
}


def test_bare_and_home_address_labels_resolve_to_full_address():
    for lbl in (
        "Home Address",
        "Home address",
        "Address",
        "Current Address",
        "Your address",
        "Personal Address",
        "Candidate Address",
        "Full Address",
        "What is your address?",
    ):
        assert g.find_resolver(lbl) == "full_address", lbl


def test_full_address_resolver_emits_one_line_address():
    st, val, _ = g.r_full_address(_ADDR_P, {})
    assert st == "ok"
    # full one-line: street, city, state zip
    assert val == "123 Example St, Kirkland, WA 98034"
    # No street on file -> degrade to city/state, never block.
    p2 = {"address": dict(_ADDR_P["address"], street="")}
    st2, val2, _ = g.r_full_address(p2, {})
    assert st2 == "ok" and val2 == "Kirkland, WA 98034"
    # Dropdown variant defers to city_state option matching.
    f = {"values": [{"label": "Washington"}, {"label": "Oregon"}]}
    st3, val3, _ = g.r_full_address(_ADDR_P, f)
    assert st3 == "ok" and val3 == "Washington"


def test_bare_address_does_not_steal_more_specific_address_labels():
    # The bare 'address' catch must stay below every more-specific address rule
    # AND below the 'email' rule (so 'email address' -> email).
    assert g.find_resolver("Street Address") == "street"
    assert g.find_resolver("Legal Address") == "street"
    assert g.find_resolver("Address Line 1") == "street"
    assert g.find_resolver("Address Line 2") == "optional_blank"
    assert g.find_resolver("Mailing Address") == "city_state"
    assert g.find_resolver("Residential Address") == "city_state"
    assert g.find_resolver("Email Address") == "email"
    assert g.find_resolver("What is your email address?") == "email"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
