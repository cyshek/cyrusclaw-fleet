#!/usr/bin/env python3
"""Phase A/B batch resolver. Tactics 1 (yaml lookup) + 8 (slug guess).

- For each remaining LinkedIn-raw row:
    a) Try yaml-listed ATS API (greenhouse/ashby/lever)
    b) Try slug-guess across greenhouse/ashby/lever using normalized company name
    c) Title fuzzy-match, pick best
    d) If score >= 0.95 AND there's exactly one strong candidate: AUTO-COMMIT
    e) Otherwise: emit a "needs-review" record with all candidates

- Outputs:
    - Auto-commits to DB
    - Writes _linkedin-resolve-phase-a-pending.json with rows needing review

Usage: linkedin_phase_a.py [--commit-threshold 0.95] [--dry-run]
"""
from __future__ import annotations
import argparse, json, re, sqlite3, sys, time
from datetime import datetime
from pathlib import Path
import requests
import yaml
import concurrent.futures as cf

WS = Path('/home/azureuser/.openclaw/agents/job-search/workspace')
DB = WS / 'projects/job-search/tracker.db'
COMPANIES = WS / 'projects/job-search/role-discovery/companies.yaml'
LOG = WS / 'projects/job-search/applications/_linkedin-resolve-20260524.log'
PENDING_OUT = WS / 'projects/job-search/applications/_linkedin-resolve-phase-a-pending.json'

HEADERS = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}

# Cache ATS API responses per slug to avoid duplicate work
ATS_CACHE = {}


def normalize_title(s):
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\bpm\b', 'product manager', s)
    s = re.sub(r'\btpm\b', 'technical program manager', s)
    s = re.sub(r'\bse\b', 'solutions engineer', s)
    s = re.sub(r'\bsa\b', 'solutions architect', s)
    return re.sub(r'\s+', ' ', s).strip()


def title_match(a, b):
    na, nb = normalize_title(a), normalize_title(b)
    if na == nb: return 1.0
    if na in nb or nb in na: return 0.92
    sa = set(na.split()) - {'manager','product','senior','i','ii','iii','staff','principal'}
    sb = set(nb.split()) - {'manager','product','senior','i','ii','iii','staff','principal'}
    if not sa or not sb: sa, sb = set(na.split()), set(nb.split())
    if not sa or not sb: return 0.0
    return len(sa & sb) / max(len(sa), len(sb))


def slug_candidates(name):
    base = re.sub(r'[^a-z0-9]+', '', name.lower())
    base = re.sub(r'(inc|llc|ltd|co|corp|the|ai)$', '', base)
    hyphen = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    hyphen = re.sub(r'-(inc|llc|ltd|co|corp|the)$', '', hyphen)
    out = []
    for s in [base, hyphen]:
        if s and s not in out: out.append(s)
    # also extra: append common variants
    if base:
        for suf in ['inc','tech','hq','ai','labs']:
            v = base + suf
            if v not in out: out.append(v)
    return out


def fetch_ats(ats, slug):
    key = (ats, slug)
    if key in ATS_CACHE: return ATS_CACHE[key]
    try:
        if ats == 'greenhouse':
            r = requests.get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true', headers=HEADERS, timeout=12)
            if r.status_code == 200:
                ATS_CACHE[key] = r.json().get('jobs', [])
            else:
                ATS_CACHE[key] = None
        elif ats == 'ashby':
            r = requests.get(f'https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true', headers=HEADERS, timeout=12)
            if r.status_code == 200:
                ATS_CACHE[key] = r.json().get('jobs', [])
            else:
                ATS_CACHE[key] = None
        elif ats == 'lever':
            r = requests.get(f'https://api.lever.co/v0/postings/{slug}?mode=json', headers=HEADERS, timeout=12)
            if r.status_code == 200:
                ATS_CACHE[key] = r.json()
            else:
                ATS_CACHE[key] = None
        else:
            ATS_CACHE[key] = None
    except Exception:
        ATS_CACHE[key] = None
    return ATS_CACHE[key]


def fetch_jd_phrases(linkedin_job_id):
    """Fetch LinkedIn JD body and extract distinctive phrases for verification."""
    if not linkedin_job_id: return [], ''
    try:
        r = requests.get(f'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{linkedin_job_id}',
                         headers=HEADERS, timeout=12)
        if r.status_code != 200: return [], ''
        body = re.sub(r'<[^>]+>', ' ', r.text)
        body = re.sub(r'\s+', ' ', body).strip()
        # Pick distinctive phrases
        boilerplate = re.compile(r'equal opportunity|do not discriminate|protected characteristic|reasonable accommodation|comprehensive benefit|compensation range|base pay range|qualified applicants|criminal histor|Sign in Sign in|By clicking Continue|Privacy Policy', re.I)
        sentences = re.split(r'[.!?]\s+', body)
        candidates = []
        for s in sentences:
            s = s.strip()
            if len(s.split()) < 7 or len(s) > 220: continue
            if boilerplate.search(s): continue
            if re.search(r"we'?re looking for|what you'?ll do|responsibilities|qualifications", s, re.I): continue
            candidates.append(s)
        return candidates[:8], body
    except Exception:
        return [], ''


