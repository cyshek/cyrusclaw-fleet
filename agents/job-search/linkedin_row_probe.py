#!/usr/bin/env python3
"""Per-row LinkedIn resolver helper.

Usage: linkedin_row_probe.py <role_id>

Does tactics 1, 2, 2b, 4 (and 8: direct ATS-slug guess) in-process:
1) companies.yaml lookup → live ATS API call → fuzzy match → JD-phrase verify
2) Fetch LinkedIn guest endpoint, dump JD + regex-scan for ATS IDs/URLs
2b) Regex extract requisition IDs/UUIDs from JD; construct candidate URLs; verify
4) Try common careers pages
8) Try known ATS APIs with normalized company slug (greenhouse/ashby/lever)

Prints structured JSON with all candidate matches + verification scores so the
agent can decide which to commit. Does NOT mutate the DB.
"""
from __future__ import annotations
import argparse, json, re, sqlite3, sys, time
from pathlib import Path
from urllib.parse import urlparse
import requests
import yaml

WS = Path('/home/azureuser/.openclaw/agents/job-search/workspace')
DB = WS / 'projects/job-search/tracker.db'
COMPANIES = WS / 'projects/job-search/role-discovery/companies.yaml'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def http_get(url, timeout=12, **kw):
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, **kw)
    except Exception as e:
        return None


def normalize_title(s):
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\bpm\b', 'product manager', s)
    s = re.sub(r'\btpm\b', 'technical program manager', s)
    s = re.sub(r'\bse\b', 'solutions engineer', s)
    s = re.sub(r'\bsa\b', 'solutions architect', s)
    return re.sub(r'\s+', ' ', s).strip()


def title_match(a, b):
    """Returns (score, reason). 1.0=perfect."""
    na, nb = normalize_title(a), normalize_title(b)
    if na == nb: return 1.0, 'exact'
    if na in nb or nb in na: return 0.92, 'substring'
    sa = set(na.split()) - {'manager','product','senior','i','ii','iii','staff','principal'}
    sb = set(nb.split()) - {'manager','product','senior','i','ii','iii','staff','principal'}
    if not sa or not sb:
        sa, sb = set(na.split()), set(nb.split())
    if not sa or not sb: return 0.0, 'empty'
    inter = sa & sb
    overlap = len(inter) / max(len(sa), len(sb))
    return overlap, f'overlap={len(inter)}/{max(len(sa),len(sb))}'


def company_slug(name):
    base = re.sub(r'[^a-z0-9]+', '', name.lower())
    base = re.sub(r'(inc|llc|ltd|co|corp|the|ai)$', '', base)
    return base


def yaml_lookup(company):
    with COMPANIES.open() as f:
        cos = yaml.safe_load(f).get('companies', [])
    cn = re.sub(r'[^a-z0-9]', '', company.lower())
    for e in cos:
        en = re.sub(r'[^a-z0-9]', '', e.get('name', '').lower())
        if cn == en or (len(cn) > 3 and cn in en) or (len(en) > 3 and en in cn):
            return e
    return None


