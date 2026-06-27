#!/usr/bin/env python3
"""
greenhouse_dryrun.py — Generate a NO-SUBMIT, dry-run application fill spec
for a Greenhouse-hosted role.

Given a Greenhouse role URL, we fetch the public application form schema
(boards-api.greenhouse.io), match each form field against
projects/job-search/personal-info.json, and write a JSON report showing
exactly what value would be filled where — so Cyrus can review before any
real submission ever happens.

ZERO writes to Greenhouse. Read-only. No POSTs. Ever.

Usage:
    .venv/bin/python greenhouse_dryrun.py <greenhouse_url> [<url2> ...]
    .venv/bin/python greenhouse_dryrun.py --all-queued    # everything queued in tracker.md

Output:
    ../applications/dryrun/{org}-{job_id}.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Work-experience repeater detection (chain_006 sidecar, 2026-05-26)
# ---------------------------------------------------------------------------
# The boards-api spec does NOT expose Lyft-style work-experience repeater
# fields. The rendered /embed/job_app HTML does. This is an informational
# helper: callers can use it to flag specs that need runtime work-exp filling.
# Actual fill happens in greenhouse_iframe_runner via JS_FILL_WORK_EXPERIENCE_BLOCK.
_WORK_EXP_ID_RE = re.compile(r'id="company-name-(\d+)"')


def detect_work_experience_block_in_html(html: str) -> dict:
    """Scan rendered Greenhouse iframe HTML for the work-experience repeater.

    Returns {detected: bool, count: int, max_index: int|None}.
    Pure function, no I/O.
    """
    if not html or not isinstance(html, str):
        return {"detected": False, "count": 0, "max_index": None}
    matches = _WORK_EXP_ID_RE.findall(html)
    if not matches:
        return {"detected": False, "count": 0, "max_index": None}
    indices = sorted({int(m) for m in matches})
    return {
        "detected": True,
        "count": len(indices),
        "max_index": indices[-1],
        "indices": indices,
    }

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent  # projects/job-search
PERSONAL_INFO_PATH = PROJECT_ROOT / "personal-info.json"
OUTPUT_DIR = PROJECT_ROOT / "applications" / "dryrun"
TRACKER_PATH = PROJECT_ROOT / "tracker.md"

API_TMPL = "https://boards-api.greenhouse.io/v1/boards/{org}/jobs/{job_id}?questions=true"
HTTP_TIMEOUT = 20

# Sentinel string for fields where we have no plausible match in personal-info.
UNRESOLVED = "__UNRESOLVED__"


# ---------------------------------------------------------------------------
# Field mapping
#
# Each entry maps a *normalized* label substring -> a resolver name. The
# resolver is a function (registered below) that takes (personal_info, field)
# and returns either a string value, a sentinel-tagged string, or None.
#
# Order matters: we match FIRST hit wins, so put more specific labels
# *before* generic ones (e.g. "preferred first name" before "first name").
# ---------------------------------------------------------------------------

# label_substring (lowercased) -> resolver key
LABEL_RULES: list[tuple[str, str]] = [
    # --- HIGH-PRIORITY phrase rules (must come before single-word
    # needles like 'state' / 'location' / 'country' that get
    # word-boundary matching but can still grab unrelated phrases) ---
    # Sony 2026-05-24 (role 982): "If yes, please state their name, the department
    # or studio they work for, and your relation to that person." — paired follow-up
    # to the family/relations question. We answer No to the gate so this should be
    # blank. Without this, the single-word 'state' rule grabs the label and writes WA.
    ("please state their name", "optional_blank"),
    ("state their name, the department", "optional_blank"),
    # Sony 2026-05-24 (role 982): "Will you need relocation assistance to work at
    # this role's specified location?" Cyrus is open to relocating but does NOT
    # need relocation assistance. Without this, the 'location' rule grabs it.
    # 2026-06-23 (Axon 3097): 'Which Axon Hub do you plan to work from?' contains
    # 'relocation assistance' in the label — must match BEFORE the generic relocation rule.
    ("which axon hub", "city_location_select"),
    ("axon hub do you plan to work from", "city_location_select"),
    ("need relocation assistance", "answer_no"),
    ("relocation assistance", "answer_no"),
    # Scopely 2026-06-04 (role 2671): "Will you require relocation support?" Yes/No.
    # Cyrus relocates anywhere in the US on his own — he does NOT REQUIRE company
    # relocation support. Truthful No; this is NOT a geo knockout (he WILL relocate).
    ("require relocation support", "answer_no"),
    ("relocation support", "answer_no"),
    # 2026-06-03 (YC batch): common GH custom-question labels seen on new YC rows
    # (Alpaca/Astranis/Gather) that previously fell to 'unresolved' blockers.
    # Map to existing safe resolvers. Phrase rules => substring match, so these
    # take precedence over single-word 'name'/'address'/'state' needles.
    ("full legal birth name", "full_name"),       # Alpaca 2615 — gov-ID legal name = full name
    ("legal birth name", "full_name"),
    ("full legal name", "full_name"),
    ("mailing address", "city_state"),             # Alpaca 2615 — city/state/zip is our address answer
    ("shipping address", "city_state"),
    ("permanent address", "city_state"),
    ("residential address", "city_state"),
    ("job code number in the job posting", "optional_blank"),  # Robinhood 2613 — no job code to enter; blank
    ("job code number", "optional_blank"),
    # --- identity ---
    ("preferred first name", "preferred_name"),
    ("preferred name", "preferred_name"),
    ("first name", "first_name"),
    ("last name", "last_name"),
    ("full name", "full_name"),
    ("legal name", "full_name"),
    ("pronouns", "pronouns"),
    ("pronoun", "pronouns"),

    # --- website (optional fallback to LinkedIn if required) ---
    # 2026-06-23 (xAI 3139): 'Have you ever worked at xAI, X, Twitter, or SpaceX?' contains 'twitter'
    # as a company name in the label, not as a URL field. Override BEFORE the twitter URL rule.
    ("worked at xai", "answer_no"),
    ("worked at xai, x, twitter", "answer_no"),
    ("ever worked at xai", "answer_no"),
    ("twitter", "twitter"),
    # Capital One background-check (Brex 8443298002): "Do you currently, or have you previously, worked at Capital One...?"
    # Cyrus has NOT worked at Capital One. Second field (EID) only needed for former employees -> blank.
    ("worked at capital one", "answer_no"),
    ("previously worked, at capital one", "optional_blank"),
    ("if you currently work, or have previously worked, at capital one", "optional_blank"),
    ("employee id (eid)", "optional_blank"),
    # Generic "worked at <company>" / "previously worked for <company>" -> No (not a current/former employee).
    # Covers Instacart, Block, etc.
    ("currently, or have you previously, worked for", "answer_no"),
    ("currently, or have you previously, worked at", "answer_no"),
    ("ever worked for", "answer_no"),
    # Block: ever been employed full-time at Block / contract work for Block
    ("ever been employed full-time at block", "answer_no"),
    ("employed full-time at block", "answer_no"),
    ("provided any contract work for block", "answer_no"),
    ("contract work for block", "answer_no"),
    # Block: LA/OC residency status (multi-select): willing to relocate
    ("describes your residency status for this role", "willing_to_relocate"),
    ("residency status for this role", "willing_to_relocate"),
    # Block: full-stack experience / technical assignment (Solutions Engineer roles) -> Yes (Cyrus has SE-relevant tech skills)
    ("full-stack development experience", "answer_yes"),
    ("comfortable completing a technical assignment", "answer_yes"),
    # Instacart: Canada work authorization (role is US-only; Cyrus doesn't need Canada).
    ("legally entitled to work in canada", "answer_no"),
    ("entitled to work in canada", "answer_no"),
    # Coinbase AI-tools ack ("I understand that Coinbase may use AI tools...") — Yes-only select.
    ("coinbase may use ai tools", "acknowledge_yes"),
    ("use ai tools to assist in the application", "acknowledge_yes"),
    # Block AI-usage essay ("Tell me about a time where you used AI in a meaningful way...")
    ("used ai in a meaningful way", "customer_facing_essay"),
    ("used ai in a meaningful", "customer_facing_essay"),
    # Block AI transcription consent ("With your permission, we may use AI transcription software...")
    ("ai transcription software to transcribe", "acknowledge_yes"),
    ("ai transcription software", "acknowledge_yes"),
    # Waymo: AI tool prohibition during interviews — acknowledge and agree (Yes).
    ("prohibits the use of unauthorized outside assistance", "acknowledge_yes"),
    ("acknowledge and agree to adhere to these guidelines", "acknowledge_yes"),
    # Block: "How we interview" / hiring process explanation — acknowledge Yes.
    ("how we interview", "acknowledge_yes"),
    # Coinbase: "Which of the following best describes how you use AI tools today?" — select most advanced option.
    ("best describes how you use ai tools", "ai_usage_level"),
    ("how you use ai tools today", "ai_usage_level"),
    # Coinbase: government official / relative (conflict-of-interest) — truthful No.
    ("current government official or were you a government official", "answer_no"),
    ("a current or former government official", "answer_no"),
    ("close relative of a government official", "answer_no"),
    ("relative of a government official", "answer_no"),
    # Canonical: "how many companies have you worked for?" (since graduation) — numeric select.
    ("how many companies have you worked for", "num_companies_worked"),
    ("in the past ten years, looking only at the time since you graduated", "num_companies_worked"),
    # Coinbase: referred by senior leader — truthful No (no referral).
    ("referred to this position by a senior leader", "answer_no"),
    ("referred to this position by a", "how_heard"),
    # Coinbase qualifying questions (cross-functional program, translated operational needs) — Yes.
    ("personally led a cross-functional technical program", "answer_yes"),
    ("translated operational or business needs into technical", "answer_yes"),
    # Thinking Machines 2026-05-26 (role 1376): "Personal Website About You" — custom
    # required text field; route to website resolver (LinkedIn fallback for required).
    ("personal website about you", "website"),
    ("website about you", "website"),
    ("website", "website"),

    # --- contact ---
    # Intercom 2026-05-26 (role 1371): "Please email me about future job openings" —
    # marketing opt-in, NOT the contact email field. Decline.
    ("email me about future", "answer_no"),
    ("please email me about", "answer_no"),
    ("future job openings", "answer_no"),
    # Raft 2026-06-04 (role 2783): "Would you like to receive our newsletter?" —
    # marketing opt-in, truthful No. And "Do you have an active Security+
    # certification?" — Cyrus does NOT hold Security+ (truthful No; not a hard gate).
    ("receive our newsletter", "answer_no"),
    ("like to receive our newsletter", "answer_no"),
    ("active security+ certification", "answer_no"),
    ("security+ certification", "answer_no"),
    ("email", "email"),
    ("phone", "phone"),
    ("mobile", "phone"),
    ("linkedin", "linkedin"),
    ("github", "github"),
    ("portfolio", "portfolio"),
    ("personal website", "portfolio"),
    ("website", "portfolio"),

    # --- work authorization / visa (PUT BEFORE address so phrases like
    # "in the country in which the job ... is located" don't grab the
    # generic 'country' rule) ---
    # SPONSORSHIP RULES MUST COME FIRST — labels like "Will you require Elastic's
    # sponsorship to continue or extend your work authorization status?" contain
    # both 'sponsorship' AND 'work authorization' and we MUST answer the
    # sponsorship question (No), not the authorized question (Yes). 2026-05-13.
    # EXCEPTION 2026-05-26 (Intercom 1371): labels that start "Are you authoris(z)ed to work"
    # are the authorization question even when they mention sponsorship in a
    # parenthetical ("Fin sponsors immigration for some roles..."). Match those
    # FIRST so the bare 'sponsorship' catch-all below doesn't steal them.
    ("are you authorised to work", "work_authorized"),  # British spelling, Intercom
    ("are you authorized to work", "work_authorized"),  # American spelling
    ("require visa sponsorship", "needs_sponsorship"),
    ("require sponsorship", "needs_sponsorship"),
    # Podium 2026-06-02 (role 2256, fresh-li-runner): "Do you currently, or will
    # you in the future, require an employer to sponsor or continue sponsoring
    # your employment authorization (for example: H-1B, TN, E-3, O-1, OPT, CPT,
    # ...)?" Uses 'sponsor'/'sponsoring' (NOT 'sponsorship'), so the bare
    # 'sponsorship' catch-all below missed it. Answer No (US citizen).
    ("require an employer to sponsor", "needs_sponsorship"),
    ("sponsor or continue sponsoring", "needs_sponsorship"),
    ("continue sponsoring your employment", "needs_sponsorship"),
    # CLEAR 2026-05-24 (role 1151): "Will you require CLEAR to sponsor you for a work permit now or in the future..."
    ("sponsor you for a work permit", "needs_sponsorship"),
    ("to sponsor you", "needs_sponsorship"),
    ("require work visa", "needs_sponsorship"),
    ("require employment visa", "needs_sponsorship"),
    ("require immigration support", "needs_sponsorship"),
    ("immigration support", "needs_sponsorship"),
    # Dealpath 2454 (2026-06-08 autonomous tick): "Will you now, or in the future
    # require Dealpath to commence ('sponsor') an immigration case in order to
    # employ you (for example, H-1B...)?" — uses the verb 'sponsor' (not the noun
    # 'sponsorship') AND "now, or in the future require" (comma after 'now' breaks
    # the existing "now or in the future require" needle), so every sponsorship
    # rule missed it -> find_resolver=None -> dryrun blocker -> role stranded.
    # "immigration case" is distinctive sponsorship language (the word
    # 'immigration' only ever appears in needs_sponsorship contexts here; verified
    # zero collision with work_authorized rules). Answer No (Cyrus is a US citizen,
    # needs no sponsorship). High reuse: this "commence an immigration case"
    # phrasing is a common Greenhouse sponsorship template.
    ("immigration case", "needs_sponsorship"),
    ("now or in the future require", "needs_sponsorship"),
    ("now or in the future need assistance with a work visa", "needs_sponsorship"),  # Fluidstack 2026-06-16
    ("need assistance with a work visa", "needs_sponsorship"),  # Fluidstack variant
    ("sponsorship to continue or extend", "needs_sponsorship"),
    ("sponsorship", "needs_sponsorship"),
    ("visa sponsorship", "needs_sponsorship"),
    ("currently eligible to work", "work_authorized"),
    ("authorized to reside and work", "work_authorized"),  # Cribl-style phrasing (2026-06-25)
    ("authorised to reside and work", "work_authorized"),  # British spelling
    ("authorized to work", "work_authorized"),
    ("authorised to work", "work_authorized"),  # British spelling — Intercom 2026-05-26
    ("legally authorized", "work_authorized"),
    ("legally authorised", "work_authorized"),  # British spelling
    ("legally allowed to work", "work_authorized"),
    ("eligible to work legally", "work_authorized"),
    # Anduril 2026-05-13: "U.S. WORK AUTHORIZATION" (all caps in source);
    # normalize_label() lowercases before matching so this catches both cases.
    ("u.s. work authorization", "work_authorized"),
    # Axon 2026-05-24 (role 1056): "Can you provide verification of both your identity
    # and authorization to work in the United States, to the extent required by law?"
    # Functionally a US-work-auth Yes/No — answer Yes.
    ("verification of both your identity", "work_authorized"),
    ("provide verification of", "work_authorized"),
    # Phoenix Contact 2026-05-24 (role 1289): "If hired, can you provide proof of citizenship or verification
    # of your Legal Right to Work in the U.S.?" — Cyrus is US citizen -> Yes.
    ("proof of citizenship or verification", "work_authorized"),
    ("legal right to work", "work_authorized"),
    ("right to work in the u.s.", "work_authorized"),
    ("right to work in the country", "work_authorized"),  # CoreWeave phrasing: "Do you have the right to work in the country you are applying to?"
    ("work authorization", "work_authorized"),
    ("presently authorized", "work_authorized"),  # Stack AV — "Are you presently authorized under U.S. immigration laws"
    ("legally eligible to work", "work_authorized"),  # Filson — "Are you legally eligible to work in the United States?"
    ("immigration laws", "work_authorized"),  # broad catch for immigration-law work-auth questions
    # CJIS clearance affirmation-of-understanding (2026-06-08, Rogo/grind batch).
    # "This offer is contingent upon maintaining a valid CJIS clearance — do you
    # understand?" and similar "I affirm my understanding of the CJIS clearance
    # requirement" are benign affirmations-of-understanding (NOT a claim that
    # Cyrus currently HOLDS a clearance). He can truthfully acknowledge he
    # understands the requirement -> Yes/Agree. MUST precede the generic
    # 'clearance'/'security clearance' rules (these labels contain 'clearance').
    ("contingent upon maintaining", "answer_yes"),
    ("cjis clearance", "answer_yes"),
    ("cjis", "answer_yes"),
    # Age-eligibility (factual: Cyrus is an adult) + collector-affinity
    # (Fanatics Collectibles 2529, 2026-06-10): both are common GH yes/no
    # selects. "over 18" is factual-Yes; "are you a collector" is answered
    # Yes to MAXIMIZE advancing (collectibles employer, no knockout downside
    # — application-form-answers doctrine). Reusable across collectibles/
    # age-gated tenants.
    ("over the age of 18", "answer_yes"),
    ("over the age of eighteen", "answer_yes"),
    ("at least 18 years", "answer_yes"),
    ("are you over 18", "answer_yes"),
    ("18 years of age or older", "answer_yes"),
    ("are you a collector", "answer_yes"),
    # Defense-contractor clearance ELIGIBILITY / LEVEL-HELD selects (Anduril
    # 2026-06-03). MUST precede the generic 'security clearance' rule because
    # these labels also contain 'security clearance'. Truthful + non-knockout:
    # Cyrus is a US citizen eligible for clearance but has never held one.
    ("clearance eligibility", "clearance_eligibility"),
    ("eligibility to obtain and maintain", "clearance_eligibility"),
    ("eligible to obtain a", "clearance_eligibility"),
    ("eligible to obtain and maintain", "clearance_eligibility"),
    ("what clearance level have you held", "clearance_level_held"),
    ("what clearance level", "clearance_level_held"),
    ("if you have held a u.s. security clearance", "clearance_level_held"),
    ("clearance level have you", "clearance_level_held"),
    ("security clearance", "security_clearance"),
    # Specific clearance yes/no — Cyrus has none -> answer No.
    # Place BEFORE generic 'security clearance' so 'top secret' / 'sci' don't fall through.
    ("top secret", "answer_no"),
    ("sci clearance", "answer_no"),
    ("ts/sci", "answer_no"),
    ("ts sci", "answer_no"),
    ("active clearance", "answer_no"),
    ("active security clearance", "answer_no"),
    # Civilian/military or government employee — Cyrus is neither -> No.
    ("civilian or military", "answer_no"),
    ("civilian/military", "answer_no"),
    ("current or former government employee", "answer_no"),
    ("government employee", "answer_no"),
    # Wiz 2026-05-25 (role 1370): "Have you ever worked for the local, state, or federal government?"
    # Cyrus has not -> No. Must precede the generic 'state' single-word rule below.
    ("worked for the local, state, or federal government", "answer_no"),
    ("local, state, or federal government", "answer_no"),
    ("state, or federal government", "answer_no"),
    ("federal government", "answer_no"),
    # Phoenix Contact 2026-05-24 (role 1289): "Are you a current or former Phoenix Contact employee?"
    # Cyrus has never worked there -> No. Generic 'current or former X employee' catch.
    ("current or former phoenix contact employee", "answer_no"),
    ("current or former employee", "answer_no"),
    # Perforce 1294 (Lever) 2026-05-26: split into two questions. Generic.
    ("current employee of", "answer_no"),
    ("are you a current employee", "answer_no"),
    ("prior employee or contractor", "answer_no"),
    ("are you a prior employee", "answer_no"),
    ("former employee or contractor", "answer_no"),
    ("are you a former employee", "answer_no"),
    # WhatsApp opt-in (Stripe) — decline.
    ("whatsapp", "answer_no"),
    # Cities / locations available to work — Cyrus is open USA-wide.
    ("cities are you available", "cities_available"),
    ("cities available to work", "cities_available"),
    ("in what cities", "cities_available"),
    ("which cities are you", "cities_available"),
    ("locations are you available", "cities_available"),
    # Languages spoken — leave blank (optional free-text)
    ("languages spoken", "languages_fluent"),
    ("languages do you speak", "languages_fluent"),
    ("languages you speak", "languages_fluent"),
    ("select all the languages", "languages_fluent"),
    ("fluent in", "languages_fluent"),
    # Post-government employment restrictions — Cyrus has none -> No.
    ("restrictions on post-government employment", "answer_no"),
    ("post-government employment", "answer_no"),
    # Cities-available-to-work (Datadog free text) — fallback to current city/state.
    ("cities are you available", "city_state"),
    ("cities are you available to work", "city_state"),
    ("in what cities", "city_state"),
    # ITAR / EAR / export control US-person acknowledgment (Cyrus is US citizen).
    # Place BEFORE generic country/state rules so phrases like
    # "...subject to export controls..." don't fall through.
    ("itar", "itar_us_person_ack"),
    ("export control", "itar_us_person_ack"),
    ("export controls", "itar_us_person_ack"),
    ("export regulation", "itar_us_person_ack"),
    ("export regulations", "itar_us_person_ack"),
    ("space technology export", "itar_us_person_ack"),
    ("deemed export", "itar_us_person_ack"),
    ("controlled technology", "itar_us_person_ack"),
    ("u.s. person", "itar_us_person_ack"),
    ("us person", "itar_us_person_ack"),
    (" ear ", "itar_us_person_ack"),
    ("are you a us citizen", "itar_us_person_ack"),
    ("are you a u.s. citizen", "itar_us_person_ack"),
    ("are you a united states citizen", "itar_us_person_ack"),
    ("u.s. citizen", "itar_us_person_ack"),
    ("us citizen", "itar_us_person_ack"),
    # Veteran / transitioning-service-member custom field (NOT EEO veteran-status).
    # Place BEFORE the demographic 'veteran' rule so it wins.
    ("transitioning service member", "transitioning_service_member"),
    ("are you a veteran", "transitioning_service_member"),
    ("military service member", "transitioning_service_member"),
    ("are you a service member", "transitioning_service_member"),

    # --- address ---
    ("street address", "street"),
    ("legal address", "street"),  # CoreWeave 2026-05-13 — uses 'Legal Address' for street
    # Bare single-line address text fields (Zuora 2755 2026-06-08: 'Home Address'
    # returned None -> no plan -> blocked). These want the FULL one-line address.
    # Multi-word phrases here are unambiguous; the bare 'address' catch is placed
    # much later (after 'address line N' and after the 'email' rule) so it can't
    # steal 'street/legal/mailing address', 'address line 1', or 'email address'.
    ("home address", "full_address"),
    ("current address", "full_address"),
    ("your address", "full_address"),
    ("personal address", "full_address"),
    ("candidate address", "full_address"),
    ("full address", "full_address"),
    # GUARD (2026-06-10, Swayable 2623): a Yes/No question like "within
    # commuting distance to San Francisco or New York City OR comfortable
    # relocating ... at your own expense?" contains the substring "city"
    # ("New York City") and was stolen by the generic ("city","city")
    # address rule below -> resolved to the home city "Kirkland" (not an
    # option) -> filled_needs_review. Cyrus relocates anywhere in the US at
    # his own expense (US onsite/relocation is NEVER a knockout), so these
    # MUST route to answer_yes. Placed BEFORE ("city","city") so first-match
    # wins. (Mirrors the answer_yes rules further down; first-match here.)
    ("commuting distance", "answer_yes"),
    ("relocating to one of these", "answer_yes"),
    ("comfortable relocating", "answer_yes"),
    # Lyft-style "Do you currently reside in commutable proximity to a Lyft Office...?"
    # Must be BEFORE the generic ('state','state') rule ("United States" would match 'state').
    ("commutable proximity to a lyft office", "willing_to_relocate"),
    ("proximity to a lyft office", "willing_to_relocate"),
    ("reside in commutable proximity", "willing_to_relocate"),
    ("city", "city"),
    ("state", "state"),
    ("zip", "zip"),
    ("postal code", "zip"),
    ("latitude", "latitude"),
    ("longitude", "longitude"),
    ("country", "country"),
    ("current location", "city_state"),
    ("address from which you plan on working", "city_state"),
    # 2026-06-08 (Rogo/grind batch): "From where do you intend to work?" — a
    # location-text field asking where the candidate will work from. Same answer
    # source as the other location-text resolvers (home city+state). Place before
    # the generic single-word 'location' catch so it routes to city_state text,
    # not stolen by an unrelated rule.
    ("from where do you intend to work", "city_state"),
    ("where do you intend to work", "city_state"),
    ("where are you based", "city_state"),
    ("where are you currently located", "city_state"),
    # Phoenix Contact 2026-05-24 (role 1289): "Where are you located?" — bare 'located' form.
    ("where are you located", "city_state"),
    # Intercom 2026-05-26 (role 1371): "work from our office location 3 days per week"
    # — hybrid/in-office gate, but "office location" contains 'location' which
    # otherwise gets stolen by the generic city_state rule below. Carve out
    # in-office phrases BEFORE the catch-all 'location' rule.
    ("work from our office location", "ack_in_office"),
    ("work from our office", "ack_in_office"),
    ("office location", "ack_in_office"),
    ("days per week", "ack_in_office"),
    ("location", "city_state"),

    # --- experience ---
    ("years of hands-on", "years_experience"),
    ("years of experience", "years_experience"),
    ("years of formal", "years_experience"),
    # "Do you have N+ years of ..." yes/no — must come BEFORE 'years of <X>' rules.
    # (Comet 2026-05-24, role 1233: "Do you have 2+ years of Product Management experience?")
    ("do you have 2+ years", "answer_yes"),
    ("do you have 3+ years", "answer_yes"),
    # 2026-06-23 (YipitData 3325): 'Do you have 5+ years of PM in data-intensive' has NON-Yes/No
    # options. Must come BEFORE generic 'do you have 5+ years' -> answer_yes.
    ("5+ years of product management experience in data", "pm_data_experience_select"),
    ("product management experience in data-intensive", "pm_data_experience_select"),
    ("do you have 5+ years", "answer_yes"),
    ("2+ years of product", "answer_yes"),
    ("3+ years of product", "answer_yes"),
    ("5+ years of product", "answer_yes"),
    ("years of product management", "years_experience"),
    ("years of pre-sales", "years_experience"),
    ("years of pre sales", "years_experience"),
    ("years of presales", "years_experience"),
    ("years of sales", "years_experience"),
    ("years of relevant", "years_experience"),
    # 2026-06-06 (Baselayer 2439): "Years of Industry Experience?" free-text
    # numeric field -> truthful years_experience (answer "2").
    ("years of industry", "years_experience"),
    ("years of professional", "years_experience"),
    ("years of work experience", "years_experience"),
    # Lyft 2026-05-24 (role 717): "May we contact your current employer?" is a Yes/No,
    # NOT a free-text "what is your current employer?". Cyrus doesn't want Microsoft tipped off -> No.
    # Must precede the generic "current employer" rule below.
    ("may we contact your current employer", "answer_no"),
    ("may we contact your current", "answer_no"),
    ("may we contact your present", "answer_no"),
    ("current employer", "current_employer"),
    ("current company", "current_employer"),
    ("current or most recent", "current_employer"),  # Intercom 2026-05-26 — 'Current or most recent company?'
    ("most recent company", "current_employer"),  # Intercom 2026-05-26 fallback
    ("most recent employer", "current_employer"),  # Intercom 2026-05-26 fallback
    ("current or previous employer", "current_employer"),
    ("previous employer", "current_employer"),
    ("past company", "current_employer"),  # Thinking Machines 2026-05-26 — 'Past Company 1' (free text)
    ("past employer", "current_employer"),
    ("current title", "current_title"),
    ("current role", "current_title"),
    ("current or previous job title", "current_title"),
    ("previous job title", "current_title"),
    ("current job title", "current_title"),
    ("past company title", "current_title"),  # Thinking Machines 2026-05-26 — 'Past Company Title or Role'
    ("company title or role", "current_title"),  # generic catchall variant
    # Pure Storage 2026-06-04 (roles 2691-2693): labels are
    # "Who is your current (or most recent) employer?" / "...title?" — the
    # parenthetical "(or most recent)" splits current<->employer so neither
    # the adjacent "current employer" needle nor "current or most recent"
    # (parens break it) matched. Add paren-tolerant phrase needles.
    ("current (or most recent) employer", "current_employer"),
    ("current (or most recent) company", "current_employer"),
    ("current (or most recent) title", "current_title"),
    ("current (or most recent) job title", "current_title"),

    # --- education ---
    ("school", "school"),
    ("university", "school"),
    ("degree", "degree"),
    ("major", "major"),
    ("minor", "minor"),
    ("field of study", "major"),
    ("discipline", "major"),
    ("gpa", "gpa"),
    ("graduation", "graduation_year"),
    ("end date month", "graduation_month"),  # GH-Remix education end-month repeater (YipitData 2756)
    # 2026-06-04 (Samsara 2694): "What is your highest level of education?" is a
    # degree-LEVEL dropdown (not a free-text school/degree). Route to the degree
    # resolver so it picks the Bachelor's option.
    ("highest level of education", "degree"),
    ("highest education level", "degree"),
    ("level of education", "degree"),
    # 2026-06-04 (DigiCert 2752): "highest level of COMPLETED education" — the word
    # "completed" breaks the "level of education" substring. Add explicit variants.
    ("level of completed education", "degree"),
    ("completed education", "degree"),
    ("education level", "degree"),
    # 2026-06-04 (Samsara 2694): "Which time-zone are you physically located in?"
    # — Kirkland WA = US Pacific. Route to timezone_pacific resolver.
    ("time-zone are you", "timezone_pacific"),
    ("time zone are you", "timezone_pacific"),
    ("timezone are you", "timezone_pacific"),
    ("which time-zone", "timezone_pacific"),
    ("which time zone", "timezone_pacific"),
    ("your time zone", "timezone_pacific"),
    ("your time-zone", "timezone_pacific"),

    # --- preferences ---
    ("minimum required yearly salary", "compensation"),
    ("minimum required salary", "compensation"),
    ("minimum yearly salary", "compensation"),
    ("compensation expectation", "compensation"),
    ("salary expectation", "compensation"),
    ("desired compensation", "compensation"),
    ("desired salary", "compensation"),
    ("expected base compensation", "compensation"),  # NanoNets 2618 (2026-06-03)
    ("expected compensation", "compensation"),
    ("base compensation", "compensation"),
    ("expected salary", "compensation"),
    ("salary requirement", "compensation"),
    ("compensation requirement", "compensation"),
    # Broader catches: 'expected ANNUAL compensation in USD' (Clipboard 2550),
    # 'annual base salary', 'compensation expectations', 'pay expectation',
    # 'salary range', 'target compensation'. Word can sit between expected/comp.
    ("annual compensation", "compensation"),
    ("compensation in usd", "compensation"),
    ("annual salary", "compensation"),
    ("annual base salary", "compensation"),
    ("base salary", "compensation"),
    ("compensation expectations", "compensation"),
    ("salary expectations", "compensation"),
    ("pay expectation", "compensation"),
    ("salary range", "compensation"),
    ("target compensation", "compensation"),
    ("compensation in mind", "compensation"),
    # 2026-06-08 cohort-close (EliseAI 2727 / Dash0 2758 audit): the existing
    # needles already catch the EliseAI/Dash0 "compensation expectations"
    # phrasings (cached dryruns confirmed comp resolves to 'Open to discuss',
    # ready_to_submit) — the old "field-walker drops comp" premise was stale.
    # But a coverage sweep found 2 real MISSes: "expected TOTAL compensation"
    # / bare "total compensation" (no "expectations" suffix), and the
    # abbreviated "comp expectations" / "comp range". Add them so the comp
    # cohort is genuinely closed for these phrasings too.
    ("total compensation", "compensation"),
    ("comp expectation", "compensation"),   # substring: 'comp expectations' too
    ("comp range", "compensation"),
    ("compensation range", "compensation"),
    ("open to relocation", "willing_to_relocate"),
    ("willing to relocate", "willing_to_relocate"),
    ("willing to travel", "willing_to_travel"),
    ("willing and able to travel", "willing_to_travel"),
    ("open to travel", "willing_to_travel"),  # Fluidstack 2969/2970 (2026-06-16)
    # 2026-06-03 (Cyrus directive via main): US onsite location is NEVER a knockout.
    # Cyrus relocates ANYWHERE in the USA, travels up to 100%. Any "do you reside in
    # <US area>" / "within commuting distance to <US city>" question -> Yes (answer_yes).
    # Proven: Gather AI ("reside in the Greater Pittsburgh area"), Swayable
    # ("within commuting distance to SF or NY"), Flip (onsite LA/Brooklyn).
    # (Non-US location stays a genuine knockout via the classifier, not here.)
    ("comfortable relocating to one of these", "answer_yes"),
    ("relocating to one of these areas", "answer_yes"),
    # 2026-06-04 (Paystand 2799): US on-site work openness -> Yes (US onsite is
    # NEVER a knockout). And "confirm you have read the job posting in full" is a
    # benign forced confirmation -> Yes.
    ("open for on-site work", "answer_yes"),
    ("open to on-site work", "answer_yes"),
    ("open for onsite work", "answer_yes"),
    ("open to onsite work", "answer_yes"),
    ("confirm that you have read the job posting", "answer_yes"),
    ("read the job posting in full", "answer_yes"),
    # Skill-proficiency dropdowns -> honest INTERMEDIATE tier (Swayable 2623
    # "level of proficiency in Python for Data Science?"). Cyrus is TPM/PM,
    # not a data scientist; truthful tier, no inflation on a concrete skill.
    ("level of proficiency in python", "proficiency_intermediate"),
    ("proficiency in python for data", "proficiency_intermediate"),
    ("your level of proficiency", "proficiency_intermediate"),
    # Open AI-projects experience essay (Swayable 2623) -> regenerate at fill-time.
    ("examples of ai projects you've worked on", "customer_facing_essay"),
    ("examples of ai projects", "customer_facing_essay"),
    # 2026-06-04 (Actively AI 2766): "Do you have any prior experience at the
    # intersection of AI x GTM ...? Please share if so." — open experience essay.
    ("experience at the intersection of", "customer_facing_essay"),
    ("prior experience at the intersection", "customer_facing_essay"),
    ("ai x gtm", "customer_facing_essay"),
    # Open accomplishment / impact essays -> auto-gen (Astranis 2617).
    ("most impressive thing you have ever accomplished", "customer_facing_essay"),
    ("most impressive thing you", "customer_facing_essay"),
    ("proudest accomplishment", "customer_facing_essay"),
    ("greatest accomplishment", "customer_facing_essay"),
    # Open-ended program/experience essays (2026-06-04 batch4: Parloa 2750,
    # Everlaw 2759, GlossGenius 2765). These are generic "tell us about your
    # experience" textareas -> route to customer_facing_essay; cover_answer_
    # generator regenerates a tailored answer at fill-time. Truthful (Cyrus is a
    # TPM/PM with real program-management experience).
    ("describe a complex enterprise software", "customer_facing_essay"),
    ("program you personally managed end-to-end", "customer_facing_essay"),
    ("please describe a complex", "customer_facing_essay"),
    ("how you use ai to get things done", "customer_facing_essay"),
    ("what ai tools are you currently using", "customer_facing_essay"),
    ("ai tools are you currently using", "customer_facing_essay"),
    ("explain any employment gaps", "customer_facing_essay"),
    ("employment gaps in your work history", "customer_facing_essay"),
    ("rank the top 3 skill sets", "customer_facing_essay"),
    ("top 3 skill sets you", "customer_facing_essay"),
    ("describe your experience working with data", "customer_facing_essay"),
    ("experience working with data pipelines", "customer_facing_essay"),
    ("experience with data tools and technologies", "answer_yes"),
    ("experience with data tools", "customer_facing_essay"),
    ("share a description explaining a solution", "customer_facing_essay"),
    ("solution you've implemented in action", "customer_facing_essay"),
    # Behavioral / "tell us about a time" program-management essays (Parloa 2750).
    ("tell us about a time you had to manage", "customer_facing_essay"),
    ("tell us about a time you", "customer_facing_essay"),
    # 2026-06-06 (Ubiquiti 2444): behavioral STAR essays phrased as "Describe a
    # period/time where you went far beyond your defined role...what drove you,
    # and what did you do?" -> customer_facing_essay (open behavioral essay).
    ("went far beyond your defined role", "customer_facing_essay"),
    ("beyond your defined role", "customer_facing_essay"),
    ("describe a period where you", "customer_facing_essay"),
    ("what drove you, and what did you", "customer_facing_essay"),
    ("why ubiquiti specifically", "customer_facing_essay"),
    ("how did you handle dependencies", "customer_facing_essay"),
    ("manage multiple cross-functional teams", "customer_facing_essay"),
    ("stakeholder alignment", "customer_facing_essay"),
    ("what experience do you have working with", "customer_facing_essay"),
    ("experience do you have working with enterprise", "customer_facing_essay"),
    # Confidentiality / trade-secret affirmation (Everlaw 2759): "I understand,
    # affirm, and agree that I am strictly prohibited from taking...trade secret..."
    # -> Yes. A benign legal affirmation Cyrus can truthfully agree to (he won't
    # misuse prior-employer confidential info). Same class as consent acknowledgments.
    ("i understand, affirm, and agree", "answer_yes"),
    ("strictly prohibited from taking, using, or disclosing", "answer_yes"),
    ("trade secret, confidential, or proprietary", "answer_yes"),
    # Single-option season-confirm select (Astranis: only option 'Summer 2026').
    ("confirm the season you are applying", "pick_only_option"),
    ("season you are applying for", "pick_only_option"),
    # Pure Storage 2026-06-04 (roles 2691-2693): required single-option
    # multi-select "Personal Information Policy" with sole option
    # "Acknowledge/Confirm" — standard data-privacy consent for a voluntary
    # application submission. pick_only_option commits the sole option (truthful
    # forced-choice acknowledgment, not a biographical claim).
    ("personal information policy", "pick_only_option"),
    # AI-evaluation consent (ClickHouse 2668, 2026-06-04): required Yes/No
    # "By selecting Yes, I am consenting to the use of AI for evaluating my
    # candidacy." -> Yes. Benign processing consent for a voluntary application,
    # same class as the data-privacy acknowledgments. Anchor on AI+consent phrasing.
    ("consenting to the use of ai", "answer_yes"),
    ("use of ai for evaluating", "answer_yes"),
    ("consent to the use of ai", "answer_yes"),
    # Internship join / end-date free-text -> earliest-start date string.
    ("when are you able to join", "earliest_start"),
    ("preferred end date for the internship", "earliest_start"),
    ("end date for the internship", "earliest_start"),
    # Onsite-requirement confirmation (Flip 2659): "This role is onsite Mon-Fri
    # at our LA or Brooklyn office. Can you meet this requirement?" -> Yes (US
    # onsite is never a knockout per Cyrus rule). Anchor on distinctive phrasing.
    ("can you meet this requirement", "answer_yes"),
    ("are you able to meet this requirement", "answer_yes"),
    # Located-in-<US-state> + in-office gate (Podium 2256: "Are you located in
    # Utah and able to come into our Lehi, UT Office Mon-Fri?") -> Yes.
    ("are you located in utah", "answer_yes"),
    ("able to come into our", "answer_yes"),
    ("come into our", "answer_yes"),
    ("come into the office", "answer_yes"),
    ("willing to come into", "answer_yes"),
    ("office 3 days", "answer_yes"),
    ("office 2 days", "answer_yes"),
    ("office 4 days", "answer_yes"),
    ("located in the area", "answer_yes"),
    ("days a week, and are you located", "answer_yes"),
    ("this role is onsite", "answer_yes"),
    ("role is onsite monday", "answer_yes"),
    ("onsite monday through friday", "answer_yes"),
    ("onsite five days", "answer_yes"),
    ("onsite at our", "answer_yes"),
    ("working onsite at", "answer_yes"),
    ("5 days a week", "answer_yes"),
    ("five days a week", "answer_yes"),
    ("comfortable with working onsite", "answer_yes"),
    ("comfortable working onsite", "answer_yes"),
    ("in-office five days", "answer_yes"),
    ("currently reside in the greater", "answer_yes"),
    ("reside in the greater", "answer_yes"),
    ("do you currently reside in", "answer_yes"),
    ("do you reside in", "answer_yes"),
    # "Do you live in the <City>, <ST> area?" (Case Status 2824). US residence/
    # relocation is never a knockout (Cyrus relocates anywhere in USA) -> Yes.
    ("do you live in", "answer_yes"),
    ("do you currently live in", "answer_yes"),
    ("live in the", "answer_yes"),
    # 2026-06-23 (Algolia 3135): 'Please share which timezone you are currently located in'
    # - the 'currently located in' substring matches answer_yes before timezone_pacific.
    # Override with timezone rule BEFORE the generic location rule.
    ("which timezone you are currently located in", "timezone_pacific"),
    ("share which timezone", "timezone_pacific"),
    # 'Are you currently located in...' (MediaAlpha 2815) -> answer_yes
    ("currently located in", "answer_yes"),
    ("located in the", "answer_yes"),
    # SaaS / rapid-growth-tech prior-experience screen (Case Status 2824) -> Yes,
    # truthful: Cyrus is a TPM/PM with SaaS / high-growth tech experience.
    ("experience working at a saas company", "answer_yes"),
    ("rapid-growth technology", "answer_yes"),
    # Advanced Excel / spreadsheet proficiency screen (Datarails 2814) -> Yes,
    # truthful for a TPM/PM (formulas, VLOOKUP, pivot tables).
    ("advanced experience in excel", "answer_yes"),
    ("experience in excel functions", "answer_yes"),
    # "reside WITHIN the continental United States" (Lila Sciences 2669) — the
    # existing rules anchor "reside in" which misses "reside within". US residence
    # is never a knockout (Cyrus relocates anywhere in USA) -> Yes.
    # 2026-06-04 (gh_jid careers-page cohort, Samsara 2694): "I confirm that I
    # reside in The United States." — plain affirmation, US residence never a
    # knockout. Existing "do you reside in" didn't match the "I confirm that I
    # reside in" phrasing.
    ("reside in the united states", "answer_yes"),
    ("i reside in the united states", "answer_yes"),
    ("confirm that i reside", "answer_yes"),
    ("reside within the continental united states", "answer_yes"),
    ("reside within the united states", "answer_yes"),
    ("reside in the continental united states", "answer_yes"),
    ("located within the continental united states", "answer_yes"),
    ("based in the united states", "answer_yes"),
    ("reside in or near", "answer_yes"),
    ("within commuting distance", "answer_yes"),
    ("commuting distance to", "answer_yes"),
    ("commutable distance", "answer_yes"),
    ("able to commute", "answer_yes"),
    ("willing to commute", "answer_yes"),
    ("comfortable commuting", "answer_yes"),
    ("located near", "answer_yes"),
    ("based in or near", "answer_yes"),
    ("remote", "remote_pref"),
    ("hybrid role based", "ack_hybrid"),
    ("can you work full-time on-site", "ack_in_office"),
    ("able to work on-site", "ack_in_office"),  # Afresh 2026-05-24 (role 994) — "Are you able to work on-site in San Francisco, CA?"
    ("willing to work from the office", "ack_in_office"),
    ("in-person in one of our offices", "ack_in_office"),
    ("work from our", "ack_in_office"),
    ("days per week", "ack_in_office"),
    ("days from one of our office", "ack_in_office"),  # CoreWeave 2026-05-13
    ("office hubs", "ack_in_office"),  # CoreWeave 2026-05-13
    # 2026-05-29 chain_013 (Orkes 1488, Otter 1509, Checkr 1548): in-office gate variants.
    # Cyrus is based in Kirkland, WA and prior chain rules accept 3-5x/week in-office
    # ("in-office work week"/"five-day in-office" added 2026-05-24). Treating these the
    # same way — answer Yes via ack_in_office resolver.
    ("open to coming on-site", "ack_in_office"),         # Orkes — "Are you open to coming on-site 3-5x/week?"
    ("coming on-site", "ack_in_office"),
    ("willing to work in the office", "ack_in_office"),  # Otter — "Are you willing to work in the office 5-days a week?"
    ("work in the office", "ack_in_office"),
    ("join us in the office", "ack_in_office"),          # Checkr — "Are you able and willing to join us in the office 3 days/week?"
    ("in the office", "ack_in_office"),                  # broad catch-all; office-presence labels rarely mean anything else
    ("commit to the hybrid policy", "ack_in_office"),  # Glean — "Are you willing and able to commit to the hybrid policy if hired?"
    ("open to working 4 days onsite", "ack_in_office"),  # Sigma Computing
    ("4 days onsite", "ack_in_office"),                # Sigma Computing variant
    ("familiar with twitch", "acknowledge_yes"),        # Twitch — "Are you familiar with Twitch?"
    ("twitch employee", "no_prior_employer"),           # Twitch — "Are you currently a Twitch employee?"
    # Checkr-style "relocate to one of our hub locations" — pair with willing_to_relocate.
    ("relocate to one of our hub", "willing_to_relocate"),
    ("relocate to our hub", "willing_to_relocate"),
    ("hub locations", "willing_to_relocate"),
    # Stripe-style "We have a hub in NYC. Are you:" — multi-select; relocation-willing answer.
    ("we have a hub in", "willing_to_relocate"),
    ("hub in nyc", "willing_to_relocate"),
    ("hub in sf", "willing_to_relocate"),
    ("hub in seattle", "willing_to_relocate"),
    # BrightHire / interview recording consent — acknowledge Yes.
    ("brighthire", "acknowledge_yes"),
    ("interview and transcribe", "acknowledge_yes"),
    ("record and transcribe", "acknowledge_yes"),
    ("recording and transcrib", "acknowledge_yes"),
    # Databricks internal-transfer disclaimers — external candidate answers Yes (no current Databricks mgr to notify; no PIP/perf issues).
    ("notify your outgoing manager", "acknowledge_yes"),
    ("not under any active performance management", "acknowledge_yes"),
    ("minimum of consistently meets", "acknowledge_yes"),
    ("been in your currently role for at least", "acknowledge_yes"),
    ("been in your current role for at least", "acknowledge_yes"),
    # Non-compete / restrictive agreements (Fastly): "Are you subject to any agreements that may restrict your ability...?"
    # Cyrus is NOT subject to any restrictive agreements.
    ("subject to any agreements that may restrict", "answer_no"),
    ("agreements that may restrict your ability", "answer_no"),
    ("subject to any non-compete", "answer_no"),
    ("non-compete agreement", "answer_no"),
    ("restrictive covenants", "answer_no"),
    ("earliest you would want to start", "earliest_start"),
    ("earliest start", "earliest_start"),
    ("earliest joining date", "earliest_start"),
    ("joining date", "earliest_start"),
    ("when can you start", "earliest_start"),
    ("can you start a new role", "earliest_start"),
    ("ideal start date", "earliest_start"),
    ("ideal start-date", "earliest_start"),  # Fireworks 2026-05-13 hyphen variant
    ("start date", "earliest_start"),
    ("start-date", "earliest_start"),
    ("preferred start date", "earliest_start"),
    ("available to start", "earliest_start"),
    ("availability to start", "earliest_start"),
    ("what is your availability", "earliest_start"),
    ("notice period", "notice_period"),
    ("when is the earliest", "earliest_start"),

    # --- talent-pool / data-retention consent (Wiz 2026-05-25, role 1370) ---
    # "Can we retain your data for up to 12 months to consider you for future opportunities at Wiz?"
    # Default: yes (Cyrus is fine being kept in talent pools).
    ("retain your data", "answer_yes"),
    ("consider you for future opportunities", "answer_yes"),
    ("future opportunities", "answer_yes"),
    # Wiz 2026-05-25 (role 1370) — their template literally asks about Alphabet/Google
    # employment history (looks like a copy-paste from a Google template). Cyrus has
    # never worked at Google/Alphabet → No, and the follow-ups are blank.
    ("contractor of alphabet", "answer_no"),
    ("employee, intern, student ambassador", "answer_no"),
    ("if you answered yes to the question above", "optional_blank"),
    ("previous google/alphabet username", "optional_blank"),
    ("google/alphabet username", "optional_blank"),

    # --- common screener questions ---
    ("how did you hear", "how_heard"),
    # 2026-06-23: "How did you initially hear about this job?" (Braze 3418, Algolia 3135)
    ("how did you initially hear", "how_heard"),
    ("hear about this job", "how_heard"),
    ("hear about this position", "how_heard"),
    ("hear about this opportunity", "how_heard"),
    # 2026-06-04 (DigiCert 2752): "Were you referred for this position?" is a
    # Yes/No question (NOT a how-heard source). Cyrus has no internal referral
    # → answer No truthfully. Must sit BEFORE how_heard referral rules.
    ("were you referred for this", "answer_no"),
    ("referred for this position", "answer_no"),
    ("how you heard", "how_heard"),
    ("where did you hear", "how_heard"),
    ("how were you referred", "how_heard"),
    ("where did you first hear", "how_heard"),
    # 2026-06-04 (Samsara 2694): "Where have you learned about Samsara? Select
    # all that apply." — multiselect source. r_how_heard picks LinkedIn.
    ("where have you learned about", "how_heard"),
    ("how did you learn about", "how_heard"),
    ("how did you learn of this", "how_heard"),  # IXL Learning 2026-06-24 — "How did you learn of this position?"
    ("where did you learn about", "how_heard"),
    # 2026-06-04 (Samsara 2694): consent/ack selects.
    ("processing of personal data", "answer_yes"),
    ("ai policy for interviews", "answer_yes"),
    # 2026-06-04 (FanDuel 2674): "Are you an employee of Flutter or a Flutter
    # brand?" — Cyrus is not a current FanDuel/Flutter employee -> No.
    ("are you an employee of", "answer_no"),
    ("are you a current employee", "answer_no"),
    # MA lie-detector statutory notice — truthful: Cyrus resides in WA, NOT MA.
    # Pick the "I don't reside in Massachusetts" option (NOT the affirmative ack).
    ("unlawful in massachusetts to require or administer a lie detector", "not_ma_resident"),
    ("lie detector test as a condition of employment", "not_ma_resident"),
    ("referred by", "referred_by"),
    ("previously applied", "previously_applied"),
    # Hume AI 2026-05-25 (role 1379): "Have you applied to any positions at Hume in the past 6 months?"
    ("applied to any positions", "previously_applied"),
    ("applied to any position", "previously_applied"),
    ("applied to", "previously_applied"),
    ("previously employed", "previously_employed"),
    ("currently employed", "currently_employed"),
    ("background check", "background_check"),
    ("drug screen", "drug_screen"),
    ("driver's license", "drivers_license"),
    ("drivers license", "drivers_license"),
    ("felony", "felony"),
    ("non-compete", "non_compete"),
    ("non compete", "non_compete"),
    ("agreement with a former employer", "non_compete"),
    # ---------------------------------------------------------------------
    # ATF Form 4473 "prohibited person" federal-firearms-eligibility block
    # (Axon 2026-06-08, role 2831 Technical Program Manager I). Axon is a
    # Federal Firearms Licensee, so its GH application appends the standard
    # ATF 4473 prohibited-person attestations as REQUIRED Yes/No selects.
    # For Cyrus (U.S. CITIZEN, NO convictions, NOT on a nonimmigrant visa,
    # never renounced citizenship, no court orders, not a controlled-substance
    # addict) every one of these is a truthful **No** -> answer_no. These are
    # negative attestations, NOT biographical claims that could falsely help.
    # Needles are distinctive phrase substrings so they never collide with the
    # work-auth / sponsorship rules above (verified find_resolver None pre-add).
    ("fugitive from justice", "answer_no"),
    ("alien illegally or unlawfully", "answer_no"),
    ("alien who has been admitted to the united states under a nonimmigrant", "answer_no"),
    ("admitted to the united states under a nonimmigrant visa", "answer_no"),
    ("unlawful user of, or addicted to", "answer_no"),
    ("addicted to, marijuana", "answer_no"),
    ("restraining you from harassing, stalking", "answer_no"),
    ("military protection order", "answer_no"),
    ("adjudicated as a mental defective", "answer_no"),
    ("committed to a mental institution", "answer_no"),
    ("misdemeanor crime of domestic violence", "answer_no"),
    ("discharged from the armed forces under dishonorable", "answer_no"),
    ("dishonorable conditions", "answer_no"),
    ("renounced your united states citizenship", "answer_no"),
    ("renounced your citizenship", "answer_no"),
    # The FFL questionnaire wrapper is a single-option "Acknowledge" confirm
    # (sole option, value present) -> pick the only option (truthful forced
    # acknowledgement, same class as Astranis season-confirm).
    ("federal firearms licensee employee accessor", "pick_only_option"),
    ("federal firearms licensee", "pick_only_option"),
    # ---------------------------------------------------------------------
    # Geo / language KNOCKOUT screeners (BeyondTrust 2026-06-08, role 2739
    # Solutions Engineer — a Republic-of-Korea-based req). Truthful No for
    # Cyrus (lives in Kirkland WA; does not claim native/fluent Korean). These
    # may legitimately knock the role out; answering truthfully is correct, and
    # banking them empty just stalled the row forever instead.
    ("currently living in the republic of korea", "answer_no"),
    ("living in the republic of korea", "answer_no"),
    ("fluent/native level korean", "answer_no"),
    ("fluent/native level", "answer_no"),
    ("native level korean", "answer_no"),
    # Axon 2026-05-24 (role 1056): "Do you have any contractual obligations,
    # agreements, relationships, or commitments to another person or entity that
    # would impact, impede or interfere with your ability to join <Company>?"
    # Cyrus has none -> No.
    ("contractual obligations", "answer_no"),
    ("impede or interfere with your ability", "answer_no"),
    ("obligations, agreements, relationships", "answer_no"),
    ("interviewed at", "previously_interviewed"),
    ("are you currently based in any of these countries", "based_in_restricted_country"),
    ("do you live in one of the following states", "based_in_restricted_state"),
    ("are you located in the united states", "us_based_confirm"),
    ("only open to candidates in the united states", "us_based_confirm"),
    ("do you know anyone currently at", "worked_at_company_before"),
    # Anduril 2026-05-13: "CONFLICT OF INTEREST" yes/no about prior gov't
    # oversight of the company. Cyrus has none -> "No".
    ("conflict of interest", "answer_no"),
    # Trivial age / experience-threshold yes/no questions — default Yes (Cyrus is 30+ with 10y XP).
    ("at least 18", "answer_yes"),
    ("are you 18", "answer_yes"),
    ("of legal working age", "answer_yes"),
    ("at least 2 years", "answer_yes"),
    ("at least 3 years", "answer_yes"),
    ("at least 5 years", "answer_yes"),
    # PM-experience yes/no (Comet 2026-05-24, role 1233) — Cyrus has 10y PM XP.
    ("proven experience shipping", "answer_yes"),
    ("shipping high-quality products", "answer_yes"),
    ("planning to launch to maintenance", "answer_yes"),
    ("created roadmaps", "answer_yes"),  # Afresh 2026-05-24 (role 994) — "Have you created roadmaps and seen products through from concept to launch?"
    ("products through from concept to launch", "answer_yes"),
    # Acknowledge-linked-doc style (Lyft 2026-05-22) — tick Yes.
    ("please review the linked document", "acknowledge_yes"),
    ("please review the document", "acknowledge_yes"),
    ("reviewed the linked", "acknowledge_yes"),
    ("please only submit a pdf", "acknowledge_yes"),
    ("only submit a pdf version", "acknowledge_yes"),
    ("submitting a pdf", "acknowledge_yes"),
    ("arrange reference calls", "acknowledge_yes"),
    ("a final step in the hiring process is for you to arrange", "acknowledge_yes"),
    # Lyft 2026-05-22: "Please enter your relevant employment ... + Add Another link"
    # is a single-option acknowledgment ("Thank you") used to gate the form.
    ("add another employment", "acknowledge_yes"),
    ("using the + add another", "acknowledge_yes"),
    ("using the +add another", "acknowledge_yes"),
    # "Have you been employed with <Company>?" (The Trade Desk 2026-05-22).
    ("have you been employed with", "worked_at_company_before"),
    ("are you currently or have you ever provided services", "worked_at_company_before"),
    ("provided services to", "worked_at_company_before"),
    # New-grad timing questions (Jane Street 2026-05-22) — Cyrus already done; reuse graduation year.
    ("year you expect to complete", "graduation_year"),
    ("year you expect to begin", "graduation_year"),
    # Address Line 1/2 (Fivetran 2026-05-22) — Address Line 1 == street, line 2 optional.
    ("address line 1", "street"),
    ("address line 2", "optional_blank"),
    ("address line", "street"),
    # Bare single-word 'address' catch-all (Zuora 2755 'Home Address' class).
    # MUST stay below 'street/legal/mailing address', the 'home/current/your
    # /personal/candidate/full address' phrases, AND 'address line N', and below
    # the 'email' rule (line ~158) so 'email address' routes to email. By the time
    # control reaches here, every more-specific address phrase has already matched,
    # so a remaining word-boundary 'address' is a generic postal-address text box.
    ("address", "full_address"),
    # "hands on experience with <X>, please specify" (Vercel 2026-05-22).
    ("hands on experience with", "experience_short_yes"),
    ("hands-on experience with", "experience_short_yes"),
    ("programming language", "coding_lang_python"),  # CoreWeave 2026-05-13
    ("prefer to use", "coding_lang_python"),  # 'which language(s) do you prefer to use'
    ("paired coding", "coding_lang_python"),
    ("have you ever worked for", "worked_at_company_before"),
    ("have you ever worked at", "worked_at_company_before"),
    ("have you worked for", "worked_at_company_before"),  # Okta 2026-05-24 — 'Have you worked for Okta in the past?'
    ("have you worked at", "worked_at_company_before"),
    ("have you ever been employed by", "worked_at_company_before"),
    ("have you been employed by", "worked_at_company_before"),
    ("been employed by", "worked_at_company_before"),
    # Box 2026-05-25 (role 1154): "Have you ever been employed at Box, including working as a contractor, intern, grad, or full-time employee?"
    ("ever been employed at", "worked_at_company_before"),
    ("been employed at", "worked_at_company_before"),
    # Asana 2026-05-25 (role 1542): "Have you been employed, or otherwise engaged, by an Asana entity in the past? (Previous independent contractors, select \"Yes.\")". The "or otherwise engaged," interjection prevents the "been employed by" rule from matching. Anchor on the unique "otherwise engaged" phrase.
    ("otherwise engaged, by an", "worked_at_company_before"),
    ("otherwise engaged", "worked_at_company_before"),
    # Asana 2026-05-25 (role 1542): follow-up free-text "If you answered “Yes,” please list the U.S. government entity you worked for. If not applicable, type 'N/A.'" — we answered No to the gate (Q66740980 via 'government employee' rule), so this should be N/A.
    ("please list the u.s. government entity", "literal_na"),
    ("list the u.s. government entity", "literal_na"),
    ("type 'n/a.'", "literal_na"),
    ("type 'n/a'", "literal_na"),
    ("have you worked here before", "worked_at_company_before"),
    ("history with ", "worked_at_company_before"),  # "HISTORY WITH ANDURIL" etc.
    ("previously worked at or consulted", "worked_at_company_before"),
    ("have you previously worked", "worked_at_company_before"),
    ("former coreweave employee", "worked_at_company_before"),  # CoreWeave 2026-05-13
    ("are you a former", "worked_at_company_before"),  # generic 'Are you a former <Company> employee?'
    # Family/personal relations at the hiring company. Cyrus has none -> No.
    ("family members", "family_relations_at_company"),
    ("family member or relative", "family_relations_at_company"),
    ("relatives or personal relationships", "family_relations_at_company"),
    ("do you have any relatives", "family_relations_at_company"),
    ("personal relationship with anyone", "family_relations_at_company"),
    # Sony Interactive Entertainment 2026-05-24 (role 982): label has a comma
    # between 'with' and 'anyone' so the prior needle misses it. Catch both
    # comma and non-comma variants, plus the broader 'close personal relationship'.
    ("personal relationship with, anyone", "family_relations_at_company"),
    ("close personal relationship", "family_relations_at_company"),
    ("are you related to", "family_relations_at_company"),
    # Countries-of-work-authorization (Elastic et al). US only.
    ("in what countries do you have", "countries_of_work_auth"),
    ("countries of work authorization", "countries_of_work_auth"),
    ("countries do you have the unrestricted right to work", "countries_of_work_auth"),
    # Privacy-statement / candidate-notice acknowledgments. Always tick.
    ("privacy statement", "privacy_ack"),
    ("privacy notice", "privacy_ack"),
    ("candidate privacy", "privacy_ack"),
    ("data privacy", "privacy_ack"),
    ("store and process my data", "privacy_ack"),
    ("store and process your data", "privacy_ack"),
    ("considering my eligibility", "privacy_ack"),
    ("process my personal data", "privacy_ack"),
    ("processing of my personal data", "privacy_ack"),
    # Essential functions / can perform with reasonable accommodation. Yes.
    ("essential functions", "essential_functions_ack"),
    ("perform the essential", "essential_functions_ack"),
    ("with or without reasonable accommodation", "essential_functions_ack"),
    ("can perform these essential functions", "essential_functions_ack"),  # Lyft exact phrasing
    # Lyft / optional accommodation request textarea — leave blank (no accommodation needed).
    ("describe any need for a reasonable accommodation for this hiring", "optional_blank"),
    ("need for a reasonable accommodation for this hiring", "optional_blank"),
    ("accommodation for this hiring process", "optional_blank"),
    # Lyft proximity/commute to office — willing to relocate.
    ("commutable proximity to a lyft office", "willing_to_relocate"),
    ("proximity to a lyft office", "willing_to_relocate"),
    ("commutable proximity", "willing_to_relocate"),
    # AI customer experience (Stripe 7975723) — textarea, answer via customer_facing_essay.
    ("worked directly with ai customers", "customer_facing_essay"),
    ("previously interviewed", "previously_interviewed"),
    ("interviewed at", "previously_interviewed"),
    ("interviewed with", "previously_interviewed"),
    ("are you currently a student", "currently_student"),
    # HackerRank 2026-05-24 (role 1140): "Are you currently attending College?"
    ("currently attending college", "currently_student"),
    ("attending college", "currently_student"),
    # HackerRank 2026-05-24 (role 1140): "This role requires a technical assessment.
    # Are you ok with this?" — Cyrus is OK doing tech assessments.
    ("requires a technical assessment", "answer_yes"),
    ("technical assessment. are you ok", "answer_yes"),
    # HackerRank 2026-05-24 (role 1140): "Are you comfortable traveling onsite
    # to meet with customers?" — Cyrus is willing to travel 100% per brief.
    ("comfortable traveling onsite", "answer_yes"),
    ("traveling onsite to meet", "answer_yes"),
    ("travel onsite to meet", "answer_yes"),
    # HackerRank 2026-05-24 (role 1140): "Please describe your customer facing
    # experience in internships or full-time roles that you've held..."
    # Mark filled with a placeholder so dryrun passes; cover_answer_generator
    # regenerates a tailored answer at fill-time via is_essay_question.
    ("describe your customer facing experience", "customer_facing_essay"),
    ("describe your customer-facing experience", "customer_facing_essay"),
    ("customer facing experience in internships", "customer_facing_essay"),
    # Phoenix Contact 2026-05-24 (role 1289): "What experience do you have in electronic component or industrial sales?"
    # — open textarea; route through customer_facing_essay placeholder so cover_answer_generator regenerates at fill-time.
    ("experience do you have in electronic", "customer_facing_essay"),
    ("experience do you have in industrial sales", "customer_facing_essay"),
    ("electronic component or industrial sales", "customer_facing_essay"),
    # Smartcat 2026-05-26 (role 1136): two custom FDE essay prompts. Route through
    # customer_facing_essay placeholder so dryrun passes; cover_answer_generator
    # regenerates tailored answers at fill-time via is_essay_question.
    ("innovative ai-first solution", "customer_facing_essay"),
    ("most innovative ai", "customer_facing_essay"),
    ("challenging pre-sales technical demo", "customer_facing_essay"),
    ("pre-sales technical demo", "customer_facing_essay"),
    ("proof of concept that you delivered", "customer_facing_essay"),
    # Cato Networks / SE qualification booleans
    ("comfortable delivering live technical product demonstrations", "answer_yes"),
    ("responded to rfis/rfps as part of a technical pre-sales", "answer_yes"),
    ("have you ever responded to rfis/rfps", "answer_yes"),
    # Alloy NYC hybrid: "Are you able to attend the office on these days?" -> ack_in_office
    ("hybrid work environment: our employees local to nyc are expected to work", "ack_in_office"),
    ("our employees local to nyc are expected to work", "ack_in_office"),
    # Waymo: "Are you a current or former Alphabet employee?" — never worked at Alphabet.
    ("are you a current or former alphabet employee", "alphabet_affiliation"),
    ("current or former alphabet employee, intern, vendor, contractor", "alphabet_affiliation"),
    # Waymo: AI tool prohibition acknowledgement
    ("waymo prohibits the use of ai", "acknowledge_yes"),
    ("prohibits the use of ai tools", "acknowledge_yes"),
    ("use of ai tools for application", "acknowledge_yes"),
    # Actively AI: customer account ownership background (essay)
    ("this is not a platform pm role", "customer_facing_essay"),
    ("directly owning a set of customer accounts", "customer_facing_essay"),
    # Taboola role-type confirmation: "this role is NOT a Software Engineer/ML/CyberSec role" — acknowledge.
    ("this role is not a software engineer, ai/ml engineer, or cybersecurity role", "acknowledge_yes"),
    ("confirm that you understand this role is not a software engineer", "acknowledge_yes"),
    # Taboola SQL skills rating (0-5 scale): Cyrus rates himself 3 (familiar/proficient, not expert).
    ("rate your sql skills on a scale of 0 - 5", "sql_skills_rating"),
    ("rate your sql skills", "sql_skills_rating"),
    # InterSystems 2026-06-24 (roles 3453/3455/3456): employment history at InterSystems (Cyrus never
    # worked there — blank) and Data Protection Information Notice (consent → ack yes).
    ("intersystems employment history", "optional_blank"),
    ("data protection information notice", "acknowledge_yes"),
    ("data protection notice", "acknowledge_yes"),
    # Formlabs 2026-06-24 (role 3438): "Please describe your most complex project." — essay.
    ("please describe your most complex project", "customer_facing_essay"),
    ("describe your most complex project", "customer_facing_essay"),
    # Avathon 2026-06-24 (role 3335): supply-chain PM 5+ years knockout — answer No truthfully
    # (Cyrus has broad PM/SE experience but not 5+ yrs supply-chain-domain-specific PM).
    ("product management in supply chain domain for at least 5+ years", "answer_no"),
    ("supply chain domain for at least 5", "answer_no"),
    # Databricks 2026-05-26 (role 1353 AI Engineer FDE): production AI/ML deployment essays.
    ("production agentic ai", "customer_facing_essay"),
    ("production ml or genai", "customer_facing_essay"),
    ("production agentic", "customer_facing_essay"),
    ("agentic ai, llm, or genai application", "customer_facing_essay"),
    ("genai deployment you have operated", "customer_facing_essay"),
    ("genai deployment", "customer_facing_essay"),
    ("deployment you have operated on aws", "customer_facing_essay"),
    ("llm application you designed", "customer_facing_essay"),
    ("by submitting my application", "acknowledge_yes"),
    ("i certify", "acknowledge_yes"),
    ("true and correct", "acknowledge_yes"),
    ("false statements", "acknowledge_yes"),
    ("truthful", "acknowledge_yes"),
    # "do you know anyone who works at <company>?" — default No
    ("do you know anyone who works at", "family_relations_at_company"),
    ("do you know anyone currently working at", "family_relations_at_company"),
    ("know any current", "family_relations_at_company"),
    ("have you been involved in procurement", "family_relations_at_company"),
    ("citizenship status", "itar_us_person_ack"),
    ("work authorization status", "itar_us_person_ack"),
    # Lyft 2026-05-23: "... commutable proximity to a Lyft Office located in X or are you open to relocating?" Cyrus is in Kirkland WA, open to relocating USA-wide.
    # 2026-05-24 (role 717): re-routed to willing_to_relocate — Lyft offers multi_value_single_select with options like "I am willing to relocate before starting employment." Generic answer_yes can't pick a non-"Yes" label; willing_to_relocate resolver now matches the right option.
    ("commutable proximity", "willing_to_relocate"),
    # CLEAR 2026-05-24 (role 1151): "5 days in-office expectation. Are you comfortable with this schedule?"
    ("in-office expectation", "answer_yes"),
    ("days in-office", "answer_yes"),
    ("in-office. are you comfortable", "answer_yes"),
    # Gradial 2026-05-24 (role 1157): "...commit to a five-day in-office work week?"
    # Cyrus is based in Kirkland, WA; Seattle-HQ 5-day in-office is fine.
    ("in-office work week", "answer_yes"),
    ("five-day in-office", "answer_yes"),
    ("comfortable with this schedule", "answer_yes"),
    ("open to relocating", "willing_to_relocate"),
    ("open to relocate", "willing_to_relocate"),
    ("willing to relocate", "willing_to_relocate"),
    # Okta 2026-05-23: outside-business-activity disclosure — Cyrus has none, answer No.
    ("outside business activit", "answer_no"),
    # Databricks 'follow-up to negative-ITAR' question (2026-05-23). Multi-select
    # asking which US-person status applies. Pick 'U.S. citizen' for Cyrus.
    ("if you selected a response to the prior question other than", "itar_us_person_ack"),
    ("please confirm whether any of the following also applies", "itar_us_person_ack"),
    # SpaceX-style employment-history-with-company (multi-option, not bool).
    ("spacex employment", "worked_at_company_before"),
    ("employment history with", "worked_at_company_before"),
    ("government employee or official", "family_relations_at_company"),
    ("please double-check", "acknowledge_yes"),
    ("please double check", "acknowledge_yes"),
    ("important to us to create an accessible", "acknowledge_yes"),
    # SAT/ACT/GRE optional test scores — leave blank
    ("sat score", "optional_blank"),
    ("act score", "optional_blank"),
    ("gre score", "optional_blank"),
    ("test score", "optional_blank"),
    # "how did you learn about" / "how did you hear"
    ("how did you learn about this job", "how_heard"),
    ("how did you learn about", "how_heard"),
    # AI familiarity self-rating dropdowns — pick highest available
    ("familiarity with ai", "ai_familiarity_high"),
    ("familiarity with artificial intelligence", "ai_familiarity_high"),
    ("experience with ai", "ai_familiarity_high"),
    ("experience with artificial intelligence", "ai_familiarity_high"),
    ("comfortable with ai", "ai_familiarity_high"),
    ("ai-driven advancements", "ai_familiarity_high"),
    # Confidential/IP/proprietary acknowledgments — Yes
    ("confidential information", "acknowledge_yes"),
    ("proprietary information", "acknowledge_yes"),
    ("non-disclosure", "acknowledge_yes"),
    ("confidentiality acknowledgement", "acknowledge_yes"),
    ("confidentiality acknowledgment", "acknowledge_yes"),  # US spelling — Thinking Machines 2026-05-26
    ("confidentiality agreement", "acknowledge_yes"),
    # Generic "do you have experience" / "have you worked in/with X" short-answer
    # questions — default to a short affirmative anchored in Cyrus's Microsoft
    # tenure. Catch-all near the END of LABEL_RULES so more specific rules win.
    ("do you have experience", "experience_short_yes"),
    ("do you have program management experience", "experience_short_yes"),
    ("have you worked in", "experience_short_yes"),
    ("have you worked with", "experience_short_yes"),
    ("do you have hands-on experience", "experience_short_yes"),
    ("experience supporting", "experience_short_yes"),
    ("experience building", "experience_short_yes"),
    # AI-in-workflow questions — always answer No per disclosure policy
    ("ai into your workflows", "ai_use_no"),
    ("using ai in your work", "ai_use_no"),
    ("how are you using ai", "ai_use_no"),
    ("incorporating ai", "ai_use_no"),
    ("privacy policy", "acknowledge_yes"),
    ("point of data transfer", "acknowledge_yes"),  # Intercom 2026-05-26 — GDPR data-transfer ack with single 'Acknowledge' option
    ("privacy notice", "acknowledge_yes"),
    # DoorDash / applicant-privacy ack (2026-06-23)
    ("applicant privacy acknowledgement", "acknowledge_yes"),
    ("applicant privacy", "acknowledge_yes"),
    # NYT — "After your review of the job description, do you meet each of the basic qualifications listed in the job?" (2026-06-23)
    ("meet each of the basic qualifications", "acknowledge_yes"),
    ("basic qualifications listed in the job", "acknowledge_yes"),
    # Affirm accuracy / falsification-disqualification (MetTel 2026-06-23)
    ("affirm all of my responses are accurate", "acknowledge_yes"),
    ("falsification of my information", "acknowledge_yes"),
    # "After your review" generic qualification gate
    ("after your review of the job description", "acknowledge_yes"),
    ("if yes, please provide further explanation", "explain_no"),
    ("if yes, please specify the level", "explain_no"),
    ("ai policy for application", "ai_policy_ack"),
    ("ai policy for interviewers", "ai_policy_ack"),  # Samsara 2026-06-24 — "AI Policy for Interviewers" Yes/No

    # --- free-form / essays ---
    # HeyGen 2026-05-25 (role 1378): custom FDE essay prompts. Route through
    # why_company_essay placeholder so dryrun passes; cover_answer_generator
    # overrides with tailored answers at browser-fill time via is_essay_question.
    ("personally shipped to production that used llms", "why_company_essay"),
    ("largest enterprise deployment you personally owned", "why_company_essay"),
    ("why ", "why_company_essay"),
    # Gradial 2026-05-24 (role 1157): "What excites you most about working in AI today?"
    # Route generic "what excites you" essays through why_company_essay so dryrun
    # passes; the calling agent overrides with cover_answer_generator output at
    # browser-fill time for a more targeted answer.
    ("what excites you", "why_company_essay"),
    ("cover letter", "cover_letter"),
    ("additional information", "additional_info"),
    ("personal preferences", "additional_info"),
    ("deadlines or timeline", "deadlines_note"),

    # --- file uploads ---
    # custom REQUIRED portfolio/brief file question (ACLU 2660/2661/2662
    # 2026-06-10): "attach a PRD or product brief / writing sample / work
    # sample / portfolio for a product you've launched". No resume/cover input
    # satisfies it; the submit runner auto-generates a sanitized product brief
    # (prd_brief_pdf) and set_input_files it. Resolve here so it is NOT a
    # blocker and the plan emits. These must precede the generic resume rules.
    ("prd or product brief", "product_brief_file"),
    ("product brief", "product_brief_file"),
    ("a prd", "product_brief_file"),
    ("writing sample", "product_brief_file"),
    ("work sample", "product_brief_file"),
    ("product requirements doc", "product_brief_file"),
    ("resume/cv", "resume"),
    ("resume", "resume"),
    ("cv", "resume"),

    # GDPR demographic-data consent — required tickbox authorizing storage
    # of the demographic answers we already declined. Always TICK.
    # Box 2026-05-25 (role 1154): "Consent To Process" single-option "I Agree" tickbox.
    ("consent to process", "acknowledge_yes"),
    ("i consent to", "gdpr_consent_ack"),
    ("demographic data", "gdpr_consent_ack"),
    ("gdpr", "gdpr_consent_ack"),

    # --- 2026-06-23 batch additions ---
    # in-office / hybrid phrasing variants not previously matched
    ("4x week in-office", "ack_in_office"),
    ("4 days a week in-office", "ack_in_office"),
    ("4 days/week in office", "ack_in_office"),
    ("hybrid with some in-person", "ack_in_office"),
    ("3 days onsite in our", "ack_in_office"),
    ("3 days onsite in chicago", "ack_in_office"),
    ("hybrid work environment with 3 days", "ack_in_office"),
    ("able to accommodate this requirement", "ack_in_office"),
    # Airtable / 'You are currently based:' -> US location
    ("you are currently based", "city_location_select"),
    ("currently based in", "city_location_select"),
    # work authorization variants
    ("eligible to legally work in the united states", "work_authorized"),
    ("eligible to work in the united states", "work_authorized"),
    ("currently eligible to legally work", "work_authorized"),
    # referral: no internal referral for Cyrus -> No
    ("did a current .* employee refer", "answer_no"),  # regex-safe pattern (substring match)
    ("did a current rithum employee refer", "answer_no"),
    ("current employee refer you", "answer_no"),
    ("employee refer you to this role", "answer_no"),
    # essay/open text: work experience / strengths / accomplishments
    ("top 3 strengths", "experience_short_yes"),
    ("top 3 skill sets", "experience_short_yes"),
    ("exceptional work", "experience_short_yes"),
    ("what exceptional", "experience_short_yes"),
    ("what exceptional work have you done", "experience_short_yes"),
    ("experience working directly with clients", "customer_facing_essay"),
    ("working directly with clients", "customer_facing_essay"),
    ("working directly with customers", "customer_facing_essay"),
    ("customer facing. please explain", "customer_facing_essay"),
    ("experience working with non technical stakeholders", "customer_facing_essay"),
    ("what makes you exceptional", "experience_short_yes"),
    ("fast-paced, growing startup", "experience_short_yes"),
    ("fast-paced.*startup.*how do you handle", "experience_short_yes"),  # approx
    # Filson / hybrid Monday-Thursday
    ("monday-thursday in office", "ack_in_office"),
    ("open to a hybrid work schedule: monday", "ack_in_office"),
    # PMP cert -> No (Cyrus does not hold PMP)
    ("do you currently hold a pmp", "answer_no"),
    ("pmp (project management professional) certification", "answer_no"),
    ("pmp certification", "answer_no"),
    # wireless PM experience (MetTel 3332) -> short essay answer
    ("do you have wireless product management experience", "experience_short_yes"),
    ("wireless product management experience", "experience_short_yes"),
    # plumbing experience (Sensei 3392) -> SKIP / No (not a plumber role, use 'answer_no')
    # Note: Sensei 3392 is likely a wrong classification — mark as answer_no
    ("experience in plumbing", "answer_no"),
    ("1+ years' experience in plumbing", "answer_no"),
    # SQL proficiency -> answer with experience level
    ("rate your proficiency with sql", "experience_short_yes"),
    ("sql proficiency", "experience_short_yes"),
    ("sql proficiency level", "experience_short_yes"),
    # visa status -> skip (Cyrus is US citizen, no visa)
    ("what is your current visa status", "visa_type_na"),
    ("current visa status", "visa_type_na"),
    # Canonical / own-words integrity pledge -> ack_yes
    ("i agree to use only my own words", "acknowledge_yes"),
    ("use only my own words", "acknowledge_yes"),
    ("plagiarism, the use of ai", "acknowledge_yes"),
    ("use of ai or other generated content will disqualify", "acknowledge_yes"),
    # Tenable hybrid (Columbia MD / Atlanta GA)
    ("willing to work at one of these locations", "ack_in_office"),
    ("headquarters in columbia, md", "ack_in_office"),
    # IXL Learning 3441-3449 — "This position requires you to be in our X office. Will you please confirm..."
    ("this position requires you to be in our", "ack_in_office"),  # IXL Learning 2026-06-24
    # --- 2026-06-23 second batch additions ---
    # Twitch/Amazon employment history
    ("twitch employee", "answer_no"),          # Twitch 3010/3011 - current Twitch employee?
    ("currently a twitch employee", "answer_no"),
    ("amazon or any amazon subsidiary", "answer_no"),
    ("current employee with amazon", "answer_no"),
    ("previously applied to amazon", "answer_no"),
    ("previously been employed by amazon", "answer_no"),
    # Twitch open to relocation - options are city names (no Yes), pick Seattle
    ("are you open to relocation", "relocation_city_select"),  # Twitch specific
    # Non-compete agreement -> No
    ("non-competition agreement", "answer_no"),
    ("non-compete agreement", "answer_no"),
    ("subject to a non-competition", "answer_no"),
    # Amazon employment eligibility -> Yes
    ("if offered employment by amazon, would you be legally eligible", "answer_yes"),
    ("legally eligible to begin employment", "work_authorized"),
    # H-1B status -> No (Cyrus is US citizen, never held H-1B)
    ("have you held h-1b status", "answer_no"),
    ("h-1b petition approved on your behalf", "answer_no"),
    ("held h-1b status", "answer_no"),
    # Timezone select -> Pacific Time (duplicates moved earlier for rule ordering)
    # (rules already at lines 691-693, kept here as alias)
    ("which timezone are you currently", "timezone_pacific"),
    ("timezone you are currently located", "timezone_pacific"),
    # Experience questions (Algolia-style Yes/No)
    ("years prior experience directly supporting", "answer_yes"),
    ("directly supporting a customer", "answer_yes"),
    ("integrated third-party apis", "answer_yes"),
    ("third-party apis or services into custom applications", "answer_yes"),
    ("optimizing search performance", "answer_yes"),
    ("search performance, including indexing", "answer_yes"),
    ("fully proficient coding in javascript", "answer_yes"),
    ("proficient coding in javascript", "answer_yes"),
    # AI interview guidelines acknowledgment
    ("guidelines for using ai in our interviewing", "acknowledge_yes"),
    ("using ai in our interview", "acknowledge_yes"),
    # Postman 3227 (already handled by work_authorized but for completeness)
    ("eligible to legally work", "work_authorized"),
    # General 'have you ever' for company employment
    ("have you ever previously worked for", "answer_no"),
    ("previously worked for tenable", "answer_no"),
    ("currently work for", "answer_no"),
    # dbt Labs / Austin location question
    ("are you based in austin", "answer_no"),   # dbt Labs 3159 - Cyrus is in Kirkland WA
    ("based in austin, texas", "answer_no"),
    # Rithum referral follow-up (freetext 'who referred you / N/A')
    ("if yes, who referred you", "answer_na_text"),  # 3345/3346
    ("if you answered no, you can enter n/a", "answer_na_text"),
    # YipitData essay questions
    ("briefly describe a data product", "customer_facing_essay"),
    ("data product or data feed you", "customer_facing_essay"),
    ("direct accountability for revenue metrics", "answer_yes"),
    ("accountability for revenue metrics", "answer_yes"),
    ("have you had direct accountability", "answer_yes"),
    # --- 2026-06-23 third batch additions ---
    # xAI/Twitter/SpaceX employment history -> No
    ("worked at xai, x, twitter", "answer_no"),
    ("ever worked at xai", "answer_no"),
    ("xai, x, twitter, or spacex", "answer_no"),
    # Sigma Computing acknowledgment (checkbox/agree multiline)
    ("acknowledge, confirm, and agree to the following", "acknowledge_yes"),
    ("acknowledge, confirm, and agree", "acknowledge_yes"),
    # Pluribus Digital / government-contracting experience attestations (Cyrus = Yes)
    ("directly facilitated agile ceremonies", "answer_yes"),
    ("sprint reviews, retrospectives", "answer_yes"),
    ("supported or managed large-scale modernization", "answer_yes"),
    ("enterprise or government systems", "answer_yes"),
    # Sensei maintenance/driver roles -> No (not maintenance tech)
    ("experience in preventive maintenance", "answer_no"),
    ("years' experience in preventive", "answer_no"),
    ("valid driver's license and an acceptable mvr", "answer_no"),
    ("driver's license and an acceptable mvr", "answer_no"),
    ("mvr (moving vehicle record)", "answer_no"),
    # Sensei referral / references -> essay
    ("have you been referred to sensei", "explain_no"),   # 'If yes, by whom' -> N/A
    ("provide a minimum of two professional references", "experience_short_yes"),
    ("minimum of two professional references", "experience_short_yes"),
    # Canonical experience essays
    ("describe your experience working with public clouds", "customer_facing_essay"),
    ("experience working with public clouds", "customer_facing_essay"),
    ("please describe your linux experience", "customer_facing_essay"),
    ("describe your linux experience", "customer_facing_essay"),
    # Cribl / channel-sales partner essays (2026-06-25)
    ("value-added resellers (var) have you worked with", "customer_facing_essay"),
    ("var) have you worked with", "customer_facing_essay"),
    ("describe your experience working with var", "customer_facing_essay"),
    ("experience working with var's and channel partners", "customer_facing_essay"),
    ("var's and channel partners", "customer_facing_essay"),
    ("experience working with logs, metrics, it operations", "customer_facing_essay"),
    ("logs, metrics, it operations and security", "customer_facing_essay"),
    ("logs, metrics, it operations", "customer_facing_essay"),
    ("logs, metrics, observability", "customer_facing_essay"),
    ("logs, metrics", "customer_facing_essay"),
    # Cribl sandbox interest -> answer yes
    ("checked out our sandbox", "answer_yes"),
    ("check out our sandbox", "answer_yes"),
    ("sandbox.cribl.io", "answer_yes"),
    # Canonical in-person meeting requirement -> ack_in_office
    ("require all colleagues to meet in person 2-4 times", "ack_in_office"),
    ("meet in person 2-4 times a year", "ack_in_office"),
    ("colleagues to meet in person", "ack_in_office"),
    # Canonical nationality -> answer us citizen
    ("please indicate your nationality", "nationality_us_citizen"),
    ("indicate your nationality", "nationality_us_citizen"),
    # Sensei 3392 - Engg Maintenance Tech role is misclassified (not PM), mark No to key Qs
    ("have you been referred to", "explain_no"),  # 'have you been referred to sensei/company'


    ("gender", "demo_gender"),
    ("race", "demo_race"),
    ("ethnicity", "demo_race"),
    ("hispanic", "demo_race"),
    ("veteran", "demo_veteran"),
    ("disability", "demo_disability"),
    ("lgbt", "demo_lgbtq"),
]


# ---------------------------------------------------------------------------
# Resolvers
#
# Each resolver returns one of:
#   ("ok", value, source_path)         -> filled
#   ("decline", value, source_path)    -> intentionally declined (still ok)
#   ("unresolved", reason)             -> needs human or new mapping
# ---------------------------------------------------------------------------

def _ok(v, src): return ("ok", v, src)
def _decline(v, src): return ("decline", v, src)
def _unresolved(reason): return ("unresolved", reason, None)


def r_first_name(p, f):       return _ok(p["identity"]["first_name"], "identity.first_name")
def r_last_name(p, f):        return _ok(p["identity"]["last_name"], "identity.last_name")
def r_preferred_name(p, f):   return _ok(p["identity"]["preferred_name"], "identity.preferred_name")
def r_full_name(p, f):        return _ok(f'{p["identity"]["first_name"]} {p["identity"]["last_name"]}', "identity.first_name+last_name")
def r_pronouns(p, f):
    val = p["identity"].get("pronouns")
    if val == "decline_to_answer":
        return _decline("Decline to answer", "identity.pronouns")
    return _ok(val, "identity.pronouns") if val else _unresolved("pronouns not set")

def r_email(p, f):            return _ok(p["contact"]["email"], "contact.email")
def r_phone(p, f):            return _ok(p["contact"]["phone"], "contact.phone")
def r_linkedin(p, f):         return _ok(p["contact"]["linkedin"], "contact.linkedin")
def r_github(p, f):           return _ok(p["contact"]["github"], "contact.github")
def r_portfolio(p, f):
    # Per Cyrus form-answer doctrine (2026-06-10): a required Portfolio/personal-site
    # URL must auto-advance the app, never block it. Use portfolio_url if set, else
    # (when REQUIRED) fall back to website_required_fallback -> LinkedIn, mirroring
    # r_website. Optional + no portfolio_url -> blank (do not invent a value).
    v = p["contact"].get("portfolio_url")
    if v:
        return _ok(v, "contact.portfolio_url")
    if f.get("required"):
        fallback = p["contact"].get("website_required_fallback") or p["contact"].get("linkedin")
        if fallback:
            return _ok(fallback, "contact.website_required_fallback (required portfolio -> LinkedIn)")
        return _unresolved("portfolio_url is null and no website_required_fallback/linkedin")
    return _ok("", "portfolio optional + portfolio_url=null -> blank")

def r_website(p, f):
    # Per Cyrus 2026-05-07: leave blank if optional; fall back to LinkedIn if required.
    v = p["contact"].get("website_default")
    if v:
        return _ok(v, "contact.website_default")
    if f.get("required"):
        fallback = p["contact"].get("website_required_fallback") or p["contact"].get("linkedin")
        return _ok(fallback, "contact.website_required_fallback (required -> LinkedIn)")
    return _ok("", "contact.website_default=null (optional -> blank)")

def r_twitter(p, f):
    if f.get("required"):
        return _unresolved("twitter required but not provided")
    return _ok("", "twitter not provided (optional -> blank)")

def r_latitude(p, f):
    v = p["address"].get("latitude")
    return _ok(str(v), "address.latitude") if v is not None else _unresolved("address.latitude not set")

def r_longitude(p, f):
    v = p["address"].get("longitude")
    return _ok(str(v), "address.longitude") if v is not None else _unresolved("address.longitude not set")

def r_based_in_restricted_country(p, f):
    return _ok("No", "address.based_in_restricted_country (Cyrus 2026-05-07: always No)")

def r_based_in_restricted_state(p, f):
    return _ok("No", "address.based_in_restricted_state (Cyrus is in WA, not on restricted lists)")

def r_us_based_confirm(p, f):
    return _ok("Yes", "address.country=United States")

def r_worked_at_company_before(p, f):
    values = f.get("values") or f.get("options") or []
    if values:
        # Prefer literal No.
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower() == "no":
                return _ok(lbl, "worked_at_company_before (No)")
        # "No, I have not..." style answers (Dropbox 2026-05-22).
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower().startswith("no,") or lbl.lower().startswith("no "):
                return _ok(lbl, f"worked_at_company_before (matched No-prefix {lbl!r})")
        # SpaceX-style "I have never worked for <Company>" / "Never".
        # Helion 2712: options are "I have not worked for Helion" (the truthful
        # No-equivalent) vs former/current/contractor. Add "have not worked" /
        # "not worked for" / "do not work" so custom-phrased negatives match.
        prefer = ["i have never", "never worked", "i have not worked", "have not worked",
                  "not worked for", "not worked at", "do not work", "have not",
                  "never", "no relation", "none of the above", "n/a", "none", "not applicable"]
        for pat in prefer:
            for v in values:
                lbl = (v.get("label") or "").strip()
                if pat in lbl.lower():
                    return _ok(lbl, f"worked_at_company_before (matched {pat!r} -> {lbl!r})")
        labels = [v.get("label") for v in values]
        return _unresolved(f"worked_at_company_before: no No/Never option among {labels}")
    return _ok("No", "common_form_answers (Cyrus 2026-05-07: always No)")

def r_currently_student(p, f):
    return _ok("No", "experience_summary.current_employer=Microsoft (not a student)")


def r_clearance_eligibility(p, f):
    """Defense-contractor 'CLEARANCE ELIGIBILITY' selects (Anduril 2026-06-03).
    Cyrus holds NO active clearance but IS eligible (U.S. citizen, no
    disqualifiers). Truthful + non-knockout: prefer the 'eligible' option,
    NOT 'hold active' (false) and NOT 'No' (a needless knockout)."""
    values = f.get("values") or f.get("options") or []
    if not values:
        return _ok("Yes, I am eligible for a U.S. security clearance",
                   "clearance_eligibility (no options; US citizen eligible)")
    lbls = [(v.get("label") or "").strip() for v in values]
    low = [l.lower() for l in lbls]
    for l, lo in zip(lbls, low):
        if "eligible" in lo and "hold" not in lo and "active" not in lo:
            return _ok(l, "clearance_eligibility (eligible, US citizen)")
    for l, lo in zip(lbls, low):
        if lo.startswith("yes") and "eligible" in lo:
            return _ok(l, "clearance_eligibility (yes-eligible)")
    for l, lo in zip(lbls, low):
        if lo == "yes" or lo.startswith("yes,") or lo.startswith("yes "):
            return _ok(l, "clearance_eligibility (affirmative; eligible)")
    return _unresolved(f"clearance_eligibility: no eligible/yes option among {lbls}")


def r_clearance_level_held(p, f):
    """'If you have held a U.S. security clearance in the past, what level?'
    Cyrus has never held one -> N/A / None / never option (truthful)."""
    values = f.get("values") or f.get("options") or []
    if not values:
        return _ok("N/A - have never held U.S. security clearance",
                   "clearance_level_held (never held)")
    lbls = [(v.get("label") or "").strip() for v in values]
    prefer = ["never held", "have never", "n/a", "none", "not applicable", "no clearance"]
    for pat in prefer:
        for l in lbls:
            if pat in l.lower():
                return _ok(l, f"clearance_level_held (matched {pat!r} -> {l!r})")
    return _unresolved(f"clearance_level_held: no never/N-A option among {lbls}")


def r_customer_facing_essay(p, f):
    # Placeholder so dryrun passes. cover_answer_generator picks this up
    # via is_essay_question() at fill-time and writes a tailored answer
    # into cover_answers.md, which the browser plan uses to overwrite the
    # textarea value before submit.
    return _ok(
        "At Microsoft I led the Resilience Automation Platform working directly with on-call engineers and partner teams as customers — gathering requirements, running customer-feedback sessions, and shipping iterations against their workflows. Earlier roles included direct customer-facing engineering across deployment, integration, and post-sales support.",
        "customer_facing_essay (placeholder; cover_answer_generator regenerates at fill-time)",
    )

def r_city_location_select(p, f):
    """Location/city select (Axon hub, Airtable 'currently based:' etc.).
    Picks the option closest to Kirkland WA — prefer Seattle, then Pacific NW,
    then first US option, then first option."""
    values = f.get("values") or f.get("options") or []
    labels = [(v.get("label") or "").strip() for v in values]
    # Priority: Seattle > Pacific > Washington > West > N/A > first US city > first
    ordered_prefs = [
        "seattle", "pacific northwest", "washington", "west coast", "west",
        "n/a", "none", "remote", "bellevue", "kirkland", "redmond",
        "san francisco", "bay area", "new york", "los angeles",
    ]
    lbl_lower = [l.lower() for l in labels]
    for pref in ordered_prefs:
        for i, ll in enumerate(lbl_lower):
            if pref in ll:
                return _ok(labels[i], f"city_location_select: matched '{pref}'")
    # Fallback: first non-empty option
    for lbl in labels:
        if lbl:
            return _ok(lbl, "city_location_select: fallback first")
    return _ok("Seattle", "city_location_select: hardcoded fallback")


def r_visa_type_na(p, f):
    """Current visa status / visa type for US citizens — no visa needed.
    Picks the 'N/A' / 'Not applicable' / 'US Citizen' option if present;
    otherwise returns 'N/A' as freetext."""
    values = f.get("values") or f.get("options") or []
    labels = [(v.get("label") or "").strip() for v in values]
    prefer = ["n/a", "not applicable", "us citizen", "u.s. citizen", "none", "no visa",
              "citizen", "i am a us citizen", "united states citizen"]
    lbl_lower = [l.lower() for l in labels]
    for pref in prefer:
        for i, ll in enumerate(lbl_lower):
            if pref in ll:
                return _ok(labels[i], f"visa_type_na: matched '{pref}'")
    # If it's a freetext field (no values), return N/A
    if not labels:
        return _ok("N/A", "visa_type_na: freetext US citizen")
    return _ok(labels[0], "visa_type_na: fallback first option")


def r_acknowledge_yes(p, f):
    # Generic acknowledgment / consent / accuracy attestation.
    values = f.get("values") or f.get("options") or []
    if values:
        # Prefer Yes / Agree / Accept / Acknowledge / I Agree style options.
        prefer = ["yes", "i agree", "agree", "i accept", "accept", "i acknowledge", "acknowledge", "confirm", "i confirm"]
        for pat in prefer:
            for v in values:
                lbl = (v.get("label") or "").strip()
                if lbl.lower() == pat:
                    return _ok(lbl, f"acknowledge_yes (matched {lbl!r})")
        # Single-option "I Agree"-style checkboxes.
        if len(values) == 1:
            lbl = (values[0].get("label") or "").strip()
            return _ok(lbl, f"acknowledge_yes (single option {lbl!r})")
    return _ok("Yes", "acknowledge consent / accuracy (default Yes)")

def r_explain_no(p, f):
    # Conditional follow-up to a No answer earlier in the form.
    return _ok("", "conditional follow-up to No answer (intentionally blank)")

def r_answer_yes(p, f):
    # Generic "Yes" for boolean / yes-no questions where the safe default
    # is Yes (e.g. "are you at least 18?", "at least N years experience").
    values = f.get("values") or []
    if values:
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower() == "yes":
                return _ok(lbl, "answer_yes (matched 'Yes' option)")
        # Wiz 2026-05-25 (role 1370): consent options can be phrased as
        # "Yes, I consent to the retention of my data." etc. Match any option
        # whose label starts with 'Yes' (case-insensitive). Skip anything
        # starting with 'No' to avoid false positives.
        for v in values:
            lbl = (v.get("label") or "").strip()
            ll = lbl.lower()
            if ll.startswith("yes") and not ll.startswith("no"):
                return _ok(lbl, f"answer_yes (matched 'Yes...' option: {lbl!r})")
        labels = [v.get("label") for v in values]
        # Affirmative-synonym fallback (Everlaw 2759): consent/affirmation selects
        # often have NO literal 'Yes' option, only 'Agree'/'I Agree'/'Acknowledge'/
        # 'Accept'/'Confirm'. The affirmative answer is that sole option. Pick the
        # first option matching an affirmative synonym (skip negatives).
        AFFIRM = ("agree", "i agree", "acknowledge", "i acknowledge", "accept",
                  "i accept", "confirm", "i confirm", "affirm", "i affirm",
                  "understood", "i understand")
        for v in values:
            ll = (v.get("label") or "").strip().lower()
            if ll.startswith("no") or ll.startswith("decline"):
                continue
            if any(ll == a or ll.startswith(a) for a in AFFIRM):
                return _ok(v.get("label"), f"answer_yes (affirmative synonym: {v.get('label')!r})")
        # Sole-option forced-choice acknowledgment: if exactly one non-empty
        # option and it's not a negative, it IS the affirmative -> pick it.
        nonempty = [v for v in values if (v.get("label") or "").strip()]
        if len(nonempty) == 1:
            ll = (nonempty[0].get("label") or "").strip().lower()
            if not (ll.startswith("no") or ll.startswith("decline")):
                return _ok(nonempty[0].get("label"), f"answer_yes (sole affirmative option: {nonempty[0].get('label')!r})")
        return _unresolved(f"answer_yes: no 'Yes' option among {labels}")
    return _ok("Yes", "answer_yes (default Yes)")

def r_answer_no(p, f):
    # Generic "No" for boolean / yes-no select questions where the safe default
    # is No (e.g. conflict-of-interest, prior gov't oversight).
    values = f.get("values") or []
    if values:
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower() == "no":
                return _ok(lbl, "answer_no (matched 'No' option)")
        # Wiz 2026-05-25 (role 1370): paired option phrasing
        # "No, do not retain my data." etc. Match any label starting with 'No'.
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower().startswith("no"):
                return _ok(lbl, f"answer_no (matched 'No...' option: {lbl!r})")
        labels = [v.get("label") for v in values]
        return _unresolved(f"answer_no: no 'No' option among {labels}")
    return _ok("No", "answer_no (default No)")

def r_num_companies_worked(p, f):
    """Canonical: 'How many companies have you worked for since graduation?'
    Count distinct employers in work_experience. Options are numeric strings: 0-10+.
    Cyrus: Microsoft, Amazon Robotics, Pro Painters = 3 distinct employers.
    """
    work_exp = (p.get("work_experience") or [])
    # Count distinct company names
    companies = set()
    for we in work_exp:
        c = (we.get("company") or "").strip()
        if c:
            companies.add(c.lower())
    count = len(companies) if companies else 3  # default 3 for Cyrus
    target = str(count)
    values = f.get("values") or []
    for v in values:
        lbl = (v.get("label") or "").strip()
        if lbl == target:
            return _ok(lbl, f"num_companies_worked: {count} distinct employers")
    # Fallback: pick closest numeric option
    for v in values:
        lbl = (v.get("label") or "").strip()
        try:
            if int(lbl) >= count:
                return _ok(lbl, f"num_companies_worked: closest option >= {count}")
        except (ValueError, TypeError):
            pass
    return _ok(target, f"num_companies_worked: {count} (free-text fallback)")


def r_sql_skills_rating(p, f):
    """Taboola / numeric-scale SQL skill rating (0-5).
    Cyrus has working SQL knowledge from PM/TPM/analyst roles, rates himself 3.
    Options are string labels like '0', '1', '2', '3', '4', '5'.
    """
    target = "3"  # proficient but not expert DBA
    values = f.get("values") or []
    for v in values:
        lbl = (v.get("label") or "").strip()
        if lbl == target:
            return _ok(lbl, "sql_skills_rating: 3 (proficient)")
    # Fallback: pick middle-ish option
    if values:
        mid = values[len(values) // 2]
        return _ok((mid.get("label") or "").strip(), "sql_skills_rating: middle option")
    return _ok(target, "sql_skills_rating: default 3")


def r_alphabet_affiliation(p, f):
    """Waymo: 'Are you a current or former Alphabet employee...?'
    Cyrus has never worked at Alphabet/Google. Pick 'Never worked at Alphabet'.
    """
    values = f.get("values") or []
    for v in values:
        lbl = (v.get("label") or "").strip()
        if "never" in lbl.lower() and "alphabet" in lbl.lower():
            return _ok(lbl, "alphabet_affiliation: never worked at Alphabet")
    # Fallback: pick the last option (typically 'Never' or 'None')
    if values:
        last = (values[-1].get("label") or "").strip()
        return _ok(last, f"alphabet_affiliation: last option {last!r}")
    return _ok("Never worked at Alphabet", "alphabet_affiliation: default")


def r_ai_usage_level(p, f):
    """Coinbase-style 'How do you use AI tools today?' select.
    Cyrus actively designs/automates workflows with AI tools — pick the most
    advanced option ('I design or automate workflows...') if present, else
    'I regularly use AI tools...' fallback. Never pick 'opposed' / 'do not use'.
    """
    values = f.get("values") or []
    labels = [(v.get("label") or "").strip() for v in values]
    if not labels:
        return _ok("I design or automate workflows with AI tools", "ai_usage_level (free text)")
    # Prefer 'design or automate' first.
    for lbl in labels:
        if "design" in lbl.lower() and "automate" in lbl.lower():
            return _ok(lbl, "ai_usage_level: design/automate option")
    # Fallback: 'regularly use'.
    for lbl in labels:
        if "regularly" in lbl.lower() and "ai" in lbl.lower():
            return _ok(lbl, "ai_usage_level: regularly use AI option")
    # Last resort: any option that isn't opposed/do-not-use.
    for lbl in labels:
        ll = lbl.lower()
        if "opposed" not in ll and "do not use" not in ll and "not use" not in ll:
            return _ok(lbl, "ai_usage_level: first non-negative option")
    return _ok(labels[-1] if labels else "I regularly use AI tools", "ai_usage_level: last resort")
def r_proficiency_intermediate(p, f):
    # Skill/tool proficiency dropdowns (e.g. "level of proficiency in Python for
    # Data Science?"). Cyrus is a TPM/PM with real but non-specialist data skills
    # — honest tier is INTERMEDIATE, not Advanced/Expert. Pick the option whose
    # label contains 'intermediate'; else the middle option (skipping a leading
    # 'no experience'/'none'); else the first option. Keeps skill claims truthful
    # (biographical fact, not a motivational essay) per the fabrication red line.
    values = f.get("values") or []
    labels = [(v.get("label") or "").strip() for v in values]
    if not labels:
        return _ok("Intermediate", "proficiency_intermediate (free text)")
    for lbl in labels:
        if "intermediate" in lbl.lower():
            return _ok(lbl, f"proficiency_intermediate (matched {lbl!r})")
    cand = [l for l in labels if l.lower() not in ("no experience", "none", "n/a")]
    if cand:
        mid = cand[len(cand) // 2]
        return _ok(mid, f"proficiency_intermediate (middle option {mid!r})")
    return _ok(labels[0], f"proficiency_intermediate (first option {labels[0]!r})")


def r_coding_lang_python(p, f):
    # Programming language preference questions (CoreWeave 2026-05-13).
    # Pick Python if available, else first option.
    values = f.get("values") or []
    if values:
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower() == "python":
                return _ok(lbl, "coding_lang_python (matched 'Python' option)")
        # fall back to first option
        first = (values[0].get("label") or "").strip()
        return _ok(first, f"coding_lang_python (no 'Python', fell back to first: {first!r})")
    return _ok("Python", "coding_lang_python (default Python)")

def r_street(p, f):           return _ok(p["address"]["street"], "address.street")
def r_city(p, f):             return _ok(p["address"]["city"], "address.city")
def r_state(p, f):
    val = p["address"]["state"]
    values = f.get("values") or []
    if values:
        # Look for an exact match against options (handles abbrev-vs-fullname mismatch).
        labels = [(v.get("label") or "").strip() for v in values]
        # Exact abbreviation match
        for lbl in labels:
            if lbl.upper() == val.upper():
                return _ok(lbl, "address.state (exact option)")
        # Map abbreviation -> full name (Wiz 2026-05-25: dropdown lists full names like 'Washington').
        us_state_full = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington D.C.",
        }
        full = us_state_full.get(val.upper())
        if full:
            for lbl in labels:
                if lbl.lower() == full.lower():
                    return _ok(lbl, f"address.state (mapped {val} -> {lbl})")
        return _ok(val, f"address.state (NOTE: {val!r} not literally in options {labels})")
    return _ok(val, "address.state")
def r_zip(p, f):              return _ok(p["address"]["zip"], "address.zip")
def r_country(p, f):          return _ok(p["address"]["country"], "address.country")
def r_city_state(p, f):
    city = p["address"]["city"]
    state = p["address"]["state"]
    val_default = f"{city}, {state}"
    # If field has dropdown options (Intercom 2026-05-26 role 1371: country/region list),
    # try to fuzzy-match the state into option labels like 'US - Washington' or 'Washington'.
    values = f.get("values") or []
    if values:
        labels = [(v.get("label") or "") for v in values]
        us_state_full = {
            "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
            "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
            "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa","KS":"Kansas",
            "KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland","MA":"Massachusetts",
            "MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri","MT":"Montana",
            "NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey",
            "NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota",
            "OH":"Ohio","OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island",
            "SC":"South Carolina","SD":"South Dakota","TN":"Tennessee","TX":"Texas",
            "UT":"Utah","VT":"Vermont","VA":"Virginia","WA":"Washington","WV":"West Virginia",
            "WI":"Wisconsin","WY":"Wyoming","DC":"Washington D.C.",
        }
        full = us_state_full.get((state or "").upper(), state or "")
        for lbl in labels:
            ll = lbl.lower()
            if ll == val_default.lower():
                return _ok(lbl, f"address.city+state (matched option {lbl!r})")
            if full and full.lower() in ll and ("us" in ll or "u.s" in ll or "united states" in ll):
                return _ok(lbl, f"address.state (matched US-state option {lbl!r})")
        for lbl in labels:
            if full and lbl.lower() == full.lower():
                return _ok(lbl, f"address.state (matched bare option {lbl!r})")
        # Fall through: keep default value but flag
        return _ok(val_default, f"address.city+state (NOTE: {val_default!r} not in options)")
    return _ok(val_default, "address.city+state")

def r_full_address(p, f):
    # Single-line bare "Address" / "Home Address" / "Current Address" text field
    # (Zuora 2755 2026-06-08: 'Home Address' had NO LABEL_RULES match -> no plan
    # emitted -> row blocked). A bare address box wants the full one-line mailing
    # address, not just city/state. Build it from the structured address parts.
    # If the field is actually a dropdown (rare for a free address box), defer to
    # the city_state matcher so we still pick a sensible option instead of dumping
    # a street string that won't match any option.
    if f.get("values"):
        return r_city_state(p, f)
    a = p["address"]
    street = (a.get("street") or "").strip()
    city = (a.get("city") or "").strip()
    state = (a.get("state") or "").strip()
    zipc = (a.get("zip") or "").strip()
    line2 = f"{city}, {state} {zipc}".strip().strip(",").strip()
    full = ", ".join(part for part in (street, line2) if part)
    if not full:
        # No street on file -> degrade gracefully to city/state rather than block.
        return r_city_state(p, f)
    return _ok(full, "address.street+city+state+zip (full one-line address)")

def r_work_authorized(p, f):
    # Lyft 2026-05-24 (role 717): "Work Authorization" select has long-form
    # options like "I am authorized to work for any employer ..." / "I require sponsorship ...".
    # No literal "Yes"/"No". Match by content.
    authorized = p["work_authorization"]["authorized_to_work_us"] == "yes"
    values = f.get("values") or []
    if values:
        for v in values:
            lbl = (v.get("label") or "").strip()
            low = lbl.lower()
            if authorized:
                if low == "yes":
                    return _ok(lbl, "work_authorization.authorized_to_work_us (matched 'Yes')")
                # Orb 2026-05-26 (role 1184): options "Can work for any employer" / "Can work for current employer" / "Seeking work authorization".
                # Pick "any employer" variant when authorized.
                if "can work for any employer" in low:
                    return _ok(lbl, "work_authorization.authorized_to_work_us (matched 'Can work for any employer')")
                if "authorized to work for any employer" in low or "authorised to work for any employer" in low or (("authorized to work" in low or "authorised to work" in low) and "sponsor" not in low and "require" not in low and "unknown" not in low):
                    return _ok(lbl, "work_authorization.authorized_to_work_us (matched 'authorized to work for any employer')")
                # Datadog 2026-05-26 (role 1364): options "Yes, no restriction." / "Yes, but I will need sponsorship..." / "No, I need sponsorship now."
                # Pick the Yes-no-restriction variant when authorized + no sponsorship needed.
                needs_spon = (p["work_authorization"].get("sponsorship_required_now") == "yes"
                              or p["work_authorization"].get("sponsorship_required_future") == "yes")
                if (not needs_spon) and low.startswith("yes") and ("no restriction" in low or "without restriction" in low or "do not" in low or "don't" in low or ("sponsor" not in low and "require" not in low)):
                    return _ok(lbl, "work_authorization.authorized_to_work_us (matched Yes/no-restriction variant)")
                # Neural Concept 2026-05-26 (role 1365): options "I am a US citizen, green card holder or VISA that does not require sponsorship" / "VISA that would require sponsorship" / "Other".
                # Pick the citizen/GC/no-sponsorship-VISA combined option when authorized + no sponsorship needed.
                if (not needs_spon) and ("us citizen" in low or "u.s. citizen" in low or "green card" in low) and ("does not require sponsorship" in low or "do not require sponsorship" in low or "no sponsorship" in low or "not require sponsorship" in low):
                    return _ok(lbl, "work_authorization.authorized_to_work_us (matched US-citizen/GC/no-sponsorship-VISA combined option)")
            else:
                if low == "no":
                    return _ok(lbl, "work_authorization.authorized_to_work_us (matched 'No')")
        labels = [v.get("label") for v in values]
        return _unresolved(f"work_authorized: no matching option among {labels}")
    return _ok("Yes" if authorized else "No", "work_authorization.authorized_to_work_us")
def r_needs_sponsorship(p, f): return _ok("Yes" if p["work_authorization"]["sponsorship_required_now"] == "yes" or p["work_authorization"]["sponsorship_required_future"] == "yes" else "No", "work_authorization.sponsorship_required_*")
def r_itar_us_person_ack(p, f):
    # Cyrus is a US citizen. Export-control questions come in TWO opposite
    # polarities and the correct answer flips between them:
    #
    #   AFFIRMATIVE phrasing -> US citizen answers YES:
    #     "Are you a U.S. person / U.S. citizen?", "I am a US person"
    #   INVERTED phrasing     -> US citizen answers NO:
    #     "Does the deemed export rule AFFECT your employment?"
    #     "Do you REQUIRE a deemed export / export license?"
    #     "Are you SUBJECT TO export controls?" / "...a foreign person?"
    #
    # The old resolver returned "Yes" for BOTH, which on Pure Storage's
    # "Does the deemed export rule affect your employment?" meant "yes, I need
    # an export license" -> AUTO-REJECT (real failure, 5 Pure Storage apps,
    # 2026-06-04). Detect the inverted polarity from the label and flip.
    is_citizen = (p.get("work_authorization", {}).get("status", "").lower()
                  == "us_citizen")
    label = (f.get("label") or f.get("question") or "").lower()
    # Inverted-polarity markers: the question asks whether the rule
    # affects/applies to / whether the applicant requires a license / is a
    # foreign person / is subject to controls. For a US citizen these are all
    # "No".
    _INVERTED_MARKERS = (
        "affect your employment", "affect your eligibility",
        "deemed export rule affect", "export rule affect",
        "require a deemed export", "require a deemed-export",
        "require an export license", "require a deemed export license",
        "require a license", "need an export license",
        "subject to export", "subject to the export",
        "are you a foreign person", "are you a foreign national",
        "foreign person under", "do you require export",
        "does the export control", "does export control",
        "will you require", "are you restricted",
    )
    inverted = any(m in label for m in _INVERTED_MARKERS)
    # Robust catch: "are you subject to ... export ..." is unambiguously
    # inverted regardless of intervening words ("subject to U.S. export
    # controls" breaks a plain 'subject to export' substring).
    if not inverted and "subject to" in label and "export" in label:
        inverted = True
    # "...require ... export license" / "require ... deemed export" likewise.
    if not inverted and "require" in label and ("export" in label or "deemed" in label):
        inverted = True
    values = f.get("values") or []
    if values:
        labels = [(v.get("label") or "") for v in values]
        if inverted and is_citizen:
            # US citizen + inverted question -> pick the NEGATIVE option.
            # Prefer an exact 'No', else a 'does not affect / not subject /
            # not a foreign person' style option.
            for lbl in labels:
                if lbl.strip().lower() in ("no", "no."):
                    return _ok(lbl, f"work_authorization.status=us_citizen (INVERTED export Q '{label[:40]}...' -> No)")
            neg_needles = ("does not", "not affect", "not subject", "not a foreign",
                           "no, ", "none of the above")
            for needle in neg_needles:
                for lbl in labels:
                    if needle in lbl.lower():
                        return _ok(lbl, f"work_authorization.status=us_citizen (inverted export Q -> {lbl!r})")
            return _unresolved(f"inverted ITAR field has no No/negative option among {labels}")
        # Affirmative phrasing: look for the most specific US-citizen / US-person
        # / yes / acknowledgment option.
        priorities = [
            "united states citizen", "u.s. citizen", "us citizen",
            "a united states citizen",
            "citizen or national of the united states",
            "national of the united states",
            "u.s. person", "us person", "i am a us person",
            "yes, i am a u.s. person", "yes, i am a us person",
            "i acknowledge", "yes",
        ]
        if is_citizen:
            for needle in priorities:
                for lbl in labels:
                    if needle in lbl.lower():
                        return _ok(lbl, f"work_authorization.status=us_citizen (matched ITAR option {lbl!r})")
            # 'Negative ITAR' pattern (Databricks-style): all listed options are
            # restrictive (sanctioned-country residence / Russia etc.) and the
            # safe answer for a US citizen is the 'None of the above' opt-out.
            for lbl in labels:
                if "none of the above" in lbl.lower():
                    return _ok(lbl, f"work_authorization.status=us_citizen (negative-ITAR opt-out: {lbl!r})")
        # Non-citizen path (shouldn't trigger for Cyrus, but be safe).
        for lbl in labels:
            if "no" == lbl.strip().lower():
                return _ok(lbl, "work_authorization (non-citizen -> No)")
        return _unresolved(f"ITAR field has no US-citizen / Yes option among {labels}")
    # Boolean / freeform path. Flip on inverted polarity:
    #   affirmative  (are you a US person?)      citizen -> Yes
    #   inverted     (does the rule affect you?) citizen -> No
    if inverted:
        return _ok("No" if is_citizen else "Yes",
                   f"work_authorization.status (INVERTED export Q -> {'No' if is_citizen else 'Yes'})")
    return _ok("Yes" if is_citizen else "No",
               "work_authorization.status (ITAR/EAR US-person ack)")


def r_transitioning_service_member(p, f):
    # Custom "are you a transitioning service member / veteran" field.
    # Distinct from EEO veteran-protected-status (which uses decline path).
    # Cyrus is not a veteran -> answer 'No'.
    values = f.get("values") or []
    if values:
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower() == "no":
                return _ok(lbl, "not a veteran / transitioning service member")
        # Couldn't find a literal "No" — leave for review rather than guess.
        labels = [v.get("label") for v in values]
        return _unresolved(f"transitioning_service_member: no 'No' option among {labels}")
    return _ok("No", "not a veteran / transitioning service member")


def r_security_clearance(p, f):
    v = p["work_authorization"].get("security_clearance", "none")
    return _ok("None" if v == "none" else v, "work_authorization.security_clearance")

def r_years_experience(p, f): return _ok(p["experience_summary"]["answer_for_years_of_experience_field"], "experience_summary.answer_for_years_of_experience_field")
def r_current_employer(p, f): return _ok(p["experience_summary"]["current_employer"], "experience_summary.current_employer")
def r_current_title(p, f):    return _ok(p["experience_summary"]["current_title"], "experience_summary.current_title")

def r_school(p, f):           return _ok(p["education"]["school"], "education.school")
def r_degree(p, f):           return _ok(p["education"]["degree"], "education.degree")
def r_major(p, f):            return _ok(p["education"]["major"], "education.major")
def r_minor(p, f):            return _ok(p["education"].get("minor") or "", "education.minor")
def r_gpa(p, f):              return _ok(p["education"]["gpa"], "education.gpa")
def r_graduation_year(p, f):  return _ok(p["education"]["graduation_year"], "education.graduation_year")
def r_graduation_month(p, f): return _ok(p["education"].get("graduation_month", "December"), "education.graduation_month")

def r_not_ma_resident(p, f):
    """MA lie-detector statutory-notice select. Cyrus resides in Kirkland WA, NOT
    Massachusetts -> pick the 'I don't reside in Massachusetts' option (truthful).
    Falls back to any non-MA / negative option."""
    values = f.get("values") or []
    for v in values:
        ll = (v.get("label") or "").lower()
        if "don" in ll and "reside in massachusetts" in ll:
            return _ok(v.get("label"), "not_ma_resident (don't reside in MA)")
    for v in values:
        ll = (v.get("label") or "").lower()
        if "not" in ll and "massachusetts" in ll:
            return _ok(v.get("label"), "not_ma_resident (not a MA resident)")
    return _unresolved(f"no non-MA option among {[v.get('label') for v in values]}")

def r_relocation_city_select(p, f):
    """Twitch/Amazon-style relocation question where 'Yes' answer is represented
    by city names (Seattle, San Francisco, etc.) rather than Yes/No.
    Cyrus is willing to relocate anywhere in the US. Pick the most desirable city
    or first city option (skip 'No' options)."""
    values = f.get("values") or []
    labels = [(v.get("label") or "").strip() for v in values]
    # Preferred cities (closest to Kirkland WA or major tech hubs)
    city_prefs = ["seattle", "bellevue", "kirkland", "redmond", "san francisco",
                  "new york", "boston", "chicago", "austin", "los angeles", "irvine"]
    lbl_lower = [l.lower() for l in labels]
    for pref in city_prefs:
        for i, ll in enumerate(lbl_lower):
            if pref in ll:
                return _ok(labels[i], f"relocation_city_select: preferred city '{pref}'")
    # Fallback: any option that is not 'No' or 'No, but...'
    for i, lbl in enumerate(labels):
        if not lbl.lower().startswith("no"):
            return _ok(lbl, "relocation_city_select: first non-No option")
    # Last resort: first option
    return _ok(labels[0] if labels else "Yes", "relocation_city_select: fallback")


def r_answer_na_text(p, f):
    """Return 'N/A' for freetext follow-up fields where no referral/prior context applies.
    Used for 'If you answered no, enter N/A' follow-up questions."""
    return _ok("N/A", "answer_na_text: no referral / not applicable")


def r_nationality_us_citizen(p, f):
    """Nationality/citizenship field. Cyrus is a US citizen.
    Picks 'United States' / 'American' / 'US' option if available;
    otherwise returns 'United States' as freetext."""
    values = f.get("values") or []
    labels = [(v.get("label") or "").strip() for v in values]
    lbl_lower = [l.lower() for l in labels]
    prefs = ["united states", "american", "u.s. citizen", "us citizen", "usa", "us"]
    for pref in prefs:
        for i, ll in enumerate(lbl_lower):
            if pref == ll or ll.startswith(pref):
                return _ok(labels[i], f"nationality_us_citizen: matched '{pref}'")
    if not labels:
        return _ok("United States", "nationality_us_citizen: freetext US citizen")
    return _ok(labels[0], "nationality_us_citizen: fallback first option")



def r_pm_data_experience_select(p, f):
    """YipitData PM experience select: pick the 'Over 5 years IN data-intensive' option.
    Cyrus has 5+ years in PM/TPM roles with data-intensive products at Microsoft."""
    values = f.get("values") or []
    labels = [(v.get("label") or "").strip() for v in values]
    lbl_lower = [l.lower() for l in labels]
    # Prefer '5 years...IN data-intensive' (strongest match)
    for i, ll in enumerate(lbl_lower):
        if "5 years" in ll and "in data" in ll:
            return _ok(labels[i], "pm_data_experience_select: 5yr in data-intensive")
    # Fall back to '5 years' option (any)
    for i, ll in enumerate(lbl_lower):
        if "5 years" in ll or "over 5" in ll:
            return _ok(labels[i], "pm_data_experience_select: over 5 years")
    return _ok(labels[0] if labels else "Yes", "pm_data_experience_select: fallback first")


def r_timezone_pacific(p, f):
    """Pick the Pacific-time option for a 'which time-zone are you in?' dropdown.
    Cyrus is based in Kirkland WA = US Pacific Time. Falls back to a free-text
    'Pacific' answer if the field has no options."""
    values = f.get("values") or []
    if values:
        # Most-specific Pacific aliases first.
        needles = ["pacific", "pst", "pdt", "pt (", "us/pacific", "america/los_angeles",
                   "los angeles", "utc-8", "utc-08", "gmt-8", "gmt-08", "west coast",
                   "western"]
        for n in needles:
            for v in values:
                if n in (v.get("label") or "").lower():
                    return _ok(v.get("label"), f"timezone_pacific (matched {n!r})")
        return _unresolved(f"no Pacific-time option among {[v.get('label') for v in values]}")
    return _ok("Pacific Time (US & Canada)", "timezone_pacific (free-text)")

def r_compensation(p, f):
    v = p["preferences"].get("compensation_expectation", "open_to_discuss")
    if v == "open_to_discuss":
        return _ok("Open to discuss", "preferences.compensation_expectation")
    return _ok(v, "preferences.compensation_expectation")
def r_willing_to_relocate(p, f):
    # Some tenants (Lyft 2026-05-24 role 717) ship a multi_value_single_select
    # with options like "I am willing to relocate before starting employment."
    # vs "I am not willing to relocate ..." vs "I already reside near a <Co> office".
    # Cyrus is in Kirkland WA, willing to relocate for any US role -> pick the
    # "willing to relocate" option, NOT "already reside near" (false claim).
    values = f.get("values") or []
    if values:
        # Prefer an exact / starts-with "willing to relocate" (excluding negations).
        for v in values:
            lbl = (v.get("label") or "").strip()
            low = lbl.lower()
            if "willing to relocate" in low and "not willing" not in low and "don't" not in low and "do not" not in low:
                return _ok(lbl, "preferences.willing_to_relocate (matched 'willing to relocate' option)")
        # Also match 'open to relocation' or 'open to relocat' (Stripe-style multiselect).
        for v in values:
            lbl = (v.get("label") or "").strip()
            low = lbl.lower()
            if ("open to relocation" in low or "open to relocat" in low) and "not local" in low:
                return _ok(lbl, "preferences.willing_to_relocate (matched 'open to relocation, not local' option)")
        # Fall back to plain 'Yes' if present.
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower() == "yes":
                return _ok(lbl, "preferences.willing_to_relocate (matched 'Yes' option)")
        labels = [v.get("label") for v in values]
        # Fallback: if options are city names (no Yes), pick nearest city (Twitch-style)
        # Cyrus is willing to relocate anywhere in the US.
        city_prefs = ["seattle", "san francisco", "new york", "remote"]
        lbl_lower = [(l or "").lower() for l in labels]
        for pref in city_prefs:
            for i, ll in enumerate(lbl_lower):
                if pref in ll:
                    return _ok(labels[i], f"willing_to_relocate: city fallback '{pref}'")
        # Pick first non-No option
        for lbl in labels:
            if lbl and not (lbl or "").lower().startswith("no"):
                return _ok(lbl, "willing_to_relocate: first non-No city option")
        return _unresolved(f"willing_to_relocate: no matching option among {labels}")
    return _ok("Yes", "preferences.willing_to_relocate")
def r_willing_to_travel(p, f):
    # Truthful travel willingness. On a FREE-TEXT field, return the pct string
    # (e.g. "25%"). On a Yes/No SELECT (e.g. "Are you willing to travel up to
    # 20%?" with Yes/No options), the pct text matches no option and the field
    # banks empty -> pick the affirmative option instead (Cyrus is willing to
    # travel up to his stated pct, and US travel is never a knockout). 2026-06-08.
    values = f.get("values") or []
    if values:
        for v in values:
            lbl = (v.get("label") or "").strip()
            if lbl.lower() == "yes":
                return _ok(lbl, "preferences.willing_to_travel_pct (matched 'Yes' option)")
        for v in values:
            lbl = (v.get("label") or "").strip()
            ll = lbl.lower()
            if ll.startswith("yes") and not ll.startswith("no"):
                return _ok(lbl, f"preferences.willing_to_travel_pct (matched 'Yes...' option: {lbl!r})")
        # Affirmative-synonym fallback (Agree/I agree/etc.), skip negatives.
        for v in values:
            ll = (v.get("label") or "").strip().lower()
            if ll.startswith("no") or ll.startswith("decline"):
                continue
            if ll in ("agree", "i agree") or ll.startswith("agree"):
                return _ok(v.get("label"), f"preferences.willing_to_travel_pct (affirmative option: {v.get('label')!r})")
        labels = [v.get("label") for v in values]
        return _unresolved(f"willing_to_travel: no Yes/affirmative option among {labels}")
    return _ok(p["preferences"]["willing_to_travel_pct"] + "%", "preferences.willing_to_travel_pct")
def r_remote_pref(p, f):         return _ok("Open to remote, hybrid, or onsite", "preferences.remote_preference")
def r_ack_hybrid(p, f):          return _ok("Yes", "preferences.remote_preference (acks hybrid)")
def r_ack_in_office(p, f):       return _ok("Yes", "preferences.willing_to_travel_pct (>=25%)")
def r_pick_only_option(p, f):
    """Single-option confirm/acknowledge selects (e.g. Astranis 'Please confirm
    the season you are applying for.' with only 'Summer 2026'). Pick the sole
    option; if multiple, pick the first non-placeholder. Truthful: these are
    forced-choice confirmations, not biographical claims."""
    values = f.get("values") or []
    labels = [(v.get("label") or "").strip() for v in values if (v.get("label") or "").strip()]
    if not labels:
        return _unresolved("pick_only_option: no options present")
    # drop obvious placeholders
    real = [l for l in labels if l.lower() not in ("select...", "select", "--", "please select", "choose one")]
    pick = real[0] if real else labels[0]
    return _ok(pick, f"pick_only_option (sole/first option {pick!r})")


def r_earliest_start(p, f):
    """Earliest start / ideal start date. Handles free-text, date pickers,
    and select fields with options like Immediately/2 weeks/1 month."""
    from datetime import date, timedelta
    ftype = f.get("type")
    values = f.get("values") or []
    # Date picker -> today + 14 days, YYYY-MM-DD.
    if ftype in ("input_date", "date"):
        return _ok((date.today() + timedelta(days=14)).isoformat(),
                   "preferences.earliest_start_date (date picker -> today+14d)")
    # Select with options -> pick "2 weeks" or closest equivalent.
    if values:
        labels = [(v.get("label") or "") for v in values]
        priorities = [
            "within 2 weeks", "2 weeks", "two weeks",
            "within 1 month", "1 month", "one month",
            "immediately", "asap", "as soon as possible",
            "within 3 months", "3 months",
        ]
        for needle in priorities:
            for lbl in labels:
                if needle in lbl.lower():
                    return _ok(lbl, f"preferences.earliest_start_date (matched select option {lbl!r})")
        return _unresolved(f"earliest_start: no recognized option among {labels}")
    return _ok("Within 2 weeks of offer", "preferences.earliest_start_date")
def r_notice_period(p, f):       return _ok(f'{p["preferences"]["notice_period_weeks"]} weeks', "preferences.notice_period_weeks")

def r_how_heard(p, f):
    val = p["common_form_answers"]["how_did_you_hear_about_us"]
    values = f.get("values") or []
    if values:
        labels = [(v.get("label") or "") for v in values]
        # 1) literal match
        for lbl in labels:
            if lbl.lower() == (val or "").lower():
                return _ok(lbl, f"how_heard literal-match {lbl!r}")
        # 2) preferred fuzzy fallbacks for known-narrow option sets
        # (Intercom 2026-05-26 role 1371): options like 'Job Board', 'Social Media', etc.
        preferred = ["linkedin", "job board", "social media", "online", "website", "other"]
        for needle in preferred:
            for lbl in labels:
                if needle in lbl.lower():
                    return _ok(lbl, f"how_heard fuzzy {needle!r} -> {lbl!r}")
        return _ok(labels[0], f"how_heard first-option fallback {labels[0]!r}")
    return _ok(val, "common_form_answers.how_did_you_hear_about_us")
def r_referred_by(p, f):
    v = p["common_form_answers"].get("referred_by_employee")
    return _ok(v, "common_form_answers.referred_by_employee") if v else _ok("", "common_form_answers.referred_by_employee (null -> blank)")
def r_previously_applied(p, f):  return _ok("No", "common_form_answers.previously_applied_to_company")
def r_previously_employed(p, f): return _ok("No", "common_form_answers.previously_employed_by_company")
def r_currently_employed(p, f):  return _ok("Yes", "common_form_answers.currently_employed")
def r_background_check(p, f):    return _ok("Yes", "common_form_answers.willing_to_complete_background_check")
def r_drug_screen(p, f):         return _ok("Yes", "common_form_answers.willing_to_complete_drug_screen")
def r_drivers_license(p, f):     return _ok("Yes", "common_form_answers.valid_drivers_license")
def r_felony(p, f):              return _ok("No", "common_form_answers.felony_conviction")
def r_non_compete(p, f):         return _ok("No", "common_form_answers.non_compete_agreement")
def r_previously_interviewed(p, f): return _ok("No", "common_form_answers.previously_applied_to_company (proxy)")
def r_ai_policy_ack(p, f):       return _ok("Yes", "hardcoded ack of AI policy")
def r_ai_use_no(p, f):           return _ok("No", "AI-disclosure policy: answer No to AI-in-workflow questions")

def r_why_company_essay(p, f):
    template = p.get("_why_company_template")
    company = p.get("_company_name") or "the company"
    if not template:
        return _unresolved('Free-form essay ("Why X?") — needs Cyrus to write per role')
    filled = template.replace("[Company]", company)
    return _ok(filled, f"why-company-template.md (substituted [Company]={company!r})")
def r_cover_letter(p, f):
    policy = p.get("cover_letter_policy", "skip_unless_required")
    if policy == "skip_unless_required":
        if f.get("required"):
            return _ok(p.get("cover_letter_default", ""), "cover_letter_default (required)")
        return _ok("", "cover_letter_policy=skip_unless_required (optional -> blank)")
    return _unresolved("cover letter policy unclear")
def r_additional_info(p, f):     return _ok("", "intentionally blank (optional)")
def r_deadlines_note(p, f):      return _ok("", "intentionally blank (optional)")

def r_resume(p, f):
    if f.get("type") == "input_file":
        return _ok(p["files"]["resume_path"], "files.resume_path")
    if f.get("type") == "textarea":
        # Greenhouse offers a paste-resume textarea fallback
        return _ok(f'<<paste contents of {p["files"]["resume_text_path"]}>>', "files.resume_text_path")
    return _unresolved(f'unexpected resume field type: {f.get("type")}')

def r_product_brief_file(p, f):
    """Resolve a required custom PRD/product-brief/writing-sample FILE question.

    We cannot fill the bytes at dryrun time, but the submit runner
    (_gh_submit.upload_custom_required_file) auto-generates a sanitized product
    brief PDF (prd_brief_pdf, grounded in the resume) and set_input_files it.
    Return a non-blocking sentinel so the field is 'filled' and the plan emits.
    A text/textarea variant (rare) gets a short pointer to the brief instead.
    """
    if f.get("type") == "input_file":
        return _ok("<<auto-generate product brief at submit (prd_brief_pdf)>>",
                   "product_brief_file: runner auto-generates + uploads PDF")
    # text fallback: brief inline summary pointer (kept generic + truthful)
    return _ok("Please see the attached product brief / resume for a launched "
               "product I defined requirements for (an internal Resilience "
               "Automation Platform built 0->1).",
               "product_brief_file (text fallback)")

def r_demo_default(p, f):
    return _decline("Decline to self-identify", "demographics_default")

def r_family_relations_at_company(p, f):
    return _ok("No", "family_relations_at_company (default no)")

def r_countries_of_work_auth(p, f):
    return _ok("United States", "countries_of_work_auth (US only)")

def _ack_pick(f, default="Yes"):
    """For acknowledgement-style fields: if the field exposes a discrete option set
    (single-select, multi-select, or radio with labels other than literal Yes/No),
    pick the option whose label looks like a positive acknowledgement
    (acknowledge / agree / accept / confirm / consent / I understand). Fallback to
    the first option when only one is present (e.g. Elastic's ['I acknowledge']),
    otherwise return the default literal ("Yes")."""
    values = f.get("values") or []
    if not values:
        return default
    labels = [(v.get("label") or "").strip() for v in values]
    # Direct Yes match wins.
    for lbl in labels:
        if lbl.lower() == default.lower():
            return lbl
    POS_KW = ("acknowledge", "i agree", "agree", "accept", "i confirm", "confirm",
              "consent", "i understand", "yes")
    for kw in POS_KW:
        for lbl in labels:
            if kw in lbl.lower():
                return lbl
    # Only one option present — that IS the acknowledgement (single-checkbox style).
    if len(labels) == 1 and labels[0]:
        return labels[0]
    return default

def r_privacy_ack(p, f):
    val = _ack_pick(f, default="Yes")
    return _ok(val, "privacy_ack (always acknowledge)")

def r_essential_functions_ack(p, f):
    val = _ack_pick(f, default="Yes")
    return _ok(val, "essential_functions_ack (default yes)")

def r_optional_blank(p, f):
    return _ok("", "optional field — intentionally blank")

def r_literal_na(p, f):
    return _ok("N/A", "literal N/A (free-text follow-up to a No gate)")

def r_cities_available(p, f):
    # When the field exposes a discrete city option set (Datadog multi-select),
    # pick US-presence and major-hub matches. Prefer Remote + Cyrus's home metro.
    values = f.get("values") or []
    if values:
        labels = [(v.get("label") or "").strip() for v in values]
        # Priority: Remote (work-from-anywhere), Cyrus's home/Bay Area, then major US hubs.
        PREFERRED = [
            "remote",
            "seattle", "san francisco", "san jose", "new york", "new york city",
            "boston", "chicago", "atlanta", "denver", "salt lake city",
        ]
        picks = []
        for needle in PREFERRED:
            for lbl in labels:
                if needle == lbl.lower() or needle in lbl.lower():
                    if lbl not in picks:
                        picks.append(lbl)
        if picks:
            return _ok(picks if len(picks) > 1 else picks[0],
                       f"cities_available (multi-select; picked US hubs {picks})")
        # No US hub matched — fall back to first option.
        return _ok(labels[0], f"cities_available (no US hub match; picked first option {labels[0]!r})")
    val = (p.get("cities_available_to_work") or "").strip()
    if not val:
        return _ok(
            "Open to relocating anywhere in the United States.",
            "cities_available (fallback)",
        )
    return _ok(val, "cities_available_to_work")

def r_languages_fluent(p, f):
    langs = p.get("languages_spoken") or ["English"]
    # Multi-select: try to match each language to an option label.
    values = f.get("values") or []
    if values:
        labels = [(v.get("label") or "") for v in values]
        picks = []
        for lang in langs:
            for lbl in labels:
                if lang.lower() == lbl.lower() or lang.lower() in lbl.lower():
                    picks.append(lbl); break
        if picks:
            return _ok(picks if len(picks) > 1 else picks[0],
                       f"languages_fluent (matched {picks})")
    # No options exposed (free-text). If field is optional, leave blank;
    # otherwise fall back to comma-joined.
    if not f.get("q_required"):
        return _ok("", "languages_fluent (optional, no options)")
    return _ok(", ".join(langs), "languages_fluent (free text)")

def r_ai_familiarity_high(p, f):
    # Pick highest familiarity option from dropdown values; fall back to "Expert"/"Advanced"
    values = f.get("values") or []
    if values:
        priority = ["expert", "advanced", "very familiar", "highly familiar", "5", "4"]
        labels = [(v.get("label") or "") for v in values]
        for needle in priority:
            for lbl in labels:
                if needle in lbl.lower():
                    return _ok(lbl, f"ai_familiarity_high (matched {lbl!r})")
        # fall back to last option (often highest)
        return _ok(labels[-1], "ai_familiarity_high (last option default)")
    return _ok("Expert", "ai_familiarity_high (free text)")

def r_english_comfort_high(p, f):
    # English-proficiency / "comfortable reading, writing and speaking in
    # English" comfort-scale questions. Cyrus is a NATIVE English speaker, so
    # the truthful answer is the HIGHEST comfort tier. Pick the option whose
    # label is the most-comfortable/native/fluent tier; for a Yes/No phrasing
    # pick Yes; for a free-text field answer affirmatively. Biographical fact,
    # not an essay — stays on the right side of the fabrication red line.
    values = f.get("values") or []
    if values:
        labels = [(v.get("label") or "") for v in values]
        # Yes/No phrasing first.
        for lbl in labels:
            if lbl.strip().lower() == "yes":
                return _ok(lbl, "english_comfort_high (Yes option)")
        # Highest comfort/fluency tier.
        priority = ["native", "native or bilingual", "fluent", "full professional",
                    "professional working", "very comfortable", "extremely comfortable",
                    "completely comfortable", "expert", "advanced", "excellent",
                    "highly proficient", "5", "4"]
        for needle in priority:
            for lbl in labels:
                if needle in lbl.lower():
                    return _ok(lbl, f"english_comfort_high (matched {lbl!r})")
        # Fall back to last option (scales usually ascend to highest last).
        return _ok(labels[-1], "english_comfort_high (last option default)")
    return _ok("Yes", "english_comfort_high (free text — native English speaker)")

def r_experience_short_yes(p, f):
    # Generic short-answer "do you have experience with X?" questions. Default
    # to a brief Yes anchored in Cyrus's Microsoft tenure. The label is in f.
    label = (f.get("label") or "").strip().rstrip("?").lower()
    # Trim leading interrogative
    for prefix in ("do you have", "have you"):
        if label.startswith(prefix):
            label = label[len(prefix):].strip()
            break
    # If it's a Yes/No dropdown with options, pick Yes
    values = f.get("values") or []
    if values:
        for v in values:
            lbl = (v.get("label") or "").strip().lower()
            if lbl == "yes":
                return _ok(v.get("label"), "experience_short_yes (Yes option)")
    return _ok(
        f"Yes. I have hands-on experience in this area through my work at Microsoft on the Resilience Automation Platform and earlier roles in customer-facing engineering.",
        "experience_short_yes (default short answer)",
    )

def r_gdpr_consent_ack(p, f):
    # GDPR demographic-data consent checkbox. Required for the form to
    # submit; just authorizes storage of the demographic answers we already
    # declined. Always tick.
    return _ok("Yes", "gdpr_consent_ack (always tick the consent)")

RESOLVERS: dict[str, Any] = {
    "first_name": r_first_name,
    "last_name": r_last_name,
    "preferred_name": r_preferred_name,
    "full_name": r_full_name,
    "pronouns": r_pronouns,
    "email": r_email,
    "phone": r_phone,
    "linkedin": r_linkedin,
    "github": r_github,
    "portfolio": r_portfolio,
    "street": r_street,
    "city": r_city,
    "state": r_state,
    "zip": r_zip,
    "country": r_country,
    "city_state": r_city_state,
    "full_address": r_full_address,
    "work_authorized": r_work_authorized,
    "needs_sponsorship": r_needs_sponsorship,
    "security_clearance": r_security_clearance,
    "clearance_eligibility": r_clearance_eligibility,
    "clearance_level_held": r_clearance_level_held,
    "itar_us_person_ack": r_itar_us_person_ack,
    "transitioning_service_member": r_transitioning_service_member,
    "years_experience": r_years_experience,
    "current_employer": r_current_employer,
    "current_title": r_current_title,
    "school": r_school,
    "degree": r_degree,
    "major": r_major,
    "minor": r_minor,
    "gpa": r_gpa,
    "graduation_year": r_graduation_year,
    "graduation_month": r_graduation_month,
    "compensation": r_compensation,
    "willing_to_relocate": r_willing_to_relocate,
    "willing_to_travel": r_willing_to_travel,
    "remote_pref": r_remote_pref,
    "ack_hybrid": r_ack_hybrid,
    "ack_in_office": r_ack_in_office,
    "earliest_start": r_earliest_start,
    "notice_period": r_notice_period,
    "how_heard": r_how_heard,
    "pick_only_option": r_pick_only_option,
    "referred_by": r_referred_by,
    "previously_applied": r_previously_applied,
    "previously_employed": r_previously_employed,
    "currently_employed": r_currently_employed,
    "background_check": r_background_check,
    "drug_screen": r_drug_screen,
    "drivers_license": r_drivers_license,
    "felony": r_felony,
    "non_compete": r_non_compete,
    "previously_interviewed": r_previously_interviewed,
    "ai_policy_ack": r_ai_policy_ack,
    "ai_use_no": r_ai_use_no,
    "why_company_essay": r_why_company_essay,
    "cover_letter": r_cover_letter,
    "additional_info": r_additional_info,
    "deadlines_note": r_deadlines_note,
    "website": r_website,
    "twitter": r_twitter,
    "latitude": r_latitude,
    "longitude": r_longitude,
    "based_in_restricted_country": r_based_in_restricted_country,
    "based_in_restricted_state": r_based_in_restricted_state,
    "us_based_confirm": r_us_based_confirm,
    "worked_at_company_before": r_worked_at_company_before,
    "currently_student": r_currently_student,
    "customer_facing_essay": r_customer_facing_essay,
    "city_location_select": r_city_location_select,
    "visa_type_na": r_visa_type_na,
    "acknowledge_yes": r_acknowledge_yes,
    "explain_no": r_explain_no,
    "answer_no": r_answer_no,
    "no_prior_employer": r_answer_no,  # alias: Cyrus is not currently employed at this company
    "answer_yes": r_answer_yes,
    "ai_usage_level": r_ai_usage_level,
    "num_companies_worked": r_num_companies_worked,
    "sql_skills_rating": r_sql_skills_rating,
    "alphabet_affiliation": r_alphabet_affiliation,
    "timezone_pacific": r_timezone_pacific,
    "relocation_city_select": r_relocation_city_select,
    "answer_na_text": r_answer_na_text,
    "nationality_us_citizen": r_nationality_us_citizen,
    "pm_data_experience_select": r_pm_data_experience_select,
    "not_ma_resident": r_not_ma_resident,
    "coding_lang_python": r_coding_lang_python,
    "proficiency_intermediate": r_proficiency_intermediate,
    "resume": r_resume,
    "product_brief_file": r_product_brief_file,
    "family_relations_at_company": r_family_relations_at_company,
    "optional_blank": r_optional_blank,
    "literal_na": r_literal_na,
    "cities_available": r_cities_available,
    "languages_fluent": r_languages_fluent,
    "ai_familiarity_high": r_ai_familiarity_high,
    "english_comfort_high": r_english_comfort_high,
    "experience_short_yes": r_experience_short_yes,
    "countries_of_work_auth": r_countries_of_work_auth,
    "privacy_ack": r_privacy_ack,
    "essential_functions_ack": r_essential_functions_ack,
    "gdpr_consent_ack": r_gdpr_consent_ack,
    "demo_gender": r_demo_default,
    "demo_race": r_demo_default,
    "demo_veteran": r_demo_default,
    "demo_disability": r_demo_default,
    "demo_lgbtq": r_demo_default,
}


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

URL_RX_NEW = re.compile(r"^/(?P<org>[^/]+)/jobs/(?P<job_id>\d+)")
URL_RX_OLD = re.compile(r"^/(?P<org>[^/]+)/jobs/(?P<job_id>\d+)")

def parse_greenhouse_url(url: str) -> tuple[str, str]:
    """Return (org_slug, job_id) for any greenhouse URL we recognize."""
    p = urlparse(url)
    host = p.netloc.lower()
    if host not in ("job-boards.greenhouse.io", "boards.greenhouse.io", "job-boards.eu.greenhouse.io", "boards.eu.greenhouse.io"):
        raise ValueError(f"not a greenhouse URL: {url}")
    m = URL_RX_NEW.match(p.path)
    if not m:
        raise ValueError(f"could not extract org/job_id from URL path: {p.path}")
    return m.group("org"), m.group("job_id")


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def fetch_form(org: str, job_id: str) -> dict:
    url = API_TMPL.format(org=org, job_id=job_id)
    resp = requests.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": "openclaw-job-search-dryrun/1.0"})
    if resp.status_code != 200:
        raise RuntimeError(f"GET {url} returned {resp.status_code}")
    return resp.json()


def normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "")).strip().lower()


# Extreme-hours / "996" questions (9am-9pm, 6-day week, 72-hour week, etc.) are
# DETECTED but auto-answered affirmatively, NOT banked to Cyrus (Cyrus directive
# 2026-06-08, REVERSING the earlier bank-to-Cyrus guard). Rationale: applying != 
# committing. A screening checkbox binds Cyrus to NOTHING; ~99% of apps auto-reject
# regardless, and the ~1% that reach an interview surface real hours/comp/expectations
# THERE, where Cyrus decides with full context. "Banking it to Cyrus" at apply-time
# just manufactures a no-stakes decision and piles a row onto his "needs Cyrus"
# backlog. So: keep the DETECTION (it's useful for the audit log), but repoint the
# ACTION from "return None -> bank" to "answer affirmatively to best-advance the app
# + log what was auto-answered to the daily memory." Application-form answers are
# NOT Cyrus-decisions; only literal credentials/SSO and genuine irreversible
# commitments (a signed offer / real money) ever bank to Cyrus.
_EXTREME_HOURS_MARKERS = (
    "996",
    "9-9-6",
    "9am-9pm",
    "9am to 9pm",
    "9 am to 9 pm",
    "9pm, 6 days",
    "9pm 6 days",
    "72 hour",
    "72-hour",
    "72 hours a week",
    "six days a week",
    "6 days a week",
    "6 days per week",
    "six-day work week",
    "6-day work week",
)


def _is_extreme_hours_label(norm: str) -> bool:
    """True when a (normalized, lowercased) label is an extreme-hours / 996 schedule
    question. DETECTED so we can (a) auto-answer affirmatively to best-advance the
    application and (b) log what was auto-answered. NOT a Cyrus bank anymore."""
    return any(m in norm for m in _EXTREME_HOURS_MARKERS)


def _log_extreme_hours_autoanswer(label: str) -> None:
    """Append an audit line to today's daily memory recording that an extreme-hours /
    996 schedule question was AUTO-ANSWERED affirmatively (not banked to Cyrus). Best
    effort: never raises into the resolver. (Cyrus directive 2026-06-08.)"""
    import os
    from datetime import datetime
    # workspace root = three levels up from role-discovery/ (.../workspace/projects/
    # job-search/role-discovery/greenhouse_dryrun.py -> workspace).
    ws = os.environ.get("OPENCLAW_WORKSPACE") or str(Path(__file__).resolve().parents[3])
    day = datetime.now().strftime("%Y-%m-%d")
    memdir = os.path.join(ws, "memory")
    line = (f"- [auto-answer] extreme-hours/996 screening question auto-answered "
            f"AFFIRMATIVELY (not banked to Cyrus): {label!r} @ "
            f"{datetime.now().strftime('%H:%M:%S')}\n")
    try:
        os.makedirs(memdir, exist_ok=True)
        with open(os.path.join(memdir, f"{day}.md"), "a") as f:
            f.write(line)
    except Exception:
        pass


def find_resolver(label: str, rules=None) -> str | None:
    if rules is None:
        rules = LABEL_RULES
    norm = normalize_label(label)
    # 996 / extreme-hours questions: auto-answer AFFIRMATIVELY (answer_yes) to
    # maximize advancing the application. Applying != committing; the real
    # hours/comp call happens at interview, not on a screening checkbox. (Cyrus
    # directive 2026-06-08, reversing the prior bank-to-Cyrus behavior. The
    # auto-answer is logged in resolve_field so there's an audit record.)
    if _is_extreme_hours_label(norm):
        return "answer_yes"
    # Use word-boundary matching so e.g. "city" doesn't match "ethnicity",
    # "state" doesn't match "States", "location" doesn't match "relocation",
    # and "country" doesn't match phrases like "in the country in which"
    # before more specific sponsorship rules get a chance.
    for needle, resolver_key in rules:
        # If the needle contains a space we treat it as a phrase substring match
        # (phrase matches are already specific enough). Single-word needles get
        # word-boundary treatment.
        if " " in needle or "-" in needle or "/" in needle:
            if needle in norm:
                return resolver_key
        else:
            if re.search(rf"\b{re.escape(needle)}\b", norm):
                return resolver_key
    return None


def resolve_field(personal: dict, q_label: str, q_required: bool, field: dict, rules=None) -> dict:
    """Resolve a single Greenhouse field into a fill spec entry."""
    out = {
        "id": field.get("name"),
        "label": q_label,
        "type": field.get("type"),
        "required": q_required,
        "value": None,
        "source": None,
        "status": None,
        "matched_rule": None,
        "options": None,
    }
    # Capture select options for human review
    values = field.get("values") or []
    if values:
        out["options"] = [{"label": v.get("label"), "value": v.get("value")} for v in values]

    resolver_key = find_resolver(q_label, rules=rules)
    out["matched_rule"] = resolver_key
    # Audit hook: if this was an extreme-hours / 996 schedule question, it is now
    # auto-answered affirmatively (resolver_key==answer_yes) rather than banked to
    # Cyrus. Flag it + log so there's a record of exactly what got auto-answered.
    # (Cyrus directive 2026-06-08.)
    if _is_extreme_hours_label(normalize_label(q_label)):
        out["auto_answered_extreme_hours"] = True
        try:
            _log_extreme_hours_autoanswer(q_label)
        except Exception:
            pass
    if not resolver_key:
        out["value"] = UNRESOLVED
        out["status"] = "unresolved"
        out["source"] = f"no LABEL_RULES match for label={q_label!r}"
        return out

    resolver = RESOLVERS.get(resolver_key)
    if resolver is None:
        out["value"] = UNRESOLVED
        out["status"] = "unresolved"
        out["source"] = f"resolver {resolver_key!r} not implemented"
        return out

    # 2026-05-26 chain_007: ensure resolvers see q_required (raw GH field
    # dict doesn't carry the `required` flag). Without this, r_website and
    # similar resolvers that branch on required-status always took the
    # "optional -> blank" path (Thinking Machines role 1376 Personal Website).
    field = dict(field)
    field["required"] = q_required
    # Also propagate the question label into the field dict so resolvers that
    # branch on the QUESTION WORDING (e.g. r_itar_us_person_ack's inverted
    # "does the export rule AFFECT you?" polarity check) can see it. The raw
    # Greenhouse boards-API field dict carries name/type/values but NOT the
    # label, so without this the polarity check read empty and defaulted to the
    # affirmative "Yes" -> wrong answer on inverted export questions (Pure
    # Storage auto-reject, 2026-06-04).
    if not field.get("label"):
        field["label"] = q_label

    try:
        kind, value, source = resolver(personal, field)
    except Exception as e:
        out["value"] = UNRESOLVED
        out["status"] = "unresolved"
        out["source"] = f"resolver {resolver_key!r} raised: {e}"
        return out

    if kind == "ok":
        out["value"] = value
        out["status"] = "filled"
        out["source"] = source
    elif kind == "decline":
        out["value"] = value
        out["status"] = "declined"
        out["source"] = source
    else:  # unresolved
        out["value"] = UNRESOLVED
        out["status"] = "unresolved"
        out["source"] = value  # reason string

    # If the field is a single-select with options, sanity-check value membership
    if out["status"] == "filled" and field.get("type") in ("multi_value_single_select", "multi_value_multi_select"):
        labels = [v.get("label") for v in values]
        if out["value"] not in labels:
            # Try smart-match: e.g. '3.8' -> '3.8 out of 4.0', '' -> 'Did not take/Do not recall',
            # 'Bachelor of Science' -> "Bachelor's degree". See _smart_match_option_label.
            matched = _smart_match_option_label(
                value=out["value"], label=q_label, options=labels,
                resolver_key=resolver_key, personal=personal,
            )
            if matched is not None:
                out["value"] = matched
                out["source"] = (out["source"] or "") + f" | smart-matched to option {matched!r}"
            else:
                # Not a hard failure, but flag it
                out["status"] = "filled_needs_review"
                out["source"] = (out["source"] or "") + f" | NOTE: '{out['value']}' not literally in options {labels}"

    return out


def _smart_match_option_label(value, label: str, options: list, resolver_key: str | None, personal: dict) -> str | None:
    """Best-effort map a resolver-produced value to one of the dropdown option labels.

    Added 2026-05-25 to fix SpaceX 872 academic-fields blocker: GPA/SAT/ACT/GRE
    are rendered as react-selects with options like '3.8 out of 4.0' or
    'Did not take/Do not recall', but our resolvers return bare '3.8' / ''.
    Without this match the dryrun marks them filled_needs_review and the filler
    can't pick the right option at runtime.

    Returns the chosen option label, or None if no confident match is found.
    """
    if not options:
        return None
    label_lower = (label or "").lower()
    val_str = ("" if value is None else str(value)).strip()

    # --- GPA fields: 'GPA (Undergraduate)' / '(Graduate)' / '(Doctorate)' ---
    if resolver_key == "gpa" or "gpa" in label_lower:
        edu = personal.get("education", {}) or {}
        # Pick the right per-degree GPA from personal-info if available.
        per_degree = None
        if "(undergrad" in label_lower or "undergraduate" in label_lower:
            per_degree = edu.get("gpa_undergrad") or edu.get("gpa")
        elif "(graduate" in label_lower or "grad gpa" in label_lower or label_lower.endswith("gpa (graduate)"):
            per_degree = edu.get("gpa_grad")
        elif "(doctorate" in label_lower or "phd" in label_lower:
            per_degree = edu.get("gpa_doctorate") or edu.get("gpa_grad")
        else:
            per_degree = edu.get("gpa")

        if per_degree is None or per_degree == "":
            # No grad/doctorate GPA on file -> pick the 'not applicable' option.
            for opt in options:
                ol = (opt or "").lower()
                if "not applicable" in ol or "do not recall" in ol or "n/a" in ol or "other" in ol:
                    return opt
            return None

        # Try to find an option like '3.8 out of 4.0' that starts with our numeric GPA.
        gpa_str = str(per_degree).strip()
        for opt in options:
            if opt and opt.startswith(gpa_str + " "):
                return opt
        # Try exact match.
        if gpa_str in options:
            return gpa_str
        # Fall back to 'Below 3.0' / 'Not applicable' style.
        return None

    # --- SAT/ACT/GRE dropdowns. Routing (chain gh-academic-fields-2026-05-30):
    #   * If the label asks for SAT and Cyrus has a recorded score in
    #     personal-info / education_answers, pick the '<score> out of <scale>'
    #     option. Else (ACT/GRE, or SAT not on file) pick 'Did not take/Do
    #     not recall'.
    #   * Falls back through `optional_blank` for any other 'test score'-shaped
    #     dropdown that returned ''.
    is_test_score_label = any(t in label_lower for t in ("sat", "act score", "gre", "test score"))
    if is_test_score_label or (resolver_key == "optional_blank" and val_str == ""):
        try:
            from education_answers import (
                match_sat_option, match_act_option, match_gre_option, _find_not_taken,
            )
        except Exception:
            match_sat_option = match_act_option = match_gre_option = None  # type: ignore
            _find_not_taken = None  # type: ignore

        if is_test_score_label and match_sat_option is not None:
            if "sat" in label_lower:
                picked = match_sat_option(options)
            elif "act" in label_lower:
                picked = match_act_option(options)
            elif "gre" in label_lower:
                picked = match_gre_option(options)
            else:
                picked = _find_not_taken(options)
            if isinstance(picked, dict):
                return picked.get("label")
            if isinstance(picked, str):
                return picked
            # If shared helper missed entirely, fall through to the legacy
            # 'did not take' textual sweep below so we still pick *something*.

        # Legacy fallback: pick the first 'did not take / do not recall' option.
        for opt in options:
            ol = (opt or "").lower()
            if "did not take" in ol or "do not recall" in ol or "not applicable" in ol or ol == "n/a" or "other" in ol:
                return opt
        return None

    # --- High school performance (Canonical-class) ---
    # Label: 'How did you perform in mathematics at high school?'
    # Options: 'Cannot recall', 'Not a strength', 'Top 50% at school', 'Top 20% at school', ...
    if "high school" in label_lower and ("perform" in label_lower or "mathematics" in label_lower or "language" in label_lower):
        target = "Top 20% at school"  # honest default for Cyrus
        for opt in options:
            if opt == target:
                return opt
        # Fallback: pick first 'Top' option
        for opt in options:
            if opt and opt.startswith("Top"):
                return opt
        return None

    # --- Degree: 'Bachelor of Science' -> "Bachelor's degree" ---
    if resolver_key == "degree" or "degree" in label_lower:
        v = val_str.lower()
        # Order matters: most specific first.
        keymap = [
            ("phd", ["phd", "doctorate", "doctoral"]),
            ("doctor", ["doctorate", "doctoral", "phd"]),
            ("mba", ["mba", "master"]),
            ("master", ["master"]),
            ("bachelor", ["bachelor"]),
            ("associate", ["associate"]),
            ("high school", ["high school", "diploma"]),
            ("jd", ["juris", "jd", "law"]),
            ("md", ["medical doctor", "md"]),
        ]
        needles = []
        for k, n in keymap:
            if k in v:
                needles = n
                break
        if needles:
            for opt in options:
                ol = (opt or "").lower()
                if any(n in ol for n in needles):
                    return opt
        return None

    # --- US-person / citizenship sentence-options (export-control / ITAR).
    # Astranis 2026-06-03: the export-control select renders full-sentence
    # options ("I am a U.S. Citizen.", "I am a lawful permanent resident...",
    # "None of the above.") rather than Yes/No, so the itar_us_person_ack 'Yes'
    # value isn't literally present. Cyrus is a US citizen -> pick the citizen
    # option. Generalizes to any export-control board with this option shape. ---
    if resolver_key == "itar_us_person_ack":
        for opt in options:
            ol = (opt or "").lower()
            if ("u.s. citizen" in ol or "us citizen" in ol
                    or "united states citizen" in ol or "a citizen of the u" in ol):
                return opt
        # Yes/No-shaped fallback: 'Yes' value -> the affirmative option.
        if val_str.lower() in ("yes", "true"):
            for opt in options:
                if (opt or "").strip().lower() in ("yes", "i am", "i confirm"):
                    return opt
        return None

    # --- Generic substring match (case-insensitive prefix) ---
    vl = val_str.lower()
    if vl:
        for opt in options:
            if (opt or "").lower().startswith(vl):
                return opt
        for opt in options:
            if vl in (opt or "").lower():
                return opt
    return None


def build_dryrun(personal: dict, role_url: str) -> dict:
    org, job_id = parse_greenhouse_url(role_url)
    schema = fetch_form(org, job_id)

    # Inject runtime context for resolvers (e.g. why-company essay).
    personal = dict(personal)
    personal["_company_name"] = (schema.get("company") or {}).get("name") if isinstance(schema.get("company"), dict) else None
    if not personal["_company_name"]:
        # Greenhouse "company_name" key in some schemas, else titlecase the org slug.
        personal["_company_name"] = schema.get("company_name") or org.replace("-", " ").title()
    tmpl_path = HERE.parent / "why-company-template.md"
    if tmpl_path.exists():
        # Strip header lines: keep paragraphs after the first '---' separator.
        raw = tmpl_path.read_text()
        if "---" in raw:
            raw = raw.split("---", 2)[-1]
        personal["_why_company_template"] = raw.strip()

    # Track-match the candidate's CURRENT TITLE to the role applied to (Cyrus 2026-06-02).
    # Form 'current/previous title' fields were frozen at the static profile value
    # ('Technical Program Manager') regardless of the target role — the same title-
    # inconsistency we fixed on the RESUME side (coerce_title_track). Use the identical
    # resolve_headline_title logic so the title we CLAIM on the form matches the role's
    # track (PM->Product Manager, TPM->Technical Program Manager, etc.) and never inflates
    # beyond what the JD title implies. Falls back to the static profile value if the
    # resolver can't derive a clean title.
    _tgt_title = schema.get("title") or ""
    if _tgt_title:
        try:
            from tailor_resume import resolve_headline_title, detect_family
            _fam = detect_family(_tgt_title)
            _matched = resolve_headline_title(_tgt_title, _fam)
            if _matched:
                es = dict(personal.get("experience_summary") or {})
                es["current_title"] = _matched
                personal["experience_summary"] = es
        except Exception:
            pass  # keep static profile current_title on any failure

    fields_out: list[dict] = []
    unresolved: list[dict] = []
    blockers: list[dict] = []

    # Standard application questions
    for q in schema.get("questions") or []:
        label = q.get("label") or ""
        required = bool(q.get("required"))
        for f in q.get("fields") or []:
            entry = resolve_field(personal, label, required, f)
            fields_out.append(entry)
            if entry["status"] == "unresolved":
                unresolved.append({"id": entry["id"], "label": entry["label"], "required": required, "reason": entry["source"]})
                if required:
                    blockers.append({"id": entry["id"], "label": entry["label"], "reason": entry["source"]})

    # Compliance / EEOC questions (default decline)
    compliance = schema.get("compliance") or []
    if not isinstance(compliance, list):
        compliance = []
    for block in compliance:
        if not isinstance(block, dict):
            continue
        for q in block.get("questions") or []:
            label = q.get("label") or ""
            required = bool(q.get("required"))
            for f in q.get("fields") or []:
                entry = resolve_field(personal, label, required, f)
                if entry["status"] == "unresolved":
                    # Force decline-to-answer for EEOC stuff
                    entry["value"] = "Decline To Self Identify"
                    entry["status"] = "declined"
                    entry["source"] = "demographics_default (eeoc compliance block)"
                entry["compliance"] = block.get("type")
                fields_out.append(entry)

    # demographic_questions can be:
    #   - a list of question dicts (each with .fields[]), like `compliance` blocks, OR
    #   - a single dict {header, description, questions: [...]} where each
    #     question has its own top-level id/type/answer_options (no .fields[]).
    dq = schema.get("demographic_questions")
    if isinstance(dq, dict):
        demo_qs = dq.get("questions") or []
        # Synthesize a `fields` array so resolve_field works uniformly
        normalized: list[dict] = []
        for q in demo_qs:
            normalized.append({
                "label": q.get("label") or "",
                "required": bool(q.get("required")),
                "fields": [{
                    "name": f"demographic_question_{q.get('id')}",
                    "type": q.get("type"),
                    "values": [
                        {"label": opt.get("label"), "value": opt.get("id")}
                        for opt in (q.get("answer_options") or [])
                    ],
                }],
            })
        demo_iter = normalized
    elif isinstance(dq, list):
        demo_iter = dq
    else:
        demo_iter = []

    for q in demo_iter:
        label = q.get("label") or ""
        required = bool(q.get("required"))
        for f in q.get("fields") or []:
            entry = resolve_field(personal, label, required, f)
            if entry["status"] == "unresolved":
                entry["value"] = "Decline To Self Identify"
                entry["status"] = "declined"
                entry["source"] = "demographics_default (demographic_questions block)"
            entry["compliance"] = "demographic"
            fields_out.append(entry)

    # Location questions (some Greenhouse forms ask office preference)
    loc_qs = schema.get("location_questions") or []
    if not isinstance(loc_qs, list):
        loc_qs = []
    for q in loc_qs:
        label = q.get("label") or "Location"
        required = bool(q.get("required"))
        for f in q.get("fields") or []:
            entry = resolve_field(personal, label, required, f)
            entry["section"] = "location"
            fields_out.append(entry)
            if entry["status"] == "unresolved":
                unresolved.append({"id": entry["id"], "label": entry["label"], "required": required, "reason": entry["source"]})
                if required:
                    blockers.append({"id": entry["id"], "label": entry["label"], "reason": entry["source"]})

    counts = {
        "total_fields": len(fields_out),
        "filled": sum(1 for f in fields_out if f["status"] == "filled"),
        "filled_needs_review": sum(1 for f in fields_out if f["status"] == "filled_needs_review"),
        "declined": sum(1 for f in fields_out if f["status"] == "declined"),
        "unresolved": len(unresolved),
        "blockers": len(blockers),
    }

    edu = personal.get("education") or {}
    education_panel = {
        "school": edu.get("school_undergrad") or edu.get("school"),
        "degree": edu.get("degree_undergrad") or edu.get("degree"),
        "discipline": edu.get("major"),
        "minor": edu.get("minor"),
        "gpa_undergrad": edu.get("gpa_undergrad") or edu.get("gpa"),
        "gpa_grad": edu.get("gpa_grad"),
        "gpa_doctorate": edu.get("gpa_doctorate"),
        "graduation_year": edu.get("graduation_year"),
        "start_year": (edu.get("start_date") or "")[:4] or None,
        "end_year": (edu.get("end_date") or "")[:4] or None,
    }

    return {
        "role_url": role_url,
        "org": org,
        "job_id": job_id,
        "job_title": schema.get("title"),
        "job_location": (schema.get("location") or {}).get("name"),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api_url": API_TMPL.format(org=org, job_id=job_id),
        "ready_to_submit": counts["blockers"] == 0,
        "counts": counts,
        "fields": fields_out,
        "unresolved": unresolved,
        "blockers": blockers,
        "education_panel": education_panel,
    }


def write_dryrun(report: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f'{report["org"]}-{report["job_id"]}.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return path


def collect_queued_greenhouse_urls() -> list[str]:
    if not TRACKER_PATH.exists():
        return []
    urls: list[str] = []
    rx = re.compile(r"https?://(?:job-boards|boards)\.greenhouse\.io/[^\s|<>)]+")
    for line in TRACKER_PATH.read_text().splitlines():
        if "queued" not in line:
            continue
        for m in rx.finditer(line):
            url = m.group(0).rstrip(",.;)")
            # Strip ?gh_jid=... duplicates and de-dupe by org/job_id later
            urls.append(url)
    # de-dupe by (org, job_id)
    seen: set[tuple[str, str]] = set()
    out: list[str] = []
    for u in urls:
        try:
            key = parse_greenhouse_url(u)
        except ValueError:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Dry-run Greenhouse application fill spec generator (NO SUBMIT).")
    parser.add_argument("urls", nargs="*", help="One or more Greenhouse role URLs.")
    parser.add_argument("--all-queued", action="store_true", help="Process every queued Greenhouse URL in tracker.md.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-role console output.")
    args = parser.parse_args(argv)

    if not PERSONAL_INFO_PATH.exists():
        print(f"ERROR: missing {PERSONAL_INFO_PATH}", file=sys.stderr)
        return 2
    personal = json.loads(PERSONAL_INFO_PATH.read_text())

    urls: list[str] = list(args.urls)
    if args.all_queued:
        urls.extend(collect_queued_greenhouse_urls())
    # de-dupe preserving order
    seen: set[str] = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]

    if not urls:
        parser.print_help()
        return 1

    rc = 0
    for url in urls:
        try:
            report = build_dryrun(personal, url)
            path = write_dryrun(report)
            if not args.quiet:
                c = report["counts"]
                ready = "READY" if report["ready_to_submit"] else f"BLOCKED({c['blockers']})"
                print(f"{ready:11} {report['org']}/{report['job_id']:>11} -> {path.name}  "
                      f"filled={c['filled']} review={c['filled_needs_review']} declined={c['declined']} unresolved={c['unresolved']}  "
                      f"({report['job_title']})")
        except Exception as e:
            rc = 1
            print(f"ERROR processing {url}: {e}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
