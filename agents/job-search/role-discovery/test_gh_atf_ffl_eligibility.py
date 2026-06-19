"""
test_gh_atf_ffl_eligibility.py — regression coverage for the ATF Form 4473
"prohibited person" federal-firearms-eligibility question block + the
Federal Firearms Licensee acknowledge wrapper + BeyondTrust Korea geo/language
knockout screeners (added 2026-06-08, Axon role 2831 / BeyondTrust role 2739).

Why these matter: Axon is a Federal Firearms Licensee, so its Greenhouse
application appends the standard ATF 4473 prohibited-person attestations as
REQUIRED Yes/No selects. Before this fix every one banked "no LABEL_RULES match"
-> the whole row stalled "uncertain". For Cyrus (U.S. citizen, no convictions,
not on a nonimmigrant visa, never renounced citizenship, no restraining orders,
not a controlled-substance addict) all of them are a truthful No, the FFL
questionnaire is a sole-option Acknowledge, and "reside in greater Seattle" is a
truthful Yes (Kirkland WA). BeyondTrust's Korea-residence / Korean-fluency
screeners are a truthful No (legitimate knockout, but answered not banked).

These are NEGATIVE attestations / forced acknowledgements, never biographical
claims that could falsely help an application.
"""
import json
import os
import unittest

import greenhouse_dryrun as gh

HERE = os.path.dirname(os.path.abspath(__file__))
PERSONAL = json.load(open(os.path.join(HERE, "..", "personal-info.json")))

YN = [{"label": "Yes", "value": 1}, {"label": "No", "value": 0}]
FFL_ACK = [{"label": "Acknowledge", "value": 162831015003}]

# (label, raw field options, expected resolver, expected committed value)
ATF_NO_CASES = [
    ("Are you a fugitive from justice?", YN),
    ("Are you an alien illegally or unlawfully in the United States?", YN),
    ("Are you an alien who has been admitted to the United States under a "
     "nonimmigrant visa? (i.e. H-1B, TN, F1)", YN),
    ("Are you an unlawful user of, or addicted to, marijuana or any depressant, "
     "stimulant, narcotic drug, or any other controlled substance? \n", YN),
    ("Are you subject to a court order, including a Military Protection Order "
     "issued by a military judge or magistrate, restraining you from harassing, "
     "stalking, or threatening your child or an intimate partner or child of "
     "such partner?", YN),
    ("Have you ever been adjudicated as a mental defective OR have you ever been "
     "committed to a mental institution?", YN),
    ("Have you ever been convicted in any court of a misdemeanor crime of "
     "domestic violence, or are you or have you ever been a member of the "
     "military and been convicted of a crime that included, as an element, the "
     "use of force against a person as identified in the instructions?", YN),
    ("Have you ever been discharged from the Armed Forces under dishonorable "
     "conditions?", YN),
    ("Have you ever renounced your United States citizenship?", YN),
]

KOREA_NO_CASES = [
    ("Are you currently living in the Republic of Korea? ", YN),
    ("Do you speak fluent/native level Korean? ", YN),
]


def _resolve(label, vals):
    fld = {"name": "q", "type": "multi_value_single_select", "values": vals}
    return gh.resolve_field(PERSONAL, label, True, fld)


class TestAtfProhibitedPersonNo(unittest.TestCase):
    def test_all_atf_questions_route_to_answer_no(self):
        for label, _ in ATF_NO_CASES:
            self.assertEqual(
                gh.find_resolver(label), "answer_no",
                f"ATF question should route to answer_no: {label!r}")

    def test_all_atf_questions_commit_no_value(self):
        for label, vals in ATF_NO_CASES:
            out = _resolve(label, vals)
            self.assertNotEqual(out["status"], "unresolved",
                                f"ATF question left unresolved: {label!r}")
            self.assertEqual(out["value"], "No",
                             f"ATF question should commit 'No': {label!r}")


class TestFflAcknowledge(unittest.TestCase):
    def test_ffl_questionnaire_routes_to_pick_only_option(self):
        self.assertEqual(
            gh.find_resolver("Federal Firearms Licensee Employee Accessor "
                             "Questionnaire"),
            "pick_only_option")

    def test_ffl_questionnaire_commits_sole_acknowledge_option(self):
        out = _resolve("Federal Firearms Licensee Employee Accessor "
                       "Questionnaire", FFL_ACK)
        self.assertNotEqual(out["status"], "unresolved")
        self.assertEqual(out["value"], "Acknowledge")


class TestKoreaKnockoutScreeners(unittest.TestCase):
    def test_korea_residence_and_language_route_to_answer_no(self):
        for label, _ in KOREA_NO_CASES:
            self.assertEqual(gh.find_resolver(label), "answer_no",
                             f"Korea screener should route to answer_no: {label!r}")

    def test_korea_screeners_commit_no(self):
        for label, vals in KOREA_NO_CASES:
            out = _resolve(label, vals)
            self.assertEqual(out["value"], "No",
                             f"Korea screener should commit 'No': {label!r}")


class TestSeattleResidenceTruthfulYes(unittest.TestCase):
    """Pre-existing rule, guard so it doesn't regress: Cyrus IS in greater
    Seattle (Kirkland WA), so this is a truthful Yes — must NOT get swept into
    the new answer_no block."""

    def test_seattle_residence_routes_to_answer_yes(self):
        self.assertEqual(
            gh.find_resolver("Do you currently reside in the greater Seattle area?"),
            "answer_yes")

    def test_seattle_residence_commits_yes(self):
        out = _resolve("Do you currently reside in the greater Seattle area?", YN)
        self.assertEqual(out["value"], "Yes")


class TestNoCollisionWithWorkAuth(unittest.TestCase):
    """The 'alien admitted under a nonimmigrant visa' / 'nonimmigrant' phrasing
    must NOT steal the genuine sponsorship/work-authorization questions, and the
    new answer_no rules must not flip a real work-auth question to a wrong No."""

    def test_authorized_to_work_still_resolves_yes_class(self):
        # Should route to work_authorized (Yes), NOT answer_no.
        r = gh.find_resolver("Are you authorized to work in the United States?")
        self.assertEqual(r, "work_authorized")

    def test_sponsorship_question_unaffected(self):
        r = gh.find_resolver(
            "Will you now or in the future require visa sponsorship?")
        self.assertEqual(r, "needs_sponsorship")


if __name__ == "__main__":
    unittest.main()