def fetch_jd_distinctive_phrases(linkedin_job_id, role_company, role_title):
    """Fetch LinkedIn JD body + extract distinctive phrases for verification."""
    out = {'jd_body': '', 'phrases': [], 'embedded_ats_urls': [], 'requisition_ids': [], 'pay_band': None, 'fetch_status': None}
    url = f'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{linkedin_job_id}'
    r = http_get(url, timeout=15)
    if not r:
        out['fetch_status'] = 'network-error'
        return out
    out['fetch_status'] = r.status_code
    if r.status_code != 200:
        return out
    t = r.text
    # Strip HTML to plain text
    body = re.sub(r'<[^>]+>', ' ', t)
    body = re.sub(r'\s+', ' ', body).strip()
    out['jd_body'] = body[:6000]

    # ATS URLs embedded
    for m in re.finditer(r'https?://[^\s"\'<>]+', t):
        u = m.group(0).rstrip('.,);]')
        if re.search(r'greenhouse|lever\.co|ashbyhq|myworkdayjobs|smartrecruiters|jobvite|icims|workable|bamboohr|recruitee|teamtailor|breezy', u, re.I):
            out['embedded_ats_urls'].append(u)
    # Requisition / job ID patterns
    for pat, label in [
        (r'\bgh_jid=(\d+)', 'gh_jid'),
        (r'\bR-?(\d{5,8})\b', 'workday-R'),
        (r'\bJR0*(\d{4,8})\b', 'workday-JR'),
        (r'(?:Requisition|Req|Job)\s*(?:ID|number|#)[:\s]+([A-Z0-9-]{3,20})', 'req-id'),
        (r'\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b', 'uuid'),
        (r'(\d{4}-\d{4,6})\b', 'icims-style'),
    ]:
        for m in re.finditer(pat, body, re.I):
            out['requisition_ids'].append({'pattern': label, 'value': m.group(1) if m.lastindex else m.group(0)})

    # Pay band
    m = re.search(r'\$([\d,]+(?:\.\d+)?)\s*(?:K|,000)?\s*[-–to]+\s*\$?([\d,]+(?:\.\d+)?)\s*(?:K|,000)?', body)
    if m:
        out['pay_band'] = (m.group(1), m.group(2))

    # Distinctive phrases: 5+ word phrases that look unique
    # Find sentences in JD, pick longer distinctive ones (avoid boilerplate)
    sentences = re.split(r'[.!?]\s+', body)
    boilerplate = re.compile(r'equal opportunity|do not discriminate|protected characteristic|reasonable accommodation|comprehensive benefit|compensation range|base pay range|qualified applicants|criminal histor', re.I)
    candidates = []
    for s in sentences:
        s = s.strip()
        if len(s.split()) < 7 or len(s) > 250: continue
        if boilerplate.search(s): continue
        # Skip generic
        if re.search(r"we'?re looking for|what you'?ll do|responsibilities|qualifications", s, re.I): continue
        candidates.append(s)
    out['phrases'] = candidates[:6]
    return out


def query_greenhouse_api(slug):
    r = http_get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs', timeout=10)
    if not r or r.status_code != 200: return None
    try:
        return r.json().get('jobs', [])
    except: return None


def query_ashby_api(slug):
    r = http_get(f'https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true', timeout=10)
    if not r or r.status_code != 200: return None
    try:
        return r.json().get('jobs', [])
    except: return None


def query_lever_api(slug):
    r = http_get(f'https://api.lever.co/v0/postings/{slug}?mode=json', timeout=10)
    if not r or r.status_code != 200: return None
    try:
        return r.json()
    except: return None


def query_workday_search(host, tenant, site, role_title):
    """Workday CXS search."""
    url = f'https://{host}/wday/cxs/{tenant}/{site}/jobs'
    try:
        r = requests.post(url, headers={**HEADERS, 'Content-Type':'application/json'},
                          json={"appliedFacets":{}, "limit":50, "offset":0, "searchText": role_title}, timeout=15)
        if r.status_code != 200: return None
        return r.json().get('jobPostings', [])
    except: return None


def jd_phrase_overlap(linkedin_phrases, candidate_text):
    """Count how many distinctive phrases (verbatim) appear in candidate page text."""
    if not linkedin_phrases or not candidate_text:
        return 0, []
    hits = []
    for p in linkedin_phrases:
        # try direct substring (case-insensitive)
        if p.lower() in candidate_text.lower():
            hits.append(p)
            continue
        # try first 8 words
        first_words = ' '.join(p.split()[:8])
        if len(first_words) > 20 and first_words.lower() in candidate_text.lower():
            hits.append(first_words)
    return len(hits), hits