def ats_job_body(ats, slug, jid):
    jobs = fetch_ats(ats, slug)
    if not jobs: return ''
    for j in jobs:
        if ats == 'greenhouse' and j.get('id') == jid:
            return re.sub(r'<[^>]+>', ' ', j.get('content','') or '')
        if ats == 'ashby' and j.get('id') == jid:
            return j.get('descriptionPlain','') or ''
        if ats == 'lever' and j.get('id') == jid:
            return re.sub(r'<[^>]+>',' ', j.get('descriptionPlain') or j.get('description','') or '')
    return ''


def phrase_verify(phrases, candidate_text):
    if not phrases or not candidate_text: return 0, []
    ct = re.sub(r'\s+',' ', candidate_text).lower()
    hits = []
    for p in phrases:
        if p.lower() in ct:
            hits.append(p[:60])
            continue
        first8 = ' '.join(p.split()[:8])
        if len(first8) > 25 and first8.lower() in ct:
            hits.append(first8[:60])
    return len(hits), hits


def normalize_job(ats, j):
    if ats == 'greenhouse':
        loc = j.get('location', {})
        loc = loc.get('name','') if isinstance(loc, dict) else (loc or '')
        return {'title': j.get('title',''), 'url': j.get('absolute_url',''), 'id': j.get('id'), 'location': loc}
    elif ats == 'ashby':
        return {'title': j.get('title',''), 'url': j.get('jobUrl',''), 'id': j.get('id'), 'location': j.get('locationName','')}
    elif ats == 'lever':
        return {'title': j.get('text',''), 'url': j.get('hostedUrl',''), 'id': j.get('id'),
                'location': j.get('categories',{}).get('location','')}
    return {}


def yaml_index():
    with COMPANIES.open() as f:
        cos = yaml.safe_load(f).get('companies', [])
    idx = {}
    for e in cos:
        n = re.sub(r'[^a-z0-9]', '', e.get('name','').lower())
        idx[n] = e
    return idx


def yaml_lookup(company, idx):
    cn = re.sub(r'[^a-z0-9]', '', company.lower())
    if cn in idx: return idx[cn]
    for k, v in idx.items():
        if len(cn)>3 and (cn in k or k in cn):
            return v
    return None


def is_us_location(loc):
    if not loc: return True  # don't filter
    L = loc.lower()
    if 'united states' in L or ' us' in L or 'usa' in L or 'remote' in L: return True
    states = ['ca','ny','tx','wa','ma','il','co','ga','fl','pa','va','az','nc','oh','mi','or','dc']
    for s in states:
        if re.search(rf'\b{s}\b', L, re.I): return True
    intl = ['india','singapore','japan','germany','uk','london','dublin','toronto','canada','poland','israel','spain','france','china','korea','brazil','mexico','australia']
    return not any(i in L for i in intl)


def best_match(role_title, jobs, ats):
    norm_jobs = [normalize_job(ats, j) for j in jobs]
    scored = []
    for nj in norm_jobs:
        score = title_match(role_title, nj['title'])
        if score >= 0.5:
            scored.append({**nj, 'score': round(score,3)})
    scored.sort(key=lambda x: -x['score'])
    # prefer US locations among top scoring
    if scored:
        top_score = scored[0]['score']
        top = [s for s in scored if s['score'] == top_score]
        us = [s for s in top if is_us_location(s['location'])]
        if us and top != us:
            scored = us + [s for s in scored if s not in us]
    return scored


def get_targets(con):
    q = """SELECT id, company, role, est_tc, app_url FROM roles
WHERE source_key LIKE 'linkedin:%' AND (status IS NULL OR status='') AND applied_by IS NULL
  AND (app_url LIKE '%linkedin.com%' OR app_url IS NULL)
  AND (agent_notes IS NULL OR agent_notes NOT LIKE 'LINKEDIN-RESOLVE 2026-05-24%')
ORDER BY CASE WHEN est_tc IS NULL THEN 1 WHEN est_tc >= 180000 THEN 0 ELSE 2 END,
         CASE WHEN est_tc >= 180000 THEN -est_tc ELSE est_tc END"""
    return con.execute(q).fetchall()


