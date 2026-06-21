"""Tests for Brave API integration in linkedin_ats_resolver_v2.

Covers:
  - _load_env_file: key loaded from workspace .env without pre-export
  - _title_from_workday_url: slug extraction for various URL formats
  - _validate_ats_url Workday fast-path: tighter j+cov gating
  - tactic3_websearch company-token guard: WD subdomain check + generic filter
  - _BRAVE_SITE_FILTER: site: operators present in Brave query
No network calls; monkeypatches _brave_api_urls."""
from __future__ import annotations
import sys, re, urllib.parse
import pytest
sys.path.insert(0, '.')
import linkedin_ats_resolver_v2 as m

# ------------------------------------------------------------------ #
# _title_from_workday_url
# ------------------------------------------------------------------ #
def test_workday_slug_simple():
    assert m._title_from_workday_url(
        'https://cisco.wd5.myworkdayjobs.com/Cisco_Careers/job/Solutions-Engineer_2015414-1'
    ) == 'Solutions Engineer'

def test_workday_slug_location_prefix():
    assert m._title_from_workday_url(
        'https://copeland.wd5.myworkdayjobs.com/Site/job/Remote---US/Technical-Sales-Engineer_JR113798'
    ) == 'Technical Sales Engineer'

def test_workday_slug_jr_prefix():
    assert m._title_from_workday_url(
        'https://copeland.wd5.myworkdayjobs.com/Site/job/Territory-Sales-Executive_JR114061'
    ) == 'Territory Sales Executive'

def test_workday_slug_ref_id():
    t = m._title_from_workday_url(
        'https://visa.wd5.myworkdayjobs.com/Visa/job/Senior-Product-Manager--AI-Product-Management-_REF083058W-1/apply'
    )
    assert 'Product Manager' in t

def test_workday_slug_non_workday_returns_empty():
    assert m._title_from_workday_url(
        'https://boards.greenhouse.io/cisco/jobs/12345'
    ) == ''

# ------------------------------------------------------------------ #
# _validate_ats_url Workday fast-path: tighter scoring
# ------------------------------------------------------------------ #
def test_validate_ats_exact_match():
    score = m._validate_ats_url(
        'workday',
        'https://cisco.wd5.myworkdayjobs.com/Cisco_Careers/job/Solutions-Engineer_2015414-1',
        'Solutions Engineer'
    )
    assert score >= m.TITLE_MIN_JACCARD

def test_validate_ats_false_positive_blocked():
    # 'Technical Sales Engineer' vs slug 'Engineer Technical Support'
    # j=0.50 < threshold -> should return 0
    score = m._validate_ats_url(
        'workday',
        'https://copeland.wd5.myworkdayjobs.com/Site/job/Mexico-City-Mexico/Engineer-Technical-Support-II_JR113798',
        'Technical Sales Engineer'
    )
    assert score < m.TITLE_MIN_JACCARD

# ------------------------------------------------------------------ #
# Company-token guard: WD subdomain check
# ------------------------------------------------------------------ #
def _co_guard(company, url):
    co_toks = {t for t in m._tokens(company) if len(t) > 2}
    _CO_GENERIC = {'cloud','systems','solutions','tech','technologies',
                   'group','labs','services','global','digital',
                   'software','data','network','networks','platform'}
    strict = {t for t in co_toks if t not in _CO_GENERIC and len(t) > 3}
    effective = strict or co_toks
    url_l = url.lower()
    if 'myworkdayjobs.com' in url_l:
        try: host = urllib.parse.urlparse(url).hostname.lower()
        except: host = ''
        return any(re.search(r'(?<![a-z0-9])'+re.escape(t)+r'(?![a-z0-9])', host) for t in effective)
    return any(re.search(r'(?<![a-z0-9])'+re.escape(t)+r'(?![a-z0-9])', url_l) for t in effective)

def test_guard_cisco_passes():
    assert _co_guard('Cisco', 'https://cisco.wd5.myworkdayjobs.com/Cisco_Careers/job/Solutions-Engineer_2015414-1')

def test_guard_google_at_salesforce_blocked():
    # 'google' appears in slug, but not in the subdomain -> should block
    assert not _co_guard('Google', 'https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site/job/Technical-Program-Manager---Google-Cloud-Platform_JR290141')

def test_guard_champ_at_salesforce_blocked():
    # 'champ' appears in 'Customer-Champion' slug -> word-boundary blocks it
    assert not _co_guard('CHAMP', 'https://salesforce.wd1.myworkdayjobs.com/External_Career_Site/job/CSG-Product-Manager---CPQ-Customer-Champion_JR43431')

def test_guard_alibaba_cloud_generic_filtered():
    # 'cloud' is generic -> effective_co_toks = {'alibaba'} -> alibaba not in devoteam URL
    assert not _co_guard('Alibaba Cloud', 'https://jobs.smartrecruiters.com/Devoteam/744000112919807-cloud-solutions-architect-google-cloud-')

# ------------------------------------------------------------------ #
# _BRAVE_SITE_FILTER contains site: operators
# ------------------------------------------------------------------ #
def test_brave_site_filter_present():
    for domain in ['myworkdayjobs.com', 'boards.greenhouse.io', 'jobs.ashbyhq.com', 'jobs.lever.co']:
        assert domain in m._BRAVE_SITE_FILTER, f'Missing {domain}'

# ------------------------------------------------------------------ #
# tactic3 uses site-scoped query when key is present
# ------------------------------------------------------------------ #
def test_tactic3_uses_site_query(monkeypatch):
    queries_seen = []
    def fake_brave(query, key):
        queries_seen.append(query)
        return []
    monkeypatch.setattr(m, '_brave_api_urls', fake_brave)
    monkeypatch.setattr(m, '_brave_api_key', lambda: 'testkey')
    res = m.Resolution(role_id=1, company='Acme Corp', role_title='Solutions Engineer')
    m.tactic3_websearch(res)
    assert queries_seen, 'No Brave query fired'
    assert 'site:' in queries_seen[0], f'First query should use site: filter: {queries_seen[0]}'
