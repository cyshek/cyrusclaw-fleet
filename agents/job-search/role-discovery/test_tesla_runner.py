"""Tests for _tesla_runner answer heuristics (Cyrus: US citizen, no sponsorship,
authorized, open to relocate/onsite). Run: python3 -m pytest test_tesla_runner.py -q
Importing the module is safe — playwright is imported lazily inside run()."""
import importlib.util, os

_spec = importlib.util.spec_from_file_location(
    "_tesla_runner", os.path.join(os.path.dirname(__file__), "_tesla_runner.py"))
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)


def test_sponsorship_is_no():
    # SPON -> No: Cyrus needs no immigration sponsorship.
    assert tr.LEGAL_RADIO_ANSWERS["legal.legalImmigrationSponsorship"] == "no"


def test_willingness_consider_other_positions_is_yes():
    # AFFIRM willingness -> Yes.
    assert tr.LEGAL_RADIO_ANSWERS["legal.legalConsiderOtherPositions"] == "yes"


def test_former_employer_questions_are_no():
    assert tr.LEGAL_RADIO_ANSWERS["legal.legalFormerTeslaEmployee"] == "no"
    assert tr.LEGAL_RADIO_ANSWERS["legal.legalFormerTeslaInternOrContractor"] == "no"


def test_notice_period_immediately():
    assert tr.LEGAL_NOTICE_PERIOD == "immediately"


def test_eeo_all_decline():
    # Privacy-respecting standard: decline to self-identify on every EEO field.
    assert set(tr.EEO_SELECT_ANSWERS.values()) == {"choose_not_to_disclose"}
    for k in ("eeo.eeoGender", "eeo.eeoVeteranStatus",
              "eeo.eeoRaceEthnicity", "eeo.eeoDisabilityStatus"):
        assert tr.EEO_SELECT_ANSWERS[k] == "choose_not_to_disclose"


def test_personal_constants():
    import json as _j, re as _re, os as _os
    _pi = _j.load(open(_os.path.join(_os.path.dirname(__file__), "..", "personal-info.json")))
    _id = _pi["identity"]
    _digits = lambda p: _re.sub(r'[^0-9]','',p or '')
    assert tr.EMAIL() == _id["email"]
    assert tr.PHONE() == _digits(_id["phone"])
    assert tr.FIRST() == _id["first_name"] and tr.LAST() == _id["last_name"]


def test_no_yes_radio_values_only():
    # Every legal radio answer must be a literal 'yes'/'no' (the form's option values).
    assert all(v in ("yes", "no") for v in tr.LEGAL_RADIO_ANSWERS.values())
