#!/usr/bin/env python3
"""
ashby_dryrun.py — Generate a NO-SUBMIT, dry-run application fill spec
for an Ashby-hosted role.

Mirrors greenhouse_dryrun.py's output shape so that the same downstream
machinery (cover_answer_generator, build_dryrun_xlsx, inline_submit's
plan-merging) works unmodified.

Source-of-truth API:
  POST https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting
  GraphQL: ApiJobPosting(organizationHostedJobsPageName, jobPostingId)
  -> { jobPosting { applicationForm { sections { fieldEntries { id field ... } } } } }

ZERO writes. Read-only. No POSTs to ANY /apply or /submit endpoint.

Usage:
    .venv/bin/python ashby_dryrun.py <ashby_url> [<url2> ...]
    .venv/bin/python ashby_dryrun.py --org openai --job-id <uuid>
    .venv/bin/python ashby_dryrun.py --quiet ...

Output:
    ../applications/dryrun/{org}-{job_id}.json     (job_id is the Ashby UUID)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# Reuse Greenhouse dryrun's resolver/rules — they're ATS-agnostic.
import greenhouse_dryrun as gh  # noqa: E402

# Ashby-specific LABEL_RULES augmentation. We splice these into gh.LABEL_RULES
# at module load so resolve_field picks them up. Order matters: more specific
# patterns should land BEFORE generic ones ("location", "start").
# Keys reuse existing GH resolvers from gh.RESOLVERS where possible; new
# resolver keys are registered below.
_ASHBY_EXTRA_RULES = [
    # --- POSITIVE work-auth phrasing that the bare GH ("sponsorship") rule
    # mis-resolves to a knockout "No" (Curri 2557, 2026-06-10). The question
    # "Are you legally authorized to work in the US WITHOUT employer
    # sponsorship?" is POSITIVE: a US citizen answers YES (he needs no
    # sponsorship). But _ASHBY_COMBINED_RULES is first-match-wins and the GH
    # base list has a bare ("sponsorship" -> needs_sponsorship) rule that fires
    # FIRST on the substring "sponsorship", producing the wrong "No" (a
    # factual knockout). These rules sit at the TOP of the Ashby-first list so
    # the positive phrasing wins. Routes to work_authorized -> truthful Yes
    # (work_authorization.status == us_citizen). Distinct from the
    # needs_sponsorship phrasings ("do you REQUIRE sponsorship?") which stay No.
    ("authorized to work in the united states without employer sponsorship", "work_authorized"),
    ("authorized to work in the us without employer sponsorship", "work_authorized"),
    ("authorized to work in the u.s without employer sponsorship", "work_authorized"),
    ("authorized to work without employer sponsorship", "work_authorized"),
    ("authorized to work without sponsorship", "work_authorized"),
    ("authorized to work without requiring sponsorship", "work_authorized"),
    ("authorized to work without needing sponsorship", "work_authorized"),
    ("eligible to work without sponsorship", "work_authorized"),
    ("legally authorized to work without", "work_authorized"),
    ("work without requiring sponsorship", "work_authorized"),
    ("work without needing sponsorship", "work_authorized"),
    # --- "Do you have N+ years of <X> experience?" rendered as a YES/NO radio
    # (Knowtex 2593, 2026-06-10). The generic years_experience resolver returns
    # the NUMERIC count (e.g. "2"), which is a valid answer for a free-text
    # "how many years" field but is NOT one of a Yes/No radio's options -> the
    # "2" lands as the radio value and the option never gets selected (form
    # banks the field). For a yes/no-phrased experience question, answer YES
    # (Cyrus exceeds the typical 2-5yr bar; this is the same fix GH already has
    # via ("do you have 2+ years" -> answer_yes) for Comet 1233). These sit
    # above the GH years_experience rules so the yes/no phrasing wins. Truthful:
    # only fires on "do you have N+ years" affirmative-bar phrasing, NOT on
    # "how many years" (which still routes to the numeric years_experience).
    ("do you have 1+ year", "answer_yes"),
    ("do you have 2+ years", "answer_yes"),
    ("do you have 3+ years", "answer_yes"),
    ("do you have 4+ years", "answer_yes"),
    ("do you have 5+ years", "answer_yes"),
    ("do you have at least 1 year", "answer_yes"),
    ("do you have at least 2 years", "answer_yes"),
    ("do you have at least 3 years", "answer_yes"),
    ("do you have at least 4 years", "answer_yes"),
    ("do you have at least 5 years", "answer_yes"),
    ("do you have 2 or more years", "answer_yes"),
    ("do you have 3 or more years", "answer_yes"),
    ("have 2+ years of experience in this role", "answer_yes"),
    # --- Multi-office "which of our primary locations are you interested in?"
    # picker (Profound 2844, 2026-06-04). A REQUIRED single-select listing the
    # company's offices. US onsite is never a knockout, so pick the first
    # concrete US office. Distinct from yes/no location_ack asks. ---
    ("which of our primary locations", "primary_location_pick"),
    ("primary locations are you interested", "primary_location_pick"),
    ("which location are you interested", "primary_location_pick"),
    ("which office are you interested", "primary_location_pick"),
    # Distyl-class: "Which location would you be able to work from or relocate to?"
    ("which location would you be able to work from or relocate", "primary_location_pick"),
    ("work from or relocate to", "primary_location_pick"),
    ("able to work from or relocate", "primary_location_pick"),
    # EliseAI 2453 (2026-06-06): "What office(s) are you applying to? If
    # interested in multiple, please select those that apply." -> multi-select
    # office picker. Options are US metros (Boston/NYC/SF) + Toronto; pick first
    # US office. Same class as primary-locations picker (US onsite never a KO).
    ("what office(s) are you applying", "primary_location_pick"),
    ("what office are you applying", "primary_location_pick"),
    ("which office(s) are you applying", "primary_location_pick"),
    # --- Combined social-link field (Basis 1301, 2026-06-03): a single
    # "LinkedIn /Twitter/Website/Github" required field was matching the
    # `twitter` rule first -> unresolved (Cyrus has no Twitter). LinkedIn
    # satisfies it; route combined social fields to the linkedin resolver
    # (truthful, always available). Must precede any twitter/website rule. ---
    ("linkedin /twitter", "linkedin"),
    ("linkedin/twitter", "linkedin"),
    ("linkedin / twitter", "linkedin"),
    ("twitter/website/github", "linkedin"),
    ("linkedin, twitter", "linkedin"),
    # Abundant 2960 (2026-06-16): "Linked In Profile" has a space -> 'linked in profile'
    # after normalize -> doesn't match needle 'linkedin'. Add explicit match.
    ("linked in profile", "linkedin"),
    ("linked in url", "linkedin"),
    ("linked in link", "linkedin"),
    # --- US residency confirmation (Atticus 2262, 2026-06-03): "Do you
    # currently reside in the United States?" -> Yes (Cyrus is US-based, WA).
    # Routes to us_based_confirm (yields the affirmative option). Truthful. ---
    ("currently reside in the united states", "us_based_confirm"),
    ("do you reside in the united states", "us_based_confirm"),
    ("reside in the united states", "us_based_confirm"),
    ("reside in the us", "us_based_confirm"),
    ("currently located in the united states", "us_based_confirm"),
    ("based in the united states", "us_based_confirm"),
    # --- Prior-employer-at-this-company variants Greenhouse rules miss ---
    # Snowflake 2026-05-24: "Have you worked at Snowflake in the past in a Full-time..."
    ("have you worked at", "worked_at_company_before"),
    ("worked at .* in the past", "worked_at_company_before"),  # used as substring; safe
    ("worked here in any", "worked_at_company_before"),
    ("in the past in a full-time", "worked_at_company_before"),

    # --- SEC auditor-independence question (e.g. Snowflake / PwC). Cyrus has
    # never worked at PwC -> No. Treat as never_no. ---
    ("sec auditor independence", "never_no"),
    ("auditor independence", "never_no"),
    ("independent auditor", "never_no"),
    ("pricewaterhousecoopers", "never_no"),
    ("worked at, or if currently working at", "never_no"),

    # --- Current employer variations (label rule "current employer" requires
    # adjacent tokens; "Current or Most Recent Employer" doesn't match it) ---
    ("current or most recent employer", "current_employer"),
    ("most recent employer", "current_employer"),
    ("current/most recent employer", "current_employer"),
    ("current/last company", "current_employer"),
    ("current or last company", "current_employer"),
    ("last company", "current_employer"),

    # --- US gov / clearance defaults: Cyrus has no prior gov employment
    # and no security clearance. Default to No so these stop being blockers. ---
    ("prior us government employment", "never_no"),
    ("prior u.s. government employment", "never_no"),
    ("previously employed by the us government", "never_no"),
    ("previously employed by the u.s. government", "never_no"),
    ("previously employed by the united states government", "never_no"),
    ("currently or formerly held a security clearance", "never_no"),
    ("currently or previously held a security clearance", "never_no"),
    ("do you currently hold a security clearance", "never_no"),
    ("have you ever held a security clearance", "never_no"),
    ("active security clearance", "never_no"),

    # --- Unrestricted work authorization phrasings the existing
    # `work_authorized` rule misses (US citizen -> Yes). ---
    # Blaxel 1325 2026-05-26: "Are you allowed to work in the US?" (the
    # GH rules cover "legally allowed" / "authorized" but not the bare
    # "allowed to work in the US" phrasing).
    ("allowed to work in the us", "work_authorized"),
    ("allowed to work in the u.s", "work_authorized"),

    # --- chain_033 2026-05-30 hybrid/in-office phrasing additions ---
    # Rho 1450: "Are you willing and able to work from your local office 5 days/week?"
    ("work from your local office", "ack_in_office"),
    ("local office 5 days", "ack_in_office"),
    ("willing and able to work", "ack_in_office"),
    # Authorium 1544: "Are you able to work hybrid\u00a0 from our San Francisco or Washington DC office?" (note non-breaking space)
    ("work hybrid", "ack_in_office"),
    ("able to work hybrid", "ack_in_office"),
    ("from our san francisco", "ack_in_office"),
    ("from our washington dc", "ack_in_office"),
    # EliseAI 2453 (2026-06-06): "EliseAI is an in-office company. Are you
    # comfortable working from our office around 4-5 days per week?" -> Yes
    # (US onsite never a knockout; EliseAI offices are NYC/SF/Boston US).
    ("in-office company", "ack_in_office"),
    ("comfortable working from our office", "ack_in_office"),
    ("allowed to work in the united states", "work_authorized"),
    ("unrestricted work authorization", "work_authorized"),
    ("permanent unrestricted authorization", "work_authorized"),
    ("permanent and unrestricted", "work_authorized"),
    ("able to work without restriction", "work_authorized"),
    ("work without restriction", "work_authorized"),
    ("unrestricted right to work", "work_authorized"),

    # --- Conditional visa-TYPE field (Assort Health 1545 2026-05-31).
    # "What type of visa will you require? (if applicable to above)" -> N/A
    # for US citizens (no visa needed). Truthful; see _r_visa_type_na. Must
    # land BEFORE any generic "visa"/"work_authorized" rule so the TYPE field
    # (free text) isn't mis-resolved to a Yes/No work-auth answer. ---
    ("what type of visa", "visa_type_na"),
    ("type of visa will you require", "visa_type_na"),
    ("which visa", "visa_type_na"),
    ("visa type", "visa_type_na"),

    # --- Employment verification check ("will the check come back saying you
    # are who you say you are") -> Yes. Cyrus is who he says he is. ---
    ("employment verification check", "acknowledge_yes"),
    ("employment verification", "acknowledge_yes"),

    # --- Customer-facing / client-interaction Y/N (Deepgram 971 2026-05-25).
    # Cyrus has 4+ yrs SE/SA experience -> Yes for all variants. ---
    ("role requires client interaction", "acknowledge_yes"),
    ("working with external clients", "acknowledge_yes"),
    ("open to working with external clients", "acknowledge_yes"),
    ("customer-facing role", "acknowledge_yes"),
    ("customer facing role", "acknowledge_yes"),

    # --- "Have you designed or implemented solutions ... for customers" Y/N
    # (Deepgram 971). Cyrus has done this extensively -> Yes. ---
    ("designed or implemented solutions", "acknowledge_yes"),
    ("address recurring technical challenges for customers", "acknowledge_yes"),
    ("recurring technical challenges", "acknowledge_yes"),

    # --- Coding ability self-rating: Cyrus reads/modifies code at work but
    # isn't a production engineer. Pick the middle option safely. ---
    ("coding ability", "coding_ability"),
    ("describes your coding", "coding_ability"),

    # --- Restricted countries citizen/resident: Cyrus is US citizen, no. ---
    ("current citizen, national, or resident of any of the following", "never_no"),
    ("citizen, national, or resident of any of the following countries", "never_no"),

    # --- North America / US-based location confirms ---
    ("open only to candidates based in north america", "us_based_confirm"),
    ("based in north america", "us_based_confirm"),
    ("located in this region", "us_based_confirm"),
    ("are you located within the united states", "us_based_confirm"),
    ("located within the united states", "us_based_confirm"),
    ("located in the united states", "us_based_confirm"),
    ("are you located in the san francisco bay area", "location_ack"),
    ("located in the san francisco bay area", "location_ack"),
    ("located in the bay area", "location_ack"),

    # --- City-specific commute / based-in / in-office asks ---
    # The `location_ack` resolver checks if it's a relocation-target city
    # (SF/NYC/Bay Area/Seattle) -> Yes; else -> No (Cyrus is in WA).
    ("based in boston or able to commute", "location_ack"),
    ("able to commute in", "location_ack"),
    ("able to commute to", "location_ack"),
    ("comfortable working in-person", "location_ack"),
    ("comfortable working in person", "location_ack"),
    # Generic "are you based in <city>" / "based in our <city> office". The
    # restricted-country variant ("based in any of the following countries")
    # is steered to never_no above, so this won't catch it.
    ("are you based in", "location_ack"),
    ("based in our", "location_ack"),
    # Blaxel 1325 2026-05-26: "Are you open to working full-time (5 days a
    # week) from our SF office?" — SF is a relocation target, location_ack
    # answers Yes for SF/NYC/Bay/Seattle.
    ("working full-time", "location_ack"),
    ("5 days a week", "location_ack"),
    ("five days a week", "location_ack"),
    ("from our sf office", "location_ack"),
    ("from our san francisco office", "location_ack"),
    ("open to working full-time", "location_ack"),

    # --- Payroll-tax location text field: emit "City, State" ---
    ("where do you plan on working from", "city_state"),
    ("plan on working from", "city_state"),
    ("payroll tax", "city_state"),
    # Neural Concept 1365 2026-05-26: "Your official address" -> full street
    # address (city_state alone is too sparse for a literal address field).
    ("your official address", "full_address"),
    ("official address", "full_address"),
    ("home address", "full_address"),
    ("mailing address", "full_address"),
    ("street address", "full_address"),
    # Neural Concept 1365 2026-05-26: "Social Network and Web Links" -> LinkedIn
    # (most relevant social/web link).
    ("social network and web links", "linkedin_url"),
    ("social networks and web links", "linkedin_url"),
    ("social media links", "linkedin_url"),
    # Neural Concept 1365 2026-05-26: "Are you eligible to work in the United
    # States?" -> Yes (citizen). The existing work_authorized rule covers
    # "authorized" not "eligible".
    ("eligible to work in the united states", "work_authorized"),
    ("eligible to work in the us", "work_authorized"),
    ("eligible to work in the u.s", "work_authorized"),
    # Neural Concept 1365 2026-05-26: "Do you have an Engineering background
    # (outside of software or computer science)?" -> No, Cyrus is CS/SE.
    ("engineering background (outside of software", "answer_no"),
    ("engineering background outside of software", "answer_no"),
    ("engineering background outside of computer science", "answer_no"),

    # --- LangChain 1230 2026-05-26: AI-engineering Y/N questions for SE/SA
    # roles. Cyrus has shipped agent-based / LLM apps, has strong Python+JS
    # fundamentals, and has deployed AI agents (Vega, etc.) -> Yes for all. ---
    ("strong python", "acknowledge_yes"),
    ("python, javascript and systems fundamentals", "acknowledge_yes"),
    ("python and javascript", "acknowledge_yes"),
    ("designed agent-based", "acknowledge_yes"),
    ("agent-based or llm-powered", "acknowledge_yes"),
    ("llm-powered applications", "acknowledge_yes"),
    ("deployed ai agents in production", "acknowledge_yes"),
    ("using langchain, langgraph", "acknowledge_yes"),
    ("shipped and operated production software", "acknowledge_yes"),
    ("shipped production software", "acknowledge_yes"),
    ("operated production software", "acknowledge_yes"),
    ("available to work onsite at the corporate office", "location_ack"),
    ("in the bay area or nyc metro, are you available", "location_ack"),
    ("if in the bay area", "location_ack"),
    ("willing to work on-site in our", "location_ack"),
    ("work on-site in our san francisco or nyc", "location_ack"),
    ("willing to work onsite in our", "location_ack"),

    # --- Timezone the candidate lives in (AVIDA 1004 2026-05-26).
    # Cyrus is in Kirkland WA -> Pacific. Resolver handles 'Pacific Time Zone (PST): UTC-8.'
    # phrasing as well as bare 'PST'/'Pacific'. ---
    # "are you currently based in EST or PST?" / "currently in PST/EST" (Deepgram 2026-06-18)
    ("currently based in est or pst", "us_timezone"),
    ("currently based in pst or est", "us_timezone"),
    ("currently in est or pst", "us_timezone"),
    ("currently in pst or est", "us_timezone"),
    # Deepgram 2998/2999 (2026-06-18): Yes/No "based within EST or PST" — Cyrus = Pacific = Yes
    ("based within either eastern or pacific time", "answer_yes"),
    ("located within eastern or pacific time", "answer_yes"),
    ("located within either eastern or pacific time", "answer_yes"),
    ("based within eastern or pacific time", "answer_yes"),
    ("eastern or pacific time in the united states", "answer_yes"),
    ("which timezone do you live in", "us_timezone"),
    ("which time zone do you live in", "us_timezone"),
    ("what timezone do you live in", "us_timezone"),
    ("what time zone do you live in", "us_timezone"),
    ("what timezone are you in", "us_timezone"),
    ("what time zone are you in", "us_timezone"),
    ("your timezone", "us_timezone"),
    ("your time zone", "us_timezone"),
    ("timezone do you live", "us_timezone"),
    ("time zone do you live", "us_timezone"),

    # "earliest month you'd be able to join" / "when could you start" -> earliest_start
    ("earliest month", "earliest_start"),
    ("month you would join", "earliest_start"),
    ("month you could join", "earliest_start"),
    ("month you'd join", "earliest_start"),
    # "based in <city> or open to relocating" -> SF/NY/etc willingness; we say Yes via relocate
    ("based in san francisco or open to relocat", "willing_to_relocate"),
    ("based in new york or open to relocat", "willing_to_relocate"),
    ("or open to relocating", "willing_to_relocate"),
    ("would you be open to relocating", "location_ack"),
    ("open to relocating to one of our offices", "location_ack"),
    ("office-first", "location_ack"),
    ("office first", "location_ack"),
    # "are you able to work from <city>" / "work from our X office" -> in-office ack
    ("are you able to work from", "ack_in_office"),
    ("work out of our", "ack_in_office"),
    ("work from our", "ack_in_office"),
    ("in-office", "ack_in_office"),
    ("in office", "ack_in_office"),
    ("in person", "ack_in_office"),

    # --- Rogo 1392/1393 2026-05-26: "Are you able, willing, and excited to
    # work full-time in an office?" Cyrus is open to in-office hybrid -> Yes. ---
    ("willing, and excited to work full-time in an office", "ack_in_office"),
    ("willing and excited to work full-time in an office", "ack_in_office"),
    ("excited to work full-time in an office", "ack_in_office"),
    ("work full-time in an office", "ack_in_office"),
    ("work full time in an office", "ack_in_office"),
    ("able, willing, and excited", "ack_in_office"),
    # ============================================================
    # PORTED FROM greenhouse_dryrun (2026-06-04): proven GH resolvers that
    # were reachable in theory (Ashby splices into gh.LABEL_RULES) but whose
    # phrasings were instead being grabbed by the old city-gated location_ack
    # or had no Ashby rule at all -> valid questions banked at PREP time.
    # Confirmed banks: Plaud 2731 + Vendelux 2774 (us-onsite), Helion 2712
    # (prior-employer), Dash0 2757 (proficiency / work-arrangement dropdowns).
    #
    # All TRUTHFUL: US onsite/relocation Yes is Cyrus policy (relocates
    # anywhere in the USA); proficiency Intermediate is honest (TPM/PM, not a
    # specialist); prior-employer is biographical fact. NOTHING here touches
    # clearance/citizenship/work-auth (those stay truthful, untouched).
    #
    # These are inserted at the FRONT of gh.LABEL_RULES (reversed-splice
    # below), so specific phrasings here win over generic GH country/state
    # rules — mirroring the export-regulations precedence lesson in TOOLS.md.
    # ---- US onsite / based-in / commute / in-person -> answer_yes ----
    ("based in the u.s", "answer_yes"),
    ("based in the us", "answer_yes"),
    ("based in the united states", "answer_yes"),
    ("located in the u.s", "answer_yes"),
    ("located in the us", "answer_yes"),
    ("currently located in the u.s", "answer_yes"),
    ("office 5 days", "answer_yes"),
    ("office 4 days", "answer_yes"),
    ("office 3 days", "answer_yes"),
    ("office 2 days", "answer_yes"),
    ("days/week in", "answer_yes"),
    ("days per week in the office", "answer_yes"),
    ("days a week in office", "answer_yes"),
    ("come into our", "answer_yes"),
    ("come into the office", "answer_yes"),
    ("able to come into", "answer_yes"),
    # Plaud 2731: "come to the office in either SF or Palo Alto at least 3 days a week"
    ("come to the office", "answer_yes"),
    ("come to our office", "answer_yes"),
    ("days a week", "answer_yes"),
    ("days per week", "answer_yes"),
    # Vendelux 2774: "able to commit to our NYC HQ up to 4 times a week?"
    ("commit to our", "answer_yes"),
    ("times a week", "answer_yes"),
    ("times per week", "answer_yes"),
    ("this role is onsite", "answer_yes"),
    ("role is onsite", "answer_yes"),
    # ============================================================
    # Overnight field-gap LABEL_RULES (2026-06-08, from triage backlog).
    # All TRUTHFUL: US-onsite / US-travel / offsite-travel ack are NEVER
    # knockouts for Cyrus (relocates/travels anywhere in the USA), and he is
    # a native English speaker. These unblock rows that the field-walker was
    # banking on "no LABEL_RULES match".
    # ---- in-person / willing-to-work-in-<city>-office -> answer_yes ----
    # Mintlify 2574/2575 ("willing to work in our San Francisco office"),
    # Lance 2594/2595, ~2602: "this is an in-person role ... in San Francisco".
    ("willing to work in our", "answer_yes"),
    ("willing to work in the", "answer_yes"),
    ("willing to work in our san francisco", "answer_yes"),
    ("work in our san francisco office", "answer_yes"),
    ("this is an in-person role", "answer_yes"),
    ("this is an in person role", "answer_yes"),
    ("in-person role based in", "answer_yes"),
    ("in-person role in san francisco", "answer_yes"),
    ("in person role in san francisco", "answer_yes"),
    ("in-person role", "answer_yes"),
    # ---- able to travel throughout the US -> answer_yes ----
    # Lance 2594: "able to travel throughout the United States".
    ("travel throughout the united states", "answer_yes"),
    ("travel throughout the us", "answer_yes"),
    ("able to travel throughout", "answer_yes"),
    ("willing to travel throughout", "answer_yes"),
    ("travel domestically", "answer_yes"),
    ("travel within the united states", "answer_yes"),
    ("travel within the us", "answer_yes"),
    # ---- twice-yearly / company-offsite travel ack -> answer_yes ----
    # authzed 2607: "...twice-yearly travel for company offsites...".
    ("twice-yearly travel", "answer_yes"),
    ("twice yearly travel", "answer_yes"),
    ("travel for company offsites", "answer_yes"),
    ("travel for company offsite", "answer_yes"),
    ("company offsites", "answer_yes"),
    ("company offsite", "answer_yes"),
    ("quarterly offsite", "answer_yes"),
    ("team offsite", "answer_yes"),
    ("travel for offsites", "answer_yes"),
    ("travel for team offsites", "answer_yes"),
    # ---- English-proficiency comfort scale -> highest tier (native) ----
    # Firecrawl 2566: "comfortable reading, writing and speaking in English?".
    # Cyrus is a NATIVE English speaker -> highest-comfort option.
    ("writing and speaking in english", "english_comfort_high"),
    ("reading, writing and speaking in english", "english_comfort_high"),
    ("reading, writing, and speaking in english", "english_comfort_high"),
    ("comfortable speaking in english", "english_comfort_high"),
    ("comfortable writing in english", "english_comfort_high"),
    ("speaking in english", "english_comfort_high"),
    ("proficiency in english", "english_comfort_high"),
    ("english proficiency", "english_comfort_high"),
    ("comfortable communicating in english", "english_comfort_high"),
    ("fluency in english", "english_comfort_high"),
    # NOTE: the "996" / extreme-hours question (Lance 2594/2595 "Are you willing
    # to work 996?" = 9am-9pm 6 days/wk, ~72hr/week) is handled by the SHARED
    # greenhouse_dryrun extreme-hours path, which AUTO-ANSWERS affirmatively
    # (REVERSED 2026-06-08 per Cyrus directive: applying != committing; auto-answer
    # ALL form fields to best-advance the app). Do NOT add an Ashby rule that banks
    # 996 to Cyrus — that would re-introduce the old (now-reversed) values-call
    # behavior. r4 submitted Lance 2594/2595 with 996->Yes via this path.
    # ============================================================
    # Antithesis 2782: "...this role is fully onsite with the team. Are you
    # willing to commit to this?" (US-onsite-never-a-knockout doctrine).
    ("fully onsite", "answer_yes"),
    ("fully in-office", "answer_yes"),
    ("fully in office", "answer_yes"),
    ("willing to commit to this", "answer_yes"),
    ("onsite with the team", "answer_yes"),
    ("onsite at our", "answer_yes"),
    ("working onsite at", "answer_yes"),
    ("comfortable working onsite", "answer_yes"),
    ("comfortable with working onsite", "answer_yes"),
    ("comfortable working in-person", "answer_yes"),
    ("comfortable working in person", "answer_yes"),
    ("within commuting distance", "answer_yes"),
    ("commuting distance to", "answer_yes"),
    ("commutable distance", "answer_yes"),
    ("do you currently reside in", "answer_yes"),
    ("do you reside in", "answer_yes"),
    ("reside in or near", "answer_yes"),
    ("reside in the greater", "answer_yes"),
    ("located near", "answer_yes"),
    ("based in or near", "answer_yes"),
    ("can you meet this requirement", "answer_yes"),
    ("are you able to meet this requirement", "answer_yes"),
    # Hudu 2664: "Do you have prior experience working for a startup or SaaS
    # company in the last five years?" -> truthful Yes (Cyrus has SaaS/startup PM
    # experience). And "Our interview process includes recording... Are you
    # comfortable..." -> Yes (consent, matches GH consent-to-AI-transcript class).
    ("prior experience working for a startup", "answer_yes"),
    ("experience working for a startup or saas", "answer_yes"),
    ("startup or saas", "answer_yes"),
    ("comfortable with your interview", "answer_yes"),
    ("interview process includes recording", "answer_yes"),
    ("comfortable being recorded", "answer_yes"),
    # Hudu 2664: "...background check... Do you acknowledge this statement?"
    # Cyrus consents to background checks (personal-info background_check=Yes).
    ("do you acknowledge this statement", "answer_yes"),
    ("submitted to a check of their background", "answer_yes"),
    ("check of their background", "answer_yes"),
    ("acknowledge this statement", "answer_yes"),
    # ---- work-authorization-REQUIRED phrasing -> truthful No (Cyrus needs none) ----
    # Starbridge: "Do you require any form of authorization to work legally in
    # the United States?" Cyrus is a US citizen -> requires NO authorization -> No.
    ("require any form of authorization to work", "needs_sponsorship"),
    ("require any authorization to work", "needs_sponsorship"),
    ("do you require authorization to work", "needs_sponsorship"),
    ("require work authorization", "needs_sponsorship"),
    # Fluidstack 2969/2970 (2026-06-16): visa-sponsorship phrased as affirmative statement.
    # "I will now or in the future need assistance with a work visa." -> No (US citizen)
    ("now or in the future need assistance with a work visa", "needs_sponsorship"),
    ("need assistance with a work visa", "needs_sponsorship"),
    # Fluidstack 2969/2970: travel willingness
    ("open to travel", "willing_to_travel"),
    ("willing and able to travel", "willing_to_travel"),
    # ---- non-compete / current-employer restrictions -> truthful No ----
    # Vendelux 2774: "Does your current employer have any restrictions on your
    # ability to work as a part time or full time employee at Vendelux?"
    # Cyrus (Microsoft) has no non-compete/restriction blocking this -> No.
    ("restrictions on your ability to work", "answer_no"),
    ("any restrictions on your ability", "answer_no"),
    ("current employer have any restrictions", "answer_no"),
    ("non-compete", "answer_no"),
    ("noncompete", "answer_no"),
    ("subject to any non-compete", "answer_no"),
    # Fluidstack 2969/2970 (2026-06-16): non-breaking hyphen variant U+2011
    # "subject to any agreement (such as a non\u2011compete...)"
    ("subject to any agreement", "answer_no"),
    ("non\u2011compete", "answer_no"),  # non-breaking hyphen
    # ---- skill / tool proficiency -> honest INTERMEDIATE tier ----
    # Dash0 2757: "What is your skill level in kubernetes/observability?"
    ("skill level in", "proficiency_intermediate"),
    ("your skill level", "proficiency_intermediate"),
    ("level of proficiency in", "proficiency_intermediate"),
    ("your level of proficiency", "proficiency_intermediate"),
    ("proficiency in python", "proficiency_intermediate"),
    ("rate your proficiency", "proficiency_intermediate"),
    ("proficiency level", "proficiency_intermediate"),
    # ---- work-arrangement / work-setup preference dropdowns ----
    ("preferred work arrangement", "work_arrangement"),
    ("work arrangement", "work_arrangement"),
    ("working arrangement", "work_arrangement"),
    ("work setup", "work_arrangement"),
    ("work-setup", "work_arrangement"),
    ("preferred work style", "work_arrangement"),
    ("remote, hybrid, or onsite", "work_arrangement"),
    ("remote, hybrid or onsite", "work_arrangement"),
    ("remote/hybrid/onsite", "work_arrangement"),
    # ---- prior/current/most-recent employer or title (biographical) ----
    # (Helion 2712 "Have you previously worked at Helion?"). worked_at_company_before
    # is the GH handler; current/most-recent employer route to current_employer.
    # Many of these already exist above; these fill the remaining GH phrasings.
    # Helion 2712: "Do you currently or have you in the past worked for Helion Energy?"
    ("currently or have you in the past worked", "worked_at_company_before"),
    ("in the past worked for", "worked_at_company_before"),
    ("in the past worked at", "worked_at_company_before"),
    ("have you previously been employed", "worked_at_company_before"),
    ("have you previously worked at", "worked_at_company_before"),
    ("have you ever worked at", "worked_at_company_before"),
    ("have you ever worked for", "worked_at_company_before"),
    ("are you a former", "worked_at_company_before"),
    ("previously worked here", "worked_at_company_before"),
    ("worked here before", "worked_at_company_before"),
    # ============================================================
    # "have you ever used X (product)" — Cyrus answers Yes (he uses everything; safer default)
    # Most companies expect Yes/No; we default Yes. If too aggressive we'll switch to No.
    ("have you ever used", "ever_used_product"),
    ("do you use", "ever_used_product"),
    ("are you a user of", "ever_used_product"),
    # AI notetaking tool consent (Sierra/Metaview, etc.) — auto-Yes
    ("notetaking tool", "ai_notetaking_consent"),
    ("note-taking tool", "ai_notetaking_consent"),
    ("ai notetaker", "ai_notetaking_consent"),
    ("recording and transcribing", "ai_notetaking_consent"),
    ("recording our", "ai_notetaking_consent"),
    ("metaview", "ai_notetaking_consent"),
    # Generic "other links" / "other relevant urls" -> optional, blank
    ("other links", "other_links"),
    ("other relevant urls", "other_links"),
    ("other relevant link", "other_links"),
    ("additional links", "other_links"),
    # Privacy policy / applicant policy ack (single-option ValueSelect handled
    # downstream, but we also catch wording like "i understand the information
    # i submit will be used in accordance with X's policy" so it gets ack=Yes).
    ("will be used in accordance", "acknowledge_yes"),
    ("applicant privacy policy", "acknowledge_yes"),
    ("privacy notice", "acknowledge_yes"),
    # Thought Machine 1367 (2026-05-30): "By submitting this application I
    # acknowledge my personal data will be processed in accordance with <co>'s
    # privacy policy" — honest Yes (you ARE consenting by submitting).
    ("acknowledge my personal data", "acknowledge_yes"),
    ("personal data will be processed", "acknowledge_yes"),
    ("by submitting this application", "acknowledge_yes"),
    ("arbitration agreement", "acknowledge_yes"),
    ("i acknowledge that i have", "acknowledge_yes"),
    ("i have read and acknowledge", "acknowledge_yes"),
    ("i have read and understood", "acknowledge_yes"),
    ("i have read, understood", "acknowledge_yes"),
    # Self-identify gate (some Ashby forms ask before each demo question)
    ("would you like to self-identify", "self_identify_decline"),
    # Thought Machine 1367 (2026-05-30): "Where did you hear about this
    # opportunity?" 5-way radio (LinkedIn / Industry Event / Company Website /
    # News Article / Other). Honest: we surface roles via LinkedIn + company
    # careers crawls; profile default is "LinkedIn", a valid option here.
    ("where did you hear about", "how_did_you_hear"),
    ("how did you hear about", "how_did_you_hear"),
    ("how did you find out about", "how_did_you_hear"),
    ("how you heard about", "how_did_you_hear"),
    ("would you like to self identify", "self_identify_decline"),
    ("self-identify", "self_identify_decline"),
    ("prefer to self-describe", "self_identify_decline"),
    # Age — demographic, decline
    ("age range", "demo_age"),
    ("what is your age", "demo_age"),
    ("your age", "demo_age"),
    # Plaid 2026-05-24: "how would you rate Plaid's position in AI compared to other tech companies"
    # — flattery-style rating, pick "Among the leaders" if available, else upper-mid.
    ("how would you rate", "company_ai_rating"),
    ("rate the company's position in ai", "company_ai_rating"),
    ("position in ai compared to", "company_ai_rating"),

    # Deepgram 2026-05-25 (FDE Restaurants) — recency of code commit. Cyrus
    # writes/commits code regularly for automation/scripts at work; pick the
    # most recent option that's plausible ("Less than 1 month").
    ("how long has it been since the last time you wrote code", "recent_code_commit"),
    ("wrote code for a non-personal", "recent_code_commit"),
    ("committed it to a repository", "recent_code_commit"),

    # Deepgram — % time engaging customers/prospects on technical matters.
    # Cyrus's TPM/PM work is heavily customer-facing; pick upper-mid bucket.
    ("percentage of your time", "customer_facing_percent"),
    ("time in your current/last role was spent directly engaging", "customer_facing_percent"),
    ("directly engaging with customers", "customer_facing_percent"),

    # Deepgram — built customer-facing demos / POCs -> Yes (he has).
    ("built customer-facing demos", "acknowledge_yes"),
    ("customer-facing demos or proof-of-concepts", "acknowledge_yes"),
    ("demos or proof-of-concepts", "acknowledge_yes"),

    # --- Academic fields (gh-academic-fields-2026-05-30). GH already has
    # short rules for school/degree/major/minor/gpa/sat/act/gre; Ashby tenants
    # sometimes phrase them as full questions that the GH substring rules
    # miss. Splice the long-form variants here. ---
    ("which university did you attend", "school"),
    ("what university did you attend", "school"),
    ("where did you go to college", "school"),
    ("name of your university", "school"),
    ("undergraduate institution", "school"),
    ("highest degree", "degree"),
    ("degree earned", "degree"),
    ("what is your major", "major"),
    ("what was your major", "major"),
    ("field of study", "major"),
    ("what is your minor", "minor"),
    ("what was your minor", "minor"),
    ("undergraduate gpa", "gpa"),
    ("college gpa", "gpa"),
    ("cumulative gpa", "gpa"),
    ("what is your gpa", "gpa"),
    # Modern Treasury ~2602 (2026-06-08, residential r4): two required custom
    # fields with non-standard labels the resolver was missing -> banked at prep
    # as "no LABEL_RULES match" even though residential PASSED the score gate.
    # (1) "What is the best number to reach you at?" = phone (custom UUID input,
    #     NOT __systemfield_phone) -> route to the phone resolver.
    ("best number to reach you at", "phone"),
    ("best number to reach you", "phone"),
    ("best phone number to reach", "phone"),
    ("best contact number", "phone"),
    ("number to reach you at", "phone"),
    ("what is the best number", "phone"),
    # (2) "Where will you be working from?" = location typeahead, but the label
    #     lacks the word "location" so the combo matcher missed it -> route to
    #     the city_state resolver (Kirkland, WA). The runner-side label-fallback
    #     regex in _LOCATION_COMBO_FILL_JS is broadened to match these too.
    ("where will you be working from", "city_state"),
    ("where will you be based", "city_state"),
    ("where are you based", "city_state"),
    ("where are you located", "city_state"),
    ("where will you work from", "city_state"),
    ("location you will be working from", "city_state"),
]


def _r_ever_used_product(p, f):
    # Default to "Yes" — Cyrus is technical; if a company asks "have you used X"
    # he probably has at minimum tried it. Safer than blanket "No".
    return ('ok', 'Yes', 'ashby_ever_used_product (default Yes)')


def _r_ai_notetaking_consent(p, f):
    return ('ok', 'Yes', 'ashby_ai_notetaking_consent (auto-Yes per AI-disclosure policy: ok with recording for interview process)')


def _r_other_links(p, f):
    if f.get('required'):
        # Required "other links" -> use github as a reasonable fallback
        v = (p.get('contact') or {}).get('github') or ''
        return ('ok', v, 'contact.github (other_links required fallback)')
    return ('ok', '', 'other_links optional -> blank')


def _r_self_identify_decline(p, f):
    return ('decline', 'I prefer not to answer', 'ashby_self_identify_decline')


def _r_demo_age(p, f):
    return ('decline', 'I prefer not to answer', 'demographics_default (age)')


def _r_never_no(p, f):
    return ('ok', 'No', 'ashby_never_no (Cyrus has no prior US gov employment / no security clearance / not citizen of restricted country)')


def _r_visa_type_na(p, f):
    # "What type of visa will you require? (if applicable to above)" — Cyrus is
    # a US citizen (work_authorization.status == us_citizen, sponsorship_required
    # == no), so NO visa is required. The honest answer to a conditional
    # "if applicable" visa-type field is "Not applicable". This is truthful, not
    # an integrity bypass: we are NOT claiming a sponsorship status we don't have.
    # Assort Health 1545 is a ValueSelect with options including
    # "Not applicable"; pick the option that means none/N-A. If no such option
    # exists and it's free text, return 'N/A'.
    wa = (p.get('work_authorization') or {})
    needs = (wa.get('sponsorship_required_now') or 'no').lower()
    if needs not in ('no', 'false', 'n'):
        # If sponsorship IS required, do NOT guess a visa type -> human review.
        return ('unresolved', None, 'ashby_visa_type: sponsorship required per profile; needs human-entered visa type')
    opts = [(o.get('label') or o.get('value') or '') for o in (f.get('values') or f.get('options') or [])]
    for needle in ('not applicable', 'n/a', 'none', 'no visa', 'do not require', "don't require"):
        for o in opts:
            if needle in o.lower():
                return ('ok', o, f'ashby_visa_type_na (US citizen; matched option {o!r})')
    if opts:
        # ValueSelect with no N/A-style option: leave for human rather than
        # pick a visa type Cyrus doesn't hold (integrity).
        return ('unresolved', None, f'ashby_visa_type: no not-applicable option among {opts}; needs human review')
    # Free-text field: N/A is honest.
    return ('ok', 'N/A', 'ashby_visa_type_na (US citizen, free-text, no visa required)')


def _r_coding_ability(p, f):
    # Pick first option matching "familiar" / "read and modify" — Cyrus is a
    # TPM, reads code daily but doesn't ship production. Falls back to first
    # non-"No experience" option.
    opts = [o.get('label') or '' for o in (f.get('values') or [])]
    for needle in ('some familiarity', 'familiar', 'read and modify', 'read code'):
        for o in opts:
            if needle in o.lower():
                return ('ok', o, f'ashby_coding_ability (matched {needle!r})')
    # Otherwise pick anything that's not the "no experience" one
    for o in opts:
        if 'no coding' not in o.lower() and 'no experience' not in o.lower() and o:
            return ('ok', o, 'ashby_coding_ability (first non-zero option)')
    if opts:
        return ('ok', opts[0], 'ashby_coding_ability (fallback first option)')
    return ('ok', 'Some familiarity', 'ashby_coding_ability (no options, free text)')


def _r_location_ack(p, f):
    # US onsite / in-person / commute / based-in / relocation ack.
    #
    # DOCTRINE (Cyrus directive via main, 2026-06-03; encoded in
    # personal-info.json _relocation_note): "US onsite is NEVER a knockout."
    # Cyrus relocates ANYWHERE in the USA and travels up to 100%, so ANY
    # US-based onsite/hybrid/in-person/commute/based-in/relocate question is
    # ELIGIBLE -> answer Yes, then submit. A NON-US location is a genuine
    # knockout, but that is detected upstream by the geo classifier, NOT here:
    # these rules only fire on onsite/commute/based-in/in-person/relocation
    # phrasings, which under the doctrine are all US-eligible.
    #
    # PRIOR BUG (fixed 2026-06-04): this resolver gated on a relocation-target
    # city list (SF/NYC/Bay/Seattle) and returned 'No' for every other US
    # city -> banked Plaud 2731 / Vendelux 2774 at prep as false geo-knockouts.
    # That contradicted the doctrine. Now always Yes, mirroring the proven
    # Greenhouse `answer_yes`/`ack_in_office` onsite handling.
    #
    # When the field is a Yes/No-style select, match the affirmative option;
    # otherwise return the bare 'Yes' string for free-text/boolean.
    values = f.get('values') or []
    for v in values:
        lbl = (v.get('label') or '').strip()
        if lbl.lower() == 'yes':
            return ('ok', lbl, "ashby_location_ack (US onsite never a knockout -> matched 'Yes')")
    for v in values:
        lbl = (v.get('label') or '').strip()
        ll = lbl.lower()
        if ll.startswith('yes') and not ll.startswith('no'):
            return ('ok', lbl, f"ashby_location_ack (US onsite never a knockout -> matched 'Yes...' {lbl!r})")
    return ('ok', 'Yes', 'ashby_location_ack (US onsite/relocation never a knockout -> Yes)')


def _r_company_ai_rating(p, f):
    # Pick "Among the leaders" if present, else "Above average", else last
    # non-"N/A" option, else first option. Avoids the safe-but-cowardly N/A.
    opts = [o.get('label') or '' for o in (f.get('values') or [])]
    for needle in ('among the leaders', 'leader', 'above average'):
        for o in opts:
            if needle in o.lower():
                return ('ok', o, f'ashby_company_ai_rating (matched {needle!r})')
    non_na = [o for o in opts if 'n/a' not in o.lower() and 'not enough' not in o.lower() and o]
    if non_na:
        return ('ok', non_na[-1], 'ashby_company_ai_rating (last non-N/A option)')
    if opts:
        return ('ok', opts[0], 'ashby_company_ai_rating (fallback first option)')
    return ('ok', 'Above average', 'ashby_company_ai_rating (free text)')


def _r_recent_code_commit(p, f):
    # Pick the most recent bucket available. Cyrus commits automation scripts
    # regularly; "Less than 1 month" is truthful. Fall back through 1-3 months.
    opts = [o.get('label') or '' for o in (f.get('values') or [])]
    for needle in ('less than 1 month', '< 1 month', '<1 month', 'within the last month',
                   '1-3 months', '1 to 3 months', '1 - 3 months'):
        for o in opts:
            if needle in o.lower():
                return ('ok', o, f'ashby_recent_code_commit (matched {needle!r})')
    if opts:
        return ('ok', opts[0], 'ashby_recent_code_commit (fallback first option)')
    return ('ok', 'Less than 1 month', 'ashby_recent_code_commit (free text)')


def _r_customer_facing_percent(p, f):
    # Cyrus's PM/TPM work is heavily customer-facing. Pick upper-mid bucket
    # (50-75%) when present, then 25-50%, then any non-zero.
    opts = [o.get('label') or '' for o in (f.get('values') or [])]
    for needle in ('50 -> 75', '50-75', '50 - 75', '50 to 75'):
        for o in opts:
            if needle in o.lower():
                return ('ok', o, f'ashby_customer_facing_percent (matched {needle!r})')
    for needle in ('25 -> 50', '25-50', '25 - 50', '25 to 50'):
        for o in opts:
            if needle in o.lower():
                return ('ok', o, f'ashby_customer_facing_percent (matched {needle!r})')
    # Avoid the 0% / lowest bucket; pick last non-100% if everything else fails.
    for o in reversed(opts):
        if '75 -> 100' not in o and '75-100' not in o and o:
            return ('ok', o, 'ashby_customer_facing_percent (fallback mid)')
    if opts:
        return ('ok', opts[0], 'ashby_customer_facing_percent (fallback first)')
    return ('ok', '25 -> 50%', 'ashby_customer_facing_percent (free text)')


def _r_us_timezone(p, f):
    """Pick Pacific Time. Cyrus is in Kirkland, WA (PST/PDT).

    Handles labels like 'Which timezone do you live in?' / 'What time zone are you in?'
    Options often phrased 'Pacific Time Zone (PST): UTC-8.' or just 'PST' / 'Pacific'.
    Fallback ladder: explicit Pacific match -> any option containing 'PST' or 'UTC-8' ->
    free text 'Pacific Time (PT/PST)'.

    Signature matches the standard resolver convention (personal, field). Options
    come from f.get('values'), same as other Ashby resolvers.
    """
    opts = f.get('values') or f.get('options') or []
    if opts:
        labels = [(o.get('label') or o.get('value') or '') for o in opts]
        # Tier 1: 'Pacific' substring (case-insensitive)
        for l in labels:
            if 'pacific' in l.lower():
                return ('ok', l, 'ashby_us_timezone (pacific match)')
        # Tier 2: 'PST' token or 'UTC-8'
        for l in labels:
            ll = l.lower()
            if 'pst' in ll or 'utc-8' in ll or 'utc−8' in ll:
                return ('ok', l, 'ashby_us_timezone (pst/utc-8 match)')
        # Tier 3: any US-mainland zone (avoid Hawaii/Alaska/Atlantic) -> Eastern as conservative fallback
        for needle in ('eastern', 'est', 'utc-5', 'central', 'cst', 'utc-6', 'mountain', 'mst', 'utc-7'):
            for l in labels:
                if needle in l.lower():
                    return ('ok', l, f'ashby_us_timezone (fallback {needle})')
        return ('ok', labels[0], 'ashby_us_timezone (fallback first)')
    return ('ok', 'Pacific Time (PT/PST)', 'ashby_us_timezone (free text)')


def _r_full_address(p, f):
    # Neural Concept 1365 2026-05-26: "Your official address" / "home address"
    # text field -> emit street + city + state + zip + country.
    addr = p.get('address') or {}
    parts = [addr.get('street'), addr.get('city'), addr.get('state'), addr.get('zip'), addr.get('country')]
    parts = [p for p in parts if p]
    if not parts:
        return ('ok', '', 'ashby_full_address (no address in prefill)')
    val = ', '.join(parts)
    return ('ok', val, 'ashby_full_address (street+city+state+zip+country)')


def _r_linkedin_url(p, f):
    # Neural Concept 1365 2026-05-26: "Social Network and Web Links" text
    # field -> LinkedIn URL (Cyrus's primary public profile).
    v = (p.get('contact') or {}).get('linkedin') or (p.get('links') or {}).get('linkedin')
    if v:
        return ('ok', v, 'ashby_linkedin_url (contact.linkedin)')
    return ('ok', 'https://www.linkedin.com/in/cyrus-shekari', 'ashby_linkedin_url (fallback hardcoded)')


def _r_how_did_you_hear(p, f):
    # Thought Machine 1367 (2026-05-30): "Where/How did you hear about this
    # opportunity?" radio. Honest: roles are surfaced via LinkedIn + company
    # careers-page crawls. Match the profile's preferred channel
    # (common_form_answers.how_did_you_hear_about_us, default "LinkedIn")
    # against the actual options; fall back through truthful alternates.
    pref = ((p.get('common_form_answers') or {}).get('how_did_you_hear_about_us') or 'LinkedIn')
    opts = [o.get('label') or '' for o in (f.get('values') or [])]
    # truthful preference ladder: profile pref -> LinkedIn -> Company Website -> Other
    ladder = [pref, 'linkedin', 'company website', 'company site', 'careers', 'other']
    for needle in ladder:
        nl = needle.lower()
        for o in opts:
            if nl and nl in o.lower():
                return ('ok', o, f'ashby_how_did_you_hear (matched {needle!r})')
    if opts:
        return ('ok', opts[-1], 'ashby_how_did_you_hear (fallback last option, usually Other)')
    return ('ok', pref, 'ashby_how_did_you_hear (free text)')


def _r_work_arrangement(p, f):
    # Work-arrangement / work-setup preference dropdowns (Dash0 2757:
    # "Preferred work arrangement?" remote/hybrid/onsite). Per the US-onsite
    # doctrine Cyrus is open to ALL US arrangements, so this is never a
    # knockout. Pick an affirmative-presence option so an onsite/hybrid role
    # isn't filtered out: prefer an explicit 'open to all/any/flexible/no
    # preference' option, else 'hybrid' (middle ground), else 'onsite'/'in
    # office', else 'remote', else first option.
    opts = [(v.get('label') or '').strip() for v in (f.get('values') or [])]
    if not opts:
        return ('ok', 'Open to remote, hybrid, or onsite',
                'ashby_work_arrangement (free text)')
    ladder = ['open to all', 'open to any', 'no preference', 'flexible',
              'any of', 'hybrid', 'on-site', 'onsite', 'in office',
              'in-office', 'in person', 'in-person', 'remote']
    for needle in ladder:
        for o in opts:
            if needle in o.lower():
                return ('ok', o, f'ashby_work_arrangement (matched {needle!r})')
    return ('ok', opts[0], 'ashby_work_arrangement (fallback first option)')


def _r_primary_location_pick(p, f):
    # Multi-office "which of our primary locations are you interested in?"
    # single-select (Profound 2844). Pick the FIRST concrete US office.
    # US onsite/relocation is never a knockout, so any real US office is a
    # truthful, valid answer. Prefer a relocation-target metro, else first
    # non-placeholder US-looking option, else first option.
    opts = [(v.get('label') or v.get('value') or '').strip()
            for v in (f.get('values') or f.get('options') or [])]
    opts = [o for o in opts if o and o.lower() not in ('select...', 'select', '-', '')]
    if not opts:
        return ('ok', '', 'ashby_primary_location_pick (no options)')
    # Tier 1: preferred US metros (relocation targets / common HQ cities).
    prefer = ['san francisco', 'new york', 'nyc', 'seattle', 'austin',
              'boston', 'los angeles', 'remote', 'united states', 'u.s.']
    for needle in prefer:
        for o in opts:
            if needle in o.lower():
                return ('ok', o, f'ashby_primary_location_pick (matched {needle!r})')
    # Tier 2: first concrete option.
    return ('ok', opts[0], 'ashby_primary_location_pick (fallback first office)')


_ASHBY_EXTRA_RESOLVERS = {
    'primary_location_pick': _r_primary_location_pick,
    'ever_used_product': _r_ever_used_product,
    'ai_notetaking_consent': _r_ai_notetaking_consent,
    'other_links': _r_other_links,
    'self_identify_decline': _r_self_identify_decline,
    'demo_age': _r_demo_age,
    'never_no': _r_never_no,
    'visa_type_na': _r_visa_type_na,
    'coding_ability': _r_coding_ability,
    'location_ack': _r_location_ack,
    'company_ai_rating': _r_company_ai_rating,
    'recent_code_commit': _r_recent_code_commit,
    'customer_facing_percent': _r_customer_facing_percent,
    'us_timezone': _r_us_timezone,
    'full_address': _r_full_address,
    'linkedin_url': _r_linkedin_url,
    'how_did_you_hear': _r_how_did_you_hear,
    'work_arrangement': _r_work_arrangement,
}

# Add the Ashby resolver IMPLEMENTATIONS to GH's shared RESOLVERS dict. These
# keys have ZERO overlap with GH's 94 resolver keys (verified), so this only
# ADDS impls and never overrides GH. (Safe to share the dict.)
gh.RESOLVERS.update(_ASHBY_EXTRA_RESOLVERS)

# Build an Ashby-SCOPED combined rule list instead of mutating GH's shared
# global LABEL_RULES in place. Ashby rules go FIRST so they keep the same
# precedence the old front-insert gave them (e.g. "earliest month" beats a
# generic "month" GH rule). gh.LABEL_RULES stays pristine/GH-only, so any
# other importer of ashby_dryrun (the real submit pipeline) no longer has its
# GH resolution silently hijacked.
_ASHBY_COMBINED_RULES = list(_ASHBY_EXTRA_RULES) + list(gh.LABEL_RULES)


def find_resolver(label, rules=None):
    """Ashby-scoped resolver lookup: defaults to the Ashby+GH combined rule
    list (Ashby rules first) instead of GH's global. Pass an explicit `rules`
    to override."""
    return gh.find_resolver(label, rules=_ASHBY_COMBINED_RULES if rules is None else rules)


# Pattern: a label that looks like an essay/open-ended question. Mirrors
# cover_answer_generator.OPEN_QUESTION_HINTS but kept local so we don't
# import that module just for a regex.
_ESSAY_LABEL_RE = re.compile(
    r"\b(why|describe|tell us|share|explain|experience with|how would|how do you|"
    r"what makes|what excites|what draws|what interests|interested in|interest in|"
    r"what attracts|tell me|walk us|walk me|elaborate|provide additional|"
    r"additional information|please provide|please share|please describe|"
    r"please tell|please explain|in your own words|briefly|background|"
    r"career summary|summary|cover letter|cover note|"
    r"what motivates|what.{0,8}proud of|favorite|habit|excites you most|"
    r"applying to work on|something specific|what's something|"
    r"anything else)\b",
    re.I,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
PERSONAL_INFO_PATH = PROJECT_ROOT / "personal-info.json"
OUTPUT_DIR = PROJECT_ROOT / "applications" / "dryrun"

GQL_URL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting"
HTTP_TIMEOUT = 25
USER_AGENT = "openclaw-job-search-dryrun/1.0 (Ashby)"

GQL_QUERY = """
query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) {
  jobPosting(organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) {
    id
    title
    locationName
    applicationForm {
      sections {
        title
        descriptionHtml
        fieldEntries {
          id
          isRequired
          isHidden
          descriptionHtml
          field
        }
      }
    }
  }
}
"""

# Ashby URL shapes:
#   https://jobs.ashbyhq.com/<org>/<uuid>
#   https://jobs.ashbyhq.com/<org>/<uuid>/application
URL_RX = re.compile(r"^/(?P<org>[^/]+)/(?P<job_id>[0-9a-fA-F-]{36})(?:/application)?/?$")


def parse_ashby_url(url: str) -> tuple[str, str]:
    p = urlparse(url)
    host = p.netloc.lower()
    if "ashbyhq.com" not in host:
        raise ValueError(f"not an Ashby URL: {url}")
    m = URL_RX.match(p.path)
    if not m:
        raise ValueError(f"could not extract org/job_id from URL path: {p.path}")
    return m.group("org"), m.group("job_id")


def fetch_form(org: str, job_id: str) -> dict:
    payload = {
        "operationName": "ApiJobPosting",
        "variables": {
            "organizationHostedJobsPageName": org,
            "jobPostingId": job_id,
        },
        "query": GQL_QUERY,
    }
    resp = requests.post(GQL_URL, json=payload, timeout=HTTP_TIMEOUT,
                         headers={"User-Agent": USER_AGENT,
                                  "Content-Type": "application/json"})
    if resp.status_code != 200:
        raise RuntimeError(f"POST {GQL_URL} returned {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    posting = (data.get("data") or {}).get("jobPosting")
    if not posting:
        raise RuntimeError(f"jobPosting not found for {org}/{job_id}")
    return posting


# ---------------------------------------------------------------------------
# Field-shape adapter: Ashby fieldEntry -> Greenhouse-style field+question
# ---------------------------------------------------------------------------
#
# Ashby's `field` JSON has shape (varies by type):
#   { "type": "String"|"Email"|"Phone"|"LongText"|"File"|"Location"|"Date"|
#             "Boolean"|"ValueSelect"|"MultiValueSelect"|"Number"|"YesNo"|...,
#     "title": "...",
#     "selectableValues": [{"label":"...","value":"..."}]   # for selects
#   }
#
# We translate to GH-style so we can reuse resolve_field unchanged:
#   GH "input_text"                  <- String, Email, Phone, Number, Url
#   GH "input_date"                  <- Date  (calendar-picker widget; see below)
#   GH "textarea"                    <- LongText
#   GH "input_file"                  <- File
#   GH "multi_value_single_select"   <- ValueSelect, Boolean, YesNo, Location
#   GH "multi_value_multi_select"    <- MultiValueSelect
#
# Boolean fields render in Ashby as a Yes/No radio pair; we model as
# single-select with options=[{"Yes",true},{"No",false}].
# Location fields in Ashby render as a typeahead string; we treat as text
# (same as GH's location_questions for our purposes).

ASHBY_TO_GH_TYPE = {
    "String": "input_text",
    "Email": "input_text",
    "Phone": "input_text",
    "Number": "input_text",
    "Url": "input_text",
    # Ashby "Date" renders as a CALENDAR-PICKER widget (e.g. OpenAI 2549
    # "When can you start a new role?"). It was mapped to "input_text", which
    # made gh.resolve_field hand the earliest_start resolver a text type ->
    # it returned the PROSE fallback "Within 2 weeks of offer" instead of an
    # ISO date, and the runner typed that prose into a date input that never
    # committed -> submit banked "Missing entry" (r4 diagnosis 2026-06-08).
    # Map to GH "input_date" so the date resolvers emit a real YYYY-MM-DD
    # (today+14d). The runner drives Ashby Date fields via the date-picker
    # path keyed on _ashby_type=="Date" (a normalized ISO value commits).
    "Date": "input_date",
    "LongText": "textarea",
    "File": "input_file",
    "ValueSelect": "multi_value_single_select",
    "Boolean": "multi_value_single_select",
    "YesNo": "multi_value_single_select",
    "MultiValueSelect": "multi_value_multi_select",
    "Location": "input_text",
}


def adapt_field(entry: dict) -> tuple[dict, str]:
    """Return (gh_style_field, gh_style_label).

    gh_style_field carries `name`, `type`, `values`, `required`,
    `_ashby_type`, `_ashby_id` so the filler can drive Ashby-specific DOM.
    """
    raw = entry["field"] or {}
    a_type = raw.get("type") or "String"
    title = raw.get("title") or ""
    gh_type = ASHBY_TO_GH_TYPE.get(a_type, "input_text")

    # Ashby system fields have stable id suffixes; rewrite the label so the
    # GH LABEL_RULES catch them. Bare "Name" otherwise has no rule (and we
    # don't want to add a generic "name" rule because it would catch
    # "company name", "school name", etc.).
    aid = entry.get("id") or ""
    if aid.endswith("__systemfield_name") and title.strip().lower() == "name":
        title = "Full Name"
    elif aid.endswith("__systemfield_email") and not title:
        title = "Email"
    elif aid.endswith("__systemfield_resume") and not title:
        title = "Resume"

    values: list[dict] = []
    if a_type == "Boolean":
        values = [{"label": "Yes", "value": True}, {"label": "No", "value": False}]
    elif raw.get("selectableValues"):
        for v in raw["selectableValues"]:
            if isinstance(v, dict):
                values.append({"label": v.get("label"), "value": v.get("value")})
            else:
                values.append({"label": str(v), "value": str(v)})

    return {
        "name": entry["id"],         # full Ashby path id (e.g. "<formId>__systemfield_name")
        "type": gh_type,
        "values": values,
        "required": bool(entry.get("isRequired")),
        "_ashby_type": a_type,
        "_ashby_id": entry["id"],
    }, title


# ---------------------------------------------------------------------------
# Build dryrun
# ---------------------------------------------------------------------------

def _is_demographic_label(label: str) -> bool:
    return bool(re.search(r"gender|race|ethnic|hispanic|latin|veteran|disabilit|self[- ]?identif|lgbt",
                          label, re.I))


def build_dryrun(personal: dict, role_url: str) -> dict:
    org, job_id = parse_ashby_url(role_url)
    posting = fetch_form(org, job_id)

    # Inject runtime context for resolvers (why-company essay).
    personal = dict(personal)
    personal["_company_name"] = (
        personal.get("_company_name")
        or org.replace("-", " ").title()
    )
    tmpl_path = PROJECT_ROOT / "why-company-template.md"
    if tmpl_path.exists():
        raw = tmpl_path.read_text()
        if "---" in raw:
            raw = raw.split("---", 2)[-1]
        personal["_why_company_template"] = raw.strip()

    # Track-match CURRENT TITLE to the role applied to (Cyrus 2026-06-02) — same fix as
    # greenhouse_dryrun: don't freeze 'current title' form answers at the static profile
    # value regardless of role. PM->Product Manager, TPM->Technical Program Manager, etc.;
    # non-PM-family (SE/FDE) returns None -> keep static profile title (no PM inflation).
    _tgt_title = posting.get("title") or ""
    if _tgt_title:
        try:
            from tailor_resume import resolve_headline_title, detect_family
            _matched = resolve_headline_title(_tgt_title, detect_family(_tgt_title))
            if _matched:
                es = dict(personal.get("experience_summary") or {})
                es["current_title"] = _matched
                personal["experience_summary"] = es
        except Exception:
            pass

    fields_out: list[dict] = []
    unresolved: list[dict] = []
    blockers: list[dict] = []

    form = posting.get("applicationForm") or {}
    for sec in form.get("sections") or []:
        sec_title = sec.get("title") or ""
        for fe in sec.get("fieldEntries") or []:
            if fe.get("isHidden"):
                continue
            gh_field, label = adapt_field(fe)
            required = gh_field["required"]
            # Thread label into the field dict so resolvers (e.g. location_ack)
            # can inspect it; gh.resolve_field also gets `label` directly.
            gh_field["_label_for_resolver"] = label
            entry = gh.resolve_field(personal, label, required, gh_field,
                                     rules=_ASHBY_COMBINED_RULES)

            # Ashby "acknowledgment" pattern: required MultiValueSelect with
            # exactly ONE option (e.g. "I confirm I have read the above.",
            # "I acknowledge that I have opened, read, and understood the
            # Arbitration Agreement..."). The only acceptable answer is to
            # check that one option.
            # Also covers ValueSelect with exactly one option (Sentry's
            # "I have read and acknowledge Sentry's Applicant Privacy Policy."
            # is rendered as a single-radio ValueSelect).
            if (entry["status"] in ("unresolved", "filled_needs_review")
                    and gh_field["_ashby_type"] in ("MultiValueSelect", "ValueSelect")
                    and required
                    and entry.get("options") and len(entry["options"]) == 1):
                only = entry["options"][0]["label"]
                entry["value"] = only
                entry["status"] = "filled"
                entry["source"] = "ashby_single_option_ack (auto-checked the only option)"

            # Ashby acknowledgment: required Boolean checkbox tied to a
            # consent / policy / agreement statement. Default to Yes/True
            # when the label looks like a passive consent.
            if (entry["status"] == "unresolved"
                    and gh_field["_ashby_type"] == "Boolean"
                    and required
                    and re.search(r"\b(confirm|acknowledg|consent|agree|read|understood|accept|in person|anchor day|policy)\b",
                                   label, re.I)):
                entry["value"] = "Yes"
                entry["status"] = "filled"
                entry["source"] = "ashby_required_ack_boolean (default Yes for consent-style)"

            # Carry Ashby-specific metadata through to the spec
            entry["_ashby_type"] = gh_field["_ashby_type"]
            entry["_ashby_id"] = gh_field["_ashby_id"]
            if sec_title:
                entry["section"] = sec_title

            # Ashby Date-widget normalization (cohort fix, 2026-06-08): an Ashby
            # "Date" field is a calendar picker that only commits a YYYY-MM-DD
            # value. Even with the input_date mapping above, guarantee the
            # resolved value is ISO-date-shaped before it reaches the runner's
            # date-picker path; coerce anything non-ISO (prose like "Within 2
            # weeks of offer", a select label, or an empty essay placeholder for
            # a *required* date) to today+14d so the field commits instead of
            # banking "Missing entry". Tag _ashby_date_iso for the runner.
            if gh_field["_ashby_type"] == "Date":
                _dv = (entry.get("value") or "").strip()
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", _dv):
                    from datetime import date as _date, timedelta as _td
                    _iso = (_date.today() + _td(days=14)).isoformat()
                    entry["value"] = _iso
                    if entry["status"] in ("unresolved", "needs_essay",
                                            "filled_needs_review"):
                        entry["status"] = "filled"
                    entry["source"] = (
                        "ashby_date_normalized (calendar widget -> today+14d ISO; "
                        f"was {_dv!r})"
                    )
                entry["_ashby_date_iso"] = entry["value"]

            # EEOC default-to-decline for demographic-shaped questions
            if entry["status"] == "unresolved" and _is_demographic_label(label):
                if entry["options"]:
                    # Pick a sensible decline label that exists in options
                    opts = [o["label"] for o in entry["options"] if o.get("label")]
                    pick = None
                    decline_pool = [
                        "Decline to self-identify",
                        "Decline To Self Identify",
                        "Decline to self identify",
                        "Prefer not to say",
                        "Prefer not to answer",
                        "Prefer not to disclose",
                        "I do not wish to answer",
                        "I don't wish to answer",
                        "I do not want to answer",
                        "I don't want to answer",
                        "Choose not to identify",
                        "Not represented here",
                    ]
                    for cand in decline_pool:
                        for o in opts:
                            if o.strip().lower() == cand.lower() or cand.lower() in o.lower():
                                pick = o
                                break
                        if pick:
                            break
                    entry["value"] = pick or "Decline to self-identify"
                else:
                    entry["value"] = "Decline to self-identify"
                entry["status"] = "declined"
                entry["source"] = "demographics_default (ashby)"
                entry["compliance"] = "eeoc"

            # Essay-style required text/textarea fields are NOT real blockers:
            # cover_answer_generator handles them at the agent layer (Phase 4)
            # and inline_submit.merge_cover_answers_into_plan splices the
            # generated answers into text_fields. Mark them 'needs_essay'
            # (non-blocking) so dryrun reports ready_to_submit=True.
            if (entry["status"] == "unresolved"
                    and gh_field["_ashby_type"] in ("String", "LongText")
                    and required
                    and ("?" in label or _ESSAY_LABEL_RE.search(label) or len(label) > 40)):
                entry["status"] = "needs_essay"
                entry["source"] = "ashby_needs_essay (cover_answer_generator handles at agent layer)"
                entry["value"] = ""  # placeholder; real answer merged in plan

            # Smart-match for select-style fields when canonical answer
            # doesn't exactly match an option label (e.g. resolver returns
            # "Yes" / "Open to relocation" but options are richer like
            # "Yes, and I currently live in the SF Bay Area." or
            # "Open to relocating to SF"). Fires for both filled and
            # filled_needs_review when no exact match exists.
            if (entry["status"] in ("filled", "filled_needs_review")
                    and gh_field["_ashby_type"] in ("ValueSelect", "MultiValueSelect", "Boolean")
                    and entry.get("options")):
                opts = [o["label"] for o in entry["options"] if o.get("label")]
                raw_val = entry["value"]
                want_str = str(raw_val).strip() if raw_val is not None else ""
                want_lc = want_str.lower()
                # Detect exact-match (already good)
                exact = any(o == want_str for o in opts) or any(
                    isinstance(o_dict.get("value"), bool) and str(o_dict["value"]).lower() == want_lc
                    for o_dict in entry["options"]
                )
                if not exact:
                    pick = None
                    rule_fired = None

                    is_yes = want_lc in ("yes", "true") or raw_val is True
                    is_no = want_lc in ("no", "false") or raw_val is False
                    relocation_positive = bool(re.search(r"\b(yes|open|willing|relocat)\b", want_lc)) and not is_no

                    addr = (personal.get("address") or {})
                    city = (addr.get("city") or "").lower()
                    state = (addr.get("state") or "").lower()
                    in_bay_area = ("san francisco" in city or city == "sf"
                                   or city in ("oakland", "berkeley", "palo alto", "mountain view")
                                   or (state in ("ca", "california") and "bay" in city))
                    us_based = state in ("wa", "washington", "ca", "california", "or", "oregon",
                                          "ny", "new york", "tx", "texas") or (
                                              (personal.get("work_authorization") or {}).get("authorized_to_work_us") in (True, "Yes"))

                    # chain_038 (2026-05-31): GUARD against the "WA" plan-emit bug.
                    # Unmapped Boolean questions sometimes inherit Cyrus's state code
                    # ("WA") as the answer string -> no option matches -> field left
                    # blank -> server 'Missing entry'. When options are exactly
                    # ['Yes','No'] and the resolved value is a 2-letter US state, that
                    # value is garbage. Re-derive an HONEST answer from the question
                    # label: gov/military/clearance employment -> No; NYC/tri-state/
                    # relocate-within-commuting -> Yes (policy: always open to relocate
                    # within USA). Anything else -> leave for needs_review (never guess).
                    _US_STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"}
                    if (sorted(o.lower() for o in opts) == ["no", "yes"]
                            and want_str and want_str.strip().upper() in _US_STATES):
                        _ll = (entry.get("label") or "").lower()
                        if any(k in _ll for k in ("government", "military", "state-owned",
                                                  "security clearance", "publicly-funded")):
                            is_yes, is_no = False, True
                            entry["source"] = (entry.get("source") or "") + " | chain_038 WA-guard->No(gov)"
                        elif any(k in _ll for k in ("tri-state", "relocate within commuting",
                                                    "nyc metro")) or ("based in nyc" in _ll and "relocat" in _ll):
                            is_yes, is_no = True, False
                            entry["source"] = (entry.get("source") or "") + " | chain_038 WA-guard->Yes(relocate)"
                        else:
                            entry["source"] = (entry.get("source") or "") + " | chain_038 WA-guard: unmapped, needs_review"

                    # Rule 1: Yes/No fields — find option starting with "Yes"/"No"
                    if is_yes:
                        yes_opts = [o for o in opts if o.lower().startswith("yes") or "yes," in o.lower()]
                        if yes_opts:
                            if in_bay_area:
                                pick = next((o for o in yes_opts if re.search(r"bay area|sf|san francisco|currently live", o, re.I)), None)
                            if not pick and not in_bay_area:
                                pick = next((o for o in yes_opts if re.search(r"elsewhere|outside|but", o, re.I)), None)
                            if not pick:
                                pick = yes_opts[0]
                            rule_fired = "yes_specific"
                    elif is_no:
                        no_opts = [o for o in opts if o.lower().startswith("no") or "no," in o.lower() or o.lower() == "no"]
                        if no_opts:
                            pick = no_opts[0]
                            rule_fired = "no_specific"

                    # Rule 1b (chain_p12, 2026-06-10, Klarity 1434): work-auth /
                    # sponsorship-status ValueSelect. The question "Do you require
                    # sponsorship...?" resolves to a negative ("No") for a US
                    # citizen, but the OPTIONS are visa/citizenship statuses
                    # (e.g. "I am a US Citizen / Green Card Holder", "I have an
                    # H-1B...", "I have OPT...") with NO plain "No" option, so
                    # Rule 1 leaves it unmatched -> banks filled_needs_review with
                    # the literal "No" (which matches no option -> submit drops it).
                    # When the profile is a US citizen / green-card holder and the
                    # answer is the no-sponsorship negative, pick the citizen/
                    # green-card status option. Truthful (Cyrus is a US citizen).
                    if not pick and is_no:
                        _wa = (personal.get("work_authorization") or {})
                        _status = str(_wa.get("status") or "").lower()
                        _needs = str(_wa.get("sponsorship_required")
                                     or _wa.get("sponsorship_required_now") or "no").lower()
                        _needs_future = str(_wa.get("sponsorship_required_future") or _needs).lower()
                        _is_citizen = ("citizen" in _status or "green" in _status
                                       or "permanent_resident" in _status
                                       or _wa.get("authorized_to_work_us") in ("yes", True))
                        if (_is_citizen and _needs in ("no", "false", "n", "")
                                and _needs_future in ("no", "false", "n", "")):
                            cit_opts = [o for o in opts if re.search(
                                r"citizen|green\s*card|permanent resident|do not require|don't require|no sponsorship|not require sponsorship",
                                o, re.I)]
                            # never pick an H-1B/OPT/visa-needed option for a citizen
                            cit_opts = [o for o in cit_opts if not re.search(
                                r"h-?1b|opt|stem|f-?1|visa.*require|require.*transfer", o, re.I)]
                            if cit_opts:
                                pick = cit_opts[0]
                                rule_fired = "workauth_citizen_status"

                    # Rule 2: in-office / SF-based acknowledgment
                    if not pick and is_yes:
                        office_opts = [o for o in opts if re.search(
                            r"san francisco based|sf based|in.?office|in.?person|on.?site|onsite", o, re.I)]
                        if office_opts and us_based:
                            pick = office_opts[0]
                            rule_fired = "in_office_ack"

                    # Rule 3: relocation — relocation-positive canonical value
                    if not pick and relocation_positive:
                        relo_opts = [o for o in opts if re.search(
                            r"open to relocat|willing to relocat|relocat", o, re.I)]
                        if relo_opts:
                            pick = next((o for o in relo_opts if re.search(r"^(yes|open)", o, re.I)), relo_opts[0])
                            rule_fired = "relocation"

                    # Rule 4: Generic substring fallback — exactly ONE option
                    # contains the value as a case-insensitive substring.
                    if not pick and want_str:
                        matches = [o for o in opts if want_lc and want_lc in o.lower()]
                        if len(matches) == 1:
                            pick = matches[0]
                            rule_fired = "substring_unique"

                    if pick:
                        entry["value"] = pick
                        entry["status"] = "filled"
                        entry["source"] = (entry["source"] or "") + f" | ashby_smart_match({rule_fired},picked={pick!r})"
                    else:
                        # Demote to needs_review with a flag so we know we tried.
                        if entry["status"] == "filled":
                            entry["status"] = "filled_needs_review"
                            entry["source"] = (entry["source"] or "") + f" | NOTE: '{want_str}' not in options {opts}"
                        entry["match_attempted"] = True

            fields_out.append(entry)
            if entry["status"] == "unresolved":
                unresolved.append({
                    "id": entry["id"], "label": entry["label"],
                    "required": required, "reason": entry["source"],
                })
                if required:
                    blockers.append({
                        "id": entry["id"], "label": entry["label"],
                        "reason": entry["source"],
                    })

    counts = {
        "total_fields": len(fields_out),
        "filled": sum(1 for f in fields_out if f["status"] == "filled"),
        "filled_needs_review": sum(1 for f in fields_out if f["status"] == "filled_needs_review"),
        "declined": sum(1 for f in fields_out if f["status"] == "declined"),
        "needs_essay": sum(1 for f in fields_out if f["status"] == "needs_essay"),
        "unresolved": len(unresolved),
        "blockers": len(blockers),
    }

    return {
        "ats": "ashby",
        "role_url": role_url,
        "org": org,
        "job_id": job_id,
        "job_title": posting.get("title"),
        "job_location": posting.get("locationName"),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api_url": GQL_URL,
        "ready_to_submit": counts["blockers"] == 0,
        "counts": counts,
        "fields": fields_out,
        "unresolved": unresolved,
        "blockers": blockers,
    }


def write_dryrun(report: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f'{report["org"]}-{report["job_id"]}.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Dry-run Ashby application fill spec generator (NO SUBMIT).")
    ap.add_argument("urls", nargs="*", help="One or more Ashby role URLs (jobs.ashbyhq.com/<org>/<uuid>).")
    ap.add_argument("--org", help="Org slug (alternative to URL).")
    ap.add_argument("--job-id", help="Job UUID (alternative to URL).")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if not PERSONAL_INFO_PATH.exists():
        print(f"ERROR: missing {PERSONAL_INFO_PATH}", file=sys.stderr)
        return 2
    personal = json.loads(PERSONAL_INFO_PATH.read_text())

    urls: list[str] = list(args.urls)
    if args.org and args.job_id:
        urls.append(f"https://jobs.ashbyhq.com/{args.org}/{args.job_id}")
    if not urls:
        ap.print_help()
        return 1

    rc = 0
    for url in urls:
        try:
            report = build_dryrun(personal, url)
            path = write_dryrun(report)
            if not args.quiet:
                c = report["counts"]
                ready = "READY" if report["ready_to_submit"] else f"BLOCKED({c['blockers']})"
                print(f"{ready:11} {report['org']}/{report['job_id']:>36} -> {path.name}  "
                      f"filled={c['filled']} review={c['filled_needs_review']} declined={c['declined']} unresolved={c['unresolved']}  "
                      f"({report['job_title']})")
        except Exception as e:
            rc = 1
            print(f"ERROR processing {url}: {e}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