def derive_source_key(ats, slug, jid):
    return f'{ats}:{slug}:{jid}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--commit-threshold', type=float, default=0.99)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    idx = yaml_index()
    con = sqlite3.connect(DB)
    targets = get_targets(con)
    if args.limit: targets = targets[:args.limit]
    print(f'[init] targets: {len(targets)}', flush=True)

    pending = []
    committed = 0
    no_candidates = 0
    log = LOG.open('a')

    for i, (rid, company, role, est_tc, app_url) in enumerate(targets, 1):
        # Build slug list to probe
        attempts = []  # (ats, slug, source)
        ye = yaml_lookup(company, idx)
        if ye:
            adapter = ye.get('adapter')
            slug = ye.get('slug')
            if adapter in ('greenhouse','ashby','lever') and slug:
                attempts.append((adapter, slug, 'yaml'))
        for s in slug_candidates(company):
            for ats in ['greenhouse','ashby','lever']:
                key = (ats, s)
                if not any(a[0]==ats and a[1]==s for a in attempts):
                    attempts.append((ats, s, 'guess'))

        # Try each
        all_matches = []
        for ats, slug, source in attempts:
            jobs = fetch_ats(ats, slug)
            if not jobs: continue
            matches = best_match(role, jobs, ats)
            if matches:
                for m in matches[:3]:
                    all_matches.append({'ats': ats, 'slug': slug, 'source': source, **m})

        all_matches.sort(key=lambda x: -x['score'])

        # Decision
        if not all_matches:
            no_candidates += 1
            pending.append({'id': rid, 'company': company, 'role': role, 'linkedin_url': app_url,
                            'reason': 'no-ats-candidates', 'attempts': len(attempts), 'matches': []})
            print(f'[{i}/{len(targets)}] id={rid} {company} | {role[:45]} -> NO CANDIDATES', flush=True)
            continue

        top = all_matches[0]
        # If top score is exactly 1.0 and second is < 1.0 OR matching ats/slug for a unique title,
        # auto-commit only when top.score >= threshold and (second.score < top.score - 0.07 or same URL)
        second = all_matches[1] if len(all_matches) > 1 else None
        unique_top_url = (second is None) or (top['url'] == second['url']) or (top['score'] - second['score'] >= 0.07)

        # If candidate is plausible, JD-phrase verify before committing
        verified_phrase_hits = 0
        if top['score'] >= args.commit_threshold and unique_top_url and is_us_location(top['location']):
            # Extract linkedin id
            m = re.search(r'(\d{8,12})(?:\?|$)', app_url or '')
            ljid = m.group(1) if m else None
            phrases, _ = fetch_jd_phrases(ljid)
            cand_text = ats_job_body(top['ats'], top['slug'], top['id'])
            verified_phrase_hits, hits_samples = phrase_verify(phrases, cand_text)
            top['_phrase_hits'] = verified_phrase_hits
            top['_phrase_samples'] = hits_samples[:3]

        if top['score'] >= args.commit_threshold and unique_top_url and is_us_location(top['location']) and verified_phrase_hits >= 1:
            # Commit
            sk = derive_source_key(top['ats'], top['slug'], top['id'])
            note = f"LINKEDIN-RESOLVE 2026-05-24: resolved via tactic1+8 (auto-batch, {top['ats']}:{top['slug']} score={top['score']}, JD-phrase-hits={verified_phrase_hits}) | original: {app_url}"
            if not args.dry_run:
                try:
                    con.execute("UPDATE roles SET app_url=?, source_key=?, agent_notes=? WHERE id=?",
                                (top['url'], sk, note, rid))
                    con.commit()
                    log.write(f'{datetime.now().isoformat(timespec="seconds")} | id={rid} | {company} | {role} | RESOLVED via tactic1+8 auto-batch ({top["ats"]}:{top["slug"]} score={top["score"]} JD-hits={verified_phrase_hits}, loc={top["location"]}): {top["url"]}\n')
                except sqlite3.IntegrityError as ie:
                    # Duplicate source_key already exists (another row already maps there).
                    note_dup = f"LINKEDIN-RESOLVE 2026-05-24: candidate-found-but-duplicate-of-existing-source-key {sk}; needs-manual-dedupe | original: {app_url}"
                    con.execute("UPDATE roles SET agent_notes=? WHERE id=?", (note_dup, rid))
                    con.commit()
                    log.write(f'{datetime.now().isoformat(timespec="seconds")} | id={rid} | {company} | {role} | DUPLICATE source_key={sk} (existing row already maps here): {top["url"]}\n')
                    committed += 0
                    pending.append({'id': rid, 'company': company, 'role': role, 'linkedin_url': app_url,
                                    'reason': 'duplicate-source-key', 'top_matches': [top]})
                    print(f'[{i}/{len(targets)}] id={rid} {company} | {role[:45]} -> DUPLICATE sk={sk}', flush=True)
                    continue
            committed += 1
            print(f'[{i}/{len(targets)}] id={rid} {company} | {role[:45]} -> COMMIT {top["ats"]}:{top["slug"]} | {top["title"]} | hits={verified_phrase_hits} | {top["location"][:25]}', flush=True)
        else:
            reason = 'needs-review'
            if top['score'] >= args.commit_threshold and verified_phrase_hits == 0:
                reason = 'phrase-verify-failed'
            pending.append({'id': rid, 'company': company, 'role': role, 'linkedin_url': app_url,
                            'reason': reason, 'top_matches': all_matches[:5]})
            print(f'[{i}/{len(targets)}] id={rid} {company} | {role[:45]} -> REVIEW reason={reason} (top score={top["score"]} hits={verified_phrase_hits} {top["title"][:30]} {top["location"][:20]})', flush=True)

    log.close()
    PENDING_OUT.write_text(json.dumps(pending, indent=2, default=str))
    print(f'\n=== summary: committed={committed} no_candidates={no_candidates} review={sum(1 for p in pending if p["reason"]=="needs-review")} total={len(targets)} pending_file={PENDING_OUT}', flush=True)


if __name__ == '__main__':
    main()