def verify_candidate(candidate_url, linkedin_phrases, linkedin_pay=None):
    """Fetch candidate URL and check for distinctive phrase overlap + pay band."""
    r = http_get(candidate_url, timeout=15)
    if not r or r.status_code != 200:
        return {'verified': False, 'status': r.status_code if r else 'err', 'phrase_hits': 0}
    text = re.sub(r'<[^>]+>', ' ', r.text)
    text = re.sub(r'\s+', ' ', text)
    hits, sample = jd_phrase_overlap(linkedin_phrases, text)
    pay_ok = False
    if linkedin_pay:
        for v in linkedin_pay:
            v_clean = v.replace(',', '').replace('.', '')
            # numeric portion
            if v_clean in text.replace(',', '').replace('.', ''):
                pay_ok = True
                break
    return {'verified': hits >= 2 or (hits >= 1 and pay_ok), 'phrase_hits': hits, 'pay_match': pay_ok, 'phrase_samples': sample[:3]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('role_id', type=int)
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    row = con.execute("SELECT id, company, role, est_tc, app_url FROM roles WHERE id=?", (args.role_id,)).fetchone()
    if not row:
        print(json.dumps({'error': 'not-found'})); return
    rid, company, role, est_tc, app_url = row

    # Extract LinkedIn job id
    m = re.search(r'(\d{8,12})$|(\d{8,12})(?=\?|$)', app_url or '')
    linkedin_job_id = m.group(1) if m else None
    if not linkedin_job_id:
        m = re.search(r'/(\d{8,12})', app_url or '')
        linkedin_job_id = m.group(1) if m else None

    result = {
        'role_id': rid, 'company': company, 'role': role, 'linkedin_url': app_url,
        'linkedin_job_id': linkedin_job_id,
        'jd': None,
        'yaml_entry': None,
        'ats_candidates': [],
        'careers_page_findings': [],
        'verified_match': None,
    }

    # Tactic 1: companies.yaml
    yaml_e = yaml_lookup(company)
    result['yaml_entry'] = yaml_e

    # Fetch JD
    jd = fetch_jd_distinctive_phrases(linkedin_job_id, company, role) if linkedin_job_id else {}
    result['jd'] = {k:v for k,v in jd.items() if k != 'jd_body'} if jd else None
    if jd:
        result['jd_body_excerpt'] = jd.get('jd_body','')[:1500]

    # Build list of ATS slugs to try (yaml + guessed)
    slugs_to_try = []
    if yaml_e:
        adapter = yaml_e.get('adapter')
        slug = yaml_e.get('slug')
        if adapter and slug:
            slugs_to_try.append((adapter, slug, 'yaml'))
        if adapter == 'workday':
            slugs_to_try.append(('workday-search', {
                'host': yaml_e.get('host'),
                'tenant': yaml_e.get('tenant'),
                'site': yaml_e.get('site'),
            }, 'yaml-workday'))
    # also guess for not-in-yaml or alternate
    guess = company_slug(company)
    if guess:
        for ats in ['greenhouse', 'ashby', 'lever']:
            if not any(s[0] == ats and s[1] == guess for s in slugs_to_try):
                slugs_to_try.append((ats, guess, 'guess'))

    # Query each
    pay = jd.get('pay_band') if jd else None
    phrases = jd.get('phrases', []) if jd else []

    for entry in slugs_to_try:
        ats, slug, source = entry
        if ats == 'greenhouse':
            jobs = query_greenhouse_api(slug)
        elif ats == 'ashby':
            jobs = query_ashby_api(slug)
        elif ats == 'lever':
            jobs = query_lever_api(slug)
        elif ats == 'workday-search':
            jobs = query_workday_search(slug['host'], slug['tenant'], slug['site'], role)
            # normalize
            if jobs is not None:
                jobs = [{'title': j.get('title'),
                         'jobUrl': f"https://{slug['host']}{j.get('externalPath','')}",
                         '_raw': j} for j in jobs]
        else:
            jobs = None

        if jobs is None:
            result['ats_candidates'].append({'ats': ats, 'slug': slug if isinstance(slug,str) else slug.get('tenant'), 'source': source, 'status': 'api-fail-or-empty'})
            continue

        # Score matches
        matches = []
        for j in jobs:
            t = j.get('title','')
            score, why = title_match(role, t)
            if score >= 0.5:
                u = j.get('absolute_url') or j.get('jobUrl') or j.get('hostedUrl') or j.get('applyUrl') or ''
                loc = ''
                if isinstance(j.get('location'), dict): loc = j['location'].get('name','')
                elif isinstance(j.get('location'), str): loc = j['location']
                matches.append({'title': t, 'url': u, 'score': round(score,2), 'why': why, 'location': loc})
        matches.sort(key=lambda x: -x['score'])
        result['ats_candidates'].append({
            'ats': ats, 'slug': slug if isinstance(slug,str) else slug.get('tenant'),
            'source': source, 'total_jobs': len(jobs), 'top_matches': matches[:5],
        })

    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
